/* 互动学习模块：单词 / 语法 / 听力 / 口语 */
(function () {
  const dataEl = document.getElementById('lesson-data');
  if (!dataEl) return;

  const data = JSON.parse(dataEl.textContent);
  const meta = window.LESSON_META || {};
  const stage = document.getElementById('lesson-stage');
  const bar = document.getElementById('lesson-progress-bar');
  const counterEl = document.getElementById('lesson-counter');
  const scorePill = document.getElementById('lesson-score-pill');
  const overlay = document.getElementById('result-overlay');
  const resultCard = document.getElementById('result-card');
  const langCode = data.language.speech_code || 'en-US';

  const KIND_LABEL = {
    vocab: '单词记忆',
    grammar: '语法练习',
    listening: '听力训练',
    speaking: '口语跟读',
  };
  const KIND_ICON = { vocab: '📖', grammar: '🧩', listening: '🎧', speaking: '🎙️' };

  const state = {
    phase: 'intro',
    index: 0,
    correct: 0,
    answeredCount: 0,
    answered: false,
    flashFlipped: false,
    speakScores: [],
    completed: false,
    submitting: false,
    itemScoreSet: false,
  };

  // ------------------------------------------------------------ 语音
  let voices = [];
  function loadVoices() {
    voices = window.speechSynthesis ? window.speechSynthesis.getVoices() : [];
  }
  if (window.speechSynthesis) {
    loadVoices();
    window.speechSynthesis.onvoiceschanged = loadVoices;
  }

  function speak(text, onEnd) {
    if (!window.speechSynthesis || !text) {
      if (onEnd) onEnd();
      return false;
    }
    window.speechSynthesis.cancel();
    const utter = new SpeechSynthesisUtterance(text);
    utter.lang = langCode;
    utter.rate = 0.88;
    utter.pitch = 1;
    const base = langCode.split('-')[0].toLowerCase();
    const match = voices.find(function (voice) {
      return (voice.lang || '').replace('_', '-').toLowerCase().indexOf(base) === 0;
    });
    if (match) utter.voice = match;
    if (onEnd) {
      utter.onend = onEnd;
      utter.onerror = onEnd;
    }
    window.speechSynthesis.speak(utter);
    return true;
  }

  function esc(value) {
    return String(value == null ? '' : value)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function setProgress(percent, label) {
    if (bar) bar.style.width = Math.max(0, Math.min(100, percent)) + '%';
    if (label && counterEl) counterEl.textContent = label;
  }

  function setScore(score) {
    if (scorePill) scorePill.textContent = score + ' 分';
  }

  // ------------------------------------------------------------ 开场
  function renderIntro() {
    const total =
      data.kind === 'speaking' ? data.speaking.length : data.questions.length;
    const unit = data.kind === 'speaking' ? '句跟读' : '道练习';
    const tipMap = {
      vocab: '先浏览闪卡理解词义，再进入测验巩固记忆。',
      grammar: '每题选择后立即查看解析，理解规则比记住答案更重要。',
      listening: '先听音频再作答，可以反复重听，最后看原文核对。',
      speaking: '点击「开始跟读」并朗读句子，系统会实时给出相似度评分。',
    };
    stage.innerHTML =
      '<div class="lesson-intro">' +
      '<div class="lesson-intro-icon">' +
      (KIND_ICON[data.kind] || '📘') +
      '</div>' +
      '<div class="quiz-eyebrow">' +
      esc(data.language.name) +
      ' · ' +
      esc(data.course.level_code) +
      '</div>' +
      '<h1>' +
      esc(data.title) +
      '</h1>' +
      '<p>' +
      esc(data.subtitle || '准备好就开始吧') +
      '</p>' +
      '<div class="lesson-intro-meta">' +
      '<span>' + total + ' ' + unit + '</span>' +
      '<span>⚡ 最高 ' + data.xp + ' XP</span>' +
      '<span>' + esc(KIND_LABEL[data.kind] || '') + '</span>' +
      '</div>' +
      '<button class="btn btn-primary btn-lg" id="start-lesson">开始学习 <span class="arrow">→</span></button>' +
      '<p class="lesson-intro-tip">' +
      (tipMap[data.kind] || '') +
      '</p>' +
      '</div>';
    setProgress(0, '准备开始');
    document.getElementById('start-lesson').addEventListener('click', start);
  }

  function start() {
    if (data.kind === 'vocab' && data.flashcards.length) {
      state.phase = 'learn';
      renderFlash(0);
    } else if (data.kind === 'speaking') {
      state.phase = 'speak';
      state.speakScores = new Array(data.speaking.length).fill(null);
      renderSpeak(0);
    } else {
      state.phase = 'quiz';
      renderQuestion(0);
    }
  }

  // ------------------------------------------------------------ 闪卡
  function renderFlash(index) {
    const cards = data.flashcards;
    const word = cards[index];
    state.index = index;
    state.flashFlipped = false;
    setProgress(((index + 1) / cards.length) * 35, '闪卡 ' + (index + 1) + ' / ' + cards.length);
    setScore(0);

    const dots = cards
      .map(function (_, i) {
        return '<span class="flash-dot ' + (i === index ? 'is-active' : '') + '"></span>';
      })
      .join('');

    stage.innerHTML =
      '<div class="flash-wrap">' +
      '<div class="quiz-footer"><small>记忆阶段 · 点击卡片翻转</small><div class="flash-dots">' + dots + '</div></div>' +
      '<div class="flash-card-3d" id="flash-card">' +
      '<div class="flash-inner">' +
      '<div class="flash-face flash-front">' +
      '<span class="ff-pos">' + esc(word.pos || '词汇') + '</span>' +
      '<span class="ff-term">' + esc(word.term) + '</span>' +
      '<span class="ff-reading">' + esc(word.reading || '') + '</span>' +
      '<span class="ff-hint">点击卡片查看释义</span>' +
      '</div>' +
      '<div class="flash-face flash-back">' +
      '<span class="ff-pos">释义</span>' +
      '<span class="fb-meaning">' + esc(word.meaning) + '</span>' +
      '<span class="fb-example">' + esc(word.example) + '</span>' +
      '<span class="fb-example-zh">' + esc(word.example_zh) + '</span>' +
      '</div>' +
      '</div>' +
      '</div>' +
      '<div class="flash-nav">' +
      '<button class="btn btn-ghost btn-sm" id="flash-prev" ' + (index === 0 ? 'disabled' : '') + '>← 上一个</button>' +
      '<span class="flash-count">' + (index + 1) + ' / ' + cards.length + '</span>' +
      '<button class="btn btn-ghost btn-sm" id="flash-next" ' + (index === cards.length - 1 ? 'disabled' : '') + '>下一个 →</button>' +
      '</div>' +
      '<div class="flash-controls">' +
      '<button class="btn btn-ghost" id="flash-speak">🔊 听发音</button>' +
      '<button class="btn btn-primary" id="start-quiz">开始测验 <span class="arrow">→</span></button>' +
      '</div>' +
      '</div>';

    const card = document.getElementById('flash-card');
    card.addEventListener('click', function () {
      state.flashFlipped = !state.flashFlipped;
      card.classList.toggle('is-flipped', state.flashFlipped);
    });
    document.getElementById('flash-speak').addEventListener('click', function (event) {
      event.stopPropagation();
      speak(word.term);
    });
    document.getElementById('flash-prev').addEventListener('click', function () {
      if (index > 0) renderFlash(index - 1);
    });
    document.getElementById('flash-next').addEventListener('click', function () {
      if (index < cards.length - 1) renderFlash(index + 1);
    });
    document.getElementById('start-quiz').addEventListener('click', function () {
      state.phase = 'quiz';
      state.correct = 0;
      state.answeredCount = 0;
      renderQuestion(0);
    });
  }

  // ------------------------------------------------------------ 题目
  function renderQuestion(index) {
    const questions = data.questions;
    const q = questions[index];
    state.index = index;
    state.answered = false;
    const total = questions.length;
    const percent = 35 + (index / total) * 65;
    setProgress(percent, '第 ' + (index + 1) + ' / ' + total + ' 题');
    setScore(state.answeredCount ? Math.round((state.correct / state.answeredCount) * 100) : 0);

    const isListening = data.kind === 'listening';
    const dots = questions
      .map(function (_, i) {
        let cls = 'quiz-dot';
        if (i < index) cls += ' is-done';
        if (i === index) cls += ' is-current';
        return '<span class="' + cls + '"></span>';
      })
      .join('');

    const optionsHtml = q.options
      .map(function (option, i) {
        return (
          '<button class="option-btn" data-index="' + i + '">' +
          '<span class="option-letter">' + String.fromCharCode(65 + i) + '</span>' +
          '<span>' + esc(option) + '</span>' +
          '</button>'
        );
      })
      .join('');

    const audioHtml = isListening
      ? '<div class="quiz-audio-row">' +
        '<button class="audio-btn" id="play-audio">▶ 播放音频</button>' +
        '<div class="audio-wave" id="audio-wave"><i></i><i></i><i></i><i></i><i></i></div>' +
        '<small class="muted" style="font-size:11px">可重复收听</small>' +
        '</div>'
      : '';

    stage.innerHTML =
      '<div class="quiz-wrap">' +
      '<div class="quiz-footer"><small>' +
      esc(KIND_LABEL[data.kind]) + ' · 第 ' + (index + 1) + ' / ' + total + ' 题</small>' +
      '<div class="quiz-dots">' + dots + '</div></div>' +
      '<div class="quiz-card">' +
      '<div class="quiz-eyebrow">' + (isListening ? 'LISTEN & CHOOSE' : 'CHOOSE THE ANSWER') + '</div>' +
      '<div class="quiz-prompt">' + esc(q.prompt) + '</div>' +
      (q.reading ? '<div class="quiz-reading">' + esc(q.reading) + '</div>' : '') +
      audioHtml +
      '<div class="quiz-options" id="quiz-options">' + optionsHtml + '</div>' +
      '<div class="quiz-feedback" id="quiz-feedback"></div>' +
      '<div class="quiz-actions"><button class="btn btn-primary" id="quiz-next" style="visibility:hidden">' +
      (index === total - 1 ? '查看结果' : '下一题') + '</button></div>' +
      '</div>' +
      '</div>';

    if (isListening) {
      const playBtn = document.getElementById('play-audio');
      const wave = document.getElementById('audio-wave');
      playBtn.addEventListener('click', function () {
        wave.classList.add('is-playing');
        playBtn.textContent = '🔊 播放中…';
        speak(q.audio, function () {
          wave.classList.remove('is-playing');
          playBtn.textContent = '▶ 重新播放';
        });
      });
    }

    document.querySelectorAll('#quiz-options .option-btn').forEach(function (button) {
      button.addEventListener('click', function () {
        if (state.answered) return;
        chooseOption(parseInt(button.dataset.index, 10));
      });
    });

    document.getElementById('quiz-next').addEventListener('click', function () {
      if (index + 1 < total) {
        renderQuestion(index + 1);
      } else {
        finish(Math.round((state.correct / total) * 100));
      }
    });
  }

  function chooseOption(selected) {
    state.answered = true;
    state.answeredCount += 1;
    const q = data.questions[state.index];
    const correct = q.answer_index;
    const isRight = selected === correct;
    if (isRight) state.correct += 1;

    const optionButtons = document.querySelectorAll('#quiz-options .option-btn');
    optionButtons.forEach(function (button, i) {
      button.disabled = true;
      if (i === correct) button.classList.add('is-correct');
      if (i === selected && !isRight) button.classList.add('is-wrong');
    });

    const feedback = document.getElementById('quiz-feedback');
    feedback.classList.add('is-visible', isRight ? 'good' : 'bad');
    const transcript = q.transcript
      ? '<strong>原文：' + esc(q.transcript) + '</strong>'
      : '';
    feedback.innerHTML =
      transcript +
      '<strong>' + (isRight ? '✅ 回答正确！' : '❌ 正确答案：' + esc(q.options[correct])) + '</strong>' +
      '<span>' + esc(q.explanation || '') + '</span>';

    setScore(Math.round((state.correct / state.answeredCount) * 100));
    const nextBtn = document.getElementById('quiz-next');
    nextBtn.style.visibility = 'visible';
  }

  // ------------------------------------------------------------ 口语
  function normalize(text) {
    return String(text || '')
      .toLowerCase()
      .replace(/[\s.,!?;:'"、。！？；：「」『』（）()【】·…—\-]/g, '');
  }

  function levenshtein(a, b) {
    const rows = a.length + 1;
    const cols = b.length + 1;
    let prev = new Array(cols);
    let curr = new Array(cols);
    for (let j = 0; j < cols; j += 1) prev[j] = j;
    for (let i = 1; i < rows; i += 1) {
      curr[0] = i;
      for (let j = 1; j < cols; j += 1) {
        const cost = a[i - 1] === b[j - 1] ? 0 : 1;
        curr[j] = Math.min(prev[j] + 1, curr[j - 1] + 1, prev[j - 1] + cost);
      }
      const tmp = prev;
      prev = curr;
      curr = tmp;
    }
    return prev[cols - 1];
  }

  function similarity(spoken, target) {
    const a = normalize(spoken);
    const b = normalize(target);
    if (!a || !b) return 0;
    const isCJK = /[\u3040-\u30ff\uac00-\ud7af\u4e00-\u9fff]/.test(b);
    if (isCJK) {
      return 1 - levenshtein(a, b) / Math.max(a.length, b.length);
    }
    const targetWords = b.split(/\s+/);
    const spokenWords = a.split(/\s+/);
    let matched = 0;
    const pool = spokenWords.slice();
    targetWords.forEach(function (word) {
      const idx = pool.indexOf(word);
      if (idx >= 0) {
        matched += 1;
        pool.splice(idx, 1);
      }
    });
    return matched / Math.max(targetWords.length, 1);
  }

  function renderSpeak(index) {
    const items = data.speaking;
    const item = items[index];
    state.index = index;
    state.itemScoreSet = false;
    const total = items.length;
    setProgress(35 + (index / total) * 65, '第 ' + (index + 1) + ' / ' + total + ' 句');
    setScore(0);

    const dots = items
      .map(function (_, i) {
        let cls = 'quiz-dot';
        if (state.speakScores[i] != null) cls += ' is-done';
        if (i === index) cls += ' is-current';
        return '<span class="' + cls + '"></span>';
      })
      .join('');

    stage.innerHTML =
      '<div class="speaking-wrap">' +
      '<div class="quiz-footer"><small>跟读阶段 · 第 ' + (index + 1) + ' / ' + total + ' 句</small>' +
      '<div class="quiz-dots">' + dots + '</div></div>' +
      '<div class="speak-card">' +
      '<div class="quiz-eyebrow">SPEAK & SCORE</div>' +
      '<div class="speak-sentence">' + esc(item.text) + '</div>' +
      (item.reading ? '<div class="speak-reading">' + esc(item.reading) + '</div>' : '') +
      '<div class="speak-translation">' + esc(item.translation) + '</div>' +
      '<div class="speak-controls">' +
      '<button class="audio-btn" id="speak-play">🔊 听示范</button>' +
      '<button class="mic-btn" id="speak-mic">🎙️ 开始跟读</button>' +
      '</div>' +
      '<div class="speak-result" id="speak-result"></div>' +
      '<div class="speak-self" id="speak-self">' +
      '<p>无法使用语音识别？可以先进行自评：</p>' +
      '<div class="self-btns">' +
      '<button class="self-btn" data-self="90">🌟 流利</button>' +
      '<button class="self-btn" data-self="70">👍 一般</button>' +
      '<button class="self-btn" data-self="50">🔁 再练</button>' +
      '</div>' +
      '</div>' +
      '<div class="speak-next" id="speak-next">' +
      '<button class="btn btn-primary" id="speak-next-btn">' + (index === total - 1 ? '查看结果' : '下一句 →') + '</button>' +
      '</div>' +
      '<p class="speak-nosupport">提示：口语评分基于浏览器语音识别，使用 Chrome 体验最佳。</p>' +
      '</div>' +
      '</div>';

    document.getElementById('speak-play').addEventListener('click', function () {
      speak(item.text);
    });
    document.getElementById('speak-mic').addEventListener('click', startRecognition);

    document.querySelectorAll('#speak-self .self-btn').forEach(function (button) {
      button.addEventListener('click', function () {
        applySpeakScore(parseInt(button.dataset.self, 10), '（自评，未进行语音识别）');
      });
    });

    document.getElementById('speak-next-btn').addEventListener('click', function () {
      if (!state.itemScoreSet) {
        window.showToast('请先跟读或选择自评，再进入下一句。', 'info');
        return;
      }
      if (index + 1 < total) {
        renderSpeak(index + 1);
      } else {
        const sum = state.speakScores.reduce(function (acc, value) {
          return acc + (value || 0);
        }, 0);
        finish(Math.round(sum / total));
      }
    });
  }

  function resetMic() {
    const mic = document.getElementById('speak-mic');
    if (!mic) return;
    mic.classList.remove('is-recording');
    mic.innerHTML = '🎙️ 重新跟读';
  }

  function getRecognition() {
    return window.SpeechRecognition || window.webkitSpeechRecognition || null;
  }

  function startRecognition() {
    const Recognition = getRecognition();
    const mic = document.getElementById('speak-mic');
    if (!Recognition) {
      document.getElementById('speak-self').classList.add('is-visible');
      window.showToast('当前浏览器不支持语音识别，请使用自评。', 'info');
      return;
    }
    let recognition;
    try {
      recognition = new Recognition();
    } catch (err) {
      document.getElementById('speak-self').classList.add('is-visible');
      return;
    }
    recognition.lang = langCode;
    recognition.interimResults = false;
    recognition.maxAlternatives = 1;
    recognition.continuous = false;

    mic.classList.add('is-recording');
    mic.innerHTML = '🎙️ 正在聆听…';

    recognition.onresult = function (event) {
      const transcript = event.results[0][0].transcript;
      const target = data.speaking[state.index].text;
      let score = Math.round(similarity(transcript, target) * 100);
      if (transcript && score < 10) score = 10;
      applySpeakScore(score, transcript);
    };
    recognition.onerror = function (event) {
      resetMic();
      document.getElementById('speak-self').classList.add('is-visible');
      if (event.error === 'not-allowed' || event.error === 'service-not-allowed') {
        window.showToast('麦克风权限未开启，可先使用自评。', 'error');
      } else if (event.error !== 'aborted' && event.error !== 'no-speech') {
        window.showToast('语音识别未成功，可再试一次或使用自评。', 'info');
      }
    };
    recognition.onend = function () {
      resetMic();
    };
    try {
      recognition.start();
      const selfPanel = document.getElementById('speak-self');
      if (selfPanel) selfPanel.classList.add('is-visible');
    } catch (err) {
      resetMic();
      document.getElementById('speak-self').classList.add('is-visible');
    }
  }

  function applySpeakScore(score, transcript) {
    state.itemScoreSet = true;
    state.speakScores[state.index] = score;
    const result = document.getElementById('speak-result');
    const stars = score >= 90 ? '★★★' : score >= 70 ? '★★☆' : '★☆☆';
    const tip = data.speaking[state.index].tip || '';
    result.classList.add('is-visible');
    result.innerHTML =
      '<div class="speak-score-row">' +
      '<div class="speak-score" style="color:' +
      (score >= 85 ? '#8effc0' : score >= 65 ? '#ffe08a' : '#ffb0c6') +
      '">' + score + '<small> 分</small></div>' +
      '<div class="speak-stars" style="color:#ffd166">' + stars + '</div>' +
      '</div>' +
      '<div class="speak-transcript">识别结果：' + esc(transcript || '（无）') + '</div>' +
      (tip ? '<div class="speak-tip">💡 ' + esc(tip) + '</div>' : '');
    setScore(score);
    document.getElementById('speak-self').classList.remove('is-visible');
    document.getElementById('speak-next').classList.add('is-visible');
    resetMic();
  }

  // ------------------------------------------------------------ 结算
  async function finish(score) {
    if (state.completed || state.submitting) return;
    state.submitting = true;
    score = Math.max(0, Math.min(100, score || 0));
    setProgress(100, '已提交');
    setScore(score);
    overlay.classList.remove('hidden');
    resultCard.innerHTML =
      '<div class="result-emoji">⏳</div><h2>正在保存学习记录…</h2>' +
      '<p class="result-sub">马上就好</p>';

    try {
      const res = await window.apiFetch('/api/lesson/' + data.id + '/complete', {
        method: 'POST',
        body: { score: score },
      });
      state.completed = true;
      state.submitting = false;
      renderResult(res, score);
      (res.achievements || []).forEach(function (ach) {
        if (window.showAchievementToast) window.showAchievementToast(ach);
      });
    } catch (err) {
      state.submitting = false;
      resultCard.innerHTML =
        '<div class="result-emoji">⚠️</div><h2>保存失败</h2>' +
        '<p class="result-sub">' + esc(err.message || '网络异常') + '</p>' +
        '<div class="result-actions">' +
        '<button class="btn btn-primary btn-block" id="retry-submit">重试</button>' +
        '<button class="btn btn-ghost btn-block" id="close-result">稍后再试</button>' +
        '</div>';
      document.getElementById('retry-submit').addEventListener('click', function () {
        finish(score);
      });
      document.getElementById('close-result').addEventListener('click', function () {
        overlay.classList.add('hidden');
      });
    }
  }

  function confettiHtml() {
    const colors = ['#7c5cff', '#22d3ee', '#ff6b9d', '#ffd166', '#4ade80'];
    let html = '';
    for (let i = 0; i < 22; i += 1) {
      const left = Math.random() * 100;
      const delay = (Math.random() * 1.6).toFixed(2);
      const duration = (1.8 + Math.random() * 1.4).toFixed(2);
      const color = colors[i % colors.length];
      html +=
        '<span class="confetti" style="left:' + left + '%;background:' + color +
        ';animation-delay:' + delay + 's;animation-duration:' + duration + 's"></span>';
    }
    return html;
  }

  function renderResult(res, score) {
    const emoji = score >= 90 ? '🎉' : score >= 70 ? '👍' : '💪';
    const title = score >= 90 ? '完美发挥！' : score >= 70 ? '不错，继续保持！' : '完成就是进步！';
    const sub = score >= 90
      ? '这一课掌握得很扎实，去挑战下一课吧。'
      : score >= 70
      ? '基础已经打稳，再复习一次会更牢固。'
      : '别灰心，回顾解析后再练一次就会更好。';

    const achievements = (res.achievements || [])
      .map(function (ach) {
        return (
          '<div class="result-ach"><span class="ra-icon">' + ach.icon + '</span>' +
          '<div><strong>' + esc(ach.name) + '</strong><small>' + esc(ach.description) + '</small></div>' +
          '<span class="ra-xp">+' + ach.xp_reward + ' XP</span></div>'
        );
      })
      .join('');

    const nextUrl = (res.next_lesson && res.next_lesson.url) || meta.nextLessonUrl;
    const nextTitle = (res.next_lesson && res.next_lesson.title) || meta.nextLessonTitle;

    const unlockHtml = res.unlocked_next_level
      ? '<div class="result-ach" style="margin-top:8px"><span class="ra-icon">🔓</span>' +
        '<div><strong>解锁新级别：' + esc(res.unlocked_next_level.title) + '</strong>' +
        '<small>完成本级别全部课程，继续挑战吧</small></div>' +
        '<a class="ra-xp" style="color:#a9f5c5" href="' + res.unlocked_next_level.url + '">前往 →</a></div>'
      : '';

    resultCard.innerHTML =
      confettiHtml() +
      '<div class="result-emoji">' + emoji + '</div>' +
      '<h2>' + title + '</h2>' +
      '<div class="result-score">' + score + '<small> 分</small></div>' +
      '<p class="result-sub">' + sub + '</p>' +
      '<div class="result-stats">' +
      '<div class="result-stat"><strong>+' + res.xp + '</strong><span>获得 XP</span></div>' +
      '<div class="result-stat"><strong>' + res.streak + '</strong><span>连续天数</span></div>' +
      '<div class="result-stat"><strong>' + res.total_xp + '</strong><span>累计 XP</span></div>' +
      '</div>' +
      (res.level_up ? '<div class="result-ach" style="margin-bottom:14px"><span class="ra-icon">✨</span><div><strong>升级啦！</strong><small>你的学习等级提升了</small></div></div>' : '') +
      (achievements ? '<div class="result-achievements">' + achievements + unlockHtml + '</div>' : unlockHtml ? '<div class="result-achievements">' + unlockHtml + '</div>' : '') +
      '<div class="result-actions">' +
      (nextUrl ? '<a class="btn btn-primary btn-block" href="' + nextUrl + '">下一课：' + esc(nextTitle || '继续学习') + ' →</a>' : '') +
      '<a class="btn btn-ghost btn-block" href="' + (res.course_url || meta.courseUrl) + '">返回课程</a>' +
      '<a class="btn btn-ghost btn-block" href="' + (meta.achievementsUrl || '/achievements') + '">查看成就</a>' +
      '</div>';
  }

  renderIntro();
})();
