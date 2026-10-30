/* 商品詳細画面の入札確認と残り時間表示 */
(function () {
  "use strict";

  const bidForm = document.getElementById("bid-form");
  const amountInput = document.getElementById("amount");
  const confirmButton = document.getElementById("bid-confirm-button");
  const confirmPanel = document.getElementById("bid-confirm");
  const confirmAmount = document.getElementById("confirm-amount");
  const cancelButton = document.getElementById("bid-cancel-button");

  if (bidForm && amountInput && confirmButton && confirmPanel) {
    confirmButton.addEventListener("click", function () {
      const minimum = Number(amountInput.min || 1);
      const value = Number(amountInput.value);
      if (!Number.isInteger(value) || value < minimum) {
        window.alert("入札額は " + minimum + "pt 以上の整数で入力してください。");
        amountInput.focus();
        return;
      }
      confirmAmount.textContent = value.toLocaleString("ja-JP");
      confirmPanel.hidden = false;
      confirmButton.hidden = true;
    });

    if (cancelButton) {
      cancelButton.addEventListener("click", function () {
        confirmPanel.hidden = true;
        confirmButton.hidden = false;
        amountInput.focus();
      });
    }

    bidForm.addEventListener("submit", function () {
      const submitButton = confirmPanel.querySelector('button[type="submit"]');
      if (submitButton) {
        submitButton.disabled = true;
        submitButton.textContent = "送信しています…";
      }
    });
  }

  const countdowns = Array.from(document.querySelectorAll(".countdown[data-end]"));
  if (!countdowns.length) return;

  function update() {
    const now = Date.now();
    countdowns.forEach(function (element) {
      const end = Date.parse(element.dataset.end);
      if (Number.isNaN(end)) return;
      const seconds = Math.max(0, Math.floor((end - now) / 1000));
      if (seconds <= 0) {
        element.textContent = "終了";
        element.classList.add("is-ended");
        return;
      }
      const days = Math.floor(seconds / 86400);
      const hours = Math.floor((seconds % 86400) / 3600);
      const minutes = Math.floor((seconds % 3600) / 60);
      const rest = seconds % 60;
      let label = "残り ";
      if (days > 0) {
        label += days + "日 " + hours + "時間 " + minutes + "分";
      } else if (hours > 0) {
        label += hours + "時間 " + minutes + "分 " + rest + "秒";
      } else {
        label += minutes + "分 " + rest + "秒";
      }
      element.textContent = label;
    });
  }

  update();
  window.setInterval(update, 1000);
})();
