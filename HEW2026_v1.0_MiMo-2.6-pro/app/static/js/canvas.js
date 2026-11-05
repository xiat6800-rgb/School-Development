/* HEW 描画エンジン
 * 1024x1024 固定キャンバス / 最大10レイヤー / 元に戻す50操作
 * ペン離し・レイヤー操作完了時に IndexedDB へ一時保存
 */
(function () {
  "use strict";

  var CFG = window.HEW_CONFIG;
  var SIZE = CFG.canvasSize;
  var MAX_LAYERS = CFG.maxLayers;
  var MAX_UNDO = CFG.maxUndo;

  var paint = document.getElementById("paint");
  var ctx = paint.getContext("2d");
  var timerEl = document.getElementById("timer");
  var statusEl = document.getElementById("save-status");
  var layerListEl = document.getElementById("layer-list");

  var layers = []; // {id, name, visible, opacity, canvas, ctx}
  var activeIndex = 0;
  var undoStack = [];
  var redoStack = [];
  var drawing = false;
  var strokeBefore = null;
  var strokeLayerIndex = -1;
  var lastPoint = null;
  var frozen = false;
  var saved = false;
  var deadlineMs = CFG.deadline ? Date.parse(CFG.deadline) : null;

  /* ---------- レイヤー ---------- */

  function makeLayer(name) {
    var c = document.createElement("canvas");
    c.width = SIZE;
    c.height = SIZE;
    return {
      id: "L" + Date.now() + Math.random().toString(36).slice(2, 6),
      name: name,
      visible: true,
      opacity: 1,
      canvas: c,
      ctx: c.getContext("2d"),
    };
  }

  function composite(targetCtx) {
    targetCtx.clearRect(0, 0, SIZE, SIZE);
    targetCtx.fillStyle = "#ffffff";
    targetCtx.fillRect(0, 0, SIZE, SIZE);
    for (var i = 0; i < layers.length; i++) {
      var layer = layers[i];
      if (!layer.visible || layer.opacity <= 0) continue;
      targetCtx.save();
      targetCtx.globalAlpha = layer.opacity;
      targetCtx.drawImage(layer.canvas, 0, 0);
      targetCtx.restore();
    }
  }

  function redraw() {
    composite(ctx);
    renderLayerList();
    syncLayerControls();
  }

  function renderLayerList() {
    layerListEl.innerHTML = "";
    for (var i = layers.length - 1; i >= 0; i--) {
      var li = document.createElement("li");
      li.textContent = layers[i].name +
        (layers[i].visible ? "" : "（非表示）") +
        " · " + Math.round(layers[i].opacity * 100) + "%";
      if (i === activeIndex) li.className = "active";
      (function (index) {
        li.addEventListener("click", function () {
          activeIndex = index;
          redraw();
        });
      })(i);
      layerListEl.appendChild(li);
    }
  }

  function syncLayerControls() {
    var layer = layers[activeIndex];
    if (!layer) return;
    document.getElementById("layer-opacity").value = Math.round(layer.opacity * 100);
    document.getElementById("layer-visible").checked = layer.visible;
  }

  /* ---------- 履歴 ---------- */

  function pushHistory(entry) {
    undoStack.push(entry);
    if (undoStack.length > MAX_UNDO) undoStack.shift();
    redoStack.length = 0;
    scheduleAutosave();
  }

  function snapshotLayer(index) {
    return layers[index].ctx.getImageData(0, 0, SIZE, SIZE);
  }

  function applyUndo(entry, isRedo) {
    switch (entry.kind) {
      case "stroke": {
        var layer = layers[entry.index];
        var current = layer.ctx.getImageData(0, 0, SIZE, SIZE);
        layer.ctx.putImageData(isRedo ? entry.after : entry.before, 0, 0);
        entry.after = isRedo ? entry.after : current;
        return;
      }
      case "addLayer": {
        if (isRedo) {
          layers.splice(entry.index, 0, entry.layer);
          activeIndex = entry.index;
        } else {
          layers.splice(entry.index, 1);
          if (activeIndex >= layers.length) activeIndex = layers.length - 1;
        }
        return;
      }
      case "deleteLayer": {
        if (isRedo) {
          layers.splice(entry.index, 1);
          if (activeIndex >= layers.length) activeIndex = layers.length - 1;
        } else {
          layers.splice(entry.index, 0, entry.layer);
          activeIndex = entry.index;
        }
        return;
      }
      case "opacity": {
        var before = layers[entry.index].opacity;
        layers[entry.index].opacity = isRedo ? entry.after : entry.before;
        entry.after = isRedo ? entry.after : before;
        return;
      }
      case "visible": {
        var beforeV = layers[entry.index].visible;
        layers[entry.index].visible = isRedo ? entry.after : entry.before;
        entry.after = isRedo ? entry.after : beforeV;
        return;
      }
      case "reorder": {
        var order = isRedo ? entry.afterOrder : entry.beforeOrder;
        var map = {};
        layers.forEach(function (l) { map[l.id] = l; });
        layers = order.map(function (id) { return map[id]; }).filter(Boolean);
        return;
      }
    }
  }

  function undo() {
    if (frozen || !undoStack.length) return;
    var entry = undoStack.pop();
    applyUndo(entry, false);
    redoStack.push(entry);
    redraw();
    scheduleAutosave();
  }

  function redo() {
    if (frozen || !redoStack.length) return;
    var entry = redoStack.pop();
    applyUndo(entry, true);
    undoStack.push(entry);
    redraw();
    scheduleAutosave();
  }

  /* ---------- 描画 ---------- */

  function penSettings() {
    return {
      type: document.getElementById("pen-type").value,
      color: document.getElementById("pen-color").value,
      size: parseInt(document.getElementById("pen-size").value, 10) || 12,
    };
  }

  function canvasPoint(event) {
    var rect = paint.getBoundingClientRect();
    return {
      x: (event.clientX - rect.left) * (SIZE / rect.width),
      y: (event.clientY - rect.top) * (SIZE / rect.height),
    };
  }

  function drawSegment(layer, from, to, settings) {
    var c = layer.ctx;
    c.save();
    if (settings.type === "eraser") {
      c.globalCompositeOperation = "destination-out";
      c.strokeStyle = "rgba(0,0,0,1)";
    } else {
      c.globalCompositeOperation = "source-over";
      c.strokeStyle = settings.color;
    }
    c.lineWidth = settings.size;
    c.lineCap = "round";
    c.lineJoin = "round";
    if (settings.type === "air") {
      c.globalAlpha = 0.08;
      var steps = Math.max(1, Math.ceil(Math.hypot(to.x - from.x, to.y - from.y) / 3));
      for (var s = 0; s <= steps; s++) {
        var x = from.x + ((to.x - from.x) * s) / steps;
        var y = from.y + ((to.y - from.y) * s) / steps;
        var gradient = c.createRadialGradient(x, y, 0, x, y, settings.size);
        gradient.addColorStop(0, settings.color);
        gradient.addColorStop(1, "rgba(0,0,0,0)");
        c.fillStyle = gradient;
        c.beginPath();
        c.arc(x, y, settings.size, 0, Math.PI * 2);
        c.fill();
      }
    } else {
      c.beginPath();
      c.moveTo(from.x, from.y);
      c.lineTo(to.x, to.y);
      c.stroke();
    }
    c.restore();
  }

  function onPointerDown(event) {
    if (frozen || saved) return;
    event.preventDefault();
    paint.setPointerCapture(event.pointerId);
    strokeLayerIndex = activeIndex;
    strokeBefore = snapshotLayer(strokeLayerIndex);
    drawing = true;
    lastPoint = canvasPoint(event);
    drawSegment(layers[strokeLayerIndex], lastPoint, lastPoint, penSettings());
    redraw();
  }

  function onPointerMove(event) {
    if (!drawing) return;
    event.preventDefault();
    var point = canvasPoint(event);
    drawSegment(layers[strokeLayerIndex], lastPoint, point, penSettings());
    lastPoint = point;
    composite(ctx);
  }

  function onPointerUp() {
    if (!drawing) return;
    drawing = false;
    pushHistory({
      kind: "stroke",
      index: strokeLayerIndex,
      before: strokeBefore,
    });
    redraw();
    scheduleAutosave();
  }

  /* ---------- レイヤー操作 ---------- */

  function addLayer() {
    if (frozen || layers.length >= MAX_LAYERS) return;
    var layer = makeLayer("レイヤー" + (layers.length + 1));
    var index = activeIndex + 1;
    layers.splice(index, 0, layer);
    activeIndex = index;
    pushHistory({ kind: "addLayer", index: index, layer: layer });
    redraw();
  }

  function deleteLayer() {
    if (frozen || layers.length <= 1) return;
    var index = activeIndex;
    var layer = layers[index];
    layers.splice(index, 1);
    if (activeIndex >= layers.length) activeIndex = layers.length - 1;
    pushHistory({ kind: "deleteLayer", index: index, layer: layer });
    redraw();
  }

  function moveLayer(delta) {
    if (frozen) return;
    var target = activeIndex + delta;
    if (target < 0 || target >= layers.length) return;
    var beforeOrder = layers.map(function (l) { return l.id; });
    var tmp = layers[activeIndex];
    layers[activeIndex] = layers[target];
    layers[target] = tmp;
    activeIndex = target;
    pushHistory({
      kind: "reorder",
      beforeOrder: beforeOrder,
      afterOrder: layers.map(function (l) { return l.id; }),
    });
    redraw();
  }

  function setOpacity(value) {
    if (frozen) return;
    var layer = layers[activeIndex];
    var before = layer.opacity;
    layer.opacity = value;
    pushHistory({ kind: "opacity", index: activeIndex, before: before, after: value });
    redraw();
  }

  function setVisible(visible) {
    if (frozen) return;
    var layer = layers[activeIndex];
    var before = layer.visible;
    layer.visible = visible;
    pushHistory({ kind: "visible", index: activeIndex, before: before, after: visible });
    redraw();
  }

  /* ---------- IndexedDB 一時保存 ---------- */

  var dbPromise = null;

  function openDb() {
    if (dbPromise) return dbPromise;
    dbPromise = new Promise(function (resolve, reject) {
      var request = indexedDB.open("hew-drawing", 1);
      request.onupgradeneeded = function () {
        var db = request.result;
        if (!db.objectStoreNames.contains("sessions")) {
          db.createObjectStore("sessions");
        }
      };
      request.onsuccess = function () { resolve(request.result); };
      request.onerror = function () { reject(request.error); };
    });
    return dbPromise;
  }

  function serializeHistory(entry) {
    var copy = { kind: entry.kind, index: entry.index };
    if (entry.before) copy.before = entry.before;
    if (entry.after !== undefined) copy.after = entry.after;
    if (entry.layer) copy.layer = entry.layer;
    if (entry.beforeOrder) copy.beforeOrder = entry.beforeOrder;
    if (entry.afterOrder) copy.afterOrder = entry.afterOrder;
    return copy;
  }

  var autosaveTimer = null;

  function scheduleAutosave() {
    if (autosaveTimer) clearTimeout(autosaveTimer);
    autosaveTimer = setTimeout(autosave, 200);
  }

  function autosave() {
    if (saved) return;
    openDb().then(function (db) {
      var payload = {
        artworkId: CFG.artworkId,
        deadline: CFG.deadline,
        savedAt: Date.now(),
        activeIndex: activeIndex,
        layers: layers.map(function (l) {
          return {
            id: l.id,
            name: l.name,
            visible: l.visible,
            opacity: l.opacity,
            pixels: l.ctx.getImageData(0, 0, SIZE, SIZE),
          };
        }),
        history: undoStack.map(serializeHistory),
      };
      var tx = db.transaction("sessions", "readwrite");
      tx.objectStore("sessions").put(payload, CFG.artworkId);
    }).catch(function () {
      /* 保存失敗時の復元は保証しない */
    });
  }

  function restoreFromDb() {
    return openDb().then(function (db) {
      return new Promise(function (resolve) {
        var tx = db.transaction("sessions", "readonly");
        var request = tx.objectStore("sessions").get(CFG.artworkId);
        request.onsuccess = function () { resolve(request.result || null); };
        request.onerror = function () { resolve(null); };
      });
    }).then(function (data) {
      if (!data || !data.layers || !data.layers.length) return false;
      layers = data.layers.map(function (l) {
        var layer = makeLayer(l.name);
        layer.id = l.id;
        layer.visible = l.visible;
        layer.opacity = l.opacity;
        layer.ctx.putImageData(l.pixels, 0, 0);
        return layer;
      });
      activeIndex = Math.min(data.activeIndex || 0, layers.length - 1);
      undoStack = (data.history || []).map(function (entry) {
        return entry;
      });
      return true;
    }).catch(function () { return false; });
  }

  function clearLocalSession() {
    openDb().then(function (db) {
      var tx = db.transaction("sessions", "readwrite");
      tx.objectStore("sessions").delete(CFG.artworkId);
    }).catch(function () {});
  }

  /* ---------- 保存 ---------- */

  function buildLayerPngs() {
    var blobs = [];
    layers.forEach(function (layer) {
      var out = document.createElement("canvas");
      out.width = SIZE;
      out.height = SIZE;
      var outCtx = out.getContext("2d");
      if (layer.visible && layer.opacity > 0) {
        outCtx.save();
        outCtx.globalAlpha = layer.opacity;
        outCtx.drawImage(layer.canvas, 0, 0);
        outCtx.restore();
      } else {
        outCtx.drawImage(layer.canvas, 0, 0);
      }
      blobs.push(out);
    });
    return blobs;
  }

  function canvasToBlob(canvas) {
    return new Promise(function (resolve) {
      canvas.toBlob(resolve, "image/png");
    });
  }

  function setStatus(text, urgent) {
    statusEl.textContent = text;
    statusEl.style.color = urgent ? "var(--danger)" : "var(--muted)";
  }

  function saveDraft() {
    if (saved) return Promise.resolve();
    frozen = true;
    setStatus("保存しています…", false);

    var compositeCanvas = document.createElement("canvas");
    compositeCanvas.width = SIZE;
    compositeCanvas.height = SIZE;
    composite(compositeCanvas.getContext("2d"));

    var manifest = layers.map(function (layer, index) {
      return {
        name: layer.name,
        visible: layer.visible,
        opacity: layer.opacity,
        order: index,
      };
    });

    return canvasToBlob(compositeCanvas).then(function (compositeBlob) {
      var layerCanvases = buildLayerPngs();
      return Promise.all(layerCanvases.map(canvasToBlob)).then(function (layerBlobs) {
        var form = new FormData();
        form.append("csrf_token", CFG.csrfToken);
        form.append("manifest", JSON.stringify(manifest));
        form.append("image", compositeBlob, "artwork.png");
        layerBlobs.forEach(function (blob, index) {
          form.append("layers", blob, "layer_" + index + ".png");
        });
        return fetch(CFG.saveUrl, { method: "POST", body: form });
      });
    }).then(function (response) {
      return response.json().then(function (data) {
        return { ok: response.ok, data: data };
      });
    }).then(function (result) {
      if (result.ok && result.data.status === "ok") {
        saved = true;
        setStatus("保存しました。", false);
        clearLocalSession();
        window.location.href = "/artworks/" + result.data.artwork_id;
      } else {
        frozen = false;
        setStatus(
          (result.data && result.data.message) || "保存に失敗しました。",
          true
        );
      }
    }).catch(function () {
      frozen = false;
      setStatus("通信エラー。再試行してください。", true);
    });
  }

  /* ---------- タイマー ---------- */

  function tick() {
    if (deadlineMs == null) {
      timerEl.textContent = "--:--";
      return;
    }
    var remaining = deadlineMs - Date.now();
    if (remaining <= 0) {
      timerEl.textContent = "00:00";
      timerEl.classList.add("urgent");
      if (!frozen && !saved) {
        frozen = true;
        redraw();
        saveDraft();
      }
      var graceMs = CFG.saveGrace * 1000;
      if (!saved && Date.now() > deadlineMs + graceMs) {
        setStatus("保存猶予を過ぎました。この作品は出品できません。", true);
      }
      return;
    }
    var totalSeconds = Math.ceil(remaining / 1000);
    var minutes = Math.floor(totalSeconds / 60);
    var seconds = totalSeconds % 60;
    timerEl.textContent =
      ("0" + minutes).slice(-2) + ":" + ("0" + seconds).slice(-2);
    timerEl.classList.toggle("urgent", remaining < 10000);
    if (remaining <= 0.2) {
      frozen = true;
      redraw();
      saveDraft();
    }
  }

  /* ---------- 初期化 ---------- */

  function init() {
    if (layers.length === 0) {
      layers.push(makeLayer("レイヤー1"));
    }
    restoreFromDb().then(function (restored) {
      if (!restored && layers.length === 0) {
        layers.push(makeLayer("レイヤー1"));
      }
      if (deadlineMs != null && Date.now() >= deadlineMs) {
        frozen = true;
      }
      redraw();
    });

    paint.addEventListener("pointerdown", onPointerDown);
    paint.addEventListener("pointermove", onPointerMove);
    paint.addEventListener("pointerup", onPointerUp);
    paint.addEventListener("pointercancel", onPointerUp);

    document.getElementById("btn-undo").addEventListener("click", undo);
    document.getElementById("btn-redo").addEventListener("click", redo);
    document.getElementById("btn-finish").addEventListener("click", saveDraft);
    document.getElementById("btn-layer-add").addEventListener("click", addLayer);
    document.getElementById("btn-layer-delete").addEventListener("click", deleteLayer);
    document.getElementById("btn-layer-up").addEventListener("click", function () {
      moveLayer(1);
    });
    document.getElementById("btn-layer-down").addEventListener("click", function () {
      moveLayer(-1);
    });
    document.getElementById("layer-opacity").addEventListener("change", function (e) {
      setOpacity(parseInt(e.target.value, 10) / 100);
    });
    document.getElementById("layer-visible").addEventListener("change", function (e) {
      setVisible(e.target.checked);
    });

    setInterval(tick, 250);
    tick();
  }

  init();
})();
