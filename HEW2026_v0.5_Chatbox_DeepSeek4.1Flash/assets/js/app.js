/* ============================================================
   app.js — 起動
   ============================================================ */
(function () {
  "use strict";

  const S = window.HEW_STORE;
  const UI = window.HEW_UI;

  S.init();
  UI.render();
  UI.tick();
  window.setInterval(function () { UI.tick(); }, 1000);

  const resetBtn = document.getElementById("reset-demo");
  if (resetBtn) {
    resetBtn.addEventListener("click", function () {
      const ok = window.confirm(
        "デモデータを初期状態に戻します。\n\nこのブラウザに保存した登録・下書き・入札・ポイントの記録はすべて消えます。よろしいですか？"
      );
      if (!ok) return;
      S.reset();
      location.hash = "#/";
      UI.render();
      UI.toast("デモデータを初期状態に戻しました。");
    });
  }

  if (S.isMemoryOnly()) {
    UI.toast("この環境では保存領域に書き込めないため、操作はこのタブ内だけで保持されます。", "error");
  }
})();
