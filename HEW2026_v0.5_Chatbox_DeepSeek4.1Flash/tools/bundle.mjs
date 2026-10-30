/**
 * 单文件打包：把 index.html、CSS、JS 内联成一个自包含的 HTML。
 * 用法：node tools/bundle.mjs
 * 输出：dist/hew2027-system.html（可直接双击打开、也可当作附件分享）
 * 说明：Google Fonts 的外链会保留；离线时会回退到系统字体。
 */
import fs from "node:fs";
import path from "node:path";

const root = path.resolve(path.dirname(new URL(import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1")), "..");
const indexPath = path.join(root, "index.html");
let html = fs.readFileSync(indexPath, "utf8");

const cssMatch = html.match(/<link rel="stylesheet" href="([^"]+)">\s*/);
if (!cssMatch) throw new Error("CSS の link が見つかりません");
const css = fs.readFileSync(path.join(root, cssMatch[1]), "utf8");
html = html.replace(cssMatch[0], "<style>\n" + css + "\n</style>\n");

html = html.replace(/<script src="([^"]+)"><\/script>/g, function (all, src) {
  const js = fs.readFileSync(path.join(root, src), "utf8");
  return "<script>\n" + js + "\n</script>";
});

if (/<script src=/.test(html) || /<link rel="stylesheet"/.test(html)) {
  throw new Error("内联できていない参照が残っています");
}

const outDir = path.join(root, "dist");
fs.mkdirSync(outDir, { recursive: true });
const outPath = path.join(outDir, "hew2027-system.html");
fs.writeFileSync(outPath, html, "utf8");
console.log("wrote", outPath, (html.length / 1024).toFixed(1) + " KB");
