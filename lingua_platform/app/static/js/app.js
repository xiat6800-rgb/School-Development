/* LinguaFlow 全局交互 */
(function () {
  const csrfMeta = document.querySelector('meta[name="csrf-token"]');
  const csrfToken = csrfMeta ? csrfMeta.content : '';

  window.apiFetch = async function (url, options = {}) {
    const opts = Object.assign({}, options);
    opts.headers = Object.assign(
      { Accept: 'application/json', 'X-CSRFToken': csrfToken },
      options.headers || {}
    );
    if (opts.body && typeof opts.body !== 'string') {
      opts.headers['Content-Type'] = 'application/json';
      opts.body = JSON.stringify(opts.body);
    }
    const res = await fetch(url, opts);
    let data = null;
    try {
      data = await res.json();
    } catch (err) {
      data = null;
    }
    if (!res.ok) {
      const message =
        (data && (data.error || data.message)) || '请求失败，请稍后再试。';
      const error = new Error(message);
      error.status = res.status;
      throw error;
    }
    return data;
  };

  window.showToast = function (message, type = 'info', title = '') {
    const root = document.getElementById('toast-root');
    if (!root) return;
    const toast = document.createElement('div');
    toast.className = 'toast toast-' + type;
    const body = document.createElement('div');
    if (title) {
      const strong = document.createElement('strong');
      strong.textContent = title;
      strong.style.display = 'block';
      body.appendChild(strong);
    }
    const text = document.createElement('span');
    text.textContent = message;
    body.appendChild(text);
    toast.appendChild(body);
    root.appendChild(toast);
    setTimeout(() => {
      toast.style.transition = 'all .35s ease';
      toast.style.opacity = '0';
      toast.style.transform = 'translateY(10px)';
      setTimeout(() => toast.remove(), 380);
    }, 4200);
  };

  window.showAchievementToast = function (ach) {
    window.showToast(
      ach.description + ' · +' + ach.xp_reward + ' XP',
      'ach',
      '解锁成就 ' + ach.icon + ' ' + ach.name
    );
  };

  // 导航
  const navToggle = document.getElementById('nav-toggle');
  const navLinks = document.getElementById('nav-links');
  if (navToggle && navLinks) {
    navToggle.addEventListener('click', () => {
      navLinks.classList.toggle('is-open');
    });
    navLinks.querySelectorAll('a').forEach((link) => {
      link.addEventListener('click', () => navLinks.classList.remove('is-open'));
    });
  }

  // 用户菜单
  const userMenu = document.querySelector('[data-user-menu]');
  if (userMenu) {
    const toggle = userMenu.querySelector('[data-menu-toggle]');
    if (toggle) {
      toggle.addEventListener('click', (event) => {
        event.stopPropagation();
        userMenu.classList.toggle('is-open');
      });
    }
    document.addEventListener('click', (event) => {
      if (!userMenu.contains(event.target)) {
        userMenu.classList.remove('is-open');
      }
    });
  }

  // Flash 自动消失
  document.querySelectorAll('.flash').forEach((flash) => {
    setTimeout(() => {
      flash.classList.add('is-hiding');
      setTimeout(() => flash.remove(), 400);
    }, 3600);
  });

  // 通用点赞按钮（社区 / 详情页）
  const likeButtons = document.querySelectorAll('.like-btn');
  likeButtons.forEach((button) => {
    button.addEventListener('click', async () => {
      const postId = button.dataset.postId;
      if (!postId) return;
      try {
        const data = await window.apiFetch('/api/posts/' + postId + '/like', {
          method: 'POST',
        });
        const count = button.querySelector('.like-count');
        if (count) count.textContent = data.count;
        button.classList.toggle('is-liked', data.liked);
        button.dataset.liked = data.liked ? '1' : '0';
        if (data.liked) {
          window.showToast('已点赞，感谢你的鼓励！', 'info');
        }
      } catch (err) {
        if (err.status === 401) {
          window.location.href = '/auth/login';
        } else {
          window.showToast(err.message || '操作失败', 'error');
        }
      }
    });
  });

  // 输入计数器（可选）
  document.querySelectorAll('textarea[maxlength]').forEach((area) => {
    const counter = area.parentElement.querySelector('.char-count');
    if (!counter) return;
    const update = () => {
      counter.textContent = area.value.length + ' / ' + area.maxLength;
    };
    area.addEventListener('input', update);
    update();
  });
})();
