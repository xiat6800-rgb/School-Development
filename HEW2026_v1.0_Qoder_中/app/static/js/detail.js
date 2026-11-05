/* 商品詳細の価格・入札履歴を3秒以内の間隔で更新する（目標: 3秒以内）。 */
(function () {
  var root = document.querySelector(".detail");
  if (!root) return;
  var stateUrl = root.dataset.stateUrl;
  var priceEl = document.getElementById("current-price");
  var statusEl = document.getElementById("auction-status");
  var amountInput = document.getElementById("bid-amount");
  var expectedInput = document.getElementById("expected-price");

  function jst(iso) {
    var d = new Date(iso);
    var p = function (n) { return String(n).padStart(2, "0"); };
    return d.getFullYear() + "/" + p(d.getMonth() + 1) + "/" + p(d.getDate()) +
      " " + p(d.getHours()) + ":" + p(d.getMinutes()) + ":" + p(d.getSeconds());
  }

  function refresh() {
    fetch(stateUrl, { credentials: "same-origin" })
      .then(function (r) { return r.json(); })
      .then(function (s) {
        if (priceEl) priceEl.textContent = s.current_price;
        if (expectedInput) expectedInput.value = s.current_price;
        if (amountInput) {
          amountInput.min = s.current_price + 1;
          if (Number(amountInput.value) <= s.current_price) {
            amountInput.value = s.current_price + 1;
          }
        }
        if (statusEl) {
          if (s.status === "ended") {
            statusEl.textContent = s.winner_id
              ? "落札確定（" + s.final_price + "pt）"
              : "終了（落札者なし）";
          } else if (new Date(s.end_time) <= new Date()) {
            statusEl.textContent = "終了・結果確定待ち";
          }
        }
        var awaiting = document.getElementById("awaiting-close");
        if (!awaiting && s.status === "active" && new Date(s.end_time) <= new Date() && statusEl) {
          var p = document.createElement("p");
          p.className = "tag-warn";
          p.id = "awaiting-close";
          p.textContent = "終了・結果確定待ち（これ以降の入札は受理されません）";
          statusEl.insertAdjacentElement("afterend", p);
          var form = document.querySelector(".bid-form");
          if (form) form.querySelectorAll("input, button").forEach(function (el) { el.disabled = true; });
        }
      })
      .catch(function () { /* 次回更新で再試行 */ });
  }

  setInterval(refresh, 3000);
})();
