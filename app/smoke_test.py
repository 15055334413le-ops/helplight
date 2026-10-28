#!/usr/bin/env python3
"""援光 HelpLight — Spark-X2.6-4B 冒烟测试：求助信息结构化抽取（固定 Prompt）。

调用本地 Ollama 的 OpenAI 兼容接口，零外部依赖（仅标准库），零云端调用。
用法: python3 smoke_test.py [--base http://127.0.0.1:11434/v1] [--model spark-x2.6-4b]
原始响应与解析结果写入 ../logs/smoke-test-*.json / .md
"""
import argparse
import json
import re
import time
import urllib.request
from datetime import datetime
from pathlib import Path

SYSTEM_PROMPT = "你是灾害求助信息整理助手。从求助文本中抽取信息，只输出 JSON，字段：location（地点）、people_count（人数，数字，未知填 null）、people_notes（人员构成）、needs（需求数组）、urgency（紧急程度：高/中/低）、contact（联系方式，无则 null）、summary（一句话中文摘要）、summary_en（一句话英文摘要）。"

SAMPLE_TEXT = "急！芜湖市南陵县三里镇这边河水涨上来了，我家一楼进水，我和我妈还有一个三岁小孩被困在二楼，家里没吃的了，孩子有点发烧，我妈腿脚不方便走不了路。我的电话是138xxxx0000，快点来人！"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:11434/v1")
    ap.add_argument("--model", default="spark-x2.6-4b")
    ap.add_argument("--temperature", type=float, default=0.0)
    ap.add_argument("--max-tokens", type=int, default=1024)
    ap.add_argument("--text", default=SAMPLE_TEXT)
    args = ap.parse_args()

    payload = {
        "model": args.model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": args.text},
        ],
        "temperature": args.temperature,
        "max_tokens": args.max_tokens,
        # Spark-X2.6 默认开启思考模式：首轮测试中 1024 个 token 全部进了 reasoning 通道，
        # content 为空。抽取任务必须关思考（Ollama OpenAI 端点用 reasoning_effort:"none"）。
        "reasoning_effort": "none",
        "stream": False,
    }
    req = urllib.request.Request(
        args.base.rstrip("/") + "/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=1200) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    elapsed = time.time() - t0

    message = body["choices"][0]["message"]
    raw = message.get("content") or ""
    finish_reason = body["choices"][0].get("finish_reason")
    usage = body.get("usage", {})

    parsed, parse_err = None, None
    m = re.search(r"\{.*\}", raw, re.S)
    if m:
        try:
            parsed = json.loads(m.group(0))
        except json.JSONDecodeError as e:
            parse_err = str(e)
    else:
        parse_err = "no JSON object found in output"

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    logdir = Path(__file__).resolve().parent.parent / "logs"
    out = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "endpoint": args.base,
        "model": args.model,
        "temperature": args.temperature,
        "max_tokens": args.max_tokens,
        "system_prompt": SYSTEM_PROMPT,
        "input_text": args.text,
        "elapsed_seconds": round(elapsed, 2),
        "usage": usage,
        "finish_reason": finish_reason,
        "full_message": message,
        "raw_output": raw,
        "parsed": parsed,
        "parse_error": parse_err,
    }
    jf = logdir / f"smoke-test-{stamp}.json"
    jf.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"elapsed: {elapsed:.2f}s  usage: {usage}")
    print("--- raw output ---")
    print(raw)
    print("--- parsed ---")
    print(json.dumps(parsed, ensure_ascii=False, indent=2) if parsed else f"PARSE FAILED: {parse_err}")
    print(f"saved: {jf}")


if __name__ == "__main__":
    main()
