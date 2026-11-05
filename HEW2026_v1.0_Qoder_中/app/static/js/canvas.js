/* HEW 描画画面: レイヤー描画・50操作の履歴・IndexedDB一時保存・
 * 合成PNG + 独自形式レイヤーZIP の送信を担当する。
 * キャンバスは 1,024×1,024px 固定で、表示だけ CSS で縮小する。 */
(function () {
  var ui = document.getElementById("draw-ui");
  if (!ui) return;

  var artworkId = Number(ui.dataset.artworkId);
  var deadline = new Date(ui.dataset.deadline).getTime();
  var maxLayers = Number(ui.dataset.maxLayers);
  var size = Number(ui.dataset.canvasSize);
  var saveUrl = ui.dataset.saveUrl;
  var draftUrl = ui.dataset.draftUrl;

  var view = document.getElementById("draw-canvas");
  var viewCtx = view.getContext("2d");
  var timerEl = document.getElementById("timer");
  var statusEl = document.getElementById("save-status");
  var layerListEl = document.getElementById("layer-list");

  var layers = [];        // {name, visible, opacity, canvas, ctx}
  var activeIndex = 0;
  var undoStack = [];     // 直近50操作のスナップショット
  var redoStack = [];
  var frozen = false;     // 完成・期限で描画を停止
  var saved = false;
  var drawing = false;
  var lastPoint = null;
  var pendingSnapshot = null;

  // ------------------------------------------------ レイヤー操作

  function makeLayer(name) {
    var canvas = document.createElement("canvas");
    canvas.width = size;
    canvas.height = size;
    return { name: name, visible: true, opacity: 1, canvas: canvas, ctx: canvas.getContext("2d") };
  }

  function addLayer() {
    if (frozen) return;
    if (layers.length >= maxLayers) {
      setStatus("レイヤーは最大 " + maxLayers + " 枚までです。");
      return;
    }
    withHistory(function () {
      layers.push(makeLayer("レイヤー " + (layers.length + 1)));
      activeIndex = layers.length - 1;
    });
  }

  function deleteLayer() {
    if (frozen || layers.length <= 1) return;
    withHistory(function () {
      layers.splice(activeIndex, 1);
      activeIndex = Math.min(activeIndex, layers.length - 1);
    });
  }

  function moveLayer(delta) {
    if (frozen) return;
    var target = activeIndex + delta;
    if (target < 0 || target >= layers.length) return;
    withHistory(function () {
      var tmp = layers[activeIndex];
      layers[activeIndex] = layers[target];
      layers[target] = tmp;
      activeIndex = target;
    });
  }

  function composite() {
    viewCtx.clearRect(0, 0, size, size);
    viewCtx.fillStyle = "#ffffff";
    viewCtx.fillRect(0, 0, size, size);
    layers.forEach(function (layer) {
      if (!layer.visible) return;
      viewCtx.globalAlpha = layer.opacity;
      viewCtx.drawImage(layer.canvas, 0, 0);
    });
    viewCtx.globalAlpha = 1;
  }

  function renderLayerList() {
    layerListEl.innerHTML = "";
    layers.forEach(function (layer, index) {
      var li = document.createElement("li");
      li.textContent = layer.name + (layer.visible ? "" : "（非表示）");
      if (index === activeIndex) li.className = "active";
      li.addEventListener("click", function () {
        activeIndex = index;
        syncLayerControls();
        renderLayerList();
      });
      layerListEl.appendChild(li);
    });
    var opacityInput = document.getElementById("layer-opacity");
    var visibleInput = document.getElementById("layer-visible");
    if (layers[activeIndex]) {
      opacityInput.value = Math.round(layers[activeIndex].opacity * 100);
      visibleInput.checked = layers[activeIndex].visible;
    }
  }

  function syncLayerControls() {
    var layer = layers[activeIndex];
    if (!layer) return;
    document.getElementById("layer-opacity").value = Math.round(layer.opacity * 100);
    document.getElementById("layer-visible").checked = layer.visible;
  }

  function setStatus(text) { statusEl.textContent = text; }

  // ------------------------------------------------ 履歴（直近50操作）

  function snapshotLayers() {
    return layers.map(function (layer) {
      return {
        name: layer.name,
        visible: layer.visible,
        opacity: layer.opacity,
        dataUrl: layer.canvas.toDataURL("image/png"),
      };
    });
  }

  function restoreSnapshot(snapshot) {
    layers = [];
    snapshot.layers.forEach(function (item) {
      var layer = makeLayer(item.name);
      layer.visible = item.visible;
      layer.opacity = item.opacity;
      layers.push(layer);
      var img = new Image();
      img.onload = function () {
        layer.ctx.drawImage(img, 0, 0);
        composite();
      };
      img.src = item.dataUrl;
    });
    activeIndex = snapshot.activeIndex || 0;
    renderLayerList();
    composite();
    persist();
  }

  function withHistory(changeFn) {
    undoStack.push({ layers: snapshotLayers(), activeIndex: activeIndex });
    if (undoStack.length > 50) undoStack.shift();
    redoStack.length = 0;
    changeFn();
    composite();
    renderLayerList();
    updateHistoryButtons();
    persist();
  }

  function undo() {
    if (frozen || !undoStack.length) return;
    redoStack.push({ layers: snapshotLayers(), activeIndex: activeIndex });
    restoreSnapshot(undoStack.pop());
    updateHistoryButtons();
  }

  function redo() {
    if (frozen || !redoStack.length) return;
    undoStack.push({ layers: snapshotLayers(), activeIndex: activeIndex });
    restoreSnapshot(redoStack.pop());
    updateHistoryButtons();
  }

  function updateHistoryButtons() {
    document.getElementById("btn-undo").disabled = frozen || !undoStack.length;
    document.getElementById("btn-redo").disabled = frozen || !redoStack.length;
  }

  // ------------------------------------------------ IndexedDB 一時保存
  // ペンを離した時点とレイヤー操作完了時に保存し、同じブラウザで復元する。

  function openDb() {
    return new Promise(function (resolve, reject) {
      var req = indexedDB.open("hew-draw", 1);
      req.onupgradeneeded = function () {
        if (!req.result.objectStoreNames.contains("sessions")) {
          req.result.createObjectStore("sessions", { keyPath: "artworkId" });
        }
      };
      req.onsuccess = function () { resolve(req.result); };
      req.onerror = function () { reject(req.error); };
    });
  }

  function persist() {
    var record = {
      artworkId: artworkId,
      deadline: ui.dataset.deadline,
      activeIndex: activeIndex,
      layers: snapshotLayers(),
    };
    openDb().then(function (db) {
      var tx = db.transaction("sessions", "readwrite");
      tx.objectStore("sessions").put(record);
    }).catch(function () { setStatus("一時保存に失敗しました（描画は続行できます）。"); });
  }

  function clearPersisted() {
    openDb().then(function (db) {
      var tx = db.transaction("sessions", "readwrite");
      tx.objectStore("sessions").delete(artworkId);
    }).catch(function () {});
  }

  function restore() {
    return openDb().then(function (db) {
      return new Promise(function (resolve) {
        var tx = db.transaction("sessions", "readonly");
        var req = tx.objectStore("sessions").get(artworkId);
        req.onsuccess = function () { resolve(req.result || null); };
        req.onerror = function () { resolve(null); };
      });
    }).catch(function () { return null; });
  }

  // ------------------------------------------------ 描画

  function canvasPoint(event) {
    var rect = view.getBoundingClientRect();
    return {
      x: (event.clientX - rect.left) * (size / rect.width),
      y: (event.clientY - rect.top) * (size / rect.height),
    };
  }

  function strokeTo(point) {
    var layer = layers[activeIndex];
    if (!layer) return;
    var ctx = layer.ctx;
    var penType = document.getElementById("pen-type").value;
    var penSize = Number(document.getElementById("pen-size").value);
    ctx.lineCap = penType === "square" ? "square" : "round";
    ctx.lineJoin = ctx.lineCap;
    ctx.lineWidth = penSize;
    if (penType === "eraser") {
      ctx.globalCompositeOperation = "destination-out";
      ctx.strokeStyle = "rgba(0,0,0,1)";
    } else {
      ctx.globalCompositeOperation = "source-over";
      ctx.strokeStyle = document.getElementById("pen-color").value;
    }
    ctx.beginPath();
    ctx.moveTo(lastPoint.x, lastPoint.y);
    ctx.lineTo(point.x, point.y);
    ctx.stroke();
    ctx.globalCompositeOperation = "source-over";
    composite();
  }

  view.addEventListener("pointerdown", function (event) {
    if (frozen) return;
    event.preventDefault();
    drawing = true;
    pendingSnapshot = { layers: snapshotLayers(), activeIndex: activeIndex };
    lastPoint = canvasPoint(event);
    strokeTo(lastPoint);
    view.setPointerCapture(event.pointerId);
  });

  view.addEventListener("pointermove", function (event) {
    if (!drawing || frozen) return;
    var point = canvasPoint(event);
    strokeTo(point);
    lastPoint = point;
  });

  function endStroke() {
    if (!drawing) return;
    drawing = false;
    if (pendingSnapshot) {
      // ペンを離した時点で履歴へ記録し、IndexedDB へ一時保存する
      undoStack.push(pendingSnapshot);
      if (undoStack.length > 50) undoStack.shift();
      redoStack.length = 0;
      pendingSnapshot = null;
      updateHistoryButtons();
      persist();
    }
  }

  view.addEventListener("pointerup", endStroke);
  view.addEventListener("pointercancel", endStroke);

  // ------------------------------------------------ タイマーと完成

  function freeze(reason) {
    if (frozen) return;
    frozen = true;
    setStatus(reason);
    document.getElementById("btn-finish").textContent = "保存中…";
    ["btn-add-layer", "btn-del-layer", "btn-up-layer", "btn-down-layer"].forEach(function (id) {
      document.getElementById(id).disabled = true;
    });
    updateHistoryButtons();
  }

  function tick() {
    var remaining = deadline - Date.now();
    if (remaining <= 0) {
      timerEl.textContent = "0:00";
      freeze("時間切れです。描画を停止し、保存します。");
      saveWithRetry();
      return;
    }
    var minutes = Math.floor(remaining / 60000);
    var seconds = Math.floor((remaining % 60000) / 1000);
    timerEl.textContent = minutes + ":" + String(seconds).padStart(2, "0");
  }

  document.getElementById("btn-finish").addEventListener("click", function () {
    if (saved) return;
    freeze("完成操作で描画を停止しました。保存します。");
    saveWithRetry();
  });

  document.getElementById("btn-local-save").addEventListener("click", function () {
    // 端末保存は提供するが、後日アップロードは認めない
    view.toBlob(function (blob) {
      var a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = "artwork_" + artworkId + "_local.png";
      a.click();
      URL.revokeObjectURL(a.href);
    }, "image/png");
  });

  async function buildPayload() {
    var compositeBlob = await new Promise(function (resolve) {
      view.toBlob(resolve, "image/png");
    });
    var manifest = {
      format: "hew-layers-v1",
      canvasSize: size,
      layers: layers.map(function (layer, index) {
        return {
          name: layer.name,
          order: index,
          visible: layer.visible,
          opacity: layer.opacity,
          file: "layer_" + index + ".png",
        };
      }),
    };
    var entries = [{
      name: "manifest.json",
      data: new TextEncoder().encode(JSON.stringify(manifest)),
    }];
    // 非表示レイヤーも含め、完成時の全レイヤーを ZIP へ入れる
    for (var i = 0; i < layers.length; i++) {
      var blob = await new Promise((function (layer) {
        return function (resolve) { layer.canvas.toBlob(resolve, "image/png"); };
      })(layers[i]));
      entries.push({
        name: "layer_" + i + ".png",
        data: new Uint8Array(await blob.arrayBuffer()),
      });
    }
    return { compositeBlob: compositeBlob, zipBlob: buildZip(entries) };
  }

  async function saveOnce() {
    var payload = await buildPayload();
    var form = new FormData();
    form.append("composite_png", payload.compositeBlob, "composite.png");
    form.append("layers_zip", payload.zipBlob, "layers.zip");
    var response = await fetch(saveUrl, {
      method: "POST",
      body: form,
      headers: { "X-CSRFToken": ui.dataset.csrf },
      credentials: "same-origin",
    });
    var result = await response.json().catch(function () { return {}; });
    if (!response.ok || !result.ok) {
      throw new Error(result.error || ("保存に失敗しました（HTTP " + response.status + "）"));
    }
    return result;
  }

  function saveWithRetry() {
    // 固定後は保存だけ60秒間再試行できる
    var giveUpAt = Math.max(deadline, Date.now()) + 60000;
    function attempt() {
      saveOnce().then(function () {
        saved = true;
        setStatus("正式保存に成功しました。下書き画面へ移動します。");
        clearPersisted(); // 正式保存成功後は端末の一時データを削除する
        window.location.href = draftUrl;
      }).catch(function (error) {
        setStatus(error.message + "（再試行します…）");
        if (Date.now() < giveUpAt) {
          setTimeout(attempt, 4000);
        } else {
          setStatus("保存猶予（60秒）を過ぎました。端末保存のみ利用できます。この作品は出品できません。");
          document.getElementById("btn-finish").disabled = true;
        }
      });
    }
    attempt();
  }

  // ------------------------------------------------ ZIP（独自形式・無圧縮）

  var CRC_TABLE = (function () {
    var table = new Uint32Array(256);
    for (var n = 0; n < 256; n++) {
      var c = n;
      for (var k = 0; k < 8; k++) {
        c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
      }
      table[n] = c >>> 0;
    }
    return table;
  })();

  function crc32(data) {
    var crc = 0xffffffff;
    for (var i = 0; i < data.length; i++) {
      crc = CRC_TABLE[(crc ^ data[i]) & 0xff] ^ (crc >>> 8);
    }
    return (crc ^ 0xffffffff) >>> 0;
  }

  function dosDateTime(date) {
    var time = (date.getHours() << 11) | (date.getMinutes() << 5) | (date.getSeconds() >> 1);
    var day = ((date.getFullYear() - 1980) << 9) | ((date.getMonth() + 1) << 5) | date.getDate();
    return { time: time, date: day };
  }

  function buildZip(entries) {
    var now = dosDateTime(new Date());
    var localParts = [];
    var centralParts = [];
    var offset = 0;
    var encoder = new TextEncoder();

    entries.forEach(function (entry) {
      var nameBytes = encoder.encode(entry.name);
      var crc = crc32(entry.data);
      var local = new DataView(new ArrayBuffer(30));
      local.setUint32(0, 0x04034b50, true);
      local.setUint16(4, 20, true);
      local.setUint16(6, 0x0800, true); // UTF-8 ファイル名
      local.setUint16(8, 0, true);      // 無圧縮
      local.setUint16(10, now.time, true);
      local.setUint16(12, now.date, true);
      local.setUint32(14, crc, true);
      local.setUint32(18, entry.data.length, true);
      local.setUint32(22, entry.data.length, true);
      local.setUint16(26, nameBytes.length, true);
      local.setUint16(28, 0, true);
      localParts.push(new Uint8Array(local.buffer), nameBytes, entry.data);

      var central = new DataView(new ArrayBuffer(46));
      central.setUint32(0, 0x02014b50, true);
      central.setUint16(4, 20, true);
      central.setUint16(6, 20, true);
      central.setUint16(8, 0x0800, true);
      central.setUint16(10, 0, true);
      central.setUint16(12, now.time, true);
      central.setUint16(14, now.date, true);
      central.setUint32(16, crc, true);
      central.setUint32(20, entry.data.length, true);
      central.setUint32(24, entry.data.length, true);
      central.setUint16(28, nameBytes.length, true);
      central.setUint16(30, 0, true);
      central.setUint16(32, 0, true);
      central.setUint16(34, 0, true);
      central.setUint16(36, 0, true);
      central.setUint32(38, 0, true);
      central.setUint32(42, offset, true);
      centralParts.push(new Uint8Array(central.buffer), nameBytes);

      offset += 30 + nameBytes.length + entry.data.length;
    });

    var centralSize = centralParts.reduce(function (sum, part) { return sum + part.length; }, 0);
    var end = new DataView(new ArrayBuffer(22));
    end.setUint32(0, 0x06054b50, true);
    end.setUint16(8, entries.length, true);
    end.setUint16(10, entries.length, true);
    end.setUint32(12, centralSize, true);
    end.setUint32(16, offset, true);
    return new Blob(localParts.concat(centralParts, [new Uint8Array(end.buffer)]), {
      type: "application/zip",
    });
  }

  // ------------------------------------------------ ツールバーバインド

  document.getElementById("btn-undo").addEventListener("click", undo);
  document.getElementById("btn-redo").addEventListener("click", redo);
  document.getElementById("btn-add-layer").addEventListener("click", addLayer);
  document.getElementById("btn-del-layer").addEventListener("click", deleteLayer);
  document.getElementById("btn-up-layer").addEventListener("click", function () { moveLayer(1); });
  document.getElementById("btn-down-layer").addEventListener("click", function () { moveLayer(-1); });
  document.getElementById("layer-opacity").addEventListener("input", function (event) {
    if (frozen || !layers[activeIndex]) return;
    layers[activeIndex].opacity = Number(event.target.value) / 100;
    composite();
  });
  document.getElementById("layer-opacity").addEventListener("change", function () {
    if (!frozen) withHistoryNoop();
  });
  document.getElementById("layer-visible").addEventListener("change", function (event) {
    if (frozen || !layers[activeIndex]) return;
    withHistory(function () { layers[activeIndex].visible = event.target.checked; });
  });

  function withHistoryNoop() {
    // 不透明度変更は change 時点で履歴に含める（レイヤー操作完了時）
    undoStack.push({ layers: lastOpacitySnapshot, activeIndex: activeIndex });
    if (undoStack.length > 50) undoStack.shift();
    redoStack.length = 0;
    updateHistoryButtons();
    persist();
    lastOpacitySnapshot = { layers: snapshotLayers(), activeIndex: activeIndex };
  }

  var lastOpacitySnapshot = { layers: snapshotLayers(), activeIndex: activeIndex };

  // ------------------------------------------------ 初期化・復元

  function init() {
    restore().then(function (record) {
      if (record && Array.isArray(record.layers) && record.layers.length) {
        setStatus("このブラウザの一時データを復元しました。");
        restoreSnapshot(record);
        lastOpacitySnapshot = { layers: snapshotLayers(), activeIndex: activeIndex };
      } else {
        layers = [makeLayer("レイヤー 1")];
        renderLayerList();
        composite();
      }
      updateHistoryButtons();
      tick();
      setInterval(tick, 250);
      if (Date.now() >= deadline) {
        // 期限到達後も復元はできるが加筆は認めない
        freeze("描画期限を過ぎています。加筆はできません。保存のみ実行します。");
        saveWithRetry();
      }
    });
  }

  init();
})();
