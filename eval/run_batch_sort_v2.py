#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""批量排序验证：把 eval/gold.json 的 12 条原文以空行分隔一次性提交
/api/parse-batch，保存服务端返回的（已按紧急程度排序的）结果，
用于验证跨级排序 高>中>低 是否成立、同级是否保持输入顺序。
"""
import json
import os
import time
import urllib.request

EVAL_DIR = os.path.dirname(os.path.abspath(__file__))
API = "http://127.0.0.1:8000/api/parse-batch"

with open(os.path.join(EVAL_DIR, "gold.json"), encoding="utf-8") as f:
    cases = json.load(f)["cases"]

joined = "\n\n".join(c["text"] for c in cases)
payload = json.dumps({"text": joined}).encode("utf-8")
req = urllib.request.Request(
    API, data=payload, headers={"Content-Type": "application/json"}, method="POST"
)
t0 = time.time()
with urllib.request.urlopen(req, timeout=2400) as resp:
    body = json.loads(resp.read().decode("utf-8"))
elapsed = round(time.time() - t0, 2)

out = {
    "elapsed_sec": elapsed,
    "count": body.get("count"),
    "input_order": [c["id"] for c in cases],
    "gold_urgency": {c["id"]: c["gold"]["urgency"] for c in cases},
    "returned": [
        {
            "seq": i + 1,
            "urgency": r.get("urgency"),
            "location": r.get("location"),
            "people_count": r.get("people_count"),
            "retried": r.get("retried"),
            "parse_failed": r.get("parse_failed"),
            "original": r.get("original"),
        }
        for i, r in enumerate(body.get("results", []))
    ],
}
with open(os.path.join(EVAL_DIR, "batch-sort-v2.json"), "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=2)
print(
    "batch done elapsed=%.1fs count=%s order=%s"
    % (elapsed, out["count"], [r["urgency"] for r in out["returned"]]),
    flush=True,
)
