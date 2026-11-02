/* HEW2026 競売詳細 JavaScript
 * 用途: 残り時間の表示、入札時の確認ダイアログ、自動入札の上限値チェック。
 * 依存: 外部ライブラリなし（ネイティブ JS / ES2017+ 相当）。
 */
(function () {
  'use strict';

  var timerEl = document.getElementById('auction-timer');
  var bidForm = document.getElementById('bid-form');
  var expectedPrice = document.getElementById('expected-price');
  var bidConfirmed = document.getElementById('bid-confirmed');
  var currentPriceEl = document.getElementById('current-price');
  var autoBidForm = document.getElementById('auto-bid-form');
  var autoBidMax = document.getElementById('auto-bid-max');

  // ---------------------------------------------------------------- ヘルパー
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

  /* 表示文字列から数値だけを取り出す（カンマ区切りや記号を無視する）。 */
  function parseNumber(text) {
    if (text === null || text === undefined) { return null; }
    var digits = String(text).replace(/[^0-9]/g, '');
    if (!digits) { return null; }
    var value = parseInt(digits, 10);
    return isNaN(value) ? null : value;
  }

  function currentPrice() {
    if (!currentPriceEl) { return null; }
    return parseNumber(currentPriceEl.textContent);
  }

  // ---------------------------------------------------------------- タイマー
  var timerId = null;

  function updateTimer() {
    if (!timerEl) { return; }
    var endMs = parseUtc(timerEl.getAttribute('data-end-time'));
    if (isNaN(endMs)) { return; }
    var remaining = Math.ceil((endMs - Date.now()) / 1000);
    if (remaining <= 0) {
      timerEl.textContent = '終了・結果確定待ち';
      timerEl.classList.add('is-ended');
      timerEl.classList.remove('is-warning');
      window.clearInterval(timerId);
      return;
    }
    timerEl.textContent = formatClock(remaining);
    if (remaining <= 10) {
      timerEl.classList.add('is-warning');
    } else {
      timerEl.classList.remove('is-warning');
    }
  }

  // ---------------------------------------------------------------- 入札
  function initBidForm() {
    if (!bidForm) { return; }
    bidForm.addEventListener('submit', function (e) {
      // 確認済み（サーバー側の確認ページを含む）ならそのまま送信する。
      if (bidConfirmed && String(bidConfirmed.value) === '1') { return; }

      e.preventDefault();

      if (expectedPrice) {
        var price = currentPrice();
        if (price !== null) { expectedPrice.value = String(price); }
      }

      if (!window.confirm('入札を確定しますか？')) { return; }

      if (bidConfirmed) { bidConfirmed.value = '1'; }
      if (typeof bidForm.requestSubmit === 'function') {
        bidForm.requestSubmit();
      } else {
        bidForm.submit();
      }
    });
  }

  // ---------------------------------------------------------------- 自動入札
  function initAutoBidForm() {
    if (!autoBidForm) { return; }
    autoBidForm.addEventListener('submit', function (e) {
      var raw = autoBidMax ? String(autoBidMax.value).trim() : '';
      var value = Number(raw);
      var price = currentPrice();
      var min = (price === null) ? 1 : price + 1;

      if (!raw || !isFinite(value) || Math.floor(value) !== value || value <= 0 || value < min) {
        e.preventDefault();
        window.alert('自動入札の上限は ' + min + ' ポイント以上の整数で入力してください。');
      }
    });
  }

  // ---------------------------------------------------------------- 初期化
  function init() {
    if (timerEl) {
      updateTimer();
      timerId = window.setInterval(updateTimer, 250);
    }
    initBidForm();
    initAutoBidForm();
  }

  init();
})();
