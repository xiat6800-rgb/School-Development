(() => {
  const config = window.DRAW_CONFIG;
  const root = document.getElementById('drawing-app');
  if (!config || !root) return;

  const SIZE = 1024;
  const MAX_LAYERS = 10;
  const MAX_HISTORY = 50;
  const stack = document.getElementById('canvas-stack');
  const statusBox = document.getElementById('save-status');
  const saveButton = document.getElementById('finish-save');
  const freezeOverlay = document.getElementById('canvas-freeze');
  const localDownload = document.getElementById('download-local');
  const undoButton = document.getElementById('undo');
  const redoButton = document.getElementById('redo');
  const layerList = document.getElementById('layer-list');
  const layerOpacity = document.getElementById('layer-opacity');
  const colorInput = document.getElementById('brush-color');
  const sizeInput = document.getElementById('brush-size');
  const opacityInput = document.getElementById('brush-opacity');

  let layers = [];
  let activeIndex = 0;
  let layerSequence = 0;
  let history = [];
  let historyIndex = -1;
  let tool = 'gpen';
  let drawing = false;
  let restoring = false;
  let ready = false;
  let frozen = Boolean(config.saved || config.finishedAt || Date.now() >= Date.parse(config.drawingEndsAt));
  let saveStarted = false;
  let graceEndsAt = Math.min(Date.now(), Date.parse(config.drawingEndsAt)) + 60000;
  let localImageUrl = '';
  let dbPromise = null;

  const setStatus = (message, kind = '') => {
    statusBox.textContent = message;
    statusBox.className = `save-status${kind ? ` is-${kind}` : ''}`;
  };

  const openDB = () => {
    if (dbPromise) return dbPromise;
    dbPromise = new Promise((resolve, reject) => {
      const request = indexedDB.open('hew-canvas-v1', 1);
      request.onupgradeneeded = () => {
        const db = request.result;
        if (!db.objectStoreNames.contains('drafts')) db.createObjectStore('drafts', { keyPath: 'artworkId' });
      };
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    });
    return dbPromise;
  };

  const readLocal = async () => {
    try {
      const db = await openDB();
      return await new Promise((resolve, reject) => {
        const request = db.transaction('drafts', 'readonly').objectStore('drafts').get(config.artworkId);
        request.onsuccess = () => resolve(request.result || null);
        request.onerror = () => reject(request.error);
      });
    } catch (_) { return null; }
  };

  const writeLocal = async () => {
    if (!ready || restoring || config.saved) return;
    try {
      const db = await openDB();
      const record = {
        artworkId: config.artworkId,
        drawingEndsAt: config.drawingEndsAt,
        current: history[historyIndex] || serializeSnapshot(),
        history,
        historyIndex,
        updatedAt: new Date().toISOString(),
      };
      await new Promise((resolve, reject) => {
        const transaction = db.transaction('drafts', 'readwrite');
        transaction.objectStore('drafts').put(record);
        transaction.oncomplete = resolve;
        transaction.onerror = () => reject(transaction.error);
      });
    } catch (_) { /* ブラウザ保存失敗時は復元を保証しない */ }
  };

  const clearLocal = async () => {
    try {
      const db = await openDB();
      await new Promise((resolve, reject) => {
        const transaction = db.transaction('drafts', 'readwrite');
        transaction.objectStore('drafts').delete(config.artworkId);
        transaction.oncomplete = resolve;
        transaction.onerror = () => reject(transaction.error);
      });
    } catch (_) { /* サーバー保存は完了済み */ }
  };

  const makeLayer = async (data = null) => {
    const canvas = document.createElement('canvas');
    canvas.width = SIZE;
    canvas.height = SIZE;
    const layer = {
      id: ++layerSequence,
      name: data?.name || `レイヤー ${layerSequence}`,
      canvas,
      ctx: canvas.getContext('2d', { willReadFrequently: false }),
      visible: data?.visible !== false,
      opacity: typeof data?.opacity === 'number' ? data.opacity : 1,
    };
    canvas.dataset.layerId = layer.id;
    if (data?.dataUrl) {
      const image = new Image();
      await new Promise((resolve, reject) => {
        image.onload = resolve;
        image.onerror = reject;
        image.src = data.dataUrl;
      });
      layer.ctx.drawImage(image, 0, 0, SIZE, SIZE);
    }
    return layer;
  };

  function serializeSnapshot() {
    return {
      activeIndex,
      layers: layers.map((layer) => ({
        name: layer.name,
        visible: layer.visible,
        opacity: layer.opacity,
        dataUrl: layer.canvas.toDataURL('image/png'),
      })),
    };
  }

  const applySnapshot = async (snapshot) => {
    if (!snapshot?.layers?.length) return;
    restoring = true;
    const token = Symbol('restore');
    applySnapshot.token = token;
    try {
      const restored = await Promise.all(snapshot.layers.slice(0, MAX_LAYERS).map(makeLayer));
      if (applySnapshot.token !== token) return;
      stack.replaceChildren();
      layers = restored;
      activeIndex = Math.max(0, Math.min(snapshot.activeIndex ?? layers.length - 1, layers.length - 1));
      layers.forEach((layer) => stack.append(layer.canvas));
      syncLayers();
    } finally {
      restoring = false;
    }
  };

  const updateHistoryButtons = () => {
    undoButton.disabled = frozen || restoring || historyIndex <= 0;
    redoButton.disabled = frozen || restoring || historyIndex < 0 || historyIndex >= history.length - 1;
  };

  const renderLayerList = () => {
    layerList.replaceChildren();
    [...layers].reverse().forEach((layer) => {
      const index = layers.indexOf(layer);
      const row = document.createElement('div');
      row.className = `layer-row${index === activeIndex ? ' is-active' : ''}`;
      const thumb = document.createElement('img');
      thumb.src = layer.canvas.toDataURL('image/png');
      thumb.alt = '';
      const select = document.createElement('button');
      select.type = 'button';
      select.className = 'text-button';
      select.textContent = layer.name;
      select.addEventListener('click', () => {
        if (frozen) return;
        activeIndex = index;
        syncLayers();
      });
      const visibility = document.createElement('button');
      visibility.type = 'button';
      visibility.className = 'layer-visibility';
      visibility.title = layer.visible ? '非表示にする' : '表示する';
      visibility.textContent = layer.visible ? '👁' : '―';
      visibility.addEventListener('click', () => {
        if (frozen) return;
        layer.visible = !layer.visible;
        pushHistory();
      });
      row.append(thumb, select, visibility);
      layerList.append(row);
    });
    document.getElementById('layer-count').textContent = layers.length;
    document.getElementById('add-layer').disabled = frozen || layers.length >= MAX_LAYERS;
    document.getElementById('delete-layer').disabled = frozen || layers.length <= 1;
    layerOpacity.value = Math.round((layers[activeIndex]?.opacity ?? 1) * 100);
    layerOpacity.disabled = frozen;
  };

  const syncLayers = () => {
    layers.forEach((layer, index) => {
      if (layer.canvas.parentElement !== stack) stack.append(layer.canvas);
      layer.canvas.style.zIndex = index;
      layer.canvas.style.opacity = layer.opacity;
      layer.canvas.style.display = layer.visible ? 'block' : 'none';
      layer.canvas.style.pointerEvents = index === activeIndex && layer.visible && !frozen ? 'auto' : 'none';
      layer.canvas.classList.toggle('is-active', index === activeIndex && !frozen);
      stack.append(layer.canvas);
    });
    renderLayerList();
    updateHistoryButtons();
  };

  const pushHistory = () => {
    if (restoring || frozen) return;
    history = history.slice(0, historyIndex + 1);
    history.push(serializeSnapshot());
    if (history.length > MAX_HISTORY) history.shift();
    historyIndex = history.length - 1;
    syncLayers();
    writeLocal();
  };

  const restoreHistory = async (nextIndex) => {
    if (frozen || nextIndex < 0 || nextIndex >= history.length) return;
    historyIndex = nextIndex;
    await applySnapshot(history[historyIndex]);
    updateHistoryButtons();
    writeLocal();
  };

  const activeLayer = () => layers[activeIndex];
  const pointFromEvent = (event) => {
    const rect = activeLayer().canvas.getBoundingClientRect();
    return {
      x: (event.clientX - rect.left) * SIZE / rect.width,
      y: (event.clientY - rect.top) * SIZE / rect.height,
      pressure: event.pressure || 0.5,
    };
  };

  const paintSegment = (from, to) => {
    const layer = activeLayer();
    const ctx = layer.ctx;
    const size = Number(sizeInput.value);
    ctx.save();
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
    ctx.globalCompositeOperation = tool === 'eraser' ? 'destination-out' : 'source-over';
    ctx.strokeStyle = colorInput.value;
    ctx.fillStyle = colorInput.value;
    ctx.globalAlpha = tool === 'eraser' ? 1 : Number(opacityInput.value) / 100;
    ctx.shadowBlur = 0;
    let width = size;
    if (tool === 'round') width = Math.max(1, size * 0.48);
    if (tool === 'gpen') width = Math.max(1, size * (0.55 + to.pressure * 0.75));
    if (tool === 'blur') {
      width = size * 1.4;
      ctx.globalAlpha *= 0.36;
      ctx.shadowBlur = size * 0.65;
      ctx.shadowColor = colorInput.value;
    }
    if (tool === 'eraser') width = size * 1.8;
    ctx.lineWidth = width;
    ctx.beginPath();
    ctx.moveTo(from.x, from.y);
    ctx.lineTo(to.x + 0.01, to.y + 0.01);
    ctx.stroke();
    ctx.restore();
  };

  let lastPoint = null;
  stack.addEventListener('pointerdown', (event) => {
    if (!ready || frozen || drawing || !activeLayer()?.visible) return;
    event.preventDefault();
    drawing = true;
    stack.setPointerCapture(event.pointerId);
    lastPoint = pointFromEvent(event);
    paintSegment(lastPoint, lastPoint);
  });
  stack.addEventListener('pointermove', (event) => {
    if (!drawing || frozen) return;
    event.preventDefault();
    const events = event.getCoalescedEvents ? event.getCoalescedEvents() : [event];
    events.forEach((part) => {
      const next = pointFromEvent(part);
      paintSegment(lastPoint, next);
      lastPoint = next;
    });
  });
  const finishStroke = (event) => {
    if (!drawing) return;
    drawing = false;
    if (stack.hasPointerCapture(event.pointerId)) stack.releasePointerCapture(event.pointerId);
    if (!frozen) pushHistory();
  };
  stack.addEventListener('pointerup', finishStroke);
  stack.addEventListener('pointercancel', finishStroke);

  document.querySelectorAll('[data-tool]').forEach((button) => {
    button.addEventListener('click', () => {
      tool = button.dataset.tool;
      document.querySelectorAll('[data-tool]').forEach((item) => item.classList.toggle('is-active', item === button));
    });
  });
  document.querySelectorAll('[data-color]').forEach((button) => {
    button.addEventListener('click', () => { colorInput.value = button.dataset.color; });
  });
  sizeInput.addEventListener('input', () => { document.getElementById('size-output').textContent = sizeInput.value; });
  opacityInput.addEventListener('input', () => { document.getElementById('opacity-output').textContent = `${opacityInput.value}%`; });
  undoButton.addEventListener('click', () => restoreHistory(historyIndex - 1));
  redoButton.addEventListener('click', () => restoreHistory(historyIndex + 1));

  document.getElementById('add-layer').addEventListener('click', async () => {
    if (frozen || layers.length >= MAX_LAYERS) return;
    const layer = await makeLayer();
    layers.push(layer);
    activeIndex = layers.length - 1;
    stack.append(layer.canvas);
    pushHistory();
  });
  document.getElementById('delete-layer').addEventListener('click', () => {
    if (frozen || layers.length <= 1) return;
    const [removed] = layers.splice(activeIndex, 1);
    removed.canvas.remove();
    activeIndex = Math.max(0, activeIndex - 1);
    pushHistory();
  });
  const moveLayer = (delta) => {
    if (frozen) return;
    const next = activeIndex + delta;
    if (next < 0 || next >= layers.length) return;
    [layers[activeIndex], layers[next]] = [layers[next], layers[activeIndex]];
    activeIndex = next;
    pushHistory();
  };
  document.getElementById('layer-up').addEventListener('click', () => moveLayer(1));
  document.getElementById('layer-down').addEventListener('click', () => moveLayer(-1));
  layerOpacity.addEventListener('input', () => {
    if (!activeLayer() || frozen) return;
    activeLayer().opacity = Number(layerOpacity.value) / 100;
    activeLayer().canvas.style.opacity = activeLayer().opacity;
  });
  layerOpacity.addEventListener('change', () => { if (!frozen) pushHistory(); });

  const compositeCanvas = () => {
    const canvas = document.createElement('canvas');
    canvas.width = SIZE;
    canvas.height = SIZE;
    const ctx = canvas.getContext('2d');
    ctx.fillStyle = '#ffffff';
    ctx.fillRect(0, 0, SIZE, SIZE);
    layers.forEach((layer) => {
      if (!layer.visible) return;
      ctx.globalAlpha = layer.opacity;
      ctx.drawImage(layer.canvas, 0, 0);
    });
    ctx.globalAlpha = 1;
    return canvas;
  };

  const blobFromCanvas = (canvas) => new Promise((resolve, reject) => {
    canvas.toBlob((blob) => blob ? resolve(blob) : reject(new Error('PNGを生成できませんでした。')), 'image/png');
  });

  const crcTable = (() => {
    const table = new Uint32Array(256);
    for (let n = 0; n < 256; n++) {
      let c = n;
      for (let k = 0; k < 8; k++) c = (c & 1) ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
      table[n] = c >>> 0;
    }
    return table;
  })();
  const crc32 = (bytes) => {
    let crc = 0xffffffff;
    for (const byte of bytes) crc = crcTable[(crc ^ byte) & 0xff] ^ (crc >>> 8);
    return (crc ^ 0xffffffff) >>> 0;
  };
  const dosDateTime = () => {
    const date = new Date();
    const time = (date.getHours() << 11) | (date.getMinutes() << 5) | (date.getSeconds() >> 1);
    const day = ((date.getFullYear() - 1980) << 9) | ((date.getMonth() + 1) << 5) | date.getDate();
    return { time, day };
  };
  const createZip = async (entries) => {
    const encoder = new TextEncoder();
    const localParts = [];
    const centralParts = [];
    let offset = 0;
    const { time, day } = dosDateTime();
    for (const entry of entries) {
      const name = encoder.encode(entry.name);
      const data = new Uint8Array(await entry.blob.arrayBuffer());
      const crc = crc32(data);
      const local = new Uint8Array(30 + name.length);
      const lv = new DataView(local.buffer);
      lv.setUint32(0, 0x04034b50, true);
      lv.setUint16(4, 20, true); lv.setUint16(6, 0x0800, true); lv.setUint16(8, 0, true);
      lv.setUint16(10, time, true); lv.setUint16(12, day, true);
      lv.setUint32(14, crc, true); lv.setUint32(18, data.length, true); lv.setUint32(22, data.length, true);
      lv.setUint16(26, name.length, true); lv.setUint16(28, 0, true);
      local.set(name, 30);
      localParts.push(local, data);

      const central = new Uint8Array(46 + name.length);
      const cv = new DataView(central.buffer);
      cv.setUint32(0, 0x02014b50, true);
      cv.setUint16(4, 20, true); cv.setUint16(6, 20, true); cv.setUint16(8, 0x0800, true);
      cv.setUint16(10, 0, true); cv.setUint16(12, time, true); cv.setUint16(14, day, true);
      cv.setUint32(16, crc, true); cv.setUint32(20, data.length, true); cv.setUint32(24, data.length, true);
      cv.setUint16(28, name.length, true); cv.setUint16(30, 0, true); cv.setUint16(32, 0, true);
      cv.setUint16(34, 0, true); cv.setUint16(36, 0, true); cv.setUint32(38, 0, true); cv.setUint32(42, offset, true);
      central.set(name, 46);
      centralParts.push(central);
      offset += local.length + data.length;
    }
    const centralSize = centralParts.reduce((sum, part) => sum + part.length, 0);
    const end = new Uint8Array(22);
    const ev = new DataView(end.buffer);
    ev.setUint32(0, 0x06054b50, true);
    ev.setUint16(8, entries.length, true); ev.setUint16(10, entries.length, true);
    ev.setUint32(12, centralSize, true); ev.setUint32(16, offset, true);
    return new Blob([...localParts, ...centralParts, end], { type: 'application/zip' });
  };

  const buildArchive = async () => {
    const manifest = {
      version: 1,
      canvas: { width: SIZE, height: SIZE },
      layers: layers.map((layer, index) => ({
        file: `layers/layer_${String(index + 1).padStart(2, '0')}.png`,
        name: layer.name,
        visible: layer.visible,
        opacity: layer.opacity,
      })),
    };
    const entries = [{ name: 'layers.json', blob: new Blob([JSON.stringify(manifest)], { type: 'application/json' }) }];
    for (let index = 0; index < layers.length; index++) {
      entries.push({ name: manifest.layers[index].file, blob: await blobFromCanvas(layers[index].canvas) });
    }
    return createZip(entries);
  };

  const showLocalDownload = async () => {
    if (localImageUrl) return;
    const blob = await blobFromCanvas(compositeCanvas());
    localImageUrl = URL.createObjectURL(blob);
    localDownload.href = localImageUrl;
    localDownload.hidden = false;
  };

  const freezeCanvas = () => {
    frozen = true;
    drawing = false;
    freezeOverlay.hidden = false;
    saveButton.disabled = true;
    syncLayers();
    showLocalDownload();
  };

  const parseResponse = async (response) => {
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.error || `保存に失敗しました (${response.status})`);
    return data;
  };

  const finishAndSave = async (automatic = false) => {
    if (!ready || saveStarted || config.saved) return;
    if (!automatic && !window.confirm('完成として描画を固定し、PNGと全レイヤーZIPを正式保存しますか？')) return;
    saveStarted = true;
    graceEndsAt = Math.min(Date.now(), Date.parse(config.drawingEndsAt)) + 60000;
    freezeCanvas();
    setStatus('描画をサーバーで固定しています…');
    try {
      const response = await window.hewFetch(config.finishUrl, { method: 'POST' });
      const data = await parseResponse(response);
      graceEndsAt = Date.parse(data.grace_ends_at);
    } catch (error) {
      setStatus(`${error.message} 固定画像の保存をこの端末から試行します。`, 'error');
    }

    let png;
    let archive;
    try {
      setStatus('合成PNGと全レイヤーZIPを生成しています…');
      png = await blobFromCanvas(compositeCanvas());
      archive = await buildArchive();
    } catch (error) {
      setStatus(`${error.message} 「固定画像を端末保存」を利用してください。`, 'error');
      return;
    }

    let lastError = '';
    while (Date.now() <= graceEndsAt) {
      try {
        const remaining = Math.max(0, Math.ceil((graceEndsAt - Date.now()) / 1000));
        setStatus(`正式保存を送信しています… 残り ${remaining} 秒`);
        const body = new FormData();
        body.append('png', png, 'composite.png');
        body.append('archive', archive, 'layers.zip');
        const response = await window.hewFetch(config.saveUrl, { method: 'POST', body });
        const data = await parseResponse(response);
        setStatus('PNGと全レイヤーZIPを正式保存しました。出品設定へ移動します。', 'success');
        await clearLocal();
        window.setTimeout(() => { window.location.href = data.listing_url; }, 900);
        return;
      } catch (error) {
        lastError = error.message;
        setStatus(`${lastError} 3秒後に再試行します。`, 'error');
        await new Promise((resolve) => window.setTimeout(resolve, 3000));
      }
    }
    setStatus(`保存猶予を過ぎました。${lastError} 端末保存は可能ですが、出品と描画ボーナスはできません。`, 'error');
  };
  saveButton.addEventListener('click', () => finishAndSave(false));

  const updateDrawingTimer = () => {
    const timer = document.getElementById('drawing-timer');
    const seconds = Math.max(0, Math.ceil((Date.parse(config.drawingEndsAt) - Date.now()) / 1000));
    const minutes = Math.floor(seconds / 60);
    timer.textContent = `${String(minutes).padStart(2, '0')}:${String(seconds % 60).padStart(2, '0')}`;
    if (seconds <= 0 && ready && !saveStarted && !config.saved) finishAndSave(true);
  };

  const setupStream = () => {
    if (!config.stream) return;
    let previewBusy = false;
    const sendPreview = async () => {
      if (config.stream.status !== 'live' || frozen || previewBusy || document.hidden) return;
      previewBusy = true;
      try {
        const blob = await blobFromCanvas(compositeCanvas());
        const body = new FormData();
        body.append('preview', blob, 'preview.png');
        await window.hewFetch(config.stream.previewUrl, { method: 'POST', body });
      } catch (_) { /* heartbeatと次のsnapshotで再試行 */ } finally { previewBusy = false; }
    };
    window.setInterval(sendPreview, 1000);
    window.setInterval(async () => {
      if (config.stream.status !== 'live' || frozen) return;
      try { await window.hewFetch(config.stream.heartbeatUrl, { method: 'POST' }); } catch (_) { /* 切断検知に委ねる */ }
    }, 5000);
    document.getElementById('pause-stream')?.addEventListener('click', async () => {
      try {
        const response = await window.hewFetch(config.stream.pauseUrl, { method: 'POST' });
        await parseResponse(response);
        config.stream.status = 'paused';
        window.location.reload();
      } catch (error) { setStatus(error.message, 'error'); }
    });
    document.getElementById('resume-stream')?.addEventListener('click', async () => {
      try {
        const response = await window.hewFetch(config.stream.resumeUrl, { method: 'POST' });
        await parseResponse(response);
        config.stream.status = 'live';
        window.location.reload();
      } catch (error) { setStatus(error.message, 'error'); }
    });
  };

  const initialize = async () => {
    setStatus('このブラウザの一時データを確認しています…');
    const record = await readLocal();
    if (record && record.drawingEndsAt === config.drawingEndsAt && record.history?.length) {
      history = record.history.slice(-MAX_HISTORY);
      historyIndex = Math.max(0, Math.min(record.historyIndex ?? history.length - 1, history.length - 1));
      try {
        await applySnapshot(history[historyIndex]);
        setStatus('レイヤーと操作履歴を復元しました。サーバーの描画期限は延長されていません。');
      } catch (_) {
        history = []; historyIndex = -1;
      }
    }
    if (!layers.length) {
      const layer = await makeLayer({ name: 'レイヤー 1' });
      layers = [layer]; activeIndex = 0;
      stack.append(layer.canvas);
      history = []; historyIndex = -1;
    }
    ready = true;
    syncLayers();
    if (historyIndex < 0) pushHistory();
    if (frozen) {
      freezeOverlay.hidden = false;
      saveButton.disabled = true;
      showLocalDownload();
      if (!config.saved) {
        saveStarted = false;
        window.setTimeout(() => finishAndSave(true), 300);
      }
    } else {
      setStatus(record ? '一時データを復元しました。正式保存すると加筆できなくなります。' : '正式保存すると加筆できなくなります。');
    }
    updateDrawingTimer();
    window.setInterval(updateDrawingTimer, 1000);
    setupStream();
  };

  initialize().catch((error) => {
    setStatus(`Canvasを初期化できませんでした: ${error.message}`, 'error');
  });
})();
