/* 共通スクリプト: 终了までのカウントダウン表示。 */
(function () {
  "use strict";

  const targets = document.querySelectorAll("[data-end-time]");
  if (!targets.length) return;

  function formatRemaining(milliseconds) {
    if (milliseconds <= 0) return "終了・結果確定待ち";
    const totalSeconds = Math.floor(milliseconds / 1000);
    const days = Math.floor(totalSeconds / 86400);
    const hours = Math.floor((totalSeconds % 86400) / 3600);
    const minutes = Math.floor((totalSeconds % 3600) / 60);
    const seconds = totalSeconds % 60;
    if (days > 0) return `${days}日 ${hours}時間`;
    if (hours > 0) return `${hours}:${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
    return `${minutes}:${String(seconds).padStart(2, "0")}`;
  }

  function update() {
    const now = Date.now();
    targets.forEach(function (element) {
      const endTime = Date.parse(element.dataset.endTime);
      if (Number.isNaN(endTime)) return;
      const remaining = endTime - now;
      element.textContent = formatRemaining(remaining);
      if (element.classList.contains("state-chip")) {
        if (remaining <= 0) {
          element.textContent = "終了";
        } else if (remaining <= 5 * 60 * 1000) {
          element.textContent = "まもなく終了";
        } else {
          element.textContent = "開催中";
        }
      }
      element.classList.toggle("is-expired", remaining <= 0);
    });
  }

  update();
  setInterval(update, 1000);
})();
