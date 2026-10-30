/* ============================================================
   ui.js — 画面の組み立てと操作
   ハッシュ ルーティング + 1 つの委譲リスナーで動かす。
   1 秒ごとの tick は「生きている数字」だけを書き換える。
   ============================================================ */
(function () {
  "use strict";

  const S = window.HEW_STORE;
  const screenEl = document.getElementById("screen");
  const railEl = document.getElementById("rail-inner");
  const toastRegion = document.getElementById("toast-region");
  const dialogRoot = document.getElementById("dialog-root");

  let mounted = null;      // 現在の画面インスタンス
  let lastFocus = null;

  /* ---------- 文と数字 ---------- */
  function esc(v) {
    return String(v === null || v === undefined ? "" : v).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  const jstFull = new Intl.DateTimeFormat("ja-JP", {
    timeZone: "Asia/Tokyo", year: "numeric", month: "2-digit", day: "2-digit",
    hour: "2-digit", minute: "2-digit", hour12: false
  });
  const jstShort = new Intl.DateTimeFormat("ja-JP", {
    timeZone: "Asia/Tokyo", month: "2-digit", day: "2-digit",
    hour: "2-digit", minute: "2-digit", hour12: false
  });

  function fmtFull(isoStr) { return jstFull.format(new Date(isoStr)); }
  function fmtShort(isoStr) { return jstShort.format(new Date(isoStr)); }
  function fmtPt(n) { return Number(n || 0).toLocaleString("ja-JP"); }
  function pct(v) { return Math.max(0, Math.min(100, v)) + "%"; }

  function remainText(ms) {
    if (ms <= 0) return "終了";
    const s = Math.floor(ms / 1000);
    const d = Math.floor(s / 86400);
    const h = Math.floor((s % 86400) / 3600);
    const m = Math.floor((s % 3600) / 60);
    const sec = s % 60;
    if (d > 0) return d + "日 " + h + "時間";
    if (h > 0) return h + "時間 " + String(m).padStart(2, "0") + "分";
    return String(m).padStart(2, "0") + ":" + String(sec).padStart(2, "0");
  }

  function clockText(ms) {
    if (ms <= 0) return "00:00";
    const s = Math.ceil(ms / 1000);
    const m = Math.floor(s / 60);
    const sec = s % 60;
    if (m >= 60) return Math.floor(m / 60) + ":" + String(m % 60).padStart(2, "0") + ":" + String(sec).padStart(2, "0");
    return String(m).padStart(2, "0") + ":" + String(sec).padStart(2, "0");
  }

  function durationLabel(sec) {
    if (sec === 10) return "10秒";
    if (sec === 30) return "30秒";
    if (sec === 60) return "1分";
    if (sec === 300) return "5分";
    return sec + "秒";
  }

  function statusBadge(auction) {
    if (!auction) return "";
    if (auction.status === "active") return '<span class="badge badge-live">開催中</span>';
    if (auction.finalPrice === null || auction.finalPrice === undefined) return '<span class="badge badge-soon">落札者なし</span>';
    return '<span class="badge">落札済み</span>';
  }

  /* 開催中は残り時間、終了後は終了日時を出す */
  function cdText(au) {
    if (!au) return "—";
    return au.status === "active" ? remainText(S.remainingMs(au)) : fmtShort(au.endsAt);
  }

  function holderName(userId) {
    const u = S.user(userId);
    return u ? u.displayName : "退会した利用者";
  }

  /* ---------- トースト・ダイアログ ---------- */
  function toast(message, kind) {
    const el = document.createElement("div");
    el.className = "toast" + (kind ? " is-" + kind : "");
    el.setAttribute("role", kind === "error" ? "alert" : "status");
    el.textContent = message;
    toastRegion.appendChild(el);
    window.setTimeout(function () {
      el.style.transition = "opacity .25s ease";
      el.style.opacity = "0";
      window.setTimeout(function () { el.remove(); }, 260);
    }, kind === "error" ? 5200 : 3600);
  }

  function closeDialog() {
    dialogRoot.innerHTML = "";
    if (lastFocus && lastFocus.focus) lastFocus.focus();
    lastFocus = null;
  }

  function openDialog(opts) {
    lastFocus = document.activeElement;
    const actions = (opts.actions || []).map(function (a, i) {
      return '<button type="button" class="btn ' + (a.kind === "primary" ? "btn-primary" : a.kind === "live" ? "btn-live" : "") +
        '" data-dlg="' + i + '">' + esc(a.label) + "</button>";
    }).join("");

    dialogRoot.innerHTML =
      '<div class="dialog-backdrop" data-dlg-close="1">' +
        '<div class="dialog" role="dialog" aria-modal="true" aria-labelledby="dlg-title">' +
          '<h2 class="h2" id="dlg-title">' + esc(opts.title) + "</h2>" +
          '<div class="dialog-body">' + (opts.body || "") + "</div>" +
          '<div class="btn-row" style="margin-top:18px">' + actions + "</div>" +
        "</div>" +
      "</div>";

    const panel = dialogRoot.querySelector(".dialog");
    dialogRoot.querySelectorAll("[data-dlg]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        const a = opts.actions[Number(btn.dataset.dlg)];
        closeDialog();
        if (a && a.onSelect) a.onSelect();
      });
    });
    dialogRoot.querySelector("[data-dlg-close]").addEventListener("mousedown", function (e) {
      if (e.target === e.currentTarget) { closeDialog(); if (opts.onDismiss) opts.onDismiss(); }
    });
    panel.addEventListener("keydown", function (e) {
      if (e.key === "Escape") { closeDialog(); if (opts.onDismiss) opts.onDismiss(); }
      if (e.key === "Tab") {
        const f = panel.querySelectorAll("button, [href], input, select, textarea");
        if (!f.length) return;
        const first = f[0], last = f[f.length - 1];
        if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
        else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
      }
    });
    const focusTarget = panel.querySelector("input, textarea, select") || panel.querySelector("button");
    if (focusTarget) focusTarget.focus();
  }

  /* ---------- ヘッダ ---------- */
  function currentPath() {
    const raw = (location.hash || "#/").replace(/^#/, "");
    return raw.split("?")[0] || "/";
  }

  function renderRail() {
    const u = S.currentUser();
    const path = currentPath();
    const link = function (href, label, extra) {
      return '<a class="rail-link" href="' + href + '"' +
        (path === href.replace("#", "") ? ' aria-current="page"' : "") + ">" + label + (extra || "") + "</a>";
    };

    let nav = link("#/", "作品を探す") + link("#/draw", "絵を描く");
    if (u) {
      const unread = S.unreadCount(u.id);
      nav += link("#/bonus", "ボーナス");
      nav += link("#/notices", "通知", unread ? '<span class="count-dot">' + unread + "</span>" : "");
      nav += link("#/account", "アカウント");
      nav += '<a class="wallet-chip" href="#/account"><span class="pt">保有</span>' + fmtPt(u.balance) + " pt</a>";
      nav += '<button type="button" class="rail-link" data-act="logout">ログアウト</button>';
    } else {
      nav += link("#/login", "ログイン");
      nav += '<a class="btn btn-primary btn-sm" href="#/register">新規登録</a>';
    }

    railEl.innerHTML =
      '<a class="brand" href="#/">' +
        '<span class="brand-mark" aria-hidden="true"></span>' +
        '<span class="brand-word">HEW</span>' +
        '<span class="brand-sub">時間内に描く<br>絵のオークション</span>' +
      "</a>" +
      '<nav class="rail-nav" aria-label="主要メニュー">' + nav + "</nav>";
  }

  /* ---------- 部品 ---------- */
  function ticketCard(row, opts) {
    const art = row.artwork;
    const au = row.auction;
    const o = opts || {};
    const active = au && au.status === "active";
    const priceValue = au
      ? (au.finalPrice !== null && au.finalPrice !== undefined ? au.finalPrice : au.currentPrice)
      : null;
    const priceLabel = au && au.status === "closed"
      ? (au.finalPrice === null ? "入札なし" : "落札額")
      : "現在価格";

    return '<article class="ticket' + (o.rise ? " rise" : "") + '">' +
      '<a class="ticket-link" href="#/work/' + art.id + '">' +
        '<div class="ticket-plate">' +
          '<span class="ticket-hole" aria-hidden="true"></span>' +
          '<img src="' + art.image + '" alt="' + esc(art.title || "無題の下書き") + ' の絵" loading="lazy">' +
        "</div>" +
        '<div class="ticket-body">' +
          '<div class="stamp-row">' + art.tags.map(function (t) {
            return '<span class="stamp">' + esc(t) + "</span>";
          }).join("") + "</div>" +
          '<h3 class="ticket-title">' + esc(art.title || "無題") + "</h3>" +
          '<p class="small muted">作者 ' + esc(holderName(art.sellerId)) + " · " + durationLabel(art.drawSeconds) + "で描画</p>" +
          '<div class="ticket-foot">' +
            '<div><span class="label">' + (active ? "残り" : "終了") + "</span>" +
              '<span class="data" data-cd="' + (au ? au.id : "") + '">' + cdText(au) + "</span>" +
            "</div>" +
            '<div class="price-tag' + (active ? "" : " is-quiet") + '">' +
              '<span class="pt-label">' + priceLabel + "</span>" +
              '<span class="pt-value">' + (priceValue === null ? "—" : fmtPt(priceValue) + " pt") + "</span>" +
            "</div>" +
          "</div>" +
        "</div>" +
      "</a>" +
    "</article>";
  }

  function strokeTrack(auction) {
    const total = Date.parse(auction.endsAt) - Date.parse(auction.createdAt);
    const remain = S.remainingMs(auction);
    const elapsed = Math.max(0, Math.min(total, total - remain));
    const w = total > 0 ? (elapsed / total) * 100 : 100;
    const urgent = auction.status === "active" && remain < 5 * 60 * 1000;
    return '<div class="stroke-track' + (urgent ? " is-urgent" : "") + '" data-stroke="' + auction.id + '">' +
      '<span style="width:' + pct(w) + '"></span></div>';
  }

  /* ---------- 空の画面 ---------- */
  function emptyState(title, body, actionHtml) {
    return '<div class="empty-state">' +
      '<h3 class="h3">' + esc(title) + "</h3>" +
      "<p>" + body + "</p>" +
      (actionHtml || "") +
    "</div>";
  }

  /* ============================================================
     画面：ホーム（作品を探す）
     ============================================================ */
  function viewHome(query) {
    const tags = (query.tags ? query.tags.split(",") : []).filter(Boolean);
    const sort = query.sort || "ending";
    const stateFilter = query.state || "all";

    const rows = S.searchWorks({ tags: tags, sort: sort, state: stateFilter });
    const activeRows = S.searchWorks({ tags: [], sort: "ending", state: "active" });
    const all = S.searchWorks({ tags: [], sort: "new", state: "all" });
    const spotlight = activeRows[0] || null;

    const heroSide = spotlight
      ? '<div class="panel live-plate tombo-frame rise rise-1">' +
          '<div class="panel-head">' +
            '<p class="label" style="margin:0">いま競り中の一枚</p>' +
            statusBadge(spotlight.auction) +
          "</div>" +
          '<a class="ticket-link" href="#/work/' + spotlight.artwork.id + '">' +
            '<div class="ticket-plate"><img src="' + spotlight.artwork.image + '" alt="' +
              esc(spotlight.artwork.title) + ' の絵"></div>' +
          "</a>" +
          '<div class="live-meta">' +
            '<div>' +
              '<p class="h3">' + esc(spotlight.artwork.title) + "</p>" +
              '<p class="small muted">作者 ' + esc(holderName(spotlight.artwork.sellerId)) + "</p>" +
            "</div>" +
            '<div class="price-tag">' +
              '<span class="pt-label">現在価格</span>' +
              '<span class="pt-value">' + fmtPt(spotlight.auction.currentPrice) + " pt</span>" +
            "</div>" +
          "</div>" +
          '<div class="live-clock">' +
            '<span class="clock-label">終了まで</span>' +
            '<span class="clock-value mono" data-cd="' + spotlight.auction.id + '">' +
              remainText(S.remainingMs(spotlight.auction)) + "</span>" +
          "</div>" +
          strokeTrack(spotlight.auction) +
          '<div class="btn-row" style="margin-top:14px">' +
            '<a class="btn btn-live" href="#/work/' + spotlight.artwork.id + '">入札する</a>' +
            '<a class="btn btn-ghost" href="#/account?tab=fav-auctions">お気に入りの一覧</a>' +
          "</div>" +
        "</div>"
      : '<div class="panel rise rise-1">' +
          '<div class="panel-head"><p class="label" style="margin:0">いま競り中の一枚</p>' +
            '<span class="badge badge-soon">開催中なし</span>' +
          "</div>" +
          emptyState("開催中のオークションはありません",
            "だれかが出品すると、ここにいちばん早く終わる作品が出ます。自分で描いて出品することもできます。",
            '<a class="btn btn-primary" href="#/draw">絵を描く</a>') +
        "</div>";

    const stampRow = S.tags().map(function (t) {
      const on = tags.indexOf(t) >= 0;
      return '<button type="button" class="stamp" data-act="tag" data-tag="' + esc(t) + '" aria-pressed="' + on + '">' + esc(t) + "</button>";
    }).join("");

    const sortOptions = [
      ["ending", "終了が近い順"],
      ["new", "新着順"],
      ["price", "現在価格が高い順"]
    ].map(function (o) {
      return '<option value="' + o[0] + '"' + (sort === o[0] ? " selected" : "") + ">" + o[1] + "</option>";
    }).join("");

    const stateOptions = [
      ["all", "すべて"],
      ["active", "開催中のみ"],
      ["ended", "終了済みのみ"]
    ].map(function (o) {
      return '<option value="' + o[0] + '"' + (stateFilter === o[0] ? " selected" : "") + ">" + o[1] + "</option>";
    }).join("");

    const body = rows.length
      ? '<div class="grid-plates">' + rows.map(function (r, i) {
          return ticketCard(r, { rise: i < 6 });
        }).join("") + "</div>"
      : emptyState("条件に合う作品がありません",
          tags.length
            ? "選んだタグ「" + esc(tags.join("・")) + "」をすべて持つ作品は見つかりませんでした。タグを減らすか、絞り込みを解除してください。"
            : "まだ出品された作品がありません。最初の一枚を描いて出品してみましょう。",
          '<div class="btn-row"><button type="button" class="btn" data-act="clear-tags">絞り込みを解除する</button>' +
          '<a class="btn btn-primary" href="#/draw">絵を描く</a></div>');

    return '<div class="wrap">' +
      '<section class="hero">' +
        '<div class="hero-copy">' +
          '<p class="eyebrow rise">HEW · 要件定義書 Ver 0.5</p>' +
          '<h1 class="rise rise-1">時間のなかで描いた<br class="hero-br">一枚を、競りにかける。</h1>' +
          '<div class="hero-stroke rise rise-1" aria-hidden="true"><span></span></div>' +
          '<p class="lede rise rise-2">10秒・30秒・1分・5分。選んだ時間で描き、下書きとして保存し、好きなときに出品します。入札はポイントで行い、終了日時のいちばん高い入札が落とします。</p>' +
          '<div class="btn-row rise rise-2">' +
            '<a class="btn btn-primary" href="#/draw">絵を描く</a>' +
            '<button type="button" class="btn" data-act="jump" data-target="catalogue">出品中の作品を見る</button>' +
          "</div>" +
          '<div class="hero-facts rise rise-3">' +
            "<span>開催中 <b>" + activeRows.length + "</b> 件</span>" +
            "<span>出品作品 <b>" + all.length + "</b> 件</span>" +
            "<span>制限時間 <b>10秒 / 30秒 / 1分 / 5分</b></span>" +
            "<span>入札 <b>ポイント制</b></span>" +
          "</div>" +
        "</div>" +
        heroSide +
      "</section>" +

      '<section class="section" id="catalogue">' +
        '<div class="section-head">' +
          '<h2 class="h2">出品中の作品から一枚を探す</h2>' +
          '<span class="section-count">' + rows.length + " 件表示 / 全 " + all.length + " 件</span>" +
        "</div>" +
        '<div class="filter-bar">' +
          '<div class="filter-block">' +
            '<span class="label">タグで絞り込む（選んだタグをすべて含む作品を表示）</span>' +
            '<div class="stamp-row">' + stampRow + "</div>" +
          "</div>" +
          '<div class="filter-block">' +
            '<label class="label" for="f-sort">並び順</label>' +
            '<select class="select" id="f-sort" data-act="sort">' + sortOptions + "</select>" +
          "</div>" +
          '<div class="filter-block">' +
            '<label class="label" for="f-state">状態</label>' +
            '<select class="select" id="f-state" data-act="state">' + stateOptions + "</select>" +
          "</div>" +
        "</div>" +
        body +
      "</section>" +
    "</div>";
  }

  /* ============================================================
     画面：商品詳細（画面内で入札）
     ============================================================ */
  function viewWork(artworkId) {
    const art = S.getArtwork(artworkId);
    if (!art || art.status === "draft") {
      return notFound("作品が見つかりません", "この作品は非公開か、削除されています。下書きは作者だけが閲覧できます。");
    }
    const au = S.auctionOfArtwork(art.id);
    const me = S.currentUser();
    const isSeller = me && me.id === art.sellerId;
    const top = au ? S.topBid(au.id) : null;
    const count = au ? S.bidCount(au.id) : 0;
    const active = au && au.status === "active" && S.remainingMs(au) > 0;

    const price = au ? (au.finalPrice !== null && au.finalPrice !== undefined ? au.finalPrice : au.currentPrice) : 0;
    const priceLabel = au && au.status === "closed"
      ? (au.finalPrice === null ? "開始価格（入札なし）" : "落札額")
      : "現在価格";

    /* 入札フォーム */
    let bidBlock = "";
    if (!au) {
      bidBlock = '<p class="muted small">この作品にはオークションが設定されていません。</p>';
    } else if (!active) {
      bidBlock = '<div class="notice-ink">' +
        "<p><b>このオークションは終了しました。</b></p>" +
        "<p class=\"small\">" + (au.finalPrice === null
          ? "入札がなかったため、落札者なしで終了しました。Ver0.5 では再出品できません。"
          : "落札者 " + esc(holderName(top ? top.userId : "")) + " / 確定額 " + fmtPt(au.finalPrice) + " pt") + "</p>" +
        "</div>";
      if (au.finalPrice !== null) {
        bidBlock += '<p class="help">落札額は入札の時点で差し引かれているため、落札確定による追加の引き落としはありません。</p>';
      }
    } else if (!me) {
      bidBlock = '<div class="notice-ink">' +
        "<p><b>入札にはログインが必要です。</b></p>" +
        '<p class="small">ゲストは公開作品の閲覧とタグ検索のみ利用できます。</p>' +
        '<div class="btn-row" style="margin-top:10px">' +
          '<a class="btn btn-primary" href="#/login">ログインする</a>' +
          '<a class="btn btn-ghost" href="#/register">新規登録</a>' +
        "</div></div>";
    } else if (isSeller) {
      bidBlock = '<div class="notice-ink"><p><b>自分の出品には入札できません。</b></p>' +
        '<p class="small">ほかの利用者の入札を待つか、アカウント画面から出品内容を確認してください。</p></div>';
    } else {
      const mineFrozen = top && top.userId === me.id ? top.amount : 0;
      const available = me.balance + mineFrozen;
      const minNext = au.currentPrice + 1;
      const quick = [10, 50, 100, 500].map(function (add) {
        return '<button type="button" class="btn btn-ghost btn-sm" data-act="bid-quick" data-add="' + add + '">+' +
          fmtPt(add) + "</button>";
      }).join("");
      bidBlock =
        '<form id="bid-form" data-auction="' + au.id + '" novalidate>' +
          '<div class="field">' +
            '<label class="label" for="bid-amount">入札額（pt）</label>' +
            '<input class="input input-data" type="number" id="bid-amount" name="amount" min="' + minNext +
              '" step="1" inputmode="numeric" value="' + minNext + '" required>' +
            '<div class="btn-row" style="margin-top:8px">' + quick + "</div>" +
            '<p class="help">現在価格 ' + fmtPt(au.currentPrice) + " pt より大きい金額を入力してください。" +
              "開始価格は " + fmtPt(au.startPrice) + " pt、あなたが使えるのは " + fmtPt(available) + " pt です。</p>" +
          "</div>" +
          '<div id="bid-feedback" class="small" role="status" aria-live="polite"></div>' +
          '<div class="btn-row"><button type="submit" class="btn btn-live">この金額で入札する</button>' +
            '<a class="btn btn-ghost btn-sm" href="#/charge">ポイントを増やす</a></div>' +
        "</form>" +
        '<hr class="rule" style="margin:18px 0">' +
        '<form id="auto-form" data-auction="' + au.id + '" novalidate>' +
          '<div class="field">' +
            '<label class="label" for="auto-max">自動入札の上限額（pt）</label>' +
            '<input class="input input-data" type="number" id="auto-max" name="max" min="' + (au.currentPrice + 1) +
              '" step="1" inputmode="numeric" placeholder="例: ' + (au.currentPrice + 200) + '">' +
            '<p class="help">他の人が入札すると、上限額の範囲で ' + S.INCREMENT +
              " pt ずつ自動的に競り上がります。上限額が同じときは、先に設定した人の入札が残ります。</p>" +
          "</div>" +
          '<div id="auto-feedback" class="small" role="status" aria-live="polite"></div>' +
          '<div class="btn-row"><button type="submit" class="btn">自動入札を設定する</button></div>' +
        "</form>";
    }

    const myAuto = me && au ? S.autoBidOf(au.id, me.id) : null;
    const autoNote = myAuto
      ? '<div class="status-line"><span class="badge badge-live">自動入札 設定済み</span>' +
        '<span class="mono">上限 ' + fmtPt(myAuto.maxAmount) + " pt · " + fmtShort(myAuto.createdAt) + " 設定</span></div>"
      : "";

    const historyRows = au && count
      ? S.bidsOf(au.id).map(function (b) {
          const mine = me && b.userId === me.id;
          return '<div class="ledger-row' + (mine ? " is-me" : "") + '" style="--ledger-cols:96px 1fr 108px">' +
            '<span class="mono faint">' + fmtShort(b.createdAt) + "</span>" +
            "<span>" + esc(holderName(b.userId)) + (mine ? "（あなた）" : "") +
              (b.kind === "auto" ? ' <span class="badge">自動</span>' : "") + "</span>" +
            '<span class="ledger-amount" style="text-align:right">' + fmtPt(b.amount) + " pt</span>" +
          "</div>";
        }).join("")
      : '<div class="ledger-empty">まだ入札はありません。開始価格 ' + fmtPt(au ? au.startPrice : 0) + " pt から受け付けます。</div>";

    const favPressedWork = me ? S.isFavWork(me.id, art.id) : false;
    const favPressedAu = me && au ? S.isFavAuction(me.id, au.id) : false;

    return '<div class="wrap">' +
      '<div class="crumbs"><a href="#/">作品を探す</a> / 商品詳細</div>' +
      '<div class="work-head">' +
        "<div>" +
          '<h1 class="work-title">' + esc(art.title || "無題") + "</h1>" +
          '<p class="muted small">作者 ' + esc(holderName(art.sellerId)) + " · " + durationLabel(art.drawSeconds) +
            "で描画 · 出品 " + fmtFull(art.listedAt || art.createdAt) + "（日本時間）</p>" +
        "</div>" +
        '<div class="btn-row">' + statusBadge(au) +
          (me ? '<button type="button" class="btn btn-sm" data-act="fav-work" data-id="' + art.id +
            '" aria-pressed="' + favPressedWork + '">' + (favPressedWork ? "★ 作品のお気に入り済み" : "☆ 作品をお気に入り") + "</button>" : "") +
          (me && au ? '<button type="button" class="btn btn-sm" data-act="fav-auction" data-id="' + au.id +
            '" aria-pressed="' + favPressedAu + '">' + (favPressedAu ? "★ オークションお気に入り済み" : "☆ オークションをお気に入り") + "</button>" : "") +
        "</div>" +
      "</div>" +

      '<div class="layout-aside">' +
        "<div>" +
          '<div class="artwork-frame tombo-frame">' +
            '<img src="' + art.image + '" alt="' + esc(art.title || "無題") + ' の絵">' +
            '<div class="artwork-caption">' +
              "<span>作品ID " + esc(art.id) + "</span>" +
              "<span>描画 " + durationLabel(art.drawSeconds) + " · 保存 " + fmtFull(art.createdAt) + "</span>" +
            "</div>" +
          "</div>" +
          '<div class="panel" style="margin-top:18px">' +
            '<div class="panel-head"><h2 class="h3">作品について</h2></div>' +
            '<p style="margin-bottom:14px">' + (art.description ? esc(art.description) : '<span class="muted">説明はありません。</span>') + "</p>" +
            '<div class="stamp-row">' + art.tags.map(function (t) {
              return '<span class="stamp">' + esc(t) + "</span>";
            }).join("") + "</div>" +
            '<dl class="deflist" style="margin-top:16px">' +
              "<dt>出品者</dt><dd>" + esc(holderName(art.sellerId)) + "</dd>" +
              "<dt>出品日時</dt><dd class=\"data\">" + fmtFull(art.listedAt || art.createdAt) + "（日本時間）</dd>" +
              "<dt>入札件数</dt><dd class=\"data\">" + count + " 件</dd>" +
            "</dl>" +
          "</div>" +
        "</div>" +

        "<div>" +
          '<div class="panel tombo-frame">' +
            '<div class="panel-head">' +
              '<p class="label" style="margin:0">' + priceLabel + "</p>" +
              statusBadge(au) +
            "</div>" +
            '<div class="bid-price">' +
              '<span class="value">' + fmtPt(price) + '</span><span class="unit">pt</span>' +
            "</div>" +
            (au ? '<div class="live-clock' + (active ? "" : " is-closed") + '" style="margin-top:14px">' +
              '<span class="clock-label">' + (active ? "終了まで" : "終了日時") + "</span>" +
              '<span class="clock-value mono" data-cd="' + au.id + '">' +
                (active ? remainText(S.remainingMs(au)) : fmtShort(au.endsAt)) + "</span>" +
            "</div>" + strokeTrack(au) : "") +
            (au ? '<dl class="deflist" style="margin-top:16px">' +
              "<dt>開始価格</dt><dd class=\"data\">" + fmtPt(au.startPrice) + " pt</dd>" +
              "<dt>終了日時</dt><dd class=\"data\">" + fmtFull(au.endsAt) + "（日本時間）</dd>" +
              "<dt>現在の最高</dt><dd class=\"data\">" + (top ? esc(holderName(top.userId)) + " / " + fmtPt(top.amount) + " pt" : "入札なし") + "</dd>" +
              (me ? "<dt>保有ポイント</dt><dd class=\"data\">" + fmtPt(me.balance) + " pt</dd>" : "") +
            "</dl>" : "") +
            autoNote +
            '<hr class="rule" style="margin:18px 0">' +
            bidBlock +
          "</div>" +

          '<div class="panel" style="margin-top:18px">' +
            '<div class="panel-head"><h2 class="h3">入札の履歴</h2>' +
              '<span class="section-count">' + count + " 件</span></div>" +
            (count ? '<div class="ledger-head" style="--ledger-cols:96px 1fr 108px">' +
              "<span>時刻</span><span>入札者</span><span style=\"text-align:right\">金額</span></div>" : "") +
            historyRows +
          "</div>" +
        "</div>" +
      "</div>" +
    "</div>";
  }

  /* ============================================================
     画面：絵を描く
     ============================================================ */
  const PENS = [
    { key: "maru", label: "丸ペン" },
    { key: "gpen", label: "Ｇペン" },
    { key: "blur", label: "ぼかし" },
    { key: "eraser", label: "消しゴム" }
  ];
  const COLORS = [
    { key: "#16181c", label: "墨" },
    { key: "#27407f", label: "藍" },
    { key: "#b3123e", label: "濃紅" },
    { key: "#ff3d6e", label: "蛍光紅" },
    { key: "#2f6b4f", label: "若竹" },
    { key: "#7b6bb0", label: "藤" },
    { key: "#c98a12", label: "黄土" },
    { key: "#f7f6f2", label: "紙（白）" }
  ];
  const SIZES = [{ v: 2, label: "細" }, { v: 4, label: "中" }, { v: 8, label: "太" }];
  const DURATIONS = [
    { v: 10, label: "10秒" },
    { v: 30, label: "30秒" },
    { v: 60, label: "1分" },
    { v: 300, label: "5分" }
  ];

  function viewDraw() {
    const me = S.currentUser();
    if (!me) {
      return '<div class="wrap section">' +
        '<div class="section-head"><h1 class="h2">絵を描く</h1></div>' +
        emptyState("絵を描くにはログインが必要です",
          "描いた絵は下書きとしてあなたのアカウントに保存され、あとから出品情報を設定できます。",
          '<div class="btn-row"><a class="btn btn-primary" href="#/login">ログインする</a>' +
          '<a class="btn" href="#/register">新規登録</a></div>') +
      "</div>";
    }

    const dur = DURATIONS.map(function (d, i) {
      return '<button type="button" class="stamp" data-dur="' + d.v + '" aria-pressed="' + (i === 0) + '">' + d.label + "</button>";
    }).join("");
    const pens = PENS.map(function (p, i) {
      return '<button type="button" class="stamp" data-pen="' + p.key + '" aria-pressed="' + (i === 0) + '">' + p.label + "</button>";
    }).join("");
    const swatches = COLORS.map(function (c, i) {
      return '<button type="button" class="swatch' + (c.key === "#f7f6f2" ? " swatch-paper" : "") +
        '" data-color="' + c.key + '" title="' + c.label + '" aria-label="' + c.label +
        '" aria-pressed="' + (i === 0) + '" style="background:' + c.key + '"></button>';
    }).join("");
    const sizes = SIZES.map(function (s, i) {
      return '<button type="button" class="stamp" data-size="' + s.v + '" aria-pressed="' + (i === 1) + '">' + s.label + "</button>";
    }).join("");

    return '<div class="wrap studio">' +
      '<div class="section-head">' +
        '<h1 class="h2">絵を描く</h1>' +
        '<span class="section-count">制限時間を選んでから描き始めます</span>' +
      "</div>" +

      '<div class="studio-time">' +
        '<div class="filter-block">' +
          '<span class="label">制限時間（開始後は変更できません）</span>' +
          '<div class="choice-set" id="duration-set">' + dur + "</div>" +
        "</div>" +
        '<div class="clock" id="draw-clock">' +
          '<span class="clock-label">残り</span>' +
          '<span class="clock-value" id="draw-clock-value">' + clockText(DURATIONS[0].v * 1000) + "</span>" +
        "</div>" +
        '<div class="btn-row">' +
          '<button type="button" class="btn btn-primary" id="draw-start">描き始める</button>' +
          '<button type="button" class="btn btn-live" id="draw-finish" disabled>完成する（PNGで保存）</button>' +
        "</div>" +
      "</div>" +

      '<div class="stroke-track" id="draw-stroke" style="margin-top:14px"><span></span></div>' +

      '<div class="canvas-stage tombo-frame">' +
        '<div class="studio-tools">' +
          '<div class="tool-group"><span class="label">ペン</span><div class="choice-set" id="pen-set">' + pens + "</div></div>" +
          '<div class="tool-group"><span class="label">太さ</span><div class="choice-set" id="size-set">' + sizes + "</div></div>" +
          '<div class="tool-group"><span class="label">色</span><div class="swatches" id="color-set">' + swatches + "</div></div>" +
          '<div class="tool-group"><span class="label">操作</span><div class="choice-set">' +
            '<button type="button" class="stamp" id="draw-undo">取り消す</button>' +
            '<button type="button" class="stamp" id="draw-clear">全部消す</button>' +
          "</div></div>" +
        "</div>" +
        '<div class="canvas-frame" id="canvas-frame" style="margin-top:14px">' +
          '<canvas id="canvas" width="1000" height="750" aria-label="描画キャンバス"></canvas>' +
          '<div class="canvas-veil" id="canvas-veil">' +
            "<p><b>制限時間を選んで「描き始める」を押してください。</b><br>" +
            '<span class="small">時間切れ、または「完成する」で PNG として下書き保存します。保存した絵に加筆はできません。</span></p>' +
          "</div>" +
        "</div>" +
      "</div>" +

      '<p class="help" style="margin-top:14px">マウス・タッチ・ペンで描けます。保存した下書きはアカウント画面の下書き一覧に入り、出品するかどうかを後から選べます。' +
      "描画の制限時間と、オークションの終了日時は別のものです。</p>" +
    "</div>";
  }

  /* ============================================================
     画面：出品設定
     ============================================================ */
  function viewListing(artworkId) {
    const me = S.currentUser();
    const art = S.getArtwork(artworkId);
    if (!me) {
      return '<div class="wrap section">' + emptyState("出品にはログインが必要です", "ログインしてから、下書き一覧を開いてください。",
        '<a class="btn btn-primary" href="#/login">ログインする</a>') + "</div>";
    }
    if (!art) return notFound("下書きが見つかりません", "すでに出品されたか、あなたの下書きではありません。");
    if (art.sellerId !== me.id) return notFound("編集できません", "下書きは作者だけが閲覧・出品できます。");
    if (art.status !== "draft") {
      return '<div class="wrap section">' +
        emptyState("この作品はすでに出品されています", "1 作品につきオークションは 1 件です。Ver0.5 では再出品・取消はできません。",
          '<a class="btn btn-primary" href="#/work/' + art.id + '">作品ページを開く</a>') + "</div>";
    }

    const tags = S.tags().map(function (t) {
      return '<button type="button" class="stamp" data-tag-pick="' + esc(t) + '" aria-pressed="false">' + esc(t) + "</button>";
    }).join("");

    const nowLocal = toLocalInput(new Date(Date.now() + 24 * 3600 * 1000));

    return '<div class="wrap section">' +
      '<div class="crumbs"><a href="#/account?tab=drafts">下書き一覧</a> / 出品設定</div>' +
      '<div class="section-head"><h1 class="h2">出品設定</h1>' +
        '<span class="section-count">公開するとオークションが始まります</span></div>' +

      '<div class="layout-aside">' +
        "<div>" +
          '<form id="list-form" class="panel" data-artwork="' + art.id + '" novalidate>' +
            '<div class="field">' +
              '<label class="label" for="l-title">タイトル</label>' +
              '<input class="input" id="l-title" name="title" maxlength="60" required placeholder="例: 放課後の自転車">' +
              "<p class=\"help\">60 文字まで。作品一覧と作品ページに出ます。</p>" +
            "</div>" +
            '<div class="field">' +
              '<label class="label" for="l-desc">説明</label>' +
              '<textarea class="textarea" id="l-desc" name="description" maxlength="400" placeholder="描いた時間や、気に入っているところを書いておくと入札の参考になります。"></textarea>' +
            "</div>" +
            '<div class="field">' +
              '<span class="label">タグ（初期登録済みのタグから複数選択）</span>' +
              '<div class="choice-set" id="tag-pick">' + tags + "</div>" +
              '<p class="help">同じ作品に同じタグは 1 つだけ付きます。検索では、選んだタグをすべて含む作品だけが表示されます。</p>' +
            "</div>" +
            '<div class="field">' +
              '<label class="label" for="l-price">開始価格（pt）</label>' +
              '<input class="input input-data" type="number" id="l-price" name="startPrice" min="0" step="1" inputmode="numeric" value="300" required>' +
              '<div class="btn-row" style="margin-top:8px">' +
                '<button type="button" class="btn btn-ghost btn-sm" data-act="price-preset" data-value="0">0 pt</button>' +
                '<button type="button" class="btn btn-ghost btn-sm" data-act="price-preset" data-value="300">300 pt</button>' +
                '<button type="button" class="btn btn-ghost btn-sm" data-act="price-preset" data-value="500">500 pt</button>' +
                '<button type="button" class="btn btn-ghost btn-sm" data-act="price-preset" data-value="1000">1000 pt</button>' +
              "</div>" +
              '<p class="help">0 以上。出品者が希望する最低額は、この開始価格で設定します（最低落札価格は使いません）。</p>' +
            "</div>" +
            '<div class="field">' +
              '<label class="label" for="l-ends">終了日時（この端末の時刻で入力し、日本時間へ換算して表示します）</label>' +
              '<input class="input input-data" type="datetime-local" id="l-ends" name="endsAt" value="' + nowLocal + '" required>' +
              '<div class="btn-row" style="margin-top:8px">' +
                '<button type="button" class="btn btn-ghost btn-sm" data-act="ends-preset" data-min="2">デモ: 2分後</button>' +
                '<button type="button" class="btn btn-ghost btn-sm" data-act="ends-preset" data-min="60">1時間後</button>' +
                '<button type="button" class="btn btn-ghost btn-sm" data-act="ends-preset" data-min="1440">24時間後</button>' +
                '<button type="button" class="btn btn-ghost btn-sm" data-act="ends-preset" data-min="10080">7日後</button>' +
              "</div>" +
              '<p class="help">終了日時で入札を締め切ります。描画が終わってもオークションは終わりません。予約開始は Ver0.5 の対象外です。</p>' +
            "</div>" +
            '<div id="list-feedback" class="small" role="status" aria-live="polite"></div>' +
            '<div class="btn-row" style="margin-top:16px">' +
              '<button type="submit" class="btn btn-primary">この内容で出品する</button>' +
              '<button type="button" class="btn" data-act="save-draft-info">下書きとして保存する</button>' +
              '<a class="btn btn-ghost" href="#/account?tab=drafts">下書き一覧に戻る</a>' +
            "</div>" +
          "</form>" +
        "</div>" +

        "<div>" +
          '<div class="panel">' +
            '<div class="panel-head"><h2 class="h3">出品する絵</h2>' +
              '<span class="badge">下書き</span></div>' +
            '<img src="' + art.image + '" alt="出品する絵" style="border:1px solid var(--ink-12);background:var(--paper-3)">' +
            '<dl class="deflist" style="margin-top:14px">' +
              "<dt>描画時間</dt><dd class=\"data\">" + durationLabel(art.drawSeconds) + "</dd>" +
              "<dt>保存日時</dt><dd class=\"data\">" + fmtFull(art.createdAt) + "（日本時間）</dd>" +
              "<dt>作品ID</dt><dd class=\"data\">" + esc(art.id) + "</dd>" +
            "</dl>" +
          "</div>" +
          '<div class="panel" style="margin-top:18px">' +
            '<div class="panel-head"><h2 class="h3">出品のルール（Ver0.5）</h2></div>' +
            '<ul class="soon-list">' +
              "<li><span class=\"label\" style=\"margin:0\">公開</span><span>確定した時点で公開し、オークションを開始します。</span></li>" +
              "<li><span class=\"label\" style=\"margin:0\">本数</span><span>1 作品につきオークションは最大 1 件です。</span></li>" +
              "<li><span class=\"label\" style=\"margin:0\">加筆</span><span>保存した絵には加筆できません。編集できるのは出品情報だけです。</span></li>" +
              "<li><span class=\"label\" style=\"margin:0\">取消</span><span>Ver0.5 では出品・入札の取消は提供しません（Ver1 対応）。</span></li>" +
            "</ul>" +
          "</div>" +
        "</div>" +
      "</div>" +
    "</div>";
  }

  function toLocalInput(date) {
    const p = function (n) { return String(n).padStart(2, "0"); };
    return date.getFullYear() + "-" + p(date.getMonth() + 1) + "-" + p(date.getDate()) +
      "T" + p(date.getHours()) + ":" + p(date.getMinutes());
  }

  /* ============================================================
     画面：ログイン／新規登録
     ============================================================ */
  function viewAuth(mode) {
    const isLogin = mode === "login";
    const field = function (id, label, type, hint, autocomplete) {
      return '<div class="field">' +
        '<label class="label" for="' + id + '">' + label + "</label>" +
        '<input class="input" type="' + type + '" id="' + id + '" name="' + id + '"' +
          (autocomplete ? ' autocomplete="' + autocomplete + '"' : "") + " required>" +
        (hint ? '<p class="help">' + hint + "</p>" : "") +
      "</div>";
    };

    const demoUsers = S.users().filter(function (u) { return u.email.indexOf("hew.local") > 0; }).slice(0, 5);
    const demoList = demoUsers.map(function (u) {
      return '<div class="ledger-row" style="--ledger-cols:1fr 1fr">' +
        '<span class="mono">' + esc(u.email) + "</span>" +
        '<span class="mono faint">' + esc(window.HEW_DATA.DEV_PASSWORD) + "</span>" +
      "</div>";
    }).join("");

    return '<div class="wrap section">' +
      '<div class="layout-aside">' +
        "<div>" +
          '<div class="section-head"><h1 class="h2">' + (isLogin ? "ログイン" : "新規登録") + "</h1>" +
            '<span class="section-count">メールアドレスとパスワードで認証します</span></div>' +
          '<form id="auth-form" class="panel" novalidate>' +
            (isLogin ? "" : field("username", "ユーザー名", "text", "20 文字まで。他の利用者と重複できません。", "username")) +
            field("email", "メールアドレス", "email", isLogin ? "" : "確認メールによる所有確認は Ver0.5 では行いません。", "email") +
            field("password", "パスワード", "password", isLogin ? "" : "8 文字以上。記号を混ぜると安全です。", isLogin ? "current-password" : "new-password") +
            (isLogin ? "" : field("confirm", "パスワード（確認）", "password", "", "new-password")) +
            '<div id="auth-feedback" class="small" role="status" aria-live="polite"></div>' +
            '<div class="btn-row" style="margin-top:14px">' +
              '<button type="submit" class="btn btn-primary">' + (isLogin ? "ログインする" : "登録して始める") + "</button>" +
              '<a class="btn btn-ghost" href="' + (isLogin ? "#/register" : "#/login") + '">' +
                (isLogin ? "アカウントを作る" : "すでにアカウントを持っている") + "</a>" +
            "</div>" +
            (isLogin ? "" : '<p class="help" style="margin-top:12px">表示名はユーザー名とは別に管理します。初期値はユーザー名で、アカウント画面から後で変更できます。</p>') +
          "</form>" +
        "</div>" +
        "<div>" +
          '<div class="panel">' +
            '<div class="panel-head"><h2 class="h3">デモ用アカウント</h2>' +
              '<span class="badge">開発用</span></div>' +
            '<p class="small muted" style="margin-bottom:12px">入札を試すときは、このアカウントでログインしてください。' +
              "登録した自分のアカウントで出品すると、別のアカウントから競り上げられます。</p>" +
            '<div class="ledger-head" style="--ledger-cols:1fr 1fr"><span>メール</span><span>パスワード</span></div>' +
            demoList +
            '<p class="help" style="margin-top:12px">パスワードはブラウザ内に難読化して保存しています。本物の認証ではないため、実運用ではサーバー側でハッシュ化してください。</p>' +
          "</div>" +
        "</div>" +
      "</div>" +
    "</div>";
  }

  /* ============================================================
     画面：アカウント
     ============================================================ */
  function viewAccount(query) {
    const me = S.currentUser();
    if (!me) {
      return '<div class="wrap section">' + emptyState("ログインすると、この画面が使えます",
        "下書き・お気に入り・保有ポイントは、ログイン中のアカウントに表示されます。",
        '<a class="btn btn-primary" href="#/login">ログインする</a>') + "</div>";
    }
    const tab = query.tab || "drafts";
    const drafts = S.draftsOf(me.id);
    const listings = S.listingsOf(me.id);
    const favWorks = S.favWorksOf(me.id);
    const favAuctions = S.favAuctionsOf(me.id);

    const tabs = [
      ["drafts", "下書き", drafts.length],
      ["listings", "出品中・出品済み", listings.length],
      ["fav-works", "作品のお気に入り", favWorks.length],
      ["fav-auctions", "オークションのお気に入り", favAuctions.length]
    ].map(function (t) {
      return '<a class="tab" role="tab" aria-selected="' + (tab === t[0]) + '" href="#/account?tab=' + t[0] + '">' +
        t[1] + ' <span class="mono faint">' + t[2] + "</span></a>";
    }).join("");

    let panelHtml = "";
    if (tab === "drafts") {
      panelHtml = drafts.length
        ? '<div class="grid-plates">' + drafts.map(function (a) {
            return '<article class="ticket" style="padding:14px">' +
              '<div class="draft-card">' +
                '<div class="draft-plate"><img src="' + a.image + '" alt="下書きの絵" loading="lazy"></div>' +
                "<div>" +
                  '<p class="label" style="margin-bottom:2px">下書き</p>' +
                  '<p class="h3">' + (a.title ? esc(a.title) : "無題の下書き") + "</p>" +
                  '<p class="small muted mono">保存 ' + fmtFull(a.createdAt) + "</p>" +
                  '<p class="small muted">描画 ' + durationLabel(a.drawSeconds) + " · 入札の対象になっていません</p>" +
                  '<div class="btn-row" style="margin-top:10px">' +
                    '<a class="btn btn-primary btn-sm" href="#/list/' + a.id + '">出品設定へ進む</a>' +
                    '<button type="button" class="btn btn-ghost btn-sm" data-act="fav-work" data-id="' + a.id + '" aria-pressed="' +
                      (S.isFavWork(me.id, a.id) ? "true" : "false") + '">' + (S.isFavWork(me.id, a.id) ? "★ お気に入り" : "☆ お気に入り") + "</button>" +
                  "</div>" +
                "</div>" +
              "</div>" +
              '<p class="help">保存した絵に加筆はできません。編集できるのは出品情報だけです。</p>' +
            "</article>";
          }).join("") + "</div>"
        : emptyState("下書きはまだありません",
            "絵を描いて保存すると、ここに下書きが並びます。出品するかどうかは、あとから選べます。",
            '<a class="btn btn-primary" href="#/draw">絵を描く</a>');
    } else if (tab === "listings") {
      panelHtml = listings.length
        ? '<div class="grid-plates">' + listings.map(function (au) {
            const art = S.getArtwork(au.artworkId);
            return ticketCard({ artwork: art, auction: au });
          }).join("") + "</div>"
        : emptyState("出品した作品はまだありません", "下書きから出品設定へ進むと、オークションが始まります。",
            '<a class="btn" href="#/account?tab=drafts">下書きを見る</a>');
    } else if (tab === "fav-works") {
      panelHtml = favWorks.length
        ? '<div class="grid-plates">' + favWorks.map(function (a) {
            return ticketCard({ artwork: a, auction: S.auctionOfArtwork(a.id) });
          }).join("") + "</div>"
        : emptyState("作品のお気に入りはまだありません", "作品ページの「☆ 作品をお気に入り」から登録できます。",
            '<a class="btn" href="#/">作品を探す</a>');
    } else {
      panelHtml = favAuctions.length
        ? '<div class="grid-plates">' + favAuctions.map(function (au) {
            return ticketCard({ artwork: S.getArtwork(au.artworkId), auction: au });
          }).join("") + "</div>"
        : emptyState("オークションのお気に入りはまだありません", "商品詳細の「☆ オークションをお気に入り」から登録できます。作品のお気に入りとは別に管理します。",
            '<a class="btn" href="#/">作品を探す</a>');
    }

    return '<div class="wrap section">' +
      '<div class="section-head"><h1 class="h2">アカウント</h1>' +
        '<span class="section-count">' + esc(me.email) + "</span></div>" +

      '<div class="panel" style="margin-bottom:22px">' +
        '<div class="balance-card">' +
          "<div>" +
            '<p class="label">保有ポイント</p>' +
            '<p class="balance-value">' + fmtPt(me.balance) + ' <span class="unit">pt</span></p>' +
            '<p class="small muted" style="margin-top:6px">入札に使えます。入札の受理時に差し引かれ、最高額を更新されると返却されます。</p>' +
          "</div>" +
          '<div class="btn-row">' +
            '<a class="btn btn-primary" href="#/bonus">ボーナスポイント</a>' +
            '<a class="btn" href="#/charge">チャージ画面</a>' +
            '<a class="btn btn-ghost" href="#/notices">通知</a>' +
          "</div>" +
        "</div>" +
        '<hr class="rule" style="margin:18px 0">' +
        '<form id="profile-form" class="btn-row" style="align-items:flex-end;gap:14px">' +
          '<div class="field" style="flex:1 1 240px;margin:0">' +
            '<label class="label" for="p-display">表示名（ユーザー名とは別に管理）</label>' +
            '<input class="input" id="p-display" name="displayName" maxlength="24" value="' + esc(me.displayName) + '">' +
          "</div>" +
          '<button type="submit" class="btn">表示名を保存する</button>' +
          '<span id="profile-feedback" class="small" role="status" aria-live="polite"></span>' +
        "</form>" +
        '<dl class="deflist" style="margin-top:16px">' +
          "<dt>ユーザー名</dt><dd>" + esc(me.username) + "</dd>" +
          "<dt>メールアドレス</dt><dd>" + esc(me.email) + "</dd>" +
          "<dt>登録日時</dt><dd class=\"data\">" + fmtFull(me.createdAt) + "（日本時間）</dd>" +
        "</dl>" +
      "</div>" +

      '<div class="tabs" role="tablist">' + tabs + "</div>" +
      panelHtml +
    "</div>";
  }

  /* ============================================================
     画面：通知
     ============================================================ */
  function viewNotices() {
    const me = S.currentUser();
    if (!me) {
      return '<div class="wrap section">' + emptyState("ログインすると通知が見られます",
        "入札・落札・返却などのお知らせを、アプリ内とメールで受け取ります。",
        '<a class="btn btn-primary" href="#/login">ログインする</a>') + "</div>";
    }
    const notices = S.noticesOf(me.id);
    const unread = S.unreadCount(me.id);
    const mails = S.mailsOf(me.id);

    const rows = notices.length
      ? notices.map(function (n) {
          return '<div class="notice-row' + (n.read ? "" : " is-unread") + '">' +
            '<span class="notice-time">' + fmtShort(n.createdAt) +
              (n.read ? "" : ' <span class="unread-dot" aria-label="未読"></span>') + "</span>" +
            "<span>" +
              '<span class="strong">' + esc(n.title) + "</span>" +
              '<span class="badge" style="margin-left:8px">' + esc(kindLabel(n.kind)) + "</span>" +
              '<br><span class="muted small">' + esc(n.body) + "</span>" +
            "</span>" +
            '<span class="notice-actions">' +
              (n.artworkId ? '<a class="btn btn-ghost btn-sm" href="#/work/' + n.artworkId + '">作品を開く</a>' : "") +
              (n.read ? "" : '<button type="button" class="btn btn-ghost btn-sm" data-act="notice-read" data-id="' + n.id + '">既読にする</button>') +
            "</span>" +
          "</div>";
        }).join("")
      : '<div class="ledger-empty">通知はまだありません。入札や落札があると、ここに届きます。</div>';

    const mailRows = mails.length
      ? mails.map(function (m) {
          return '<div class="ledger-row" style="--ledger-cols:1fr 128px 74px">' +
            "<span>" + esc(m.subject) + '<br><span class="faint small">' + esc(m.to) + "</span></span>" +
            '<span class="mono faint">' + fmtShort(m.createdAt) + "</span>" +
            '<span class="mono">' + esc(m.status === "queued" ? "未送信" : m.status) + "</span>" +
          "</div>";
        }).join("")
      : '<div class="ledger-empty">メール通知の記録はまだありません。</div>';

    return '<div class="wrap section">' +
      '<div class="section-head"><h1 class="h2">通知</h1>' +
        '<span class="section-count">未読 ' + unread + " / 全 " + notices.length + " 件</span></div>" +
      '<div class="panel">' +
        '<div class="panel-head"><h2 class="h3">アプリ内の通知</h2>' +
          (unread ? '<button type="button" class="btn btn-sm" data-act="notice-all">すべて既読にする</button>' : "") +
        "</div>" +
        rows +
      "</div>" +

      '<div class="section-head" style="margin-top:34px"><h2 class="h2">メール通知の送信記録</h2>' +
        '<span class="section-count">SMTP 未設定のため送信していません</span></div>' +
      '<div class="panel">' +
        '<p class="help" style="margin-bottom:12px">入札・落札のたびに、登録メールアドレス宛の通知をキューに積みます。' +
          "送信先の設定が済むまでは「未送信」のまま記録だけが残ります（送信日時・試行回数も保存する設計です）。</p>" +
        (mails.length ? '<div class="ledger-head" style="--ledger-cols:1fr 128px 74px"><span>件名 / 宛先</span><span>作成</span><span>状態</span></div>' : "") +
        mailRows +
      "</div>" +
    "</div>";
  }

  function kindLabel(kind) {
    return {
      welcome: "登録", bid: "入札", outbid: "更新", won: "落札",
      sold: "出品", unsold: "終了", auto: "自動入札", bonus: "ボーナス"
    }[kind] || kind;
  }

  /* ============================================================
     画面：ボーナスポイント
     ============================================================ */
  function viewBonus() {
    const me = S.currentUser();
    if (!me) {
      return '<div class="wrap section">' + emptyState("ログインするとボーナスを受け取れます",
        "ユーザー登録・初描画・初出品に応じて、入札に使えるポイントを付与します。",
        '<a class="btn btn-primary" href="#/login">ログインする</a>') + "</div>";
    }
    const items = S.bonusItems(me.id);
    const rows = items.map(function (b) {
      const stateText = b.granted ? "受け取り済み" : b.done ? "受け取れます" : "条件未達";
      const badge = b.granted
        ? '<span class="badge badge-ink">' + stateText + "</span>"
        : b.done
          ? '<span class="badge badge-live">' + stateText + "</span>"
          : '<span class="badge badge-soon">' + stateText + "</span>";
      return '<div class="bonus-row">' +
        "<div>" +
          '<p class="h3">' + esc(b.label) + "</p>" +
          '<p class="small muted">' + esc(b.hint) + "</p>" +
        "</div>" +
        '<div class="btn-row" style="align-items:center;gap:14px">' +
          '<span class="bonus-amount">' + fmtPt(b.amount) + " pt</span>" +
          badge +
          (b.granted || !b.done ? "" : '<button type="button" class="btn btn-live btn-sm" data-act="claim" data-key="' + b.key + '">受け取る</button>') +
        "</div>" +
      "</div>";
    }).join("");

    const ledger = S.ledgerOf(me.id);
    const ledgerRows = ledger.length
      ? ledger.map(function (t) {
          return '<div class="ledger-row" style="--ledger-cols:1fr 88px 116px">' +
            "<span>" + esc(txLabel(t.kind)) + '<br><span class="faint small">' + esc(t.note) + "</span></span>" +
            '<span class="ledger-amount" style="color:' + (t.amount < 0 ? "var(--spot-deep)" : "var(--indigo)") + '">' +
              (t.amount > 0 ? "+" : "") + fmtPt(t.amount) + "</span>" +
            '<span class="mono faint" style="text-align:right">' + fmtShort(t.createdAt) + " · 残 " + fmtPt(t.balanceAfter) + "</span>" +
          "</div>";
        }).join("")
      : '<div class="ledger-empty">まだ記録がありません。</div>';

    return '<div class="wrap section">' +
      '<div class="crumbs"><a href="#/account">アカウント</a> / ボーナスポイント</div>' +
      '<div class="section-head"><h1 class="h2">ボーナスポイント</h1>' +
        '<span class="section-count">保有 ' + fmtPt(me.balance) + " pt</span></div>" +

      '<div class="notice-ink" style="margin-bottom:20px">' +
        "<p><b>付与の量と条件は、まだ確定していません。</b></p>" +
        '<p class="small">ここに表示している金額（登録 500 pt / はじめて描く 50 pt / はじめて出品 100 pt）は、' +
        "要件定義書 9 章の未決事項に対する開発用の既定値です。付与した事実はポイント取引の履歴に残ります。</p>" +
      "</div>" +

      '<div class="layout-aside">' +
        '<div class="panel">' +
          '<div class="panel-head"><h2 class="h3">受け取れるボーナス</h2>' +
            '<span class="badge">1 人につき各種 1 回</span></div>' +
          rows +
        "</div>" +
        '<div class="panel">' +
          '<div class="panel-head"><h2 class="h3">ポイントの履歴</h2>' +
            '<span class="section-count">' + ledger.length + " 件</span></div>" +
          (ledger.length ? '<div class="ledger-head" style="--ledger-cols:1fr 88px 116px">' +
            "<span>内容</span><span>増減</span><span style=\"text-align:right\">日時 / 残高</span></div>" : "") +
          ledgerRows +
        "</div>" +
      "</div>" +
    "</div>";
  }

  function txLabel(kind) {
    return {
      dev: "開発用の初期ポイント", signup: "登録ボーナス", bonus: "ボーナスポイント",
      bid: "入札による引き落とし", refund: "高値更新の返却"
    }[kind] || kind;
  }

  /* ============================================================
     画面：チャージ／支払い（遷移先のみ）
     ============================================================ */
  function viewCharge() {
    return '<div class="wrap section">' +
      '<div class="crumbs"><a href="#/account">アカウント</a> / アプリ内チャージ</div>' +
      '<div class="section-head"><h1 class="h2">アプリ内チャージ</h1>' +
        '<span class="badge badge-soon">Ver0.5 では未提供</span></div>' +
      '<div class="soon-panel halftone">' +
        '<span class="soon-watermark" aria-hidden="true">VER 1</span>' +
        '<h2 class="h3" style="margin-bottom:8px">この画面では、まだポイントを買えません。</h2>' +
        '<p class="lede" style="margin-bottom:14px">Ver0.5 は Stripe との通信・テスト決済・実際の課金・決済によるポイント加算のすべてを行いません。' +
        "画面の遷移先だけを用意し、課金機能が未提供であることが分かるようにしています。</p>" +
        '<dl class="deflist" style="margin-bottom:16px">' +
          "<dt>いまできること</dt><dd>登録・初描画・初出品のボーナスポイントを受け取る</dd>" +
          "<dt>できないこと</dt><dd>カード決済、コンビニ決済、コード決済、チャージ</dd>" +
          "<dt>予定</dt><dd>Ver1 で Stripe 連携を検討（上限額は未決）</dd>" +
        "</dl>" +
        '<div class="btn-row">' +
          '<a class="btn btn-primary" href="#/bonus">ボーナスポイントを受け取る</a>' +
          '<a class="btn" href="#/payment">支払い画面を見る</a>' +
          '<a class="btn btn-ghost" href="#/">作品を探す</a>' +
        "</div>" +
      "</div>" +
      '<p class="help" style="margin-top:16px">商品詳細からこの画面へ来られるのは、入札に必要なポイントが足りないときだけです。</p>' +
    "</div>";
  }

  function viewPayment() {
    return '<div class="wrap section">' +
      '<div class="crumbs"><a href="#/charge">アプリ内チャージ</a> / 支払い画面</div>' +
      '<div class="section-head"><h1 class="h2">支払い画面</h1>' +
        '<span class="badge badge-soon">決済は行いません</span></div>' +
      '<div class="soon-panel halftone">' +
        '<span class="soon-watermark" aria-hidden="true">STRIPE</span>' +
        '<h2 class="h3" style="margin-bottom:8px">支払いの手続きはありません。</h2>' +
        '<p class="lede" style="margin-bottom:14px">カード番号や決済手段の入力欄は設けていません。' +
          "決済事業者との通信も行わないため、この画面では何も入力せず、何も確定しません。</p>" +
        '<div class="empty-state" style="margin-bottom:16px">' +
          '<h3 class="h3">空の画面は、行き止まりではなく案内です</h3>' +
          "<p>Ver0.5 でポイントを増やす方法は、ボーナスポイントだけです。受取済みのボーナスは残高と履歴に反映されます。</p>" +
          '<a class="btn btn-primary" href="#/bonus">ボーナスポイントを確認する</a>' +
        "</div>" +
        '<a class="btn btn-ghost" href="#/charge">チャージ画面に戻る</a>' +
      "</div>" +
    "</div>";
  }

  /* ============================================================
     画面：将来機能（配信・管理）
     ============================================================ */
  function viewSoon(kind) {
    const map = {
      viewer: {
        title: "配信画面（閲覧側）",
        lead: "描いているところを、そのまま見られるようにする構想です。",
        items: [
          ["配信", "SkyWay（NTT）または aiortc を使い、ブラウザ間で映像をやり取りします。"],
          ["コメント", "配信中のコメントとスーパーチャットは将来機能です。"],
          ["連携", "見ている画面からそのまま商品詳細へ入札に行ける導線を想定しています。"]
        ]
      },
      streamer: {
        title: "配信画面（配信側）",
        lead: "描画画面から配信を始め、そのまま出品へ進む導線です。",
        items: [
          ["開始", "絵を描く画面から配信を開始し、作品ページへつなげます。"],
          ["終了", "配信を終えると出品設定画面へ進みます。"],
          ["記録", "タイムラプス保存は将来機能です。"]
        ]
      },
      admin: {
        title: "管理画面／管理者モード",
        lead: "商品・アカウント・タグの管理は Ver0.5 の対象外です。",
        items: [
          ["現状", "初期タグは開発用のコマンドで準備します。"],
          ["予定", "商品・アカウント・タグの管理画面を Ver1 以降で検討します。"],
          ["権限", "DB 上は管理者の権限を保持できますが、画面は提供していません。"]
        ]
      }
    }[kind];

    return '<div class="wrap section">' +
      '<div class="section-head"><h1 class="h2">' + esc(map.title) + "</h1>" +
        '<span class="badge badge-soon">将来機能 · Ver0.5 対象外</span></div>' +
      '<div class="soon-panel halftone">' +
        '<span class="soon-watermark" aria-hidden="true">VER 1</span>' +
        '<h2 class="h3" style="margin-bottom:8px">' + esc(map.lead) + "</h2>" +
        '<p class="lede" style="margin-bottom:8px">要件定義書では、この画面は将来機能として区別されています。Ver0.5 の完成条件には含まれません。</p>' +
        '<ul class="soon-list">' + map.items.map(function (i) {
          return "<li><span class=\"label\" style=\"margin:0\">" + esc(i[0]) + "</span><span>" + esc(i[1]) + "</span></li>";
        }).join("") + "</ul>" +
        '<div class="btn-row" style="margin-top:18px">' +
          '<a class="btn btn-primary" href="#/">作品を探す</a>' +
          '<a class="btn btn-ghost" href="#/draw">絵を描く</a>' +
        "</div>" +
      "</div>" +
    "</div>";
  }

  function notFound(title, body) {
    return '<div class="wrap section">' +
      emptyState(title || "ページが見つかりません",
        body || "URL を確認するか、作品一覧へ戻ってください。",
        '<div class="btn-row"><a class="btn btn-primary" href="#/">作品を探す</a>' +
        '<a class="btn btn-ghost" href="#/draw">絵を描く</a></div>') +
    "</div>";
  }

  /* ============================================================
     ルーティング
     ============================================================ */
  function route() {
    const raw = (location.hash || "#/").replace(/^#/, "");
    const qi = raw.indexOf("?");
    const path = (qi >= 0 ? raw.slice(0, qi) : raw) || "/";
    const query = {};
    if (qi >= 0) {
      raw.slice(qi + 1).split("&").forEach(function (kv) {
        if (!kv) return;
        const p = kv.split("=");
        query[decodeURIComponent(p[0])] = decodeURIComponent((p[1] || "").replace(/\+/g, " "));
      });
    }
    return { path: path, parts: path.split("/").filter(Boolean), query: query };
  }

  function render(opts) {
    const o = opts || {};
    const r = route();
    const keepScroll = o.scroll === "keep" ? window.scrollY : null;

    if (mounted && mounted.unmount) mounted.unmount();
    mounted = null;

    let html = "";
    let mountFn = null;

    switch (r.parts[0]) {
      case undefined: html = viewHome(r.query); break;
      case "work": html = viewWork(r.parts[1]); break;
      case "draw": html = viewDraw(); mountFn = mountDraw; break;
      case "list": html = viewListing(r.parts[1]); mountFn = mountListing; break;
      case "login": html = viewAuth("login"); mountFn = mountAuth; break;
      case "register": html = viewAuth("register"); mountFn = mountAuth; break;
      case "account": html = viewAccount(r.query); break;
      case "notices": html = viewNotices(); break;
      case "bonus": html = viewBonus(); break;
      case "charge": html = viewCharge(); break;
      case "payment": html = viewPayment(); break;
      case "live": html = viewSoon(r.parts[1] === "streamer" ? "streamer" : "viewer"); break;
      case "admin": html = viewSoon("admin"); break;
      default: html = notFound(); break;
    }

    screenEl.innerHTML = html;
    renderRail();

    if (mountFn) mounted = mountFn() || null;

    if (keepScroll !== null) window.scrollTo(0, Math.min(keepScroll, document.body.scrollHeight));
    else if (!o.keepFocus) screenEl.focus({ preventScroll: true });
    if (o.focusSelector) {
      const el = document.querySelector(o.focusSelector);
      if (el) el.focus();
    }
  }

  function rerender() { render({ scroll: "keep" }); }

  /* ============================================================
     描画キャンバスの実装
     ============================================================ */
  function mountDraw() {
    const canvas = document.getElementById("canvas");
    if (!canvas) return null;
    const ctx = canvas.getContext("2d");
    const frame = document.getElementById("canvas-frame");
    const veil = document.getElementById("canvas-veil");
    const startBtn = document.getElementById("draw-start");
    const finishBtn = document.getElementById("draw-finish");
    const clockBox = document.getElementById("draw-clock");
    const clockValue = document.getElementById("draw-clock-value");
    const strokeEl = document.getElementById("draw-stroke");
    const strokeFill = strokeEl.querySelector("span");
    const durationSet = document.getElementById("duration-set");

    const d = {
      canvas: canvas, ctx: ctx,
      duration: 10, startedAt: 0, endsAt: 0,
      started: false, finished: false, saved: null,
      pen: "maru", color: "#16181c", size: 4,
      undo: [], drawing: false, last: null, dirty: false
    };

    function resetCanvas() {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      d.undo = [];
      d.dirty = false;
    }
    resetCanvas();

    function pushUndo() {
      try {
        if (d.undo.length > 10) d.undo.shift();
        d.undo.push(ctx.getImageData(0, 0, canvas.width, canvas.height));
      } catch (e) { /* 画像が大きすぎる環境では取り消し不可 */ }
    }

    function pos(e) {
      const rect = canvas.getBoundingClientRect();
      return {
        x: (e.clientX - rect.left) * (canvas.width / rect.width),
        y: (e.clientY - rect.top) * (canvas.height / rect.height)
      };
    }

    function beginStroke(p) {
      pushUndo();
      d.drawing = true;
      d.last = p;
      d.dirty = true;
      dot(p);
    }

    function dot(p) {
      ctx.save();
      applyPen();
      ctx.beginPath();
      ctx.arc(p.x, p.y, Math.max(0.6, lineWidth() / 2), 0, Math.PI * 2);
      ctx.fillStyle = d.color;
      ctx.fill();
      ctx.restore();
    }

    function lineWidth() {
      if (d.pen === "maru") return d.size * 0.7;
      if (d.pen === "gpen") return d.size * 1.2;
      if (d.pen === "blur") return d.size * 1.8;
      return d.size * 3;
    }

    function applyPen() {
      ctx.lineCap = "round";
      ctx.lineJoin = "round";
      ctx.lineWidth = lineWidth();
      ctx.strokeStyle = d.color;
      if (d.pen === "eraser") {
        ctx.globalCompositeOperation = "destination-out";
        ctx.strokeStyle = "rgba(0,0,0,1)";
        ctx.globalAlpha = 1;
      } else if (d.pen === "blur") {
        ctx.globalCompositeOperation = "source-over";
        ctx.globalAlpha = 0.55;
        ctx.shadowBlur = d.size * 2.6;
        ctx.shadowColor = d.color;
      } else if (d.pen === "gpen") {
        ctx.globalCompositeOperation = "source-over";
        ctx.globalAlpha = 1;
        ctx.shadowBlur = 0;
      } else {
        ctx.globalCompositeOperation = "source-over";
        ctx.globalAlpha = 0.95;
        ctx.shadowBlur = 0;
      }
    }

    function moveStroke(p) {
      ctx.save();
      applyPen();
      ctx.beginPath();
      ctx.moveTo(d.last.x, d.last.y);
      ctx.quadraticCurveTo(d.last.x, d.last.y, (d.last.x + p.x) / 2, (d.last.y + p.y) / 2);
      ctx.stroke();
      ctx.restore();
      d.last = p;
    }

    function endStroke() { d.drawing = false; d.last = null; }

    canvas.addEventListener("pointerdown", function (e) {
      if (!d.started || d.finished) return;
      e.preventDefault();
      try { canvas.setPointerCapture(e.pointerId); } catch (err) { /* 合成イベントでは対象外 */ }
      beginStroke(pos(e));
    });
    canvas.addEventListener("pointermove", function (e) {
      if (!d.drawing) return;
      e.preventDefault();
      moveStroke(pos(e));
    });
    canvas.addEventListener("pointerup", endStroke);
    canvas.addEventListener("pointercancel", endStroke);
    canvas.addEventListener("pointerleave", function () { d.drawing = false; });

    /* 制限時間の選択 */
    durationSet.addEventListener("click", function (e) {
      const btn = e.target.closest("[data-dur]");
      if (!btn || d.started) return;
      d.duration = Number(btn.dataset.dur);
      durationSet.querySelectorAll("[data-dur]").forEach(function (b) {
        b.setAttribute("aria-pressed", String(b === btn));
      });
      clockValue.textContent = clockText(d.duration * 1000);
      strokeFill.style.width = "0%";
    });

    /* ペン・色・太さ */
    document.getElementById("pen-set").addEventListener("click", function (e) {
      const btn = e.target.closest("[data-pen]");
      if (!btn) return;
      d.pen = btn.dataset.pen;
      document.querySelectorAll("#pen-set [data-pen]").forEach(function (b) {
        b.setAttribute("aria-pressed", String(b === btn));
      });
    });
    document.getElementById("color-set").addEventListener("click", function (e) {
      const btn = e.target.closest("[data-color]");
      if (!btn) return;
      d.color = btn.dataset.color;
      document.querySelectorAll("#color-set [data-color]").forEach(function (b) {
        b.setAttribute("aria-pressed", String(b === btn));
      });
      if (d.pen === "eraser") {
        d.pen = "maru";
        document.querySelectorAll("#pen-set [data-pen]").forEach(function (b) {
          b.setAttribute("aria-pressed", String(b.dataset.pen === "maru"));
        });
      }
    });
    document.getElementById("size-set").addEventListener("click", function (e) {
      const btn = e.target.closest("[data-size]");
      if (!btn) return;
      d.size = Number(btn.dataset.size);
      document.querySelectorAll("#size-set [data-size]").forEach(function (b) {
        b.setAttribute("aria-pressed", String(b === btn));
      });
    });

    document.getElementById("draw-undo").addEventListener("click", function () {
      if (!d.started || d.finished) return;
      const img = d.undo.pop();
      if (!img) { toast("取り消せる操作がありません。"); return; }
      ctx.save();
      ctx.globalCompositeOperation = "source-over";
      ctx.globalAlpha = 1;
      ctx.shadowBlur = 0;
      ctx.putImageData(img, 0, 0);
      ctx.restore();
    });
    document.getElementById("draw-clear").addEventListener("click", function () {
      if (!d.started || d.finished) return;
      pushUndo();
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      d.dirty = false;
    });

    function lockUI() {
      frame.classList.add("is-locked");
      startBtn.disabled = true;
      finishBtn.disabled = false;
      durationSet.querySelectorAll("[data-dur]").forEach(function (b) { b.disabled = true; });
      veil.style.display = "none";
    }

    startBtn.addEventListener("click", function () {
      if (d.started) return;
      d.started = true;
      d.startedAt = Date.now();
      d.endsAt = d.startedAt + d.duration * 1000;
      lockUI();
      clockBox.classList.remove("is-urgent");
      clockValue.textContent = clockText(d.duration * 1000);
      toast(durationLabel(d.duration) + "の描画を始めました。");
      canvas.focus();
    });

    finishBtn.addEventListener("click", function () {
      if (!d.started || d.finished) return;
      finish("manual");
    });

    function finish(reason) {
      d.finished = true;
      finishBtn.disabled = true;
      frame.classList.add("is-locked");
      const elapsed = Math.min(d.duration, Math.max(0, Math.round((Date.now() - d.startedAt) / 1000)));
      if (reason === "timeout") {
        clockValue.textContent = clockText(0);
        strokeFill.style.width = "100%";
        toast("時間切れです。描画を停止し、PNG として保存します。");
      }
      save(elapsed);
    }

    function save(elapsed) {
      let dataUrl = "";
      try { dataUrl = canvas.toDataURL("image/png"); }
      catch (e) { dataUrl = ""; }
      const res = S.saveDraft({ image: dataUrl, drawSeconds: d.duration });
      if (!res.ok) {
        veil.style.display = "flex";
        veil.innerHTML = "<div><p><b>保存できませんでした。</b><br><span class=\"small\">" + esc(res.message) +
          "絵はこのまま残っています。保存をやり直せます。</span></p></div>";
        const retry = document.createElement("button");
        retry.type = "button";
        retry.className = "btn btn-primary";
        retry.style.marginTop = "12px";
        retry.textContent = "保存をやり直す";
        retry.addEventListener("click", function () { save(elapsed); });
        veil.querySelector("div").appendChild(retry);
        return;
      }
      d.saved = res.artwork;
      veil.style.display = "flex";
      veil.innerHTML =
        "<div><p><b>下書きとして保存しました。</b><br>" +
        '<span class="small">保存した絵に加筆はできません。出品情報はあとから編集できます。</span></p>' +
        '<div class="btn-row" style="justify-content:center;margin-top:14px">' +
          '<button type="button" class="btn btn-primary" data-act="go" data-href="#/list/' + res.artwork.id + '">出品設定へ進む</button>' +
          '<button type="button" class="btn" data-act="go" data-href="#/account?tab=drafts">下書き一覧へ</button>' +
        "</div></div>";
      openDialog({
        title: "下書きを保存しました",
        body:
          '<p class="small muted">描画 ' + durationLabel(d.duration) + " · 保存 " + fmtFull(res.artwork.createdAt) + "（日本時間）</p>" +
          '<img src="' + dataUrl + '" alt="保存した絵" style="border:1px solid var(--ink-22);background:var(--paper-3)">' +
          '<p class="small">次に出品情報（タイトル・説明・タグ・開始価格・終了日時）を設定します。ここで決めずに、あとからアカウント画面の下書き一覧で決めることもできます。</p>',
        actions: [
          { label: "出品設定へ進む", kind: "primary", onSelect: function () { location.hash = "#/list/" + res.artwork.id; } },
          { label: "あとで決める（下書き一覧へ）", onSelect: function () { location.hash = "#/account?tab=drafts"; } }
        ]
      });
    }

    /* 1 秒ごとの呼び出し（ui の ticker から） */
    function tick() {
      if (!d.started) return;
      if (d.finished) return;
      const remain = d.endsAt - Date.now();
      clockValue.textContent = clockText(Math.max(0, remain));
      const total = d.duration * 1000;
      strokeFill.style.width = pct(((total - Math.max(0, remain)) / total) * 100);
      const urgent = remain <= 10000;
      clockBox.classList.toggle("is-urgent", urgent);
      strokeEl.classList.toggle("is-urgent", urgent);
      if (remain <= 0) finish("timeout");
    }

    tick();
    return {
      unloadState: function () { return { dirty: d.started && !d.finished && d.dirty }; },
      tick: tick
    };
  }

  /* 未保存の描画があるか（画面離脱の確認に使う） */
  function drawHasUnsaved() {
    return !!(mounted && mounted.unloadState && mounted.unloadState().dirty);
  }

  /* ============================================================
     出品設定の画面マウント
     ============================================================ */
  function mountListing() {
    const form = document.getElementById("list-form");
    if (!form) return null;
    const pickBox = document.getElementById("tag-pick");
    const picked = [];

    pickBox.addEventListener("click", function (e) {
      const btn = e.target.closest("[data-tag-pick]");
      if (!btn) return;
      const t = btn.dataset.tagPick;
      const i = picked.indexOf(t);
      if (i >= 0) picked.splice(i, 1); else picked.push(t);
      btn.setAttribute("aria-pressed", String(i < 0));
    });

    form.addEventListener("submit", function (e) {
      e.preventDefault();
      const fb = document.getElementById("list-feedback");
      const artworkId = form.dataset.artwork;
      const endsLocal = document.getElementById("l-ends").value;
      if (!endsLocal) { fb.innerHTML = '<span class="problem">終了日時を入力してください。</span>'; return; }
      const endsAt = new Date(endsLocal).toISOString();

      const info = {
        title: document.getElementById("l-title").value,
        description: document.getElementById("l-desc").value,
        tags: picked.slice(),
        startPrice: document.getElementById("l-price").value,
        endsAt: endsAt
      };

      openDialog({
        title: "この内容で出品しますか",
        body:
          '<dl class="deflist">' +
            "<dt>タイトル</dt><dd>" + esc(info.title || "（未入力）") + "</dd>" +
            "<dt>タグ</dt><dd>" + (picked.length ? esc(picked.join("・")) : "（未選択）") + "</dd>" +
            "<dt>開始価格</dt><dd class=\"data\">" + esc(String(info.startPrice)) + " pt</dd>" +
            "<dt>終了日時</dt><dd class=\"data\">" + fmtFull(endsAt) + "（日本時間）</dd>" +
          "</dl>" +
          '<p class="small muted">公開すると同時にオークションが始まります。Ver0.5 では出品の取消や再出品はできません。</p>',
        actions: [
          {
            label: "出品して公開する", kind: "primary",
            onSelect: function () {
              const res = S.publish(artworkId, info);
              if (!res.ok) {
                document.getElementById("list-feedback").innerHTML = '<span class="problem">' + esc(res.message) + "</span>";
                return;
              }
              toast("出品しました。オークションが始まりました。");
              location.hash = "#/work/" + res.artwork.id;
            }
          },
          { label: "入力に戻る" }
        ]
      });
    });
    return null;
  }

  function mountAuth() {
    const form = document.getElementById("auth-form");
    if (!form) return null;
    const isLogin = !document.getElementById("username");
    form.addEventListener("submit", function (e) {
      e.preventDefault();
      const fb = document.getElementById("auth-feedback");
      const email = document.getElementById("email").value;
      const password = document.getElementById("password").value;
      const res = isLogin
        ? S.login(email, password)
        : S.register({
            username: document.getElementById("username").value,
            email: email,
            password: password,
            confirm: document.getElementById("confirm").value
          });
      if (!res.ok) {
        fb.innerHTML = '<span class="problem">' + esc(res.message) + "</span>";
        (document.getElementById(isLogin ? "email" : "username") || document.getElementById("email")).focus();
        return;
      }
      toast(isLogin ? "ログインしました。" : "登録しました。ボーナス " + S.BONUS.signup + " pt を付与しました。");
      location.hash = isLogin ? "#/account" : "#/draw";
    });
    return null;
  }

  /* ============================================================
     委譲イベント
     ============================================================ */
  document.addEventListener("click", function (e) {
    const el = e.target.closest("[data-act]");
    if (!el) return;
    const act = el.dataset.act;
    const me = S.currentUser();

    if (act === "logout") {
      S.logout();
      toast("ログアウトしました。");
      location.hash = "#/";
      render();
      return;
    }

    if (act === "jump") {
      const t = document.getElementById(el.dataset.target);
      if (t) t.scrollIntoView({ behavior: "smooth", block: "start" });
      return;
    }

    if (act === "tag") {
      const tag = el.dataset.tag;
      const r = route();
      const cur = (r.query.tags ? r.query.tags.split(",") : []).filter(Boolean);
      const i = cur.indexOf(tag);
      if (i >= 0) cur.splice(i, 1); else cur.push(tag);
      setHomeQuery({ tags: cur });
      return;
    }

    if (act === "clear-tags") { setHomeQuery({ tags: [] }); return; }

    if (act === "go") {
      location.hash = el.dataset.href;
      return;
    }

    if (act === "fav-work") {
      const res = S.toggleFavWork(el.dataset.id);
      toast(res.message, res.ok ? null : "error");
      if (res.ok) rerender();
      return;
    }

    if (act === "fav-auction") {
      const res = S.toggleFavAuction(el.dataset.id);
      toast(res.message, res.ok ? null : "error");
      if (res.ok) rerender();
      return;
    }

    if (act === "bid-quick") {
      const input = document.getElementById("bid-amount");
      if (!input) return;
      input.value = String(Number(input.value || 0) + Number(el.dataset.add));
      input.focus();
      return;
    }

    if (act === "price-preset") {
      const input = document.getElementById("l-price");
      if (input) { input.value = el.dataset.value; input.focus(); }
      return;
    }

    if (act === "ends-preset") {
      const input = document.getElementById("l-ends");
      if (input) {
        input.value = toLocalInput(new Date(Date.now() + Number(el.dataset.min) * 60 * 1000));
        input.focus();
      }
      return;
    }

    if (act === "save-draft-info") {
      const form = document.getElementById("list-form");
      if (!form) return;
      const picked = Array.prototype.map.call(document.querySelectorAll('[data-tag-pick][aria-pressed="true"]'), function (b) {
        return b.dataset.tagPick;
      });
      const res = S.updateDraftInfo(form.dataset.artwork, {
        title: document.getElementById("l-title").value,
        description: document.getElementById("l-desc").value,
        tags: picked
      });
      const fb = document.getElementById("list-feedback");
      if (fb) fb.innerHTML = res.ok ? '<span class="muted">下書きに保存しました。出品はまだ行っていません。</span>' : '<span class="problem">' + esc(res.message) + "</span>";
      toast(res.ok ? "下書きに保存しました。" : res.message, res.ok ? null : "error");
      return;
    }

    if (act === "notice-read") {
      S.markNoticeRead(el.dataset.id);
      rerender();
      return;
    }

    if (act === "notice-all") {
      if (me) { S.markAllRead(me.id); toast("すべての通知を既読にしました。"); rerender(); }
      return;
    }

    if (act === "claim") {
      const res = S.claimBonus(el.dataset.key);
      toast(res.ok ? "ボーナス " + res.amount + " pt を残高に反映しました。" : res.message, res.ok ? null : "error");
      if (res.ok) rerender();
      return;
    }
  });

  document.addEventListener("change", function (e) {
    const el = e.target.closest("[data-act]");
    if (!el) return;
    if (el.dataset.act === "sort") { setHomeQuery({ sort: el.value }); }
    if (el.dataset.act === "state") { setHomeQuery({ state: el.value }); }
  });

  function setHomeQuery(patch) {
    const r = route();
    const q = Object.assign({}, r.query, patch);
    if (q.tags && Array.isArray(q.tags)) {
      if (!q.tags.length) delete q.tags; else q.tags = q.tags.join(",");
    }
    if (q.sort === "ending") delete q.sort;
    if (q.state === "all") delete q.state;
    const qs = Object.keys(q).filter(function (k) { return q[k]; })
      .map(function (k) { return encodeURIComponent(k) + "=" + encodeURIComponent(q[k]); }).join("&");
    location.hash = "#/" + (qs ? "?" + qs : "");
  }

  /* 入札・自動入札・表示名のフォーム（画面ごとに委譲で拾う） */
  document.addEventListener("submit", function (e) {
    const form = e.target;
    if (form.id === "bid-form") {
      e.preventDefault();
      const auctionId = form.dataset.auction;
      const amount = document.getElementById("bid-amount").value;
      const res = S.placeBid(auctionId, amount, "manual");
      render({ scroll: "keep" });
      const fb = document.getElementById("bid-feedback");
      if (fb) {
        fb.innerHTML = res.ok
          ? '<div class="notice-ink">入札を受け付けました。現在価格は ' + fmtPt(res.auction.currentPrice) + " pt です。</div>"
          : '<span class="problem">' + esc(res.message) + "</span>";
      }
      toast(res.ok ? "入札しました。" : res.message, res.ok ? null : "error");
      return;
    }
    if (form.id === "auto-form") {
      e.preventDefault();
      const auctionId = form.dataset.auction;
      const max = document.getElementById("auto-max").value;
      const res = S.setAutoBid(auctionId, null, max);
      render({ scroll: "keep" });
      const fb = document.getElementById("auto-feedback");
      if (fb) {
        fb.innerHTML = res.ok
          ? '<div class="notice-ink">自動入札を設定しました。上限 ' + fmtPt(res.auto.maxAmount) + " pt です。</div>"
          : '<span class="problem">' + esc(res.message) + "</span>";
      }
      toast(res.ok ? "自動入札を設定しました。" : res.message, res.ok ? null : "error");
      return;
    }
    if (form.id === "profile-form") {
      e.preventDefault();
      const res = S.updateDisplayName(document.getElementById("p-display").value);
      const fb = document.getElementById("profile-feedback");
      if (fb) fb.innerHTML = res.ok ? '<span class="muted">保存しました。</span>' : '<span class="problem">' + esc(res.message) + "</span>";
      if (res.ok) { toast("表示名を保存しました。"); renderRail(); }
      return;
    }
  });

  /* ============================================================
     画面離脱の確認と定期実行
     ============================================================ */
  window.addEventListener("beforeunload", function (e) {
    if (drawHasUnsaved()) { e.preventDefault(); e.returnValue = ""; }
  });

  window.addEventListener("hashchange", function () {
    if (drawHasUnsaved()) {
      const leave = window.confirm("描いている絵はまだ保存されていません。移動すると絵は失われます。移動しますか？");
      if (!leave) {
        history.replaceState(null, "", location.href);
        return;
      }
    }
    render();
  });

  let lastCat = "";
  function tick() {
    const closed = S.closeExpired();
    const path = currentPath();
    if (closed && path !== "/draw") { render({ scroll: "keep" }); return; }

    document.querySelectorAll("[data-cd]").forEach(function (el) {
      const au = S.getAuction(el.dataset.cd);
      if (!au) return;
      el.textContent = cdText(au);
    });
    document.querySelectorAll("[data-stroke]").forEach(function (el) {
      const au = S.getAuction(el.dataset.stroke);
      if (!au) return;
      const total = Date.parse(au.endsAt) - Date.parse(au.createdAt);
      const remain = S.remainingMs(au);
      const w = total > 0 ? ((total - Math.max(0, Math.min(total, remain))) / total) * 100 : 100;
      const fill = el.querySelector("span");
      if (fill) fill.style.width = pct(w);
      el.classList.toggle("is-urgent", au.status === "active" && remain < 5 * 60 * 1000);
    });
    if (mounted && mounted.tick) mounted.tick();

    const me = S.currentUser();
    const cat = me ? me.id + ":" + S.unreadCount(me.id) + ":" + me.balance : "guest";
    if (cat !== lastCat) { lastCat = cat; renderRail(); }
  }

  window.HEW_UI = {
    render: render,
    rerender: rerender,
    toast: toast,
    tick: tick,
    hasUnsaved: drawHasUnsaved,
    fmtPt: fmtPt,
    remainText: remainText,
    durationLabel: durationLabel,
    fmtFull: fmtFull,
    fmtShort: fmtShort
  };
})();
