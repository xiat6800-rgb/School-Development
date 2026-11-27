/* 社区交互：发布动态、评论 */
(function () {
  const composer = document.getElementById('composer');
  const openBtn = document.getElementById('open-composer');
  const form = document.getElementById('composer-form');

  if (openBtn && composer) {
    openBtn.addEventListener('click', function () {
      composer.hidden = !composer.hidden;
      if (!composer.hidden) {
        const title = composer.querySelector('input[name="title"]');
        if (title) title.focus();
        composer.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
    });
  }

  if (form) {
    form.addEventListener('submit', async function (event) {
      event.preventDefault();
      const title = form.querySelector('input[name="title"]').value.trim();
      const content = form.querySelector('textarea[name="content"]').value.trim();
      const languageCode = form.querySelector('select[name="language_code"]').value;
      if (title.length < 4) {
        window.showToast('标题至少需要 4 个字符。', 'error');
        return;
      }
      if (content.length < 10) {
        window.showToast('正文至少需要 10 个字符。', 'error');
        return;
      }
      const submit = form.querySelector('button[type="submit"]');
      submit.disabled = true;
      submit.textContent = '发布中…';
      try {
        const data = await window.apiFetch('/api/posts', {
          method: 'POST',
          body: { title: title, content: content, language_code: languageCode },
        });
        (data.achievements || []).forEach(function (ach) {
          if (window.showAchievementToast) window.showAchievementToast(ach);
        });
        window.showToast('发布成功，正在跳转…', 'success');
        setTimeout(function () {
          window.location.href = data.url;
        }, 900);
      } catch (err) {
        window.showToast(err.message || '发布失败', 'error');
        submit.disabled = false;
        submit.textContent = '发布';
      }
    });
  }

  const commentForm = document.getElementById('comment-form');
  if (commentForm) {
    commentForm.addEventListener('submit', async function (event) {
      event.preventDefault();
      const input = commentForm.querySelector('input[name="content"]');
      const content = input.value.trim();
      if (!content) return;
      const postId = commentForm.dataset.postId;
      const submit = commentForm.querySelector('button[type="submit"]');
      submit.disabled = true;
      try {
        const data = await window.apiFetch('/api/posts/' + postId + '/comments', {
          method: 'POST',
          body: { content: content },
        });
        const comment = data.comment;
        const list = document.getElementById('comment-list');
        const placeholder = document.getElementById('no-comments');
        if (placeholder) placeholder.remove();

        const item = document.createElement('div');
        item.className = 'comment-item';

        const avatar = document.createElement('span');
        avatar.className = 'avatar avatar-xs';
        avatar.style.setProperty('--avatar', comment.color);
        avatar.textContent = comment.initial;

        const body = document.createElement('div');
        body.className = 'comment-body';

        const head = document.createElement('div');
        head.className = 'comment-head';
        const author = document.createElement('strong');
        author.textContent = comment.author;
        const when = document.createElement('small');
        when.textContent = comment.created_at;
        head.appendChild(author);
        head.appendChild(when);

        const text = document.createElement('p');
        text.textContent = comment.content;

        body.appendChild(head);
        body.appendChild(text);
        item.appendChild(avatar);
        item.appendChild(body);
        list.appendChild(item);

        const total = document.getElementById('comment-total');
        const inline = document.getElementById('comment-count-inline');
        if (total) total.textContent = comment.count;
        if (inline) inline.textContent = comment.count;
        input.value = '';
        window.showToast('评论已发布', 'success');
      } catch (err) {
        window.showToast(err.message || '评论失败', 'error');
      } finally {
        submit.disabled = false;
      }
    });
  }
})();
