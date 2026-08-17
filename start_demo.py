#!/usr/bin/env python3
"""Start the local API, open a tunnel through the local proxy, update Pages."""

from __future__ import annotations

from datetime import datetime, timezone
import argparse
import json
from pathlib import Path
import re
import signal
import subprocess
import sys
import time
import urllib.request
from urllib.parse import quote


ROOT = Path(__file__).resolve().parent
CONFIG = ROOT / "backend-url.json"
PORT = 8765
TUNNEL_PATTERN = re.compile(r"https://[a-z0-9.-]+\.lhr\.life")
PAGES_URL = "https://0nanimonai0.github.io/OpenVideoAI/"


def run(command: list[str], *, check: bool = True):
    return subprocess.run(command, cwd=ROOT, check=check, text=True)


def wait_for_backend(timeout: float = 10.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/health", timeout=1) as response:
                if response.status == 200:
                    return
        except OSError:
            time.sleep(0.2)
    raise RuntimeError("本地后端启动超时")


def update_pages(tunnel_url: str, manual: bool = False):
    payload = {
        "url": tunnel_url,
        "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    if manual:
        print("手动模式：没有修改配置文件，也没有执行 git push。", flush=True)
        return
    rendered = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    CONFIG.write_text(rendered, encoding="utf-8")
    run(["git", "add", "backend-url.json"])
    changed = subprocess.run(
        ["git", "diff", "--cached", "--quiet"], cwd=ROOT, check=False
    ).returncode
    if changed:
        run(["git", "commit", "-m", "chore: update demo backend tunnel"])
        run(["git", "push", "origin", "main"])
        print("GitHub Pages 后端地址已自动更新", flush=True)
    else:
        print("后端地址没有变化，无需更新 Pages", flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--manual",
        action="store_true",
        help="只打印 Pages 配置，不执行 git commit/push",
    )
    args = parser.parse_args()
    backend = subprocess.Popen(
        [sys.executable, "backend/server.py", "--port", str(PORT)], cwd=ROOT
    )
    tunnel = None
    try:
        wait_for_backend()
        proxy_command = "nc -X connect -x 127.0.0.1:6789 %h %p"
        tunnel = subprocess.Popen(
            [
                "ssh",
                "-T",
                "-o",
                f"ProxyCommand={proxy_command}",
                "-o",
                "StrictHostKeyChecking=accept-new",
                "-o",
                "ServerAliveInterval=30",
                "-o",
                "ExitOnForwardFailure=yes",
                "-R",
                f"80:127.0.0.1:{PORT}",
                "nokey@localhost.run",
            ],
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        tunnel_url = ""
        for line in tunnel.stdout:
            print(line, end="", flush=True)
            match = TUNNEL_PATTERN.search(line)
            if match:
                tunnel_url = match.group(0)
                break
        if not tunnel_url:
            raise RuntimeError("没有从隧道服务获取到公网地址")
        print(f"公网 API：{tunnel_url}", flush=True)
        share_url = f"{PAGES_URL}?api={quote(tunnel_url, safe='')}"
        print(f"手机分享网址：{share_url}", flush=True)
        update_pages(tunnel_url, manual=args.manual)
        print("演示已启动。按 Ctrl+C 同时停止后端和隧道。", flush=True)
        return_code = tunnel.wait()
        raise RuntimeError(f"公网隧道已退出，状态码 {return_code}")
    except KeyboardInterrupt:
        print("\n正在停止演示……", flush=True)
    finally:
        for process in (tunnel, backend):
            if process and process.poll() is None:
                process.send_signal(signal.SIGINT)
        for process in (tunnel, backend):
            if process:
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.terminate()


if __name__ == "__main__":
    main()
