(() => {
  const view = document.getElementById('stream-view');
  if (!view) return;
  const csrf = document.querySelector('meta[name="csrf-token"]').content;
  const preview = document.getElementById('stream-preview');
  const placeholder = document.getElementById('stream-placeholder');
  const ended = document.getElementById('stream-ended');
  const status = document.getElementById('stream-status');
  const list = document.getElementById('comment-list');
  const form = document.getElementById('comment-form');
  const submit = form?.querySelector('button[type="submit"]');
  let previewVersion = '';
  let commentSignature = '';
  let busy = false;
  const statusLabels = { ready: '配信前', live: '配信中', paused: '一時中断', ended: '終了' };

  const actionForm = (url, label) => {
    const action = document.createElement('form');
    action.method = 'post';
    action.action = url;
    const token = document.createElement('input');
    token.type = 'hidden'; token.name = 'csrf_token'; token.value = csrf;
    const button = document.createElement('button');
    button.type = 'submit'; button.className = 'text-button'; button.textContent = label;
    action.append(token, button);
    return action;
  };

  const renderComments = (comments) => {
    const signature = comments.map((c) => `${c.id}:${c.status}`).join('|');
    if (signature === commentSignature) return;
    commentSignature = signature;
    list.replaceChildren();
    if (!comments.length) {
      const empty = document.createElement('p');
      empty.className = 'empty-comments'; empty.textContent = '配信中の最初のコメントをどうぞ。';
      list.append(empty); return;
    }
    comments.forEach((comment) => {
      const item = document.createElement('div');
      item.className = `comment${comment.status === 'visible' ? '' : ' comment-hidden'}`;
      item.dataset.commentId = comment.id;
      const body = document.createElement('p');
      if (comment.status === 'visible') {
        const user = document.createElement('strong'); user.textContent = comment.user;
        body.textContent = comment.body;
        const time = document.createElement('time');
        time.textContent = new Date(comment.created_at).toLocaleTimeString('ja-JP', { hour: '2-digit', minute: '2-digit', hour12: false });
        item.append(user, body, time);
        if (comment.delete_url) item.append(actionForm(comment.delete_url, '削除'));
        else if (comment.hide_url) item.append(actionForm(comment.hide_url, '非表示'));
      } else {
        body.textContent = `このコメントは${comment.status === 'deleted' ? '削除' : '非表示'}されました。`;
        item.append(body);
      }
      list.append(item);
    });
    list.scrollTop = list.scrollHeight;
  };

  const refresh = async () => {
    if (busy) return;
    busy = true;
    try {
      const response = await fetch(view.dataset.stateUrl, { headers: { Accept: 'application/json' } });
      if (!response.ok) return;
      const data = await response.json();
      status.lastChild.textContent = statusLabels[data.status] || data.status;
      const isEnded = data.status === 'ended';
      ended.hidden = !isEnded;
      if (submit) submit.disabled = data.status !== 'live';
      if (data.preview_version && data.preview_version !== previewVersion) {
        previewVersion = data.preview_version;
        const image = new Image();
        image.onload = () => {
          preview.src = image.src; preview.hidden = false; placeholder.hidden = true;
        };
        image.src = `${view.dataset.previewUrl}?v=${encodeURIComponent(previewVersion)}`;
      }
      renderComments(data.comments);
    } catch (_) { /* 次の更新で再試行 */ } finally { busy = false; }
  };

  form?.addEventListener('submit', async (event) => {
    event.preventDefault();
    const error = document.getElementById('comment-error');
    error.textContent = '';
    submit.disabled = true;
    try {
      const response = await window.hewFetch(view.dataset.commentUrl, { method: 'POST', body: new FormData(form) });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || '投稿できませんでした。');
      form.reset(); commentSignature = ''; await refresh();
    } catch (err) { error.textContent = err.message; } finally {
      submit.disabled = false;
    }
  });
  window.setInterval(refresh, 1000);
})();
