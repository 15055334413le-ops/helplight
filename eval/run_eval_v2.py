#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""援光 HelpLight 正式评估运行器：逐条调 /api/parse 跑真实模型，
原始结果（含每条耗时、retried/parse_failed 标记）增量写入 results-v2.json。
不做任何评分（评分在人工对照 gold.json 后单独进行）。
"""
import json
import os
import time
import urllib.request

EVAL_DIR = os.path.dirname(os.path.abspath(__file__))
API = "http://127.0.0.1:8000/api/parse"
CLIENT_TIMEOUT = 1500  # 服务端 MODEL_TIMEOUT=900，客户端留足余量

with open(os.path.join(EVAL_DIR, "gold.json"), encoding="utf-8") as f:
    cases = json.load(f)["cases"]

out_path = os.path.join(EVAL_DIR, "results-v2.json")
results = []
if os.path.exists(out_path):
    with open(out_path, encoding="utf-8") as f:
        results = json.load(f)
done_ids = {r["id"] for r in results}
print("already done:", sorted(done_ids), flush=True)

for case in cases:
    if case["id"] in done_ids:
        continue
    payload = json.dumps({"text": case["text"]}).encode("utf-8")
    req = urllib.request.Request(
        API, data=payload, headers={"Content-Type": "application/json"}, method="POST"
    )
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=CLIENT_TIMEOUT) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        rec = body.get("result", {})
        err = ""
    except Exception as exc:  # 记录客户端层失败，继续下一条
        rec = {}
        err = "%s: %s" % (type(exc).__name__, exc)
    elapsed = round(time.time() - t0, 2)
    results.append(
        {
            "id": case["id"],
            "tag": case["tag"],
            "gold_urgency": case["gold"]["urgency"],
            "elapsed_sec": elapsed,
            "retried": rec.get("retried"),
            "parse_failed": rec.get("parse_failed"),
            "error": rec.get("error", err),
            "result": rec,
        }
    )
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(
        "[%s] %s elapsed=%.1fs urgency=%s parse_failed=%s"
        % (case["id"], case["tag"], elapsed, rec.get("urgency"), rec.get("parse_failed")),
        flush=True,
    )

print("ALL DONE", len(results), flush=True)
