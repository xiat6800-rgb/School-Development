/* 描画キャンバス（要件定義書 5.2）
   - 制限時間は開始後に変更できない
   - 時間切れ・完成操作のどちらでも PNG を送信して下書き保存する
*/
(function () {
  "use strict";

  const canvas = document.getElementById("draw-canvas");
  if (!canvas) return;

  const ctx = canvas.getContext("2d");
  const overlay = document.getElementById("canvas-overlay");
  const frame = canvas.closest(".canvas-frame");
  const saveForm = document.getElementById("save-form");
  const saveButton = document.getElementById("save-button");
  const imageInput = document.getElementById("image-data");
  const startButton = document.getElementById("start-button");
  const undoButton = document.getElementById("undo-button");
  const clearButton = document.getElementById("clear-button");
  const timerLabel = document.getElementById("timer");
  const sizeInput = document.getElementById("brush-size");
  const sizeOutput = document.getElementById("size-output");
  const colorInput = document.getElementById("pen-color");
  const penButtons = Array.from(document.querySelectorAll(".pen-button"));
  const timeInputs = Array.from(document.querySelectorAll('input[name="time_limit"]'));

  let started = false;
  let saving = false;
  let drawing = false;
  let pen = "gpen";
  let remaining = 0;
  let timerId = null;
  const undoStack = [];
  const UNDO_LIMIT = 20;

  function fillWhite() {
    ctx.save();
    ctx.globalCompositeOperation = "source-over";
    ctx.globalAlpha = 1;
    ctx.fillStyle = "#ffffff";
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.restore();
  }

  function applyPen() {
    const size = Number(sizeInput.value) || 6;
    const color = colorInput.value || "#1b2a3a";
    ctx.lineJoin = "round";
    ctx.lineCap = "round";
    ctx.shadowBlur = 0;
    ctx.shadowColor = "transparent";

    if (pen === "eraser") {
      ctx.globalCompositeOperation = "source-over";
      ctx.globalAlpha = 1;
      ctx.strokeStyle = "#ffffff";
      ctx.lineWidth = size * 1.6;
    } else if (pen === "blur") {
      ctx.globalCompositeOperation = "source-over";
      ctx.globalAlpha = 0.22;
      ctx.strokeStyle = color;
      ctx.lineWidth = size * 1.7;
      ctx.shadowBlur = size * 2.2;
      ctx.shadowColor = color;
    } else if (pen === "maru") {
      ctx.globalCompositeOperation = "source-over";
      ctx.globalAlpha = 0.92;
      ctx.strokeStyle = color;
      ctx.lineWidth = size * 0.9;
      ctx.shadowBlur = size * 0.5;
      ctx.shadowColor = color;
    } else {
      ctx.globalCompositeOperation = "source-over";
      ctx.globalAlpha = 1;
      ctx.strokeStyle = color;
      ctx.lineWidth = size;
    }
  }

  function pushUndo() {
    try {
      const snapshot = ctx.getImageData(0, 0, canvas.width, canvas.height);
      undoStack.push(snapshot);
      if (undoStack.length > UNDO_LIMIT) undoStack.shift();
    } catch (error) {
      /* 取得できない環境では undo を無効化する */
      undoStack.length = 0;
    }
  }

  function position(event) {
    const rect = canvas.getBoundingClientRect();
    return {
      x: ((event.clientX - rect.left) * canvas.width) / rect.width,
      y: ((event.clientY - rect.top) * canvas.height) / rect.height,
    };
  }

  canvas.addEventListener("pointerdown", function (event) {
    if (!started || saving) return;
    drawing = true;
    canvas.setPointerCapture(event.pointerId);
    pushUndo();
    applyPen();
    const point = position(event);
    ctx.beginPath();
    ctx.moveTo(point.x, point.y);
    event.preventDefault();
  });

  canvas.addEventListener("pointermove", function (event) {
    if (!drawing || !started) return;
    const point = position(event);
    ctx.lineTo(point.x, point.y);
    ctx.stroke();
    event.preventDefault();
  });

  function endStroke(event) {
    if (!drawing) return;
    drawing = false;
    ctx.closePath();
    ctx.globalAlpha = 1;
    ctx.shadowBlur = 0;
    if (event && canvas.hasPointerCapture(event.pointerId)) {
      canvas.releasePointerCapture(event.pointerId);
    }
  }

  canvas.addEventListener("pointerup", endStroke);
  canvas.addEventListener("pointercancel", endStroke);
  canvas.addEventListener("pointerleave", function (event) {
    if (drawing) endStroke(event);
  });

  penButtons.forEach(function (button) {
    button.addEventListener("click", function () {
      pen = button.dataset.pen || "gpen";
      penButtons.forEach(function (item) {
        item.classList.toggle("is-active", item === button);
      });
    });
  });

  sizeInput.addEventListener("input", function () {
    sizeOutput.textContent = sizeInput.value;
  });

  function formatTime(seconds) {
    const safe = Math.max(0, seconds);
    const minutes = Math.floor(safe / 60);
    const rest = safe % 60;
    return String(minutes).padStart(2, "0") + ":" + String(rest).padStart(2, "0");
  }

  function saveDraft() {
    if (saving) return;
    if (!started) {
      window.alert("先に「描き始める」を押してください。");
      return;
    }
    saving = true;
    if (timerId) {
      window.clearInterval(timerId);
      timerId = null;
    }
    imageInput.value = canvas.toDataURL("image/png");
    saveButton.disabled = true;
    saveButton.textContent = "保存しています…";
    saveForm.submit();
  }

  startButton.addEventListener("click", function () {
    if (started) return;
    const selected = timeInputs.find(function (input) {
      return input.checked;
    });
    if (!selected) {
      window.alert("制限時間を選んでください。");
      return;
    }

    started = true;
    remaining = Number(selected.value) || 60;
    timeInputs.forEach(function (input) {
      input.disabled = true;
    });
    overlay.classList.add("is-hidden");
    frame.classList.add("is-active");
    startButton.disabled = true;
    startButton.textContent = "描画中";
    saveButton.disabled = false;

    timerLabel.textContent = formatTime(remaining);
    timerId = window.setInterval(function () {
      remaining -= 1;
      timerLabel.textContent = formatTime(remaining);
      if (remaining <= 0) {
        window.clearInterval(timerId);
        timerId = null;
        timerLabel.textContent = "00:00";
        saveDraft();
      }
    }, 1000);
  });

  undoButton.addEventListener("click", function () {
    if (!started || saving) return;
    const snapshot = undoStack.pop();
    if (!snapshot) return;
    ctx.putImageData(snapshot, 0, 0);
  });

  clearButton.addEventListener("click", function () {
    if (!started || saving) return;
    pushUndo();
    fillWhite();
  });

  saveButton.addEventListener("click", function (event) {
    event.preventDefault();
    if (!started) return;
    if (!window.confirm("下書きとして保存します。保存後は加筆できません。よろしいですか？")) {
      return;
    }
    saveDraft();
  });

  canvas.addEventListener("contextmenu", function (event) {
    event.preventDefault();
  });

  fillWhite();
})();
