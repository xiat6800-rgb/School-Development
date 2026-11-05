"""CDP によるデバイスエミュレーション付きスクリーンショット取得（開発用）。

headless Edge の --window-size には最小幅の制限がありActual 430px を
再現できないため、DevTools Protocol の Emulation.setDeviceMetricsOverride
で正確なビューポート幅を指定して撮像する。

Usage:
    python tools/cdp_shot.py <output_dir> <width> <height> <url> [<url> ...]
"""

from __future__ import annotations

import base64
import json
import subprocess
import sys
import time
from pathlib import Path

import requests
import websocket

EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
PORT = 9333


def start_edge(user_data_dir: Path) -> subprocess.Popen:
    proc = subprocess.Popen(
        [
            EDGE,
            "--headless=new",
            "--disable-gpu",
            "--hide-scrollbars",
            "--no-first-run",
            "--no-default-browser-check",
            f"--remote-debugging-port={PORT}",
            f"--user-data-dir={user_data_dir}",
            "about:blank",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    deadline = time.time() + 30
    while time.time() < deadline:
        try:
            requests.get(f"http://127.0.0.1:{PORT}/json/version", timeout=2)
            return proc
        except requests.RequestException:
            time.sleep(0.4)
    proc.terminate()
    raise RuntimeError("Edge DevTools endpoint did not come up")


class CDP:
    def __init__(self, ws_url: str) -> None:
        self.ws = websocket.create_connection(ws_url, timeout=60)
        self.seq = 0

    def send(self, method: str, params: dict | None = None) -> dict:
        self.seq += 1
        msg_id = self.seq
        self.ws.send(json.dumps({"id": msg_id, "method": method, "params": params or {}}))
        while True:
            data = json.loads(self.ws.recv())
            if data.get("id") == msg_id:
                if "error" in data:
                    raise RuntimeError(f"{method} failed: {data['error']}")
                return data.get("result", {})

    def close(self) -> None:
        self.ws.close()


def shot(client: CDP, url: str, out_path: Path, width: int, height: int) -> None:
    client.send(
        "Emulation.setDeviceMetricsOverride",
        {
            "width": width,
            "height": height,
            "deviceScaleFactor": 1,
            "mobile": True,
            "screenWidth": width,
            "screenHeight": height,
        },
    )
    client.send("Page.enable")
    client.send("Page.navigate", {"url": url})
    time.sleep(2.0)
    metrics = client.send("Page.getLayoutMetrics")
    css_w = int(metrics.get("cssLayoutViewport", {}).get("clientWidth", width))
    css_h = int(metrics.get("cssLayoutViewport", {}).get("clientHeight", height))
    client.send(
        "Emulation.setDeviceMetricsOverride",
        {
            "width": width,
            "height": css_h,
            "deviceScaleFactor": 1,
            "mobile": True,
            "screenWidth": width,
            "screenHeight": css_h,
        },
    )
    time.sleep(0.8)
    result = client.send("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": False})
    out_path.write_bytes(base64.b64decode(result["data"]))
    print(f"wrote {out_path.name} viewport={css_w}x{css_h} <- {url}")


def main(argv: list[str]) -> int:
    if len(argv) < 5:
        print(__doc__)
        return 2
    out_dir = Path(argv[1])
    width = int(argv[2])
    height = int(argv[3])
    urls = argv[4:]
    out_dir.mkdir(parents=True, exist_ok=True)

    proc = start_edge(out_dir / "ud")
    try:
        targets = requests.get(f"http://127.0.0.1:{PORT}/json/list", timeout=10).json()
        page = next(t for t in targets if t["type"] == "page")
        client = CDP(page["webSocketDebuggerUrl"])
        for url in urls:
            name = url.rstrip("/").split("/")[-1].split("?")[0] or "index"
            if name.endswith(".html"):
                name = name[:-5]
            safe = "".join(c for c in name if c.isalnum() or c in "-_") or "page"
            shot(client, url, out_dir / f"{safe}.png", width, height)
        client.close()
    finally:
        proc.terminate()
        proc.wait(timeout=15)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
