#!/usr/bin/env python3
"""Small upload API that reads duration from MP4/MOV metadata."""

from __future__ import annotations

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import struct
from urllib.parse import unquote


MAX_UPLOAD_BYTES = 100 * 1024 * 1024
ALLOWED_ORIGINS = {
    "https://0nanimonai0.github.io",
    "http://127.0.0.1:8000",
    "http://localhost:8000",
}


class VideoError(ValueError):
    pass


def iter_boxes(data: bytes, start: int = 0, end: int | None = None):
    """Yield ISO BMFF boxes as (type, payload_start, box_end)."""
    end = len(data) if end is None else min(end, len(data))
    position = start
    while position + 8 <= end:
        size = struct.unpack_from(">I", data, position)[0]
        box_type = data[position + 4 : position + 8]
        header_size = 8
        if size == 1:
            if position + 16 > end:
                return
            size = struct.unpack_from(">Q", data, position + 8)[0]
            header_size = 16
        elif size == 0:
            size = end - position
        if size < header_size or position + size > end:
            return
        yield box_type, position + header_size, position + size
        position += size


def mp4_duration(data: bytes) -> float:
    moov = next((box for box in iter_boxes(data) if box[0] == b"moov"), None)
    if moov is None:
        raise VideoError("未找到 MP4 的 moov 元数据，请换一个普通 MP4/MOV 文件")
    mvhd = next(
        (box for box in iter_boxes(data, moov[1], moov[2]) if box[0] == b"mvhd"),
        None,
    )
    if mvhd is None:
        raise VideoError("视频缺少 mvhd 时长信息")
    payload_start, payload_end = mvhd[1], mvhd[2]
    if payload_start + 20 > payload_end:
        raise VideoError("视频时长元数据不完整")
    version = data[payload_start]
    if version == 0:
        timescale = struct.unpack_from(">I", data, payload_start + 12)[0]
        duration = struct.unpack_from(">I", data, payload_start + 16)[0]
    elif version == 1:
        if payload_start + 32 > payload_end:
            raise VideoError("视频时长元数据不完整")
        timescale = struct.unpack_from(">I", data, payload_start + 20)[0]
        duration = struct.unpack_from(">Q", data, payload_start + 24)[0]
    else:
        raise VideoError(f"不支持的 mvhd 版本：{version}")
    if not timescale or not duration:
        raise VideoError("视频时长为零或使用了暂不支持的分片格式")
    seconds = duration / timescale
    if seconds <= 0 or seconds > 7 * 24 * 3600:
        raise VideoError("视频时长数值异常")
    return seconds


class Handler(BaseHTTPRequestHandler):
    server_version = "VideoAIDemo/1.0"

    def _cors_headers(self):
        origin = self.headers.get("Origin", "")
        if origin in ALLOWED_ORIGINS:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-File-Name")
        self.send_header("Access-Control-Max-Age", "86400")

    def _send_json(self, status: int, payload: dict):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self._cors_headers()
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors_headers()
        self.end_headers()

    def do_GET(self):
        if self.path.split("?", 1)[0] == "/health":
            self._send_json(200, {"ok": True, "service": "video-ai-demo"})
        else:
            self._send_json(404, {"error": "接口不存在"})

    def do_POST(self):
        if self.path != "/api/duration":
            self._send_json(404, {"error": "接口不存在"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        if length <= 0:
            self._send_json(400, {"error": "没有收到视频数据"})
            return
        if length > MAX_UPLOAD_BYTES:
            self._send_json(413, {"error": "视频超过 100 MB 限制"})
            return
        content_type = self.headers.get("Content-Type", "")
        if not (content_type.startswith("video/") or content_type == "application/octet-stream"):
            self._send_json(415, {"error": "请上传 MP4、MOV 或 M4V 视频"})
            return
        filename = unquote(self.headers.get("X-File-Name", "video.mp4"))[:240]
        try:
            data = self.rfile.read(length)
            if len(data) != length:
                raise VideoError("视频上传不完整")
            duration = mp4_duration(data)
            self._send_json(
                200,
                {
                    "ok": True,
                    "filename": filename,
                    "duration_seconds": round(duration, 3),
                    "method": "MP4 元数据",
                    "retained": False,
                },
            )
        except VideoError as error:
            self._send_json(422, {"error": str(error)})
        except Exception:
            self._send_json(500, {"error": "服务器解析视频时发生错误"})

    def log_message(self, fmt, *args):
        print(f"{self.client_address[0]} - {fmt % args}", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Video AI backend: http://{args.host}:{args.port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
