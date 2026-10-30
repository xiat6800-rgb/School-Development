/* ============================================================
   store.js — 業務ロジック（ブラウザ内で完結するデモ用の実装）
   要件定義書 Ver0.5 のルールだけを実装する。
   ・入札：開催中 / 終了前 / 自己入札禁止 / 現在価格より大きい / 残高内
   ・受理時に引き落とし、高値更新で前の最高額を返却（同一トランザクション相当）
   ・自動入札：他人の入札に上限額の範囲で上乗せ。同額上限は設定が早い人を優先
   ・終了：終了日時で落札確定。落札時に二重に引き落とさない
   ※ 本物の認証・DB・排他制御ではありません。画面と業務ルールの確認用です。
   ============================================================ */
(function () {
  "use strict";

  const KEY = "hew2027.v05.chatbox.prototype";
  const INCREMENT = 10;                 // 自動入札の上乗せ幅（未決事項の開発用既定値）
  const BONUS = { signup: 500, draw: 50, list: 100 };

  let state = null;
  let memoryOnly = false;               // localStorage が使えない環境の退避

  /* ---------- 小物 ---------- */
  const now = () => Date.now();
  const iso = (ms) => new Date(ms).toISOString();
  const uniq = (arr) => Array.from(new Set(arr));

  function nextId(prefix) {
    state.seq.n += 1;
    return prefix + "-" + state.seq.n;
  }

  function enc(pw) {
    try { return btoa(unescape(encodeURIComponent("hew:" + pw))); }
    catch (e) { return "raw:" + pw; }
  }

  function persist() {
    if (memoryOnly) return;
    try {
      localStorage.setItem(KEY, JSON.stringify(state));
    } catch (e) {
      memoryOnly = true;
      console.warn("保存領域に書き込めないため、このタブ内だけで動作します。", e);
    }
  }

  function load() {
    try {
      const raw = localStorage.getItem(KEY);
      if (!raw) return null;
      const parsed = JSON.parse(raw);
      if (!parsed || parsed.version !== 1) return null;
      return parsed;
    } catch (e) { return null; }
  }

  /* ---------- 種データの組み立て ---------- */
  function blank() {
    return {
      version: 1,
      seq: { n: 0 },
      users: [],
      artworks: [],
      auctions: [],
      bids: [],
      autoBids: [],
      tx: [],
      notices: [],
      mails: [],
      favWorks: [],
      favAuctions: [],
      bonus: {},
      session: { userId: null },
      meta: { seededAt: null }
    };
  }

  function addUser(username, email, displayName, balance) {
    const u = {
      id: nextId("u"),
      username: username,
      email: email.toLowerCase(),
      pw: enc(window.HEW_DATA.DEV_PASSWORD),
      displayName: displayName,
      balance: 0,
      createdAt: iso(now())
    };
    state.users.push(u);
    // 開発用の初期ポイントは登録ボーナスより先に付与した扱いにする
    credit(u.id, "dev", balance - BONUS.signup, "開発用の初期ポイント", now() - 2000);
    credit(u.id, "signup", BONUS.signup, "登録ボーナス");
    state.bonus[u.id] = { signup: true, draw: false, list: false };
    return u;
  }

  function credit(userId, kind, amount, note, atMs) {
    if (amount === 0) return null;
    const u = user(userId);
    if (!u) return null;
    u.balance += amount;
    const row = {
      id: nextId("t"),
      userId: userId,
      kind: kind,
      amount: amount,
      balanceAfter: u.balance,
      note: note || "",
      createdAt: iso(atMs || now())
    };
    state.tx.push(row);
    return row;
  }

  function buildSeed() {
    state = blank();
    const users = window.HEW_DATA.USERS.map((u) => addUser(u.username, u.email, u.displayName, u.balance));
    const base = now();

    window.HEW_DATA.WORKS.forEach((w, i) => {
      const seller = users[w.seller === undefined ? 1 : w.seller] || users[1];
      const agoMin = w.listedAgoMin || (i + 1) * 186;
      const createdAt = base - agoMin * 60 * 1000;
      const art = {
        id: nextId("a"),
        sellerId: seller.id,
        title: w.title,
        description: w.description,
        tags: w.tags.slice(),
        image: window.HEW_ART.svgArt(w.seed, w.artStyle),
        imageKind: "svg",
        drawSeconds: w.drawSeconds || 30,
        status: "listed",
        createdAt: iso(createdAt),
        listedAt: iso(createdAt)
      };
      state.artworks.push(art);
      state.auctions.push({
        id: nextId("au"),
        artworkId: art.id,
        sellerId: seller.id,
        startPrice: w.startPrice,
        currentPrice: w.startPrice,
        endsAt: iso(base + w.endsIn * 1000),
        createdAt: iso(createdAt),
        status: "active",
        winnerBidId: null,
        finalPrice: null
      });
    });

    // デモアカウントの下書きを 1 枚用意する（すぐ出品の流れを試せるように）
    const demoUser = users[0];
    state.artworks.push({
      id: nextId("a"),
      sellerId: demoUser.id,
      title: "",
      description: "",
      tags: [],
      image: window.HEW_ART.svgArt(window.HEW_DATA.DEMO_DRAFT.seed, window.HEW_DATA.DEMO_DRAFT.artStyle),
      imageKind: "svg",
      drawSeconds: window.HEW_DATA.DEMO_DRAFT.drawSeconds,
      status: "draft",
      createdAt: iso(base - 25 * 60 * 1000),
      listedAt: null
    });

    // デモアカウントのお気に入りを少しだけ入れておく
    if (state.auctions[3]) {
      state.favWorks.push({ userId: demoUser.id, artworkId: state.auctions[3].artworkId, createdAt: iso(base - 60 * 1000) });
    }
    if (state.auctions[6]) {
      state.favWorks.push({ userId: demoUser.id, artworkId: state.auctions[6].artworkId, createdAt: iso(base - 120 * 1000) });
    }
    if (state.auctions[5]) {
      state.favAuctions.push({ userId: demoUser.id, auctionId: state.auctions[5].id, createdAt: iso(base - 90 * 1000) });
    }

    // 入札の履歴を 1 件ずつ実際のルールで処理して作る
    state.auctions.forEach((au, i) => {
      const w = window.HEW_DATA.WORKS[i];
      let rivals = state.users.filter((u) => u.id !== au.sellerId);
      if (!w.demoJoins) {
        const withoutDemo = rivals.filter((u) => u.id !== demoUser.id);
        if (withoutDemo.length) rivals = withoutDemo;
      }
      const step = Math.max(10, Math.round((au.startPrice * 0.16) / 10) * 10);
      const n = Math.min(w.rivals || 0, rivals.length);
      for (let k = 0; k < n; k++) {
        const bidder = rivals[(i + k) % rivals.length];
        const amount = au.startPrice + step * (k + 1);
        placeBid(au.id, amount, "manual", bidder.id, true);
      }
      if (w.autoRival && n > 0) {
        // 自動入札を仕掛けるのは出品者でもデモアカウントでもない相手にする
        const owner = rivals.length > 2 ? rivals[(i + 1) % rivals.length] : rivals[i % rivals.length];
        const challenger = rivals.length > 2 ? rivals[(i + 2) % rivals.length] : rivals[(i + 1) % rivals.length];
        setAutoBid(au.id, owner.id, au.currentPrice + step * 3, true);
        const cur = getAuction(au.id);
        placeBid(au.id, cur.currentPrice + step, "manual", challenger.id, false);
      }
      if (w.demoTops) {
        const cur = getAuction(au.id);
        placeBid(au.id, cur.currentPrice + step, "manual", demoUser.id, true);
      }
    });

    state.meta.seededAt = iso(base);
    closeExpired(true);
    return state;
  }

  /* ---------- 参照 ---------- */
  function user(id) { return state.users.find((u) => u.id === id) || null; }
  function getAuction(id) { return state.auctions.find((a) => a.id === id) || null; }
  function getArtwork(id) { return state.artworks.find((a) => a.id === id) || null; }
  function auctionOfArtwork(artworkId) {
    return state.auctions.find((a) => a.artworkId === artworkId) || null;
  }
  function bidsOf(auctionId) {
    return state.bids
      .filter((b) => b.auctionId === auctionId)
      .sort((a, b) => b.amount - a.amount || Date.parse(a.createdAt) - Date.parse(b.createdAt));
  }
  function topBid(auctionId) { return bidsOf(auctionId)[0] || null; }
  function bidCount(auctionId) { return state.bids.filter((b) => b.auctionId === auctionId).length; }
  function remainingMs(auction) { return Date.parse(auction.endsAt) - now(); }
  function autoBidOf(auctionId, userId) {
    return state.autoBids.find((x) => x.auctionId === auctionId && x.userId === userId && x.active) || null;
  }
  function currentUser() { return state.session.userId ? user(state.session.userId) : null; }
  function isFavWork(userId, artworkId) {
    return state.favWorks.some((f) => f.userId === userId && f.artworkId === artworkId);
  }
  function isFavAuction(userId, auctionId) {
    return state.favAuctions.some((f) => f.userId === userId && f.auctionId === auctionId);
  }
  function noticesOf(userId) {
    return state.notices
      .filter((n) => n.userId === userId)
      .sort((a, b) => Date.parse(b.createdAt) - Date.parse(a.createdAt));
  }
  function unreadCount(userId) { return noticesOf(userId).filter((n) => !n.read).length; }
  function ledgerOf(userId) {
    return state.tx
      .filter((t) => t.userId === userId)
      .sort((a, b) => Date.parse(b.createdAt) - Date.parse(a.createdAt));
  }
  function mailsOf(userId) {
    const u = user(userId);
    if (!u) return [];
    return state.mails
      .filter((m) => m.to === u.email)
      .sort((a, b) => Date.parse(b.createdAt) - Date.parse(a.createdAt));
  }
  function artworksOf(userId) { return state.artworks.filter((a) => a.sellerId === userId); }
  function draftsOf(userId) {
    return artworksOf(userId).filter((a) => a.status === "draft")
      .sort((a, b) => Date.parse(b.createdAt) - Date.parse(a.createdAt));
  }
  function listingsOf(userId) { return state.auctions.filter((a) => a.sellerId === userId); }

  /* 検索：公開作品のみ。複数タグは AND。 */
  function searchWorks(opts) {
    const o = opts || {};
    const tags = o.tags || [];
    let rows = state.artworks
      .filter((a) => a.status !== "draft")
      .map((a) => ({ artwork: a, auction: auctionOfArtwork(a.id) }))
      .filter((r) => r.auction);

    if (tags.length) {
      rows = rows.filter((r) => tags.every((t) => r.artwork.tags.indexOf(t) >= 0));
    }
    if (o.state === "active") rows = rows.filter((r) => r.auction.status === "active");
    if (o.state === "ended") rows = rows.filter((r) => r.auction.status === "closed");

    const sort = o.sort || "ending";
    rows.sort((x, y) => {
      if (sort === "new") return Date.parse(y.artwork.createdAt) - Date.parse(x.artwork.createdAt);
      if (sort === "price") return y.auction.currentPrice - x.auction.currentPrice;
      // 終了が近い順（開催中を先、終了済みは最後）
      const ax = x.auction.status === "active" ? 0 : 1;
      const ay = y.auction.status === "active" ? 0 : 1;
      if (ax !== ay) return ax - ay;
      return Date.parse(x.auction.endsAt) - Date.parse(y.auction.endsAt);
    });
    return rows;
  }

  /* ---------- 認証 ---------- */
  function register(input) {
    const username = (input.username || "").trim();
    const email = (input.email || "").trim().toLowerCase();
    const password = input.password || "";
    const confirm = input.confirm || "";
    if (!username || !email || !password) return { ok: false, message: "ユーザー名・メールアドレス・パスワードはすべて必須です。" };
    if (username.length > 20) return { ok: false, message: "ユーザー名は 20 文字までです。" };
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) return { ok: false, message: "メールアドレスの形式を確認してください。" };
    if (password.length < 8) return { ok: false, message: "パスワードは 8 文字以上にしてください。" };
    if (confirm !== "" && confirm !== password) return { ok: false, message: "確認用パスワードが一致しません。" };
    if (state.users.some((u) => u.username.toLowerCase() === username.toLowerCase())) return { ok: false, message: "このユーザー名はすでに使われています。" };
    if (state.users.some((u) => u.email === email)) return { ok: false, message: "このメールアドレスはすでに登録されています。" };

    const u = {
      id: nextId("u"),
      username: username,
      email: email,
      pw: enc(password),
      displayName: username,
      balance: 0,
      createdAt: iso(now())
    };
    state.users.push(u);
    state.bonus[u.id] = { signup: true, draw: false, list: false };
    credit(u.id, "signup", BONUS.signup, "登録ボーナス");
    state.session.userId = u.id;
    notify(u.id, "welcome", "ようこそ HEW へ", "登録ボーナス " + BONUS.signup + " pt を受け取りました。絵を描いて出品してみましょう。", {});
    persist();
    return { ok: true, user: u };
  }

  function login(email, password) {
    const e = (email || "").trim().toLowerCase();
    const u = state.users.find((x) => x.email === e);
    if (!u || u.pw !== enc(password || "")) return { ok: false, message: "メールアドレスまたはパスワードが違います。" };
    state.session.userId = u.id;
    persist();
    return { ok: true, user: u };
  }

  function logout() {
    state.session.userId = null;
    persist();
  }

  function updateDisplayName(name) {
    const u = currentUser();
    if (!u) return { ok: false, message: "ログインが必要です。" };
    const v = (name || "").trim();
    if (!v) return { ok: false, message: "表示名を入力してください。" };
    if (v.length > 24) return { ok: false, message: "表示名は 24 文字までです。" };
    u.displayName = v;
    persist();
    return { ok: true };
  }

  /* ---------- 作品・出品 ---------- */
  function saveDraft(input) {
    const u = currentUser();
    if (!u) return { ok: false, message: "ログインが必要です。" };
    const image = input.image || "";
    if (!/^data:image\/png;base64,/.test(image)) return { ok: false, message: "PNG の形式で保存できませんでした。もう一度お試しください。" };
    // 画像サイズの上限（未決事項の開発用既定値: 4MB）
    if (image.length > 5.5 * 1024 * 1024) return { ok: false, message: "画像が大きすぎます。画面を小さくして描き直してください。" };

    const art = {
      id: nextId("a"),
      sellerId: u.id,
      title: "",
      description: "",
      tags: [],
      image: image,
      imageKind: "png",
      drawSeconds: input.drawSeconds || 0,
      status: "draft",
      createdAt: iso(now()),
      listedAt: null,
      checksumHint: image.length
    };
    state.artworks.push(art);
    persist();
    return { ok: true, artwork: art };
  }

  function updateDraftInfo(artworkId, info) {
    const u = currentUser();
    const art = getArtwork(artworkId);
    if (!u || !art) return { ok: false, message: "作品が見つかりません。" };
    if (art.sellerId !== u.id) return { ok: false, message: "自分の下書きだけを編集できます。" };
    if (art.status !== "draft") return { ok: false, message: "出品済みの作品は編集できません。" };
    art.title = (info.title || "").trim();
    art.description = (info.description || "").trim();
    art.tags = uniq((info.tags || []).filter((t) => window.HEW_DATA.TAGS.indexOf(t) >= 0));
    persist();
    return { ok: true, artwork: art };
  }

  function publish(artworkId, info) {
    const u = currentUser();
    const art = getArtwork(artworkId);
    if (!u || !art) return { ok: false, message: "作品が見つかりません。" };
    if (art.sellerId !== u.id) return { ok: false, message: "自分の下書きだけを出品できます。" };
    if (art.status !== "draft") return { ok: false, message: "この作品はすでに出品されています。" };

    const title = (info.title || "").trim();
    const description = (info.description || "").trim();
    const tags = uniq((info.tags || []).filter((t) => window.HEW_DATA.TAGS.indexOf(t) >= 0));
    const startPrice = Number(info.startPrice);
    const endsAt = info.endsAt;

    if (!title) return { ok: false, message: "タイトルを入力してください。" };
    if (title.length > 60) return { ok: false, message: "タイトルは 60 文字までです。" };
    if (!Number.isFinite(startPrice) || startPrice < 0) return { ok: false, message: "開始価格は 0 以上の整数で入力してください。" };
    if (startPrice % 1 !== 0) return { ok: false, message: "開始価格は整数で入力してください。" };
    if (!tags.length) return { ok: false, message: "タグを 1 つ以上選んでください。" };
    const endMs = Date.parse(endsAt);
    if (!endsAt || !Number.isFinite(endMs)) return { ok: false, message: "終了日時を入力してください。" };
    if (endMs <= now() + 60 * 1000) return { ok: false, message: "終了日時は 1 分より先の時刻を指定してください。" };

    art.title = title;
    art.description = description;
    art.tags = tags;
    art.status = "listed";
    art.listedAt = iso(now());

    const au = {
      id: nextId("au"),
      artworkId: art.id,
      sellerId: u.id,
      startPrice: startPrice,
      currentPrice: startPrice,
      endsAt: iso(endMs),
      createdAt: iso(now()),
      status: "active",
      winnerBidId: null,
      finalPrice: null
    };
    state.auctions.push(au);
    persist();
    return { ok: true, artwork: art, auction: au };
  }

  /* ---------- 通知・メール ---------- */
  function notify(userId, kind, title, body, ref) {
    const n = {
      id: nextId("n"),
      userId: userId,
      kind: kind,
      title: title,
      body: body,
      artworkId: (ref && ref.artworkId) || null,
      auctionId: (ref && ref.auctionId) || null,
      read: false,
      createdAt: iso(now())
    };
    state.notices.push(n);

    const u = user(userId);
    if (u) {
      state.mails.push({
        id: nextId("m"),
        to: u.email,
        subject: "[HEW] " + title,
        body: body,
        status: "queued",       // 送信先 SMTP が未設定のため、実際には送信しない
        attempts: 0,
        sentAt: null,
        error: null,
        createdAt: iso(now())
      });
    }
    return n;
  }

  function markNoticeRead(id) {
    const n = state.notices.find((x) => x.id === id);
    if (n) { n.read = true; persist(); }
  }
  function markAllRead(userId) {
    noticesOf(userId).forEach((n) => { n.read = true; });
    persist();
  }

  /* ---------- 入札 ---------- */
  function placeBid(auctionId, amount, kind, userId, skipAuto) {
    const au = getAuction(auctionId);
    if (!au) return { ok: false, message: "オークションが見つかりません。" };
    const uid = userId || (currentUser() && currentUser().id);
    if (!uid) return { ok: false, message: "ログインが必要です。" };
    const amt = Math.floor(Number(amount));

    if (au.status !== "active") return { ok: false, message: "このオークションはすでに終了しています。" };
    if (remainingMs(au) <= 0) { closeExpired(); return { ok: false, message: "終了日時を過ぎたため、入札を受け付けられません。" }; }
    if (au.sellerId === uid) return { ok: false, message: "自分の出品には入札できません。" };
    if (!Number.isFinite(amt) || amt <= 0) return { ok: false, message: "入札額は 1 pt 以上の整数で入力してください。" };
    if (amt % 1 !== 0) return { ok: false, message: "入札額は整数で入力してください。" };

    const prev = topBid(au.id);
    const floor = Math.max(au.currentPrice, prev ? prev.amount : 0);
    if (amt <= floor) {
      return { ok: false, message: "現在価格 " + floor.toLocaleString("ja-JP") + " pt より高い金額を入力してください。" };
    }
    const me = user(uid);
    const mineFrozen = prev && prev.userId === uid ? prev.amount : 0;
    const available = me.balance + mineFrozen;
    if (amt > available) {
      return {
        ok: false,
        message: "ポイントが足りません。必要 " + amt.toLocaleString("ja-JP") + " pt / 使える " + available.toLocaleString("ja-JP") + " pt",
        needsPoints: true
      };
    }

    /* --- 受理：入札履歴・残高・返却・現在価格をまとめて処理 --- */
    const bid = {
      id: nextId("b"),
      auctionId: au.id,
      userId: uid,
      amount: amt,
      kind: kind || "manual",
      createdAt: iso(now())
    };
    state.bids.push(bid);
    credit(uid, "bid", -amt, "入札（" + artworkLabel(au) + "）");

    if (prev && prev.userId !== uid) {
      credit(prev.userId, "refund", prev.amount, "高値更新の返却（" + artworkLabel(au) + "）");
      notify(prev.userId, "outbid", "最高額を更新されました",
        artworkLabel(au) + " の最高額が " + amt.toLocaleString("ja-JP") + " pt になりました。入札した " + prev.amount.toLocaleString("ja-JP") + " pt は返却されました。",
        { artworkId: au.artworkId, auctionId: au.id });
    }
    au.currentPrice = amt;
    notify(uid, "bid", "入札を受け付けました",
      artworkLabel(au) + " に " + amt.toLocaleString("ja-JP") + " pt で入札しました。現在価格は " + amt.toLocaleString("ja-JP") + " pt です。",
      { artworkId: au.artworkId, auctionId: au.id });

    persist();
    if (!skipAuto) resolveAutoBids(au.id);
    persist();
    return { ok: true, bid: bid, auction: getAuction(au.id) };
  }

  function artworkLabel(au) {
    const art = getArtwork(au.artworkId);
    return art ? "「" + (art.title || "無題") + "」" : "作品";
  }

  /* 自動入札：他人の入札に対して、上限額の範囲で上乗せする */
  function resolveAutoBids(auctionId) {
    let guard = 0;
    while (guard++ < 40) {
      const au = getAuction(auctionId);
      if (!au || au.status !== "active") return;
      const top = topBid(auctionId);
      if (!top) return;
      const candidates = state.autoBids
        .filter((x) => x.auctionId === auctionId && x.active && x.userId !== top.userId && x.maxAmount > top.amount)
        .sort((a, b) => b.maxAmount - a.maxAmount || Date.parse(a.createdAt) - Date.parse(b.createdAt));
      const c = candidates[0];
      if (!c) return;
      const bidder = user(c.userId);
      const available = bidder ? bidder.balance : 0;
      let target = Math.min(c.maxAmount, top.amount + INCREMENT);
      if (available < target) target = Math.min(c.maxAmount, available);
      if (target <= top.amount) {
        c.active = false;                     // 上限または残高に届かないので降りる
        continue;
      }
      const res = placeBid(auctionId, target, "auto", c.userId, true);
      if (!res.ok) { c.active = false; return; }
    }
  }

  function setAutoBid(auctionId, userId, maxAmount, skipResolve) {
    const au = getAuction(auctionId);
    if (!au) return { ok: false, message: "オークションが見つかりません。" };
    const uid = userId || (currentUser() && currentUser().id);
    if (!uid) return { ok: false, message: "ログインが必要です。" };
    const max = Math.floor(Number(maxAmount));
    if (au.status !== "active") return { ok: false, message: "終了したオークションには自動入札を設定できません。" };
    if (remainingMs(au) <= 0) return { ok: false, message: "終了日時を過ぎています。" };
    if (au.sellerId === uid) return { ok: false, message: "自分の出品には自動入札を設定できません。" };
    if (!Number.isFinite(max) || max <= au.currentPrice) {
      return { ok: false, message: "上限額は現在価格 " + au.currentPrice.toLocaleString("ja-JP") + " pt より大きい金額にしてください。" };
    }
    const me = user(uid);
    if (max > me.balance + (topBid(au.id) && topBid(au.id).userId === uid ? topBid(au.id).amount : 0)) {
      return { ok: false, message: "上限額が保有ポイントを超えています。上限は " + me.balance.toLocaleString("ja-JP") + " pt までです。" };
    }
    if (autoBidOf(au.id, uid)) return { ok: false, message: "この作品にはすでに自動入札を設定しています。" };

    const row = {
      id: nextId("ab"),
      auctionId: au.id,
      userId: uid,
      maxAmount: max,
      active: true,
      createdAt: iso(now())
    };
    state.autoBids.push(row);
    notify(uid, "auto", "自動入札を設定しました",
      artworkLabel(au) + " に上限 " + max.toLocaleString("ja-JP") + " pt の自動入札を設定しました。他の人が入札すると、この範囲で自動的に競り上がります。",
      { artworkId: au.artworkId, auctionId: au.id });
    persist();
    if (!skipResolve) { resolveAutoBids(au.id); persist(); }
    return { ok: true, auto: row };
  }

  /* ---------- 終了・落札 ---------- */
  function closeExpired(quiet) {
    let changed = false;
    state.auctions.forEach((au) => {
      if (au.status !== "active") return;
      if (remainingMs(au) > 0) return;
      const top = topBid(au.id);
      au.status = "closed";
      state.autoBids.forEach((x) => { if (x.auctionId === au.id) x.active = false; });
      if (top) {
        au.winnerBidId = top.id;
        au.finalPrice = top.amount;
        notify(top.userId, "won", "落札しました",
          artworkLabel(au) + " を " + top.amount.toLocaleString("ja-JP") + " pt で落札しました。落札額は入札時に差し引かれているため、追加の引き落としはありません。",
          { artworkId: au.artworkId, auctionId: au.id });
        notify(au.sellerId, "sold", "落札されました",
          artworkLabel(au) + " が " + top.amount.toLocaleString("ja-JP") + " pt で落札されました。",
          { artworkId: au.artworkId, auctionId: au.id });
      } else {
        au.winnerBidId = null;
        au.finalPrice = null;
        notify(au.sellerId, "unsold", "入札がないまま終了しました",
          artworkLabel(au) + " は入札がないまま終了しました。Ver0.5 では再出品できません。",
          { artworkId: au.artworkId, auctionId: au.id });
      }
      changed = true;
      if (!quiet) console.info("オークションを終了しました:", au.id);
    });
    if (changed) persist();
    return changed;
  }

  /* ---------- お気に入り ---------- */
  function toggleFavWork(artworkId) {
    const u = currentUser();
    if (!u) return { ok: false, message: "お気に入りの登録にはログインが必要です。" };
    const i = state.favWorks.findIndex((f) => f.userId === u.id && f.artworkId === artworkId);
    if (i >= 0) { state.favWorks.splice(i, 1); persist(); return { ok: true, on: false, message: "作品のお気に入りを解除しました。" }; }
    state.favWorks.push({ userId: u.id, artworkId: artworkId, createdAt: iso(now()) });
    persist();
    return { ok: true, on: true, message: "作品をお気に入りに登録しました。" };
  }

  function toggleFavAuction(auctionId) {
    const u = currentUser();
    if (!u) return { ok: false, message: "お気に入りの登録にはログインが必要です。" };
    const i = state.favAuctions.findIndex((f) => f.userId === u.id && f.auctionId === auctionId);
    if (i >= 0) { state.favAuctions.splice(i, 1); persist(); return { ok: true, on: false, message: "オークションのお気に入りを解除しました。" }; }
    state.favAuctions.push({ userId: u.id, auctionId: auctionId, createdAt: iso(now()) });
    persist();
    return { ok: true, on: true, message: "オークションをお気に入りに登録しました。" };
  }

  function favWorksOf(userId) {
    return state.favWorks
      .filter((f) => f.userId === userId)
      .map((f) => getArtwork(f.artworkId))
      .filter(Boolean);
  }
  function favAuctionsOf(userId) {
    return state.favAuctions
      .filter((f) => f.userId === userId)
      .map((f) => getAuction(f.auctionId))
      .filter(Boolean);
  }

  /* ---------- ボーナスポイント ---------- */
  function bonusItems(userId) {
    const b = state.bonus[userId] || { signup: false, draw: false, list: false };
    const arts = artworksOf(userId);
    return [
      { key: "signup", label: "ユーザー登録", amount: BONUS.signup, done: true, granted: !!b.signup, hint: "登録した時点で付与します。" },
      { key: "draw", label: "はじめて絵を描く", amount: BONUS.draw, done: arts.length > 0, granted: !!b.draw, hint: "下書きを 1 件保存すると受け取れます。" },
      { key: "list", label: "はじめて出品する", amount: BONUS.list, done: listingsOf(userId).length > 0, granted: !!b.list, hint: "作品を 1 件出品すると受け取れます。" }
    ];
  }

  function claimBonus(key) {
    const u = currentUser();
    if (!u) return { ok: false, message: "ログインが必要です。" };
    const item = bonusItems(u.id).find((i) => i.key === key);
    if (!item) return { ok: false, message: "対象のボーナスが見つかりません。" };
    if (item.granted) return { ok: false, message: "すでに受け取り済みです。" };
    if (!item.done) return { ok: false, message: "条件を満たしていません。" };
    state.bonus[u.id][key] = true;
    credit(u.id, "bonus", item.amount, "ボーナスポイント（" + item.label + "）");
    notify(u.id, "bonus", "ボーナスポイントを受け取りました",
      item.label + " のボーナス " + item.amount + " pt を残高に反映しました。", {});
    persist();
    return { ok: true, amount: item.amount };
  }

  /* ---------- 公開API ---------- */
  const api = {
    INCREMENT: INCREMENT,
    BONUS: BONUS,
    init: function () {
      if (state) return state;
      state = load();
      if (!state) buildSeed();
      closeExpired(true);
      return state;
    },
    reset: function () {
      try { localStorage.removeItem(KEY); } catch (e) { /* 無視 */ }
      memoryOnly = false;
      state = buildSeed();
      persist();
      return state;
    },
    dump: function () { return state; },
    isMemoryOnly: function () { return memoryOnly; },

    currentUser: currentUser,
    user: user,
    users: function () { return state.users.slice(); },
    register: register,
    login: login,
    logout: logout,
    updateDisplayName: updateDisplayName,

    tags: function () { return window.HEW_DATA.TAGS.slice(); },
    searchWorks: searchWorks,
    getArtwork: getArtwork,
    getAuction: getAuction,
    auctionOfArtwork: auctionOfArtwork,
    bidsOf: bidsOf,
    topBid: topBid,
    bidCount: bidCount,
    remainingMs: remainingMs,
    autoBidOf: autoBidOf,
    draftsOf: draftsOf,
    listingsOf: listingsOf,
    artworksOf: artworksOf,

    saveDraft: saveDraft,
    updateDraftInfo: updateDraftInfo,
    publish: publish,

    placeBid: placeBid,
    setAutoBid: setAutoBid,
    closeExpired: closeExpired,

    toggleFavWork: toggleFavWork,
    toggleFavAuction: toggleFavAuction,
    isFavWork: isFavWork,
    isFavAuction: isFavAuction,
    favWorksOf: favWorksOf,
    favAuctionsOf: favAuctionsOf,

    noticesOf: noticesOf,
    unreadCount: unreadCount,
    markNoticeRead: markNoticeRead,
    markAllRead: markAllRead,
    mailsOf: mailsOf,
    ledgerOf: ledgerOf,
    credit: credit,

    bonusItems: bonusItems,
    claimBonus: claimBonus
  };

  window.HEW_STORE = api;
})();
