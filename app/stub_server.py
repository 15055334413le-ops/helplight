# -*- coding: utf-8 -*-
"""本地 stub：假装成 OpenAI 兼容推理端点，供无真实模型时联调全流程。

启动：python3 stub_server.py   （默认监听 127.0.0.1:8080，可用 STUB_PORT 覆盖）
接口：POST /v1/chat/completions  → 返回 chat.completion 形状的 JSON，
      message.content 是一段按关键词启发式生成的抽取 JSON 字符串。

注意：这只是联调用的假端点，抽取质量不代表 Spark-X2.6-4B 的真实效果。
切换到真实模型的方法见 README.md「配置」一节。
"""

import json
import os
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HOST = os.environ.get("STUB_HOST", "127.0.0.1")
PORT = int(os.environ.get("STUB_PORT", "8080"))

NEED_KEYWORDS = [
    ("饮用水", ("饮用水", "喝水", "纯净水", "矿泉水")),
    ("食物", ("食物", "吃的", "干粮", "面包")),
    ("药品", ("药", "急救")),
    ("担架", ("担架",)),
    ("帐篷", ("帐篷",)),
    ("棉被", ("棉被", "被子", "毯子")),
    ("冲锋舟", ("冲锋舟", "船")),
    ("救援队", ("救援", "接应")),
    ("送药上门", ("送药",)),
]

HIGH_KEYWORDS = ("被困", "淹到", "受伤", "断药", "吃完了", "头晕", "倒塌", "生命危险", "急需")
MID_KEYWORDS = ("不够", "紧缺", "没有", "缺", "停水", "停电")


def heuristic_extract(text):
    """非常朴素的关键词启发式，仅供联调演示流程，不代表模型效果。"""
    # 地点：找第一个含 市/县/区/镇/街道/小区/村/学校 等字样的短句片段
    location = "未知"
    for seg in re.split(r"[，。！!；;]", text):
        seg = seg.strip()
        if seg and any(k in seg for k in ("市", "县", "区", "镇", "街道", "小区", "村", "中学", "学校", "花园")):
            location = re.sub(r"^(求扩散|帮帮我|求助|紧急)[！!：:]*", "", seg)
            break
    # 人数
    people_count = 0
    m = re.search(r"(\d+)\s*(?:名|位|人|个)", text)
    if m:
        people_count = int(m.group(1))
    cn_nums = {"一": 1, "两": 2, "二": 2, "三": 3, "四": 4, "五": 5}
    if people_count == 0:
        m = re.search(r"一家([一两二三四五])口", text)
        if m:
            people_count = cn_nums[m.group(1)]
    # 人员构成
    notes = []
    for kw, label in (("老人", "老人"), ("小孩", "儿童"), ("儿童", "儿童"),
                      ("学生", "学生"), ("受伤", "有伤员"), ("高血压", "慢性病患者")):
        if kw in text and label not in notes:
            notes.append(label)
    # 需求
    needs = []
    for label, kws in NEED_KEYWORDS:
        if any(k in text for k in kws) and label not in needs:
            needs.append(label)
    # 联系方式（打码手机号）
    m = re.search(r"1\d{2}\*{4}\d{4}", text)
    contact = m.group() if m else ""
    # 紧急程度
    if any(k in text for k in HIGH_KEYWORDS):
        urgency = "高"
    elif any(k in text for k in MID_KEYWORDS):
        urgency = "中"
    else:
        urgency = "低"
    summary = text.strip().replace("\n", " ")[:40]
    return {
        "location": location,
        "people_count": people_count,
        "people_notes": "、".join(notes),
        "needs": needs,
        "urgency": urgency,
        "contact": contact,
        "summary": summary,
        "summary_en": "[stub] Placeholder English summary for integration testing only.",
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "HelpLightStub/1.0"

    def log_message(self, fmt, *args):
        import sys

        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def do_POST(self):
        if self.path.rstrip("/") not in ("/v1/chat/completions", "/chat/completions"):
            self._reply({"error": "not found"}, 404)
            return
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            payload = json.loads(raw.decode("utf-8"))
        except Exception:
            self._reply({"error": "bad json"}, 400)
            return
        messages = payload.get("messages") or []
        user_text = ""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                user_text = msg.get("content") or ""
                break
        result = heuristic_extract(user_text)
        content = json.dumps(result, ensure_ascii=False)
        self._reply(
            {
                "id": "chatcmpl-stub",
                "object": "chat.completion",
                "created": 0,
                "model": payload.get("model", "stub"),
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": content},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            }
        )

    def _reply(self, obj, status=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main():
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print("Stub 模型端点已启动: http://%s:%d/v1" % (HOST, PORT))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
