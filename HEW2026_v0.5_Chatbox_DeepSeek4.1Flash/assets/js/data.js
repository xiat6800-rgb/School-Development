/* ============================================================
   data.js — 初期タグとデモ用の種データ
   作品の画像は art.js が seed から描く。入札・ポイントの
   履歴は store.js が起動時に 1 件ずつ処理して作るので、
   残高・台帳・通知が食い違わない。
   ============================================================ */
(function () {
  "use strict";

  const DEV_PASSWORD = "HewDemo2027!";

  const TAGS = [
    "乗り物",
    "動物",
    "昆虫",
    "植物",
    "食べ物",
    "キャラクター",
    "風景",
    "抽象"
  ];

  const USERS = [
    { username: "demo", email: "demo@hew.local", displayName: "デモ見学者", balance: 8000 },
    { username: "minato", email: "artist0@hew.local", displayName: "みなと", balance: 9000 },
    { username: "kohaku", email: "artist1@hew.local", displayName: "こはく", balance: 8500 },
    { username: "soyokaze", email: "artist2@hew.local", displayName: "そよかぜ", balance: 8000 },
    { username: "kuroha", email: "artist3@hew.local", displayName: "くろは", balance: 7500 }
  ];

  /* デモアカウント自身が下書きとして持っている 1 枚 */
  const DEMO_DRAFT = { seed: 1201, artStyle: "figure", drawSeconds: 30 };

  /* endsIn は起動時からの秒数。負の値は「すでに終了したオークション」。
     rivals は入札してくる相手の人数（0 なら落札者なし）。
     seller は USERS の添字（0 はデモアカウント）。demoJoins は
     デモアカウントも初期の入札に加わる作品、demoTops はさらに
     最後の一手をデモアカウントが入れて最高額になる作品。 */
  const WORKS = [
    {
      title: "放課後の自転車",
      description: "30秒で描きました。サドルの影を濃くすると遠近が出た気がします。",
      tags: ["乗り物", "風景"],
      seed: 101, artStyle: "line", seller: 1, drawSeconds: 30,
      startPrice: 300, endsIn: 8 * 60, rivals: 3, autoRival: true, demoJoins: true
    },
    {
      title: "ねこ又",
      description: "1分。耳の角度だけ納得いっていませんが、そこも含めて味ということにしました。",
      tags: ["動物", "キャラクター"],
      seed: 202, artStyle: "figure", seller: 2, drawSeconds: 60,
      startPrice: 500, endsIn: 41 * 60, rivals: 2
    },
    {
      title: "朝の通学路",
      description: "5分。電柱を描き込んだら、道の方が小さくなってしまいました。",
      tags: ["風景"],
      seed: 303, artStyle: "line", seller: 3, drawSeconds: 300,
      startPrice: 1000, endsIn: 3 * 3600, rivals: 4, autoRival: true, demoJoins: true
    },
    {
      title: "蝉の抜け殻",
      description: "10秒チャレンジ。脚は 6 本あるはずですが 4 本しか見えません。",
      tags: ["昆虫", "抽象"],
      seed: 404, artStyle: "icon", seller: 1, drawSeconds: 10,
      startPrice: 200, endsIn: 9 * 3600, rivals: 1
    },
    {
      title: "たんぽぽの綿毛",
      description: "1分。消しゴムで削りすぎて、綿毛が飛んだあとみたいになりました。",
      tags: ["植物"],
      seed: 505, artStyle: "icon", seller: 4, drawSeconds: 60,
      startPrice: 400, endsIn: 25 * 3600, rivals: 2
    },
    {
      title: "湯気のラーメン",
      description: "30秒。湯気は円を半分にして描くとそれらしくなります。",
      tags: ["食べ物"],
      seed: 606, artStyle: "hatch", seller: 2, drawSeconds: 30,
      startPrice: 600, endsIn: 50 * 3600, rivals: 3, demoJoins: true, demoTops: true
    },
    {
      title: "オリキャラ・アカリ",
      description: "5分。自分の分身です。髪の跳ねを一筆で描けたのがうれしい。",
      tags: ["キャラクター", "動物"],
      seed: 707, artStyle: "figure", seller: 3, drawSeconds: 300,
      startPrice: 800, endsIn: 2 * 86400, rivals: 5, autoRival: true, demoJoins: true
    },
    {
      title: "屋上から見た街",
      description: "1分。窓の数を全部描いたら時間が終わりました。",
      tags: ["風景", "抽象"],
      seed: 808, artStyle: "hatch", seller: 1, drawSeconds: 60,
      startPrice: 350, endsIn: 3 * 86400, rivals: 2
    },
    {
      title: "線だけの抽象",
      description: "10秒。意図はありません。手の動きだけが残っています。",
      tags: ["抽象"],
      seed: 909, artStyle: "line", seller: 4, drawSeconds: 10,
      startPrice: 150, endsIn: 4 * 86400, rivals: 0
    },
    {
      title: "虫かごの中",
      description: "30秒。格子が多すぎて中身が見えません。逆に良かった。",
      tags: ["昆虫"],
      seed: 111, artStyle: "hatch", seller: 2, drawSeconds: 30,
      startPrice: 250, endsIn: 5 * 86400, rivals: 1
    },
    {
      title: "おにぎりと味噌汁",
      description: "1分。海苔の位置を直したかった。",
      tags: ["食べ物", "抽象"],
      seed: 222, artStyle: "icon", seller: 3, drawSeconds: 60,
      startPrice: 300, endsIn: 6 * 86400, rivals: 2
    },
    {
      title: "橋と電車",
      description: "5分。線路を描き込むほど、橋が短くなっていきます。",
      tags: ["乗り物", "風景"],
      seed: 333, artStyle: "line", seller: 4, drawSeconds: 300,
      startPrice: 1200, endsIn: 7 * 86400, rivals: 3
    },
    {
      title: "観葉植物の窓辺",
      description: "すでに落札済み。葉の重なりを 3 色で分けました。",
      tags: ["植物", "風景"],
      seed: 444, artStyle: "icon", seller: 1, drawSeconds: 60,
      startPrice: 500, endsIn: -3600, rivals: 3
    },
    {
      title: "ペン先の兎",
      description: "入札なしで終了した作品。見てくれる人がいないと、こうなります。",
      tags: ["動物", "抽象"],
      seed: 555, artStyle: "figure", seller: 2, drawSeconds: 10,
      startPrice: 800, endsIn: -7200, rivals: 0
    },
    {
      title: "通学路の電柱",
      description: "30秒。自分の出品です。別のアカウントから競り上がってもらえます。",
      tags: ["風景", "乗り物"],
      seed: 616, artStyle: "line", seller: 0, drawSeconds: 30, listedAgoMin: 9,
      startPrice: 400, endsIn: 6 * 60, rivals: 2
    },
    {
      title: "ゆるキャラ・ヘウ",
      description: "1分。サイトの宣伝用に描きました。",
      tags: ["キャラクター", "動物"],
      seed: 717, artStyle: "figure", seller: 0, drawSeconds: 60, listedAgoMin: 110,
      startPrice: 600, endsIn: 4 * 86400, rivals: 3
    }
  ];

  window.HEW_DATA = {
    DEV_PASSWORD: DEV_PASSWORD,
    TAGS: TAGS,
    USERS: USERS,
    WORKS: WORKS,
    DEMO_DRAFT: DEMO_DRAFT
  };
})();
