/* ==========================================================================
   描画エンジン
   - キャンバス 1,024×1,024 / レイヤー最大 10 枚
   - 元に戻す・やり直すは直近 50 操作（操作履歴から再描画する）
   - ペンを離した時点とレイヤー操作完了時に IndexedDB へ一時保存
   - 完成・時間切れで固定し、合成 PNG と全レイヤー PNG を送信する
   ========================================================================== */
(function () {
  "use strict";

  const root = document.getElementById("draw-app");
  if (!root) return;

  const ARTWORK_ID = root.dataset.artworkId;
  const SIZE = Number(root.dataset.canvasSize) || 1024;
  const MAX_LAYERS = Number(root.dataset.maxLayers) || 10;
  const SAVE_URL = root.dataset.saveUrl;
  const DRAFT_URL = root.dataset.draftUrl;
  const DRAWING_DEADLINE = Date.parse(root.dataset.drawingDeadline);
  const SAVE_DEADLINE = Date.parse(root.dataset.saveDeadline);
  const SERVER_NOW = Date.parse(root.dataset.now);
  const GRACE_EXPIRED = root.dataset.graceExpired === "1";
  const CLOCK_OFFSET = Number.isNaN(SERVER_NOW) ? 0 : SERVER_NOW - Date.now();
  const HISTORY_LIMIT = 50;
  const STORAGE_KEY = "artwork:" + ARTWORK_ID;
  const CSRF_TOKEN =
    (document.querySelector('meta[name="csrf-token"]') || {}).content || "";

  const board = document.getElementById("board");
  const boardContext = board.getContext("2d");

  const timerElement = document.getElementById("timer");
  const timerLabel = document.getElementById("timer-label");
  const saveTimerElement = document.getElementById("save-timer");
  const canvasLock = document.getElementById("canvas-lock");
  const deadlineNotice = document.getElementById("deadline-notice");
  const saveStateElement = document.getElementById("save-state");
  const historyNote = document.getElementById("history-note");
  const layerListElement = document.getElementById("layer-list");
  const layerCountElement = document.getElementById("layer-count");
  const layerOpacityInput = document.getElementById("layer-opacity");
  const layerOpacityValue = document.getElementById("layer-opacity-value");
  const penSizeInput = document.getElementById("pen-size");
  const penSizeValue = document.getElementById("pen-size-value");
  const penOpacityInput = document.getElementById("pen-opacity");
  const penOpacityValue = document.getElementById("pen-opacity-value");
  const finishButton = document.getElementById("finish");
  const undoButton = document.getElementById("undo");
  const redoButton = document.getElementById("redo");
  const addLayerButton = document.getElementById("add-layer");
  const removeLayerButton = document.getElementById("remove-layer");

  const state = {
    layers: [],
    applied: [],
    redo: [],
    active: 0,
    tool: "pen",
    color: "#141821",
    size: 6,
    opacity: 1,
    locked: false,
    saving: false,
    saved: false,
    undoCount: 0,
  };

  let currentStroke = null;

  /* ------------------------------------------------------------ レイヤー */

  function makeCanvas() {
    const canvas = document.createElement("canvas");
    canvas.width = SIZE;
    canvas.height = SIZE;
    return canvas;
  }

  function makeLayerModel(name) {
    return {
      name: name || "レイヤー" + (state.layers.length + 1),
      visible: true,
      opacity: 1,
      strokes: [],
      canvas: null,
    };
  }

  function drawStroke(context, stroke) {
    if (!stroke || !stroke.points || !stroke.points.length) return;
    context.save();
    context.globalAlpha = stroke.opacity == null ? 1 : stroke.opacity;
    context.globalCompositeOperation =
      stroke.tool === "eraser" ? "destination-out" : "source-over";
    context.strokeStyle = stroke.tool === "eraser" ? "#000000" : stroke.color;
    context.fillStyle = context.strokeStyle;
    context.lineWidth = stroke.size;
    context.lineCap = "round";
    context.lineJoin = "round";

    if (stroke.points.length === 1) {
      const point = stroke.points[0];
      context.beginPath();
      context.arc(point[0], point[1], Math.max(stroke.size / 2, 0.5), 0, Math.PI * 2);
      context.fill();
    } else {
      context.beginPath();
      context.moveTo(stroke.points[0][0], stroke.points[0][1]);
      for (let index = 1; index < stroke.points.length; index += 1) {
        context.lineTo(stroke.points[index][0], stroke.points[index][1]);
      }
      context.stroke();
    }
    context.restore();
  }

  function drawSegment(context, stroke, from, to) {
    context.save();
    context.globalAlpha = stroke.opacity == null ? 1 : stroke.opacity;
    context.globalCompositeOperation =
      stroke.tool === "eraser" ? "destination-out" : "source-over";
    context.strokeStyle = stroke.tool === "eraser" ? "#000000" : stroke.color;
    context.lineWidth = stroke.size;
    context.lineCap = "round";
    context.lineJoin = "round";
    context.beginPath();
    context.moveTo(from[0], from[1]);
    context.lineTo(to[0], to[1]);
    context.stroke();
    context.restore();
  }

  function replayLayer(layer) {
    const context = layer.canvas.getContext("2d");
    context.clearRect(0, 0, SIZE, SIZE);
    layer.strokes.forEach(function (stroke) {
      drawStroke(context, stroke);
    });
  }

  function renderBoard() {
    boardContext.save();
    boardContext.fillStyle = "#ffffff";
    boardContext.fillRect(0, 0, SIZE, SIZE);
    state.layers.forEach(function (layer) {
      if (!layer.visible || !layer.canvas) return;
      boardContext.globalAlpha = layer.opacity;
      boardContext.drawImage(layer.canvas, 0, 0);
    });
    boardContext.restore();
  }

  function applyOp(op) {
    if (!op) return;
    switch (op.type) {
      case "stroke": {
        const layer = state.layers[op.layerIndex];
        if (layer) layer.strokes.push(op.stroke);
        break;
      }
      case "add_layer":
        state.layers.push(makeLayerModel(op.data && op.data.name));
        break;
      case "remove_layer":
        if (state.layers.length > 1) state.layers.splice(op.index, 1);
        break;
      case "toggle_visibility": {
        const layer = state.layers[op.index];
        if (layer) layer.visible = op.visible;
        break;
      }
      case "layer_opacity": {
        const layer = state.layers[op.index];
        if (layer) layer.opacity = op.opacity;
        break;
      }
      case "reorder": {
        const moved = state.layers.splice(op.from, 1)[0];
        if (moved) state.layers.splice(op.to, 0, moved);
        break;
      }
      default:
        break;
    }
  }

  function rebuild() {
    state.layers = [makeLayerModel("レイヤー1")];
    state.applied.forEach(applyOp);
    state.layers.forEach(function (layer) {
      layer.canvas = makeCanvas();
      replayLayer(layer);
    });
    state.active = Math.min(Math.max(state.active, 0), state.layers.length - 1);
    renderBoard();
    renderLayerPanel();
    updateHistoryNote();
  }

  function pushOp(op, options) {
    state.applied.push(op);
    applyOp(op);
    if (!options || !options.keepRedo) {
      state.redo = [];
      state.undoCount = 0;
    }
    updateHistoryNote();
    persist();
  }

  function updateHistoryNote() {
    const recent = Math.min(state.applied.length, HISTORY_LIMIT);
    historyNote.textContent = "履歴 " + recent + " / " + HISTORY_LIMIT;
    undoButton.disabled = state.locked || state.applied.length === 0;
    redoButton.disabled = state.locked || state.redo.length === 0;
  }

  function undo() {
    if (state.locked || !state.applied.length) return;
    if (state.undoCount >= HISTORY_LIMIT) {
      setSaveState("戻せるのは直近50操作までです。", "error");
      return;
    }
    const op = state.applied.pop();
    state.redo.push(op);
    state.undoCount += 1;
    rebuild();
    persist();
  }

  function redo() {
    if (state.locked || !state.redo.length) return;
    const op = state.redo.pop();
    state.applied.push(op);
    applyOp(op);
    state.undoCount = Math.max(0, state.undoCount - 1);
    rebuild();
    persist();
  }

  function renderLayerPanel() {
    layerListElement.innerHTML = "";
    layerCountElement.textContent = state.layers.length;

    for (let index = state.layers.length - 1; index >= 0; index -= 1) {
      const layer = state.layers[index];
      const item = document.createElement("div");
      item.className = "layer-item" + (index === state.active ? " is-active" : "");
      item.dataset.index = String(index);

      const toggle = document.createElement("button");
      toggle.type = "button";
      toggle.className = "layer-icon";
      toggle.dataset.action = "toggle";
      toggle.title = "表示・非表示";
      toggle.textContent = layer.visible ? "○" : "×";

      const name = document.createElement("button");
      name.type = "button";
      name.className = "layer-name";
      name.dataset.action = "select";
      name.textContent = layer.name;

      const up = document.createElement("button");
      up.type = "button";
      up.className = "layer-icon";
      up.dataset.action = "up";
      up.title = "上へ";
      up.textContent = "↑";

      const down = document.createElement("button");
      down.type = "button";
      down.className = "layer-icon";
      down.dataset.action = "down";
      down.title = "下へ";
      down.textContent = "↓";

      item.append(toggle, name, up, down);
      layerListElement.appendChild(item);
    }

    const activeLayer = state.layers[state.active];
    if (activeLayer) {
      layerOpacityInput.value = String(Math.round(activeLayer.opacity * 100));
      layerOpacityValue.textContent = String(Math.round(activeLayer.opacity * 100));
    }
    removeLayerButton.disabled = state.layers.length <= 1;
    addLayerButton.disabled = state.layers.length >= MAX_LAYERS;
  }

  layerListElement.addEventListener("click", function (event) {
    const button = event.target.closest("button");
    if (!button || state.locked) return;
    const item = button.closest(".layer-item");
    const index = Number(item.dataset.index);
    const action = button.dataset.action;

    if (action === "select") {
      state.active = index;
      renderLayerPanel();
      return;
    }
    if (action === "toggle") {
      const layer = state.layers[index];
      pushOp({ type: "toggle_visibility", index: index, visible: !layer.visible });
      renderLayerPanel();
      renderBoard();
      return;
    }
    if (action === "up" && index < state.layers.length - 1) {
      pushOp({ type: "reorder", from: index, to: index + 1 });
      state.active = index + 1;
      rebuild();
      persist();
      return;
    }
    if (action === "down" && index > 0) {
      pushOp({ type: "reorder", from: index, to: index - 1 });
      state.active = index - 1;
      rebuild();
      persist();
    }
  });

  addLayerButton.addEventListener("click", function () {
    if (state.locked) return;
    if (state.layers.length >= MAX_LAYERS) {
      setSaveState("レイヤーは最大" + MAX_LAYERS + "枚までです。", "error");
      return;
    }
    const name = "レイヤー" + (state.layers.length + 1);
    state.active = state.layers.length;
    pushOp({ type: "add_layer", data: { name: name } });
    rebuild();
    persist();
  });

  removeLayerButton.addEventListener("click", function () {
    if (state.locked) return;
    if (state.layers.length <= 1) {
      setSaveState("最後のレイヤーは削除できません。", "error");
      return;
    }
    const index = state.active;
    state.active = Math.max(0, index - 1);
    pushOp({ type: "remove_layer", index: index });
    rebuild();
    persist();
  });

  layerOpacityInput.addEventListener("input", function () {
    const value = Math.round(Number(layerOpacityInput.value) / 100 * 100) / 100;
    layerOpacityValue.textContent = layerOpacityInput.value;
    const layer = state.layers[state.active];
    if (!layer) return;
    layer.opacity = Math.min(Math.max(value, 0), 1);
    renderBoard();
  });

  layerOpacityInput.addEventListener("change", function () {
    if (state.locked) return;
    const layer = state.layers[state.active];
    if (!layer) return;
    const value = Math.min(Math.max(Number(layerOpacityInput.value) / 100, 0), 1);
    pushOp({ type: "layer_opacity", index: state.active, opacity: value });
    renderLayerPanel();
    persist();
  });

  /* --------------------------------------------------------------- 描画 */

  function pointFromEvent(event) {
    const rect = board.getBoundingClientRect();
    const x = ((event.clientX - rect.left) / rect.width) * SIZE;
    const y = ((event.clientY - rect.top) / rect.height) * SIZE;
    return [
      Math.round(Math.min(Math.max(x, 0), SIZE) * 100) / 100,
      Math.round(Math.min(Math.max(y, 0), SIZE) * 100) / 100,
    ];
  }

  board.addEventListener("pointerdown", function (event) {
    if (state.locked || state.saved) return;
    const layer = state.layers[state.active];
    if (!layer) return;
    board.setPointerCapture(event.pointerId);
    currentStroke = {
      tool: state.tool,
      color: state.color,
      size: state.size,
      opacity: state.opacity,
      points: [pointFromEvent(event)],
    };
    drawStroke(layer.canvas.getContext("2d"), currentStroke);
    renderBoard();
  });

  board.addEventListener("pointermove", function (event) {
    if (!currentStroke || state.locked) return;
    const layer = state.layers[state.active];
    if (!layer) return;
    const point = pointFromEvent(event);
    const points = currentStroke.points;
    points.push(point);
    drawSegment(
      layer.canvas.getContext("2d"),
      currentStroke,
      points[points.length - 2],
      point
    );
    renderBoard();
  });

  function finishStroke() {
    if (!currentStroke) return;
    const stroke = currentStroke;
    currentStroke = null;
    pushOp({ type: "stroke", layerIndex: state.active, stroke: stroke });
  }

  board.addEventListener("pointerup", finishStroke);
  board.addEventListener("pointercancel", finishStroke);
  board.addEventListener("pointerleave", function (event) {
    if (event.buttons === 0) finishStroke();
  });

  /* ------------------------------------------------------------- ツール */

  document.querySelectorAll(".seg[data-tool]").forEach(function (button) {
    button.addEventListener("click", function () {
      document.querySelectorAll(".seg[data-tool]").forEach(function (other) {
        other.classList.toggle("is-active", other === button);
      });
      state.tool = button.dataset.tool;
    });
  });

  document.querySelectorAll(".swatch").forEach(function (swatch) {
    swatch.addEventListener("click", function () {
      document.querySelectorAll(".swatch").forEach(function (other) {
        other.classList.toggle("is-active", other === swatch);
      });
      state.color = swatch.dataset.color;
      state.tool = "pen";
      document.querySelectorAll(".seg[data-tool]").forEach(function (other) {
        other.classList.toggle("is-active", other.dataset.tool === "pen");
      });
    });
  });

  penSizeInput.addEventListener("input", function () {
    state.size = Number(penSizeInput.value);
    penSizeValue.textContent = penSizeInput.value;
  });

  penOpacityInput.addEventListener("input", function () {
    state.opacity = Number(penOpacityInput.value) / 100;
    penOpacityValue.textContent = penOpacityInput.value;
  });

  undoButton.addEventListener("click", undo);
  redoButton.addEventListener("click", redo);

  document.addEventListener("keydown", function (event) {
    const modifier = event.ctrlKey || event.metaKey;
    if (!modifier) return;
    if (event.key === "z" && !event.shiftKey) {
      event.preventDefault();
      undo();
    } else if ((event.key === "z" && event.shiftKey) || event.key === "y") {
      event.preventDefault();
      redo();
    }
  });

  /* ------------------------------------------------------- 一時保存 */

  function openDatabase() {
    return new Promise(function (resolve, reject) {
      if (!("indexedDB" in window)) {
        reject(new Error("IndexedDB が使えません"));
        return;
      }
      const request = indexedDB.open("hew-draw", 1);
      request.onupgradeneeded = function () {
        if (!request.result.objectStoreNames.contains("sessions")) {
          request.result.createObjectStore("sessions");
        }
      };
      request.onsuccess = function () {
        resolve(request.result);
      };
      request.onerror = function () {
        reject(request.error);
      };
    });
  }

  async function persist() {
    try {
      const database = await openDatabase();
      await new Promise(function (resolve, reject) {
        const transaction = database.transaction("sessions", "readwrite");
        transaction.objectStore("sessions").put(
          { ops: state.applied, updatedAt: Date.now() },
          STORAGE_KEY
        );
        transaction.oncomplete = resolve;
        transaction.onerror = function () {
          reject(transaction.error);
        };
      });
      database.close();
    } catch (error) {
      console.warn("一時保存に失敗しました", error);
    }
  }

  async function loadStoredSession() {
    try {
      const database = await openDatabase();
      const stored = await new Promise(function (resolve, reject) {
        const transaction = database.transaction("sessions", "readonly");
        const request = transaction.objectStore("sessions").get(STORAGE_KEY);
        request.onsuccess = function () {
          resolve(request.result);
        };
        request.onerror = function () {
          reject(request.error);
        };
      });
      database.close();
      return stored;
    } catch (error) {
      console.warn("一時保存の読み込みに失敗しました", error);
      return null;
    }
  }

  async function deleteStoredSession() {
    try {
      const database = await openDatabase();
      await new Promise(function (resolve, reject) {
        const transaction = database.transaction("sessions", "readwrite");
        transaction.objectStore("sessions").delete(STORAGE_KEY);
        transaction.oncomplete = resolve;
        transaction.onerror = function () {
          reject(transaction.error);
        };
      });
      database.close();
    } catch (error) {
      console.warn("一時データの削除に失敗しました", error);
    }
  }

  /* ----------------------------------------------------------- 保存 */

  function setSaveState(message, variant) {
    saveStateElement.textContent = message || "";
    saveStateElement.classList.toggle("is-error", variant === "error");
    saveStateElement.classList.toggle("is-ok", variant === "ok");
  }

  function canvasToBlob(canvas) {
    return new Promise(function (resolve, reject) {
      canvas.toBlob(function (blob) {
        if (blob) resolve(blob);
        else reject(new Error("画像を書き出せませんでした。"));
      }, "image/png");
    });
  }

  async function renderComposite() {
    const composite = makeCanvas();
    const context = composite.getContext("2d");
    context.fillStyle = "#ffffff";
    context.fillRect(0, 0, SIZE, SIZE);
    state.layers.forEach(function (layer) {
      if (!layer.visible || !layer.canvas) return;
      context.globalAlpha = layer.opacity;
      context.drawImage(layer.canvas, 0, 0);
    });
    context.globalAlpha = 1;
    return canvasToBlob(composite);
  }

  function offerLocalSave(blob) {
    if (document.getElementById("local-download")) return;
    const link = document.createElement("a");
    link.id = "local-download";
    link.className = "button button-small";
    link.textContent = "端末に保存";
    link.href = URL.createObjectURL(blob);
    link.download = "hew-artwork-" + ARTWORK_ID + ".png";
    saveStateElement.after(link);
  }

  async function saveAssets() {
    if (state.saving || state.saved) return;
    state.saving = true;
    setSaveState("保存しています…");

    try {
      const compositeBlob = await renderComposite();
      const form = new FormData();
      form.append("composite", compositeBlob, "composite.png");

      const manifest = {
        canvas_size: SIZE,
        layers: state.layers.map(function (layer, index) {
          return {
            name: layer.name,
            index: index,
            visible: layer.visible,
            opacity: layer.opacity,
          };
        }),
      };

      for (let index = 0; index < state.layers.length; index += 1) {
        const layerBlob = await canvasToBlob(state.layers[index].canvas);
        form.append("layers", layerBlob, "layer_" + index + ".png");
      }
      form.append("manifest", JSON.stringify(manifest));

      const response = await fetch(SAVE_URL, {
        method: "POST",
        body: form,
        headers: { "X-CSRFToken": CSRF_TOKEN },
      });
      const data = await response.json().catch(function () {
        return {};
      });

      if (!response.ok || !data.ok) {
        throw new Error(data.error || "保存に失敗しました。");
      }

      state.saved = true;
      setSaveState(
        data.bonus
          ? "正式保存しました。描画ボーナス +" + data.bonus + "pt"
          : "正式保存しました。",
        "ok"
      );
      await deleteStoredSession();
      window.setTimeout(function () {
        window.location.href = data.redirect || DRAFT_URL;
      }, 900);
    } catch (error) {
      setSaveState(error.message + " 60秒以内は再送できます。", "error");
      try {
        offerLocalSave(await renderComposite());
      } catch (inner) {
        console.warn(inner);
      }
    } finally {
      state.saving = false;
      finishButton.disabled = state.saved;
    }
  }

  function lockCanvas(message) {
    if (state.locked && message === null) return;
    state.locked = true;
    canvasLock.hidden = false;
    canvasLock.textContent = message || "描画を終了しました";
    timerLabel.textContent = "描画終了";
    saveTimerElement.hidden = false;
    updateHistoryNote();
    document.querySelectorAll(".seg[data-tool], .swatch").forEach(function (node) {
      node.disabled = true;
    });
    finishButton.disabled = true;
    addLayerButton.disabled = true;
    removeLayerButton.disabled = true;
    layerOpacityInput.disabled = true;
  }

  finishButton.addEventListener("click", function () {
    lockCanvas("完成しました。保存しています…");
    saveAssets();
  });

  /* --------------------------------------------------------- タイマー */

  function updateTimer() {
    const now = Date.now() + CLOCK_OFFSET;
    const remaining = DRAWING_DEADLINE - now;

    if (!state.locked && remaining > 0) {
      timerElement.textContent = String(Math.ceil(remaining / 1000));
      timerElement.classList.toggle("is-low", remaining <= 10000);
      return;
    }

    if (!state.locked) {
      lockCanvas("時間切れです。このまま保存します…");
      saveAssets();
    }

    timerElement.textContent = "0";
    const saveRemaining = Math.max(0, Math.ceil((SAVE_DEADLINE - now) / 1000));
    saveTimerElement.hidden = false;
    const counter = saveTimerElement.querySelector("b");
    if (counter) counter.textContent = String(saveRemaining);
    if (saveRemaining <= 0) {
      deadlineNotice.hidden = false;
    }
  }

  /* ------------------------------------------------------------ init */

  window.addEventListener("beforeunload", function (event) {
    if (!state.saved && state.applied.length) {
      event.preventDefault();
      event.returnValue = "";
    }
  });

  async function init() {
    if (GRACE_EXPIRED) {
      deadlineNotice.hidden = false;
    }
    const stored = await loadStoredSession();
    if (stored && Array.isArray(stored.ops)) {
      state.applied = stored.ops;
    }
    rebuild();
    updateTimer();
    window.setInterval(updateTimer, 250);

    if (GRACE_EXPIRED) {
      lockCanvas("保存の猶予（60秒）を過ぎました。出品できません。");
    } else if (!Number.isNaN(DRAWING_DEADLINE) && Date.now() + CLOCK_OFFSET >= DRAWING_DEADLINE) {
      lockCanvas("時間切れです。保存してください。");
    }
  }

  init();
})();
