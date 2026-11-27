/* 学习进度页：数据可视化 */
(function () {
  const statsXp = document.getElementById('stat-xp');
  if (!statsXp) return;

  const KIND_COLORS = {
    vocab: ['#8b7bff', '#5b8cff'],
    grammar: ['#ff6b9d', '#ff9f5a'],
    listening: ['#22d3ee', '#4f7cff'],
    speaking: ['#4ade80', '#22d3ee'],
  };

  function fmt(value) {
    return Number(value || 0).toLocaleString('zh-CN');
  }

  async function load() {
    try {
      const data = await window.apiFetch('/api/stats');
      render(data.stats);
    } catch (err) {
      document.getElementById('activity-chart').innerHTML =
        '<p class="empty-note">统计数据加载失败，请刷新重试。</p>';
    }
  }

  function render(stats) {
    const totals = stats.totals;
    statsXp.textContent = fmt(totals.xp);
    document.getElementById('stat-lessons').textContent = totals.lessons;
    document.getElementById('stat-minutes').textContent = totals.minutes;
    document.getElementById('stat-score').textContent = totals.avg_score;
    document.getElementById('stat-words').textContent = totals.words;
    document.getElementById('stat-streak').textContent = totals.streak;

    renderActivity(stats.series);
    renderSkills(stats.skills);
    renderLanguages(stats.languages);
    renderRecent(stats.recent);
    renderToday(stats.today);
  }

  function renderActivity(series) {
    const container = document.getElementById('activity-chart');
    if (!container) return;
    const width = Math.max(container.clientWidth || 640, 320);
    const height = 220;
    const padLeft = 34;
    const padRight = 12;
    const padTop = 16;
    const padBottom = 28;
    const plotW = width - padLeft - padRight;
    const plotH = height - padTop - padBottom;
    const maxXp = Math.max.apply(
      null,
      series.map(function (d) {
        return d.xp;
      }).concat([20])
    );
    const step = Math.ceil(maxXp / 4 / 10) * 10 || 20;
    const top = step * 4;

    const xAt = function (i) {
      return padLeft + (plotW * i) / Math.max(series.length - 1, 1);
    };
    const yAt = function (value) {
      return padTop + plotH - (value / top) * plotH;
    };

    const points = series.map(function (d, i) {
      return { x: xAt(i), y: yAt(d.xp), data: d };
    });

    let linePath = '';
    points.forEach(function (p, i) {
      linePath += (i === 0 ? 'M' : 'L') + p.x.toFixed(1) + ' ' + p.y.toFixed(1) + ' ';
    });
    const areaPath =
      linePath +
      'L' + points[points.length - 1].x.toFixed(1) + ' ' + (padTop + plotH) +
      ' L' + points[0].x.toFixed(1) + ' ' + (padTop + plotH) + ' Z';

    let grid = '';
    for (let i = 0; i <= 4; i += 1) {
      const value = (top / 4) * i;
      const y = yAt(value);
      grid +=
        '<line class="chart-grid-line" x1="' + padLeft + '" y1="' + y +
        '" x2="' + (width - padRight) + '" y2="' + y + '" />' +
        '<text class="chart-axis-label" x="' + (padLeft - 8) + '" y="' + (y + 3) +
        '" text-anchor="end">' + Math.round(value) + '</text>';
    }

    let labels = '';
    points.forEach(function (p, i) {
      if (i % 2 === 0 || i === points.length - 1) {
        labels +=
          '<text class="chart-axis-label" x="' + p.x + '" y="' + (height - 8) +
          '" text-anchor="middle">' + p.data.label + '</text>';
      }
    });

    let dots = '';
    points.forEach(function (p, i) {
      if (p.data.xp > 0 || i === points.length - 1) {
        dots +=
          '<circle class="chart-dot ' + (i === points.length - 1 ? 'is-today' : '') +
          '" cx="' + p.x + '" cy="' + p.y + '" r="' +
          (i === points.length - 1 ? 4.4 : 3) + '"><title>' +
          p.data.label + ' · ' + p.data.xp + ' XP</title></circle>';
      }
    });

    const totalXp = series.reduce(function (acc, d) {
      return acc + d.xp;
    }, 0);
    const totalEl = document.getElementById('activity-total');
    if (totalEl) totalEl.textContent = '14 天共 ' + totalXp + ' XP';

    container.innerHTML =
      '<svg viewBox="0 0 ' + width + ' ' + height + '" preserveAspectRatio="none" role="img" aria-label="近 14 天 XP 活跃曲线">' +
      '<defs>' +
      '<linearGradient id="areaGrad" x1="0" y1="0" x2="0" y2="1">' +
      '<stop offset="0%" stop-color="#8b7bff" stop-opacity=".85"/>' +
      '<stop offset="100%" stop-color="#8b7bff" stop-opacity="0"/>' +
      '</linearGradient>' +
      '<linearGradient id="lineGrad" x1="0" y1="0" x2="1" y2="0">' +
      '<stop offset="0%" stop-color="#8b7bff"/>' +
      '<stop offset="100%" stop-color="#22d3ee"/>' +
      '</linearGradient>' +
      '</defs>' +
      grid +
      '<path class="chart-area-fill" d="' + areaPath + '" fill="url(#areaGrad)"/>' +
      '<path class="chart-line" d="' + linePath + '" stroke="url(#lineGrad)"/>' +
      dots +
      labels +
      '</svg>';
  }

  function renderSkills(skills) {
    const container = document.getElementById('skill-chart');
    if (!container) return;
    container.innerHTML = skills
      .map(function (skill) {
        const colors = KIND_COLORS[skill.kind] || ['#8b7bff', '#22d3ee'];
        return (
          '<div class="skill-row">' +
          '<div class="skill-top"><span>' + skill.icon + ' ' + skill.label + '</span>' +
          '<span>' + skill.completed + ' / ' + skill.total + ' · ' + skill.percent + '%</span></div>' +
          '<div class="meter"><span style="width:' + skill.percent + '%;background:linear-gradient(90deg,' +
          colors[0] + ',' + colors[1] + ')"></span></div>' +
          '</div>'
        );
      })
      .join('');
  }

  function renderLanguages(languages) {
    const container = document.getElementById('lang-chart');
    if (!container) return;
    const r = 34;
    const circumference = 2 * Math.PI * r;
    container.innerHTML = languages
      .map(function (lang) {
        const offset = circumference * (1 - lang.percent / 100);
        return (
          '<div class="lang-donut">' +
          '<svg viewBox="0 0 84 84">' +
          '<circle class="donut-track" cx="42" cy="42" r="' + r + '"/>' +
          '<circle class="donut-value" cx="42" cy="42" r="' + r + '" stroke="' + lang.color +
          '" stroke-dasharray="' + circumference.toFixed(1) + '" stroke-dashoffset="' +
          offset.toFixed(1) + '"/>' +
          '</svg>' +
          '<div class="donut-label"><strong>' + lang.percent + '%</strong><span>' +
          lang.flag + ' ' + lang.name + '</span></div>' +
          '</div>'
        );
      })
      .join('');
  }

  function renderRecent(recent) {
    const container = document.getElementById('recent-list');
    if (!container) return;
    if (!recent || !recent.length) {
      container.innerHTML = '<p class="empty-row">还没有学习记录，去完成第一节课吧。</p>';
      return;
    }
    container.innerHTML = recent
      .map(function (row) {
        return (
          '<div class="recent-row">' +
          '<span class="recent-flag">' + row.flag + '</span>' +
          '<div class="recent-main"><strong>' + row.course + ' · ' + row.lesson + '</strong>' +
          '<span>' + row.kind_label + '</span></div>' +
          '<span class="recent-kind">' + row.kind_label + '</span>' +
          '<span class="recent-score">' + row.score + ' 分</span>' +
          '<span class="recent-when">' + row.when + '</span>' +
          '</div>'
        );
      })
      .join('');
  }

  function renderToday(today) {
    const container = document.getElementById('today-goal');
    if (!container) return;
    container.innerHTML =
      '<div class="today-goal-big"><strong>' + today.xp + '</strong><span>/ ' + today.goal + ' XP</span></div>' +
      '<div class="meter"><span style="width:' + today.percent + '%"></span></div>' +
      '<p class="today-goal-tip">' +
      (today.xp >= today.goal
        ? '🎉 今日目标已完成，非常棒！'
        : '再获得 ' + (today.goal - today.xp) + ' XP 即可完成今日目标。') +
      '</p>';
  }

  let resizeTimer = null;
  window.addEventListener('resize', function () {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(load, 260);
  });

  load();
})();
