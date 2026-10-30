/* ============================================================
   art.js — デモ用の作品画像をその場で描く
   サーバーに画像を持たないので、seed から SVG を組み立てて
   data URI として渡す。同じ seed なら必ず同じ絵になる。
   rr(rnd, a, b) は「rnd を使って a〜b の実数を返す」補助関数。
   ============================================================ */
(function () {
  "use strict";

  function mulberry32(a) {
    return function () {
      a |= 0;
      a = (a + 0x6d2b79f5) | 0;
      let t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  const INKS = [
    "#16181c", // 墨
    "#27407f", // 藍
    "#b3123e", // 濃紅
    "#2f6b4f", // 若竹
    "#7b6bb0", // 藤
    "#c98a12"  // 黄土
  ];

  const W = 800;
  const H = 600;

  function rr(rnd, a, b) { return a + rnd() * (b - a); }
  function pick(rnd, arr) { return arr[Math.floor(rnd() * arr.length) % arr.length]; }
  function fx(n) { return Number(n).toFixed(1); }

  /* 手ぶれのある流れる線を 1 本つくる */
  function flowingPath(rnd, x, y, steps, len, drift) {
    let d = "M" + fx(x) + " " + fx(y);
    let angle = rr(rnd, 0, Math.PI * 2);
    for (let i = 0; i < steps; i++) {
      angle += rr(rnd, -drift, drift);
      const nx = x + Math.cos(angle) * len;
      const ny = y + Math.sin(angle) * len;
      const cx = x + Math.cos(angle - 1.1) * len * 0.6;
      const cy = y + Math.sin(angle - 1.1) * len * 0.6;
      d += "Q" + fx(cx) + " " + fx(cy) + " " + fx(nx) + " " + fx(ny);
      x = nx;
      y = ny;
    }
    return d;
  }

  function blobPath(rnd, cx, cy, r, points) {
    const pts = [];
    for (let i = 0; i < points; i++) {
      const a = (Math.PI * 2 * i) / points;
      const rad = r * rr(rnd, 0.74, 1.16);
      pts.push([cx + Math.cos(a) * rad, cy + Math.sin(a) * rad]);
    }
    let d = "M" + fx(pts[0][0]) + " " + fx(pts[0][1]);
    for (let i = 1; i <= pts.length; i++) {
      const p = pts[i % pts.length];
      const q = pts[(i + 1) % pts.length];
      d += "Q" + fx(p[0]) + " " + fx(p[1]) + " " + fx((p[0] + q[0]) / 2) + " " + fx((p[1] + q[1]) / 2);
    }
    return d + "Z";
  }

  function styleFigure(rnd, ink) {
    const cx = rr(rnd, W * 0.34, W * 0.66);
    const cy = rr(rnd, H * 0.42, H * 0.58);
    const r = rr(rnd, 64, 92);
    const out = [];
    out.push('<path d="' + blobPath(rnd, cx, cy, r, 11) + '" fill="none" stroke="' + ink +
      '" stroke-width="3.4" stroke-linejoin="round"/>');
    const ex = r * 0.34;
    out.push('<circle cx="' + fx(cx - ex) + '" cy="' + fx(cy - r * 0.22) + '" r="' + fx(rr(rnd, 4, 8)) + '" fill="' + ink + '"/>');
    out.push('<circle cx="' + fx(cx + ex) + '" cy="' + fx(cy - r * 0.22) + '" r="' + fx(rr(rnd, 4, 8)) + '" fill="' + ink + '"/>');
    out.push('<path d="M' + fx(cx - r * 0.3) + " " + fx(cy + r * 0.3) + "Q" + fx(cx) + " " + fx(cy + r * 0.5) + " " +
      fx(cx + r * 0.3) + " " + fx(cy + r * 0.3) + '" fill="none" stroke="' + ink +
      '" stroke-width="3" stroke-linecap="round"/>');
    for (let i = 0; i < 3; i++) {
      out.push('<path d="' + flowingPath(rnd, rr(rnd, 40, W - 40), rr(rnd, 40, H - 40), 3, rr(rnd, 22, 44), 0.9) +
        '" fill="none" stroke="' + pick(rnd, INKS) + '" stroke-width="2" stroke-linecap="round" opacity="0.75"/>');
    }
    return out.join("");
  }

  function styleLine(rnd) {
    const out = [];
    const n = Math.floor(rr(rnd, 11, 17));
    for (let i = 0; i < n; i++) {
      out.push('<path d="' + flowingPath(rnd, rr(rnd, 60, W - 60), rr(rnd, 60, H - 60),
        Math.floor(rr(rnd, 5, 9)), rr(rnd, 42, 96), 0.95) +
        '" fill="none" stroke="' + pick(rnd, INKS) + '" stroke-width="' + fx(rr(rnd, 2, 5.4)) +
        '" stroke-linecap="round" opacity="' + rr(rnd, 0.72, 1).toFixed(2) + '"/>');
    }
    out.push('<path d="' + blobPath(rnd, rr(rnd, 190, W - 190), rr(rnd, 150, H - 150), rr(rnd, 60, 110), 10) +
      '" fill="none" stroke="' + pick(rnd, INKS) + '" stroke-width="2.6"/>');
    return out.join("");
  }

  function styleIcon(rnd) {
    const ink = pick(rnd, INKS);
    const cx = W / 2;
    const cy = H / 2;
    const r = rr(rnd, 140, 200);
    const out = [];
    out.push('<circle cx="' + cx + '" cy="' + cy + '" r="' + fx(r) + '" fill="none" stroke="' + ink + '" stroke-width="4"/>');
    out.push('<path d="' + blobPath(rnd, cx, cy, r * 0.55, 9) + '" fill="none" stroke="' + pick(rnd, INKS) + '" stroke-width="3"/>');
    for (let i = 0; i < 5; i++) {
      const a = rr(rnd, 0, Math.PI * 2);
      const k1 = rr(rnd, 1.2, 1.5);
      const k2 = rr(rnd, 1.2, 1.5);
      out.push('<line x1="' + fx(cx + Math.cos(a) * r) + '" y1="' + fx(cy + Math.sin(a) * r) +
        '" x2="' + fx(cx + Math.cos(a) * r * k1) + '" y2="' + fx(cy + Math.sin(a) * r * k2) +
        '" stroke="' + pick(rnd, INKS) + '" stroke-width="2.4" stroke-linecap="round"/>');
    }
    return out.join("");
  }

  function styleHatch(rnd) {
    const ink = pick(rnd, INKS);
    const out = [];
    const x0 = rr(rnd, 90, 300);
    const y0 = rr(rnd, 70, 200);
    const bw = rr(rnd, 220, 380);
    const bh = rr(rnd, 200, 320);
    out.push('<rect x="' + fx(x0) + '" y="' + fx(y0) + '" width="' + fx(bw) + '" height="' + fx(bh) +
      '" fill="none" stroke="' + ink + '" stroke-width="3"/>');
    const gap = rr(rnd, 11, 20);
    for (let x = -bh; x < bw + bh; x += gap) {
      out.push('<line x1="' + fx(x0 + x) + '" y1="' + fx(y0 + bh) + '" x2="' + fx(x0 + x + bh) + '" y2="' + fx(y0) +
        '" stroke="' + ink + '" stroke-width="1.5" opacity="0.72"/>');
    }
    out.push('<path d="' + blobPath(rnd, rr(rnd, 140, W - 140), rr(rnd, H * 0.6, H - 80), rr(rnd, 40, 80), 9) +
      '" fill="none" stroke="' + pick(rnd, INKS) + '" stroke-width="3"/>');
    return out.join("");
  }

  /* seed から作品画像（data URI）をつくる */
  function svgArt(seed, style) {
    const rnd = mulberry32((seed * 2654435761) >>> 0);
    const styles = ["figure", "line", "icon", "hatch"];
    const st = style || styles[Math.floor(rnd() * styles.length)];
    let body = "";
    if (st === "figure") body = styleFigure(rnd, pick(rnd, INKS));
    else if (st === "icon") body = styleIcon(rnd);
    else if (st === "hatch") body = styleHatch(rnd);
    else body = styleLine(rnd);

    const svg =
      '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ' + W + " " + H + '" width="' + W + '" height="' + H + '">' +
      '<rect width="' + W + '" height="' + H + '" fill="#f7f6f2"/>' +
      '<g stroke-linecap="round">' + body + "</g>" +
      '<g fill="none" stroke="#16181c" stroke-opacity="0.25" stroke-width="1">' +
      '<circle cx="52" cy="' + (H - 52) + '" r="13"/>' +
      '<path d="M39 ' + (H - 52) + 'h26M52 ' + (H - 65) + 'v26"/></g>' +
      "</svg>";
    return "data:image/svg+xml;charset=utf-8," + encodeURIComponent(svg);
  }

  window.HEW_ART = { svgArt: svgArt, INKS: INKS };
})();
