(() => {
  const detail = document.querySelector('.auction-detail[data-status-url]');
  if (!detail) return;
  let lastSignature = '';
  let stopped = false;

  const renderBids = (bids) => {
    const signature = bids.map((bid) => `${bid.id}:${bid.amount}`).join('|');
    if (signature === lastSignature) return;
    lastSignature = signature;
    const list = document.getElementById('bid-list');
    const count = document.getElementById('bid-count');
    if (!list) return;
    list.replaceChildren();
    if (count) count.textContent = `${bids.length}件`;
    if (!bids.length) {
      const empty = document.createElement('p');
      empty.className = 'muted';
      empty.textContent = '最初の入札は現在価格＋1ptから。';
      list.append(empty);
      return;
    }
    bids.forEach((bid) => {
      const row = document.createElement('div');
      row.className = 'bid-row';
      const bidder = document.createElement('span');
      bidder.textContent = bid.bidder;
      if (bid.auto) {
        const auto = document.createElement('small');
        auto.textContent = '自動';
        bidder.append(auto);
      }
      const amount = document.createElement('strong');
      amount.textContent = `${bid.amount.toLocaleString()}pt`;
      const time = document.createElement('time');
      time.textContent = new Date(`${bid.created_at}`).toLocaleTimeString('ja-JP', { hour12: false });
      row.append(bidder, amount, time);
      list.append(row);
    });
  };

  const refresh = async () => {
    if (stopped || document.hidden) return;
    try {
      const response = await fetch(detail.dataset.statusUrl, { headers: { Accept: 'application/json' } });
      if (!response.ok) return;
      const data = await response.json();
      const price = document.getElementById('current-price');
      if (price && data.status === 'active') price.innerHTML = `${data.current_price.toLocaleString()}<small>pt</small>`;
      const bidder = document.getElementById('current-bidder');
      if (bidder && data.status === 'active') bidder.textContent = data.current_bidder ? `最高入札: ${data.current_bidder}` : 'まだ入札はありません';
      renderBids(data.bids);
      if (data.status !== 'active') {
        stopped = true;
        window.setTimeout(() => window.location.reload(), 800);
      }
    } catch (_) { /* 次の3秒更新で再試行 */ }
  };
  window.setInterval(refresh, 3000);
})();
