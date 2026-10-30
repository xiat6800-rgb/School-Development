(() => {
  const csrf = document.querySelector('meta[name="csrf-token"]')?.content || '';
  window.hewFetch = (url, options = {}) => {
    const headers = new Headers(options.headers || {});
    headers.set('X-CSRFToken', csrf);
    if (!headers.has('Accept')) headers.set('Accept', 'application/json');
    return fetch(url, { credentials: 'same-origin', ...options, headers });
  };

  document.querySelectorAll('form[data-confirm]').forEach((form) => {
    form.addEventListener('submit', (event) => {
      if (!window.confirm(form.dataset.confirm)) event.preventDefault();
    });
  });

  document.querySelectorAll('[data-copy]').forEach((button) => {
    button.addEventListener('click', async () => {
      const target = document.querySelector(button.dataset.copy);
      if (!target) return;
      try {
        await navigator.clipboard.writeText(target.textContent.trim());
        button.textContent = 'コピーしました';
      } catch (_) {
        const range = document.createRange();
        range.selectNodeContents(target);
        window.getSelection().removeAllRanges();
        window.getSelection().addRange(range);
        button.textContent = '選択しました。Ctrl+Cでコピー';
      }
    });
  });

  const updateCountdowns = () => {
    const now = Date.now();
    document.querySelectorAll('.countdown[data-end]').forEach((element) => {
      const seconds = Math.max(0, Math.floor((Date.parse(element.dataset.end) - now) / 1000));
      const hours = Math.floor(seconds / 3600);
      const minutes = Math.floor((seconds % 3600) / 60);
      const rest = seconds % 60;
      element.textContent = seconds <= 0 ? '終了・結果確定待ち' :
        (hours > 0 ? `${hours}:${String(minutes).padStart(2, '0')}:${String(rest).padStart(2, '0')}` :
          `${String(minutes).padStart(2, '0')}:${String(rest).padStart(2, '0')}`);
    });
  };
  updateCountdowns();
  if (document.querySelector('.countdown')) window.setInterval(updateCountdowns, 1000);
})();
