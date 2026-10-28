# -*- coding: utf-8 -*-
"""援光 HelpLight — 灾害求助信息结构化与分诊台（本地 Web 应用）。

仅使用 Python 标准库，无第三方依赖，无任何云端调用。
启动：python3 server.py   （默认监听 127.0.0.1:8000，可用 PORT 覆盖）

接口：
  GET  /                 单页前端
  GET  /api/health       服务与模型配置状态
  GET  /api/examples     3 条内置脱敏虚构示例
  POST /api/parse        {"text": "..."}            单条解析
  POST /api/parse-batch  {"text": "多条以空行分隔"}  批量解析（按紧急度排序）
"""

import json
import os
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import model_client
from examples import EXAMPLES

HOST = os.environ.get("HOST", "127.0.0.1")
PORT = int(os.environ.get("PORT", "8000"))
STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")


def split_batch(text):
    """批量文本按空行切分，逐条去空白，空段丢弃。"""
    parts = re.split(r"\n\s*\n", text or "")
    return [p.strip() for p in parts if p.strip()]


def parse_batch(text):
    items = [model_client.extract(t) for t in split_batch(text)]
    # 按紧急程度排序：高 > 中 > 低；同级保持输入顺序（稳定排序）
    items.sort(key=lambda r: model_client.URGENCY_RANK.get(r["urgency"], 1))
    return items


class Handler(BaseHTTPRequestHandler):
    server_version = "HelpLight/1.0"

    # ---------- 工具 ----------
    def _send_json(self, obj, status=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self):
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        return json.loads(raw.decode("utf-8"))

    def log_message(self, fmt, *args):  # 精简日志到 stderr
        import sys

        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    # ---------- 路由 ----------
    def do_GET(self):
        if self.path in ("/", "/index.html"):
            path = os.path.join(STATIC_DIR, "index.html")
            with open(path, "rb") as f:
                body = f.read()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path == "/api/health":
            self._send_json(
                {
                    "ok": True,
                    "app": "HelpLight",
                    "model_endpoint": model_client.MODEL_ENDPOINT,
                    "model_name": model_client.MODEL_NAME,
                }
            )
        elif self.path == "/api/examples":
            self._send_json({"examples": EXAMPLES})
        else:
            self._send_json({"error": "not found"}, status=404)

    def do_POST(self):
        try:
            payload = self._read_json()
        except Exception:
            self._send_json({"error": "请求体不是合法 JSON"}, status=400)
            return
        text = (payload.get("text") or "").strip()
        if self.path == "/api/parse":
            if not text:
                self._send_json({"error": "text 不能为空"}, status=400)
                return
            self._send_json({"result": model_client.extract(text)})
        elif self.path == "/api/parse-batch":
            if not text:
                self._send_json({"error": "text 不能为空"}, status=400)
                return
            results = parse_batch(text)
            self._send_json({"results": results, "count": len(results)})
        else:
            self._send_json({"error": "not found"}, status=404)


def main():
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print("HelpLight 已启动: http://%s:%d" % (HOST, PORT))
    print("模型端点: %s  模型: %s" % (model_client.MODEL_ENDPOINT, model_client.MODEL_NAME))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
