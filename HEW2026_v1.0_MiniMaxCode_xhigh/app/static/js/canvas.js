/* HEW2026 キャンバス編集 JavaScript
 * 用途: 複数レイヤーのお絵かき、undo/redo、IndexedDB による途中保存、締切タイマー、作品の保存。
 * 依存: 外部ライブラリなし（ネイティブ JS / ES2017+ 相当）。
 */
(function () {
  'use strict';

  var CANVAS_SIZE = 1024;
  var MAX_LAYERS = 10;
  var HISTORY_LIMIT = 50;
  var DB_NAME = 'hew2026';
  var DB_STORE = 'drawings';

  // ---------------------------------------------------------------- DOM
  var canvas = document.getElementById('canvas');
  var timerEl = document.getElementById('timer');
  var saveForm = document.getElementById('save-form');
  var penType = document.getElementById('pen-type');
  var penColor = document.getElementById('pen-color');
  var penSize = document.getElementById('pen-size');
  var btnUndo = document.getElementById('btn-undo');
  var btnRedo = document.getElementById('btn-redo');
  var btnClear = document.getElementById('btn-clear');
  var btnAddLayer = document.getElementById('btn-add-layer');
  var btnDeleteLayer = document.getElementById('btn-delete-layer');
  var btnLayerUp = document.getElementById('btn-layer-up');
  var btnLayerDown = document.getElementById('btn-layer-down');
  var layerSelect = document.getElementById('layer-select');
  var layerVisible = document.getElementById('layer-visible');
  var layerOpacity = document.getElementById('layer-opacity');
  var btnFinish = document.getElementById('btn-finish');
  var statusEl = document.getElementById('status');

  if (!canvas) { return; }
  var ctx = canvas.getContext('2d');

  // ---------------------------------------------------------------- 状態
  var layers = [];
  var activeIndex = 0;
  var layerSeq = 0;
  var history = [];
  var historyIndex = -1;
  var drawing = false;
  var locked = false;
  var saving = false;
  var saved = false;
  var timeoutHandled = false;
  var lastPoint = null;
  var timerId = null;

  var deadlineMs = NaN;
  var deadlineIso = '';
  var graceSeconds = 60;

  var artworkId = parseArtworkId(saveForm);
  var csrfToken = readCsrfToken(saveForm);

  // ------------------------------------------------------------ ヘルパー
  function setStatus(message) {
    if (statusEl) { statusEl.textContent = message; }
  }

  function parseArtworkId(form) {
    if (!form || !form.action) { return ''; }
    var m = String(form.action).match(/\/artworks\/(\d+)\/save/);
    return m ? m[1] : '';
  }

  function readCsrfToken(form) {
    if (!form) { return ''; }
    var input = form.querySelector('input[name="csrf_token"]');
    return input ? (input.value || '') : '';
  }

  /* サーバーの UTC 時刻文字列を Millisecond に変換する（末尾 Z が無い場合は UTC とみなす）。 */
  function parseUtc(value) {
    if (!value) { return NaN; }
    var s = String(value).trim();
    if (!s) { return NaN; }
    if (/[Zz]$/.test(s) || /[+-]\d{2}:?\d{2}$/.test(s)) { return Date.parse(s); }
    if (/T\d{2}:\d{2}(:\d{2}(\.\d+)?)?$/.test(s)) { return Date.parse(s + 'Z'); }
    return Date.parse(s);
  }

  function formatClock(totalSeconds) {
    var s = Math.max(0, Math.floor(totalSeconds));
    var mm = Math.floor(s / 60);
    var ss = s % 60;
    return (mm < 10 ? '0' : '') + mm + ':' + (ss < 10 ? '0' : '') + ss;
  }

  // ------------------------------------------------------------ レイヤー
  function createLayer(name) {
    var off = document.createElement('canvas');
    off.width = CANVAS_SIZE;
    off.height = CANVAS_SIZE;
    layerSeq += 1;
    return {
      id: 'layer-' + layerSeq,
      name: name || ('レイヤー' + layerSeq),
      visible: true,
      opacity: 1,
      canvas: off,
      ctx: off.getContext('2d')
    };
  }

  function activeLayer() {
    return layers[activeIndex] || null;
  }

  function syncLayerControls() {
    var layer = activeLayer();
    if (layerSelect) {
      layerSelect.innerHTML = '';
      for (var i = 0; i < layers.length; i += 1) {
        var opt = document.createElement('option');
        opt.value = layers[i].id;
        opt.textContent = layers[i].name;
        layerSelect.appendChild(opt);
      }
      if (layer) { layerSelect.value = layer.id; }
    }
    if (layerVisible) { layerVisible.checked = layer ? !!layer.visible : true; }
    if (layerOpacity && layer) { layerOpacity.value = String(layer.opacity); }
  }

  /* 表示可能なレイヤーを不透明度つきで主キャンバスに合成する。 */
  function composite() {
    ctx.clearRect(0, 0, CANVAS_SIZE, CANVAS_SIZE);
    for (var i = 0; i < layers.length; i += 1) {
      var layer = layers[i];
      if (!layer.visible) { continue; }
      ctx.globalAlpha = layer.opacity;
      ctx.drawImage(layer.canvas, 0, 0);
    }
    ctx.globalAlpha = 1;
  }

  function compositeDataUrl() {
    var out = document.createElement('canvas');
    out.width = CANVAS_SIZE;
    out.height = CANVAS_SIZE;
    var octx = out.getContext('2d');
    for (var i = 0; i < layers.length; i += 1) {
      var layer = layers[i];
      if (!layer.visible) { continue; }
      octx.globalAlpha = layer.opacity;
      octx.drawImage(layer.canvas, 0, 0);
    }
    octx.globalAlpha = 1;
    return out.toDataURL('image/png');
  }

  // ------------------------------------------------------------ 履歴
  function captureState() {
    var snapshot = { layers: [], activeIndex: activeIndex };
    for (var i = 0; i < layers.length; i += 1) {
      var layer = layers[i];
      snapshot.layers.push({
        id: layer.id,
        name: layer.name,
        visible: layer.visible,
        opacity: layer.opacity,
        data: layer.canvas.toDataURL('image/png')
      });
    }
    return snapshot;
  }

  function pushHistory() {
    history = history.slice(0, historyIndex + 1);
    history.push(captureState());
    while (history.length > HISTORY_LIMIT) { history.shift(); }
    historyIndex = history.length - 1;
    updateHistoryButtons();
  }

  function updateHistoryButtons() {
    if (btnUndo) { btnUndo.disabled = historyIndex <= 0; }
    if (btnRedo) { btnRedo.disabled = historyIndex >= history.length - 1; }
  }

  /* スナップショットからレイヤーを復元する（dataURL は非同期に読み込む）。 */
  function applyState(state, done) {
    var items = (state && state.layers) || [];
    if (!items.length) {
      layers = [];
      activeIndex = 0;
      syncLayerControls();
      composite();
      if (done) { done(); }
      return;
    }
    var built = new Array(items.length);
    var loaded = 0;
    items.forEach(function (item, index) {
      var img = new Image();
      var finish = function (ok) {
        if (ok) {
          var layer = createLayer(item.name);
          layer.id = item.id || layer.id;
          layer.visible = item.visible !== false;
          layer.opacity = typeof item.opacity === 'number' ? item.opacity : 1;
          layer.ctx.drawImage(img, 0, 0);
          built[index] = layer;
        }
        loaded += 1;
        if (loaded === items.length) {
          var result = built.filter(function (l) { return !!l; });
          layers = result;
          activeIndex = Math.min(state.activeIndex || 0, Math.max(0, layers.length - 1));
          syncLayerControls();
          composite();
          if (done) { done(); }
        }
      };
      img.onload = function () { finish(true); };
      img.onerror = function () { finish(false); };
      img.src = item.data;
    });
  }

  function undo() {
    if (historyIndex <= 0) { return; }
    historyIndex -= 1;
    applyState(history[historyIndex], function () {
      updateHistoryButtons();
      persistDraft();
    });
  }

  function redo() {
    if (historyIndex >= history.length - 1) { return; }
    historyIndex += 1;
    applyState(history[historyIndex], function () {
      updateHistoryButtons();
      persistDraft();
    });
  }

  // ------------------------------------------------------------ 描画
  function currentPen() {
    return {
      type: penType ? penType.value : 'round',
      color: penColor ? penColor.value : '#000000',
      size: penSize ? parseFloat(penSize.value) || 6 : 6
    };
  }

  function pointFromClient(clientX, clientY) {
    var rect = canvas.getBoundingClientRect();
    var width = rect.width || CANVAS_SIZE;
    var height = rect.height || CANVAS_SIZE;
    return {
      x: (clientX - rect.left) * (CANVAS_SIZE / width),
      y: (clientY - rect.top) * (CANVAS_SIZE / height)
    };
  }

  function setupStrokeContext(pctx, pen) {
    pctx.save();
    pctx.globalCompositeOperation = (pen.type === 'eraser') ? 'destination-out' : 'source-over';
    pctx.strokeStyle = pen.color;
    pctx.fillStyle = pen.color;
    pctx.lineWidth = pen.size;
    pctx.lineCap = 'round';
    pctx.lineJoin = 'round';
    if (pen.type === 'blur') {
      if ('filter' in pctx) {
        pctx.filter = 'blur(4px)';
      } else {
        pctx.globalAlpha = 0.35;
      }
    }
  }

  /* 線分を描く。gpen は硬いエッジを実心図形と矩形の連結で表現する。 */
  function strokeSegment(pctx, from, to, pen) {
    if (pen.type === 'gpen') {
      pctx.beginPath();
      pctx.arc(to.x, to.y, pen.size / 2, 0, Math.PI * 2);
      pctx.fill();
      var dx = to.x - from.x;
      var dy = to.y - from.y;
      var len = Math.sqrt(dx * dx + dy * dy);
      if (len > 0) {
        pctx.save();
        pctx.translate(from.x, from.y);
        pctx.rotate(Math.atan2(dy, dx));
        pctx.fillRect(0, -pen.size / 2, len, pen.size);
        pctx.restore();
      }
      return;
    }
    pctx.beginPath();
    pctx.moveTo(from.x, from.y);
    pctx.lineTo(to.x, to.y);
    pctx.stroke();
  }

  function beginStroke(point) {
    var layer = activeLayer();
    if (!layer) { return; }
    var pen = currentPen();
    setupStrokeContext(layer.ctx, pen);
    drawing = true;
    lastPoint = point;
    var pctx = layer.ctx;
    if (pen.type === 'gpen') {
      pctx.beginPath();
      pctx.arc(point.x, point.y, pen.size / 2, 0, Math.PI * 2);
      pctx.fill();
    } else {
      pctx.beginPath();
      pctx.moveTo(point.x, point.y);
      pctx.lineTo(point.x + 0.01, point.y);
      pctx.stroke();
    }
  }

  function extendStroke(point) {
    if (!drawing) { return; }
    var layer = activeLayer();
    if (!layer) { return; }
    var pen = currentPen();
    strokeSegment(layer.ctx, lastPoint, point, pen);
    lastPoint = point;
    composite();
  }

  function endStroke() {
    if (!drawing) { return; }
    drawing = false;
    var layer = activeLayer();
    if (layer) { layer.ctx.restore(); }
    lastPoint = null;
    composite();
    pushHistory();
    persistDraft();
  }

  // ------------------------------------------------------------ 入力
  function onMouseDown(e) {
    if (locked) { return; }
    if (typeof e.button === 'number' && e.button !== 0) { return; }
    e.preventDefault();
    beginStroke(pointFromClient(e.clientX, e.clientY));
  }

  function onMouseMove(e) {
    if (!drawing) { return; }
    e.preventDefault();
    extendStroke(pointFromClient(e.clientX, e.clientY));
  }

  function onMouseUp() {
    endStroke();
  }

  function touchPoint(touch) {
    return pointFromClient(touch.clientX, touch.clientY);
  }

  function onTouchStart(e) {
    if (locked) { return; }
    if (!e.touches || !e.touches.length) { return; }
    e.preventDefault();
    beginStroke(touchPoint(e.touches[0]));
  }

  function onTouchMove(e) {
    if (!drawing) { return; }
    if (!e.touches || !e.touches.length) { return; }
    e.preventDefault();
    extendStroke(touchPoint(e.touches[0]));
  }

  function onTouchEnd(e) {
    if (e.preventDefault) { e.preventDefault(); }
    endStroke();
  }

  // ------------------------------------------------------------ レイヤー操作
  function addLayer() {
    if (layers.length >= MAX_LAYERS) {
      setStatus('レイヤー数は最大10枚です');
      return;
    }
    var layer = createLayer('レイヤー' + (layers.length + 1));
    layers.push(layer);
    activeIndex = layers.length - 1;
    syncLayerControls();
    composite();
    pushHistory();
    persistDraft();
  }

  function deleteLayer() {
    if (layers.length <= 1) {
      setStatus('最低1枚のレイヤーが必要です');
      return;
    }
    layers.splice(activeIndex, 1);
    activeIndex = Math.max(0, Math.min(activeIndex, layers.length - 1));
    syncLayerControls();
    composite();
    pushHistory();
    persistDraft();
  }

  function moveLayer(offset) {
    var next = activeIndex + offset;
    if (next < 0 || next >= layers.length) { return; }
    var tmp = layers[activeIndex];
    layers[activeIndex] = layers[next];
    layers[next] = tmp;
    activeIndex = next;
    syncLayerControls();
    composite();
    pushHistory();
    persistDraft();
  }

  function clearActiveLayer() {
    var layer = activeLayer();
    if (!layer) { return; }
    layer.ctx.clearRect(0, 0, CANVAS_SIZE, CANVAS_SIZE);
    composite();
    pushHistory();
    persistDraft();
  }

  // ------------------------------------------------------------ IndexedDB
  var dbPromise = null;

  function openDb() {
    if (dbPromise) { return dbPromise; }
    dbPromise = new Promise(function (resolve) {
      if (!window.indexedDB) { resolve(null); return; }
      try {
        var request = window.indexedDB.open(DB_NAME, 1);
        request.onupgradeneeded = function () {
          var db = request.result;
          if (!db.objectStoreNames.contains(DB_STORE)) {
            db.createObjectStore(DB_STORE, { keyPath: 'artworkId' });
          }
        };
        request.onsuccess = function () { resolve(request.result); };
        request.onerror = function () { resolve(null); };
        request.onblocked = function () { resolve(null); };
      } catch (err) {
        resolve(null);
      }
    });
    return dbPromise;
  }

  function persistDraft() {
    if (!artworkId) { return; }
    var record = {
      artworkId: artworkId,
      deadline: deadlineIso,
      updatedAt: Date.now(),
      history: history,
      historyIndex: historyIndex,
      layers: (function () {
        var list = [];
        for (var i = 0; i < layers.length; i += 1) {
          var layer = layers[i];
          list.push({
            id: layer.id,
            order: i + 1,
            name: layer.name,
            visible: layer.visible,
            opacity: layer.opacity,
            data: layer.canvas.toDataURL('image/png')
          });
        }
        return list;
      }())
    };
    openDb().then(function (db) {
      if (!db) { return; }
      try {
        var tx = db.transaction(DB_STORE, 'readwrite');
        tx.objectStore(DB_STORE).put(record);
      } catch (err) { /* 静かに無視 */ }
    });
  }

  function readDraft() {
    if (!artworkId) { return Promise.resolve(null); }
    return openDb().then(function (db) {
      if (!db) { return null; }
      return new Promise(function (resolve) {
        try {
          var tx = db.transaction(DB_STORE, 'readonly');
          var request = tx.objectStore(DB_STORE).get(artworkId);
          request.onsuccess = function () { resolve(request.result || null); };
          request.onerror = function () { resolve(null); };
        } catch (err) {
          resolve(null);
        }
      });
    });
  }

  function restoreDraft() {
    readDraft().then(function (record) {
      if (!record || !record.layers || !record.layers.length) { return; }
      var recordDeadline = parseUtc(record.deadline);
      if (!isNaN(recordDeadline) && Date.now() > recordDeadline) {
        setStatus('保存期限を過ぎているため、加筆できません。');
        locked = true;
        return;
      }
      var state = { layers: record.layers, activeIndex: record.activeIndex || 0 };
      applyState(state, function () {
        if (Array.isArray(record.history) && record.history.length) {
          history = record.history;
          historyIndex = typeof record.historyIndex === 'number'
            ? record.historyIndex
            : record.history.length - 1;
          updateHistoryButtons();
        } else {
          pushHistory();
        }
        setStatus('前回の続きを復元しました');
      });
    });
  }

  // ------------------------------------------------------------ タイマー
  function updateTimer() {
    if (!timerEl) { return; }
    if (isNaN(deadlineMs)) { return; }
    var remaining = Math.ceil((deadlineMs - Date.now()) / 1000);
    if (remaining <= 0) {
      timerEl.textContent = '00:00';
      timerEl.classList.add('is-ended');
      timerEl.classList.remove('is-warning');
      handleTimeout();
      return;
    }
    timerEl.textContent = formatClock(remaining);
    if (remaining <= 10) {
      timerEl.classList.add('is-warning');
    } else {
      timerEl.classList.remove('is-warning');
    }
  }

  function handleTimeout() {
    if (timeoutHandled) { return; }
    timeoutHandled = true;
    locked = true;
    setStatus('時間切れです。画像を保存しています。');
    saveArtwork();
  }

  // ------------------------------------------------------------ 保存
  // サーバーの日本語メッセージを優先し、無い場合のみ HTTP 状態から
  // 日本語の文言へ翻訳する（英文の statusText をそのまま見せない）
  function httpMessage(status) {
    if (status === 400) { return '入力内容を確認してください。'; }
    if (status === 403) { return 'この操作を行う権限がありません。'; }
    if (status === 404) { return '対象が見つかりませんでした。'; }
    if (status === 409) { return 'すでに処理されています。'; }
    if (status === 413) { return '画像のサイズが大きすぎます。'; }
    if (status === 419 || status === 440) { return 'セッションが期限切れです。ページを再読み込みしてください。'; }
    if (status >= 500) { return 'サーバーエラーが発生しました。時間をおいて再度お試しください。'; }
    return '保存に失敗しました。';
  }

  function buildLayerPayload() {
    var payload = [];
    for (var i = 0; i < layers.length; i += 1) {
      var layer = layers[i];
      payload.push({
        name: layer.name,
        visible: layer.visible,
        opacity: layer.opacity,
        data: layer.canvas.toDataURL('image/png')
      });
    }
    return payload;
  }

  function saveArtwork() {
    if (saving || saved) { return; }
    if (!saveForm || !saveForm.action) {
      setStatus('保存フォームが見つかりません。');
      return;
    }
    saving = true;
    if (btnFinish) { btnFinish.disabled = true; }
    setStatus('保存しています…');

    var body = JSON.stringify({
      png: compositeDataUrl(),
      layers: buildLayerPayload(),
      finished: true
    });

    fetch(saveForm.action, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': csrfToken
      },
      credentials: 'same-origin',
      body: body
    }).then(function (res) {
      return res.json().catch(function () { return null; }).then(function (data) {
        return { res: res, data: data };
      });
    }).then(function (result) {
      var res = result.res;
      var data = result.data;
      if (res.ok && data && data.ok === true) {
        saved = true;
        saving = false;
        setStatus('保存しました。出品設定へ進みます。');
        var listingUrl = canvas.getAttribute('data-listing-url');
        window.location.href = listingUrl || window.location.href;
        return;
      }
      saving = false;
      var message = (data && data.message) || httpMessage(res.status) || '保存に失敗しました。';
      if (!isNaN(deadlineMs) && Date.now() > deadlineMs + graceSeconds * 1000) {
        message += '（保存猶予を超過しています）';
      }
      setStatus(message);
      if (btnFinish) { btnFinish.disabled = false; }
    }).catch(function (err) {
      saving = false;
      setStatus('保存に失敗しました: ' + ((err && err.message) || '通信エラー'));
      if (btnFinish) { btnFinish.disabled = false; }
    });
  }

  // ------------------------------------------------------------ 初期化
  function bindEvents() {
    canvas.addEventListener('mousedown', onMouseDown);
    window.addEventListener('mousemove', onMouseMove);
    window.addEventListener('mouseup', onMouseUp);
    canvas.addEventListener('touchstart', onTouchStart, { passive: false });
    window.addEventListener('touchmove', onTouchMove, { passive: false });
    window.addEventListener('touchend', onTouchEnd);
    window.addEventListener('touchcancel', onTouchEnd);

    if (btnUndo) { btnUndo.addEventListener('click', undo); }
    if (btnRedo) { btnRedo.addEventListener('click', redo); }
    if (btnClear) { btnClear.addEventListener('click', clearActiveLayer); }
    if (btnAddLayer) { btnAddLayer.addEventListener('click', addLayer); }
    if (btnDeleteLayer) { btnDeleteLayer.addEventListener('click', deleteLayer); }
    if (btnLayerUp) { btnLayerUp.addEventListener('click', function () { moveLayer(1); }); }
    if (btnLayerDown) { btnLayerDown.addEventListener('click', function () { moveLayer(-1); }); }
    if (btnFinish) { btnFinish.addEventListener('click', saveArtwork); }

    if (layerSelect) {
      layerSelect.addEventListener('change', function () {
        for (var i = 0; i < layers.length; i += 1) {
          if (layers[i].id === layerSelect.value) {
            activeIndex = i;
            break;
          }
        }
        syncLayerControls();
      });
    }
    if (layerVisible) {
      layerVisible.addEventListener('change', function () {
        var layer = activeLayer();
        if (!layer) { return; }
        layer.visible = !!layerVisible.checked;
        composite();
        persistDraft();
      });
    }
    if (layerOpacity) {
      layerOpacity.addEventListener('input', function () {
        var layer = activeLayer();
        if (!layer) { return; }
        var value = parseFloat(layerOpacity.value);
        layer.opacity = isNaN(value) ? 1 : Math.min(1, Math.max(0, value));
        composite();
      });
      layerOpacity.addEventListener('change', persistDraft);
    }
  }

  function init() {
    if (timerEl) {
      deadlineIso = timerEl.getAttribute('data-deadline') || '';
      deadlineMs = parseUtc(deadlineIso);
      var grace = parseInt(timerEl.getAttribute('data-grace-seconds'), 10);
      graceSeconds = isNaN(grace) ? 60 : grace;
    }

    layers = [createLayer('レイヤー1')];
    activeIndex = 0;
    syncLayerControls();
    composite();
    pushHistory();
    bindEvents();
    updateHistoryButtons();
    restoreDraft();

    if (!isNaN(deadlineMs)) {
      updateTimer();
      timerId = window.setInterval(updateTimer, 250);
    }
  }

  init();
})();
