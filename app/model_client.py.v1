# -*- coding: utf-8 -*-
"""模型接入层：通过 OpenAI 兼容端点调用本地推理服务（Spark-X2.6-4B）。

配置（环境变量）：
  MODEL_ENDPOINT  OpenAI 兼容端点基地址，默认 http://127.0.0.1:8080/v1
                  （实际请求 POST {MODEL_ENDPOINT}/chat/completions）
  MODEL_NAME      模型名，默认 Spark-X2.6-4B
  MODEL_TIMEOUT   单次请求超时（秒），默认 120

抽取结果若无法解析为 JSON，会自动重试一次；仍失败则返回带
parse_failed 标记的兜底记录，绝不静默吞掉。
"""

import json
import os
import re
import urllib.error
import urllib.request

MODEL_ENDPOINT = os.environ.get("MODEL_ENDPOINT", "http://127.0.0.1:8080/v1")
MODEL_NAME = os.environ.get("MODEL_NAME", "Spark-X2.6-4B")
MODEL_TIMEOUT = float(os.environ.get("MODEL_TIMEOUT", "120"))

# 抽取 Prompt（与 PLAN.md 一致，复现说明中全文引用此常量）
SYSTEM_PROMPT = (
    "你是一个灾害求助信息抽取助手。给定一条原始求助文本，只输出一个 JSON 对象，"
    "不要输出任何其他文字、解释或 Markdown 代码块。\n"
    "JSON 字段固定为：\n"
    "- location：求助地点（字符串，原文未提及填 \"未知\"）\n"
    "- people_count：被困/受影响人数（整数，未知填 0）\n"
    "- people_notes：人员构成说明，如老人、儿童、伤病员等（字符串，未知填 \"\"）\n"
    "- needs：需求列表（字符串数组，如 [\"饮用水\", \"药品\"]，未知填 []）\n"
    "- urgency：紧急程度，只能是 \"高\"、\"中\"、\"低\" 之一"
    "（存在人身危险、被困、重伤或急需医疗为\"高\"；物资紧缺但暂无生命危险为\"中\"；其余为\"低\"）\n"
    "- contact：联系方式（字符串，原文没有填 \"\"）\n"
    "- summary：一句话中文摘要（不超过 40 字）\n"
    "- summary_en：上面摘要的一句话英文版本（须为语法正确、用词自然的完整英文句子）\n"
    "只输出 JSON。"
)

RETRY_HINT = "\n注意：上一次输出无法解析为 JSON。本次请只输出 JSON 对象本身，不要任何其他内容。"

URGENCY_VALUES = ("高", "中", "低")
URGENCY_RANK = {"高": 0, "中": 1, "低": 2}

_FIELD_DEFAULTS = {
    "location": "未知",
    "people_count": 0,
    "people_notes": "",
    "needs": [],
    "urgency": "中",
    "contact": "",
    "summary": "",
    "summary_en": "",
}


def _chat_completion(messages):
    """向 OpenAI 兼容端点发一次 chat/completions 请求，返回 assistant 文本。"""
    url = MODEL_ENDPOINT.rstrip("/") + "/chat/completions"
    payload = {
        "model": MODEL_NAME,
        "messages": messages,
        "temperature": 0.1,
        "stream": False,
    }
    # Spark-X2.6 的聊天模板默认开启思考模式：不关思考时全部输出进入
    # reasoning 通道、content 为空，且单条耗时可达 ~680 秒（见
    # logs/model-runtime.md 冒烟测试第一轮）。OpenAI 兼容端点用
    # reasoning_effort="none" 关闭（Ollama 端点已实测有效）。
    # 仅当模型名含 "spark" 时附加该参数：本应用只为 Spark-X2.6-4B 而写，
    # 真实部署的模型名（Ollama 登记名 spark-x2.6-4b、HF 名 Spark-X2.6-4B）
    # 都含 spark；而对不认识该字段的严格端点平白附加未知参数有被拒（400）
    # 的风险，换其它模型联调时不应受此影响。
    if "spark" in MODEL_NAME.lower():
        payload["reasoning_effort"] = "none"
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=MODEL_TIMEOUT) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    return body["choices"][0]["message"]["content"]


def _extract_json(text):
    """从模型输出中尽量稳健地取出 JSON 对象；失败抛 ValueError。"""
    if text is None:
        raise ValueError("empty model output")
    s = text.strip()
    # 去掉可能的 ```json 代码块围栏
    s = re.sub(r"^```(?:json)?\s*", "", s)
    s = re.sub(r"\s*```$", "", s)
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        pass
    # 兜底：截取第一个 { 到最后一个 } 再试
    start, end = s.find("{"), s.rfind("}")
    if start != -1 and end > start:
        return json.loads(s[start : end + 1])
    raise ValueError("no JSON object found in model output")


def _normalize(obj):
    """把模型给的 JSON 规整成固定字段结构。"""
    rec = dict(_FIELD_DEFAULTS)
    if not isinstance(obj, dict):
        return rec
    for key in _FIELD_DEFAULTS:
        if key in obj and obj[key] is not None:
            rec[key] = obj[key]
    # people_count 规整为 int
    pc = rec["people_count"]
    if isinstance(pc, str):
        m = re.search(r"\d+", pc)
        pc = int(m.group()) if m else 0
    try:
        rec["people_count"] = int(pc)
    except (TypeError, ValueError):
        rec["people_count"] = 0
    # needs 规整为字符串列表
    needs = rec["needs"]
    if isinstance(needs, str):
        needs = [x.strip() for x in re.split(r"[、,，;；]", needs) if x.strip()]
    elif isinstance(needs, list):
        needs = [str(x) for x in needs]
    else:
        needs = []
    rec["needs"] = needs
    # urgency 只允许 高/中/低
    if rec["urgency"] not in URGENCY_VALUES:
        rec["urgency"] = "中"
    # 其余字段强制为字符串
    for key in ("location", "people_notes", "contact", "summary", "summary_en"):
        rec[key] = str(rec[key])
    return rec


def extract(text):
    """抽取一条求助文本，返回结构化记录。

    记录在固定字段之外还包含：
      original     原始文本
      retried      是否发生过一次重试
      parse_failed 两次都无法解析（或端点不可用）时为 True，需人工核对
      error        失败原因（成功时为 ""）
    """
    base_messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": text},
    ]
    retried = False
    last_error = ""
    for attempt in (1, 2):
        messages = base_messages
        if attempt == 2:
            retried = True
            messages = base_messages + [
                {"role": "user", "content": RETRY_HINT.strip()}
            ]
        try:
            raw = _chat_completion(messages)
            rec = _normalize(_extract_json(raw))
            rec.update(
                original=text, retried=retried, parse_failed=False, error=""
            )
            return rec
        except Exception as exc:  # 端点不可用 / 超时 / JSON 解析失败 都走重试与标注
            last_error = "%s: %s" % (type(exc).__name__, exc)
    # 两次都失败：兜底记录，明确标注待人工核对
    rec = dict(_FIELD_DEFAULTS)
    rec["summary"] = text.strip()[:40]
    rec.update(
        original=text,
        retried=retried,
        parse_failed=True,
        error=last_error,
    )
    return rec
