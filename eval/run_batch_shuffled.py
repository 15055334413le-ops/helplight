#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""乱序排序压力测试：从 gold.json 取 低/中/高 各一条，以 低→中→高 的
逆序提交 /api/parse-batch，验证服务端确实发生跨级重排（而非原样返回）。
"""
import json
import os
import time
import urllib.request

EVAL_DIR = os.path.dirname(os.path.abspath(__file__))
API = "http://127.0.0.1:8000/api/parse-batch"

with open(os.path.join(EVAL_DIR, "gold.json"), encoding="utf-8") as f:
    cases = {c["id"]: c for c in json.load(f)["cases"]}

order_in = ["E10", "E06", "E01"]  # 低 → 中 → 高（逆序输入）
joined = "\n\n".join(cases[i]["text"] for i in order_in)
payload = json.dumps({"text": joined}).encode("utf-8")
req = urllib.request.Request(
    API, data=payload, headers={"Content-Type": "application/json"}, method="POST"
)
t0 = time.time()
with urllib.request.urlopen(req, timeout=1200) as resp:
    body = json.loads(resp.read().decode("utf-8"))
elapsed = round(time.time() - t0, 2)

id_by_text = {c["text"]: cid for cid, c in cases.items()}
out = {
    "elapsed_sec": elapsed,
    "input_order": order_in,
    "input_urgency": [cases[i]["gold"]["urgency"] for i in order_in],
    "returned": [
        {
            "seq": i + 1,
            "id": id_by_text.get(r.get("original")),
            "urgency": r.get("urgency"),
            "retried": r.get("retried"),
            "parse_failed": r.get("parse_failed"),
        }
        for i, r in enumerate(body.get("results", []))
    ],
}
with open(os.path.join(EVAL_DIR, "batch-sort-shuffled.json"), "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=2)
print(
    "shuffled batch done elapsed=%.1fs returned=%s"
    % (elapsed, [(r["id"], r["urgency"]) for r in out["returned"]]),
    flush=True,
)
