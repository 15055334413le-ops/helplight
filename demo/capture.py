#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""援光 HelpLight — 演示录屏 + 截图清单拍摄（Playwright 无头 Chromium）。

全程驱动真实应用（http://127.0.0.1:8000，真实 Spark-X2.6-4B 端点），
按 demo/SHOT-LIST.md 拍摄截图 1/2/3/4/5/6，并录制完整操作视频（webm）。
所有解析均为真实模型调用，耗时即真实耗时；结果 JSON 同步归档。
"""
import json
import sys
import time
from pathlib import Path

BASE = Path(__file__).resolve().parent
ROOT = BASE.parent
sys.path.insert(0, str(ROOT / "app"))
from examples import EXAMPLES  # noqa: E402

from playwright.sync_api import sync_playwright  # noqa: E402

APP = "http://127.0.0.1:8000"
SHOTS = BASE / "shots"
EXPORTS = SHOTS / "exports"
VIDEO_RAW = BASE / "video-raw"
for d in (SHOTS, EXPORTS, VIDEO_RAW):
    d.mkdir(parents=True, exist_ok=True)

E12_TEXT = ("你好，咨询一下，我们社区在合肥市包河区淝河镇这边，想给安置点捐一批"
            "矿泉水和方便面，大概20箱，请问送到哪里、找谁对接？")

log = {"started_at": time.strftime("%Y-%m-%d %H:%M:%S"), "steps": []}


def note(step, **kw):
    entry = {"step": step, "at": time.strftime("%H:%M:%S"), **kw}
    log["steps"].append(entry)
    print(json.dumps(entry, ensure_ascii=False), flush=True)


def wait_status(page, el_id, prefix, timeout_ms):
    page.wait_for_function(
        """([id, prefix]) => {
            const el = document.getElementById(id);
            return el && el.textContent.startsWith(prefix);
        }""",
        arg=[el_id, prefix],
        timeout=timeout_ms,
    )


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(
            viewport={"width": 1440, "height": 1050},
            record_video_dir=str(VIDEO_RAW),
            record_video_size={"width": 1440, "height": 1050},
            accept_downloads=True,
        )
        page = ctx.new_page()

        # 截图 1：界面全貌
        page.goto(APP)
        page.wait_for_load_state("networkidle")
        page.screenshot(path=str(SHOTS / "shot1-home.png"), full_page=True)
        note("shot1-home")

        # 截图 2：单条解析（洪涝示例）
        t0 = time.time()
        page.fill("#singleInput", EXAMPLES[0]["text"])
        page.click("#btnSingle")
        wait_status(page, "singleStatus", "完成", 600_000)
        single_secs = round(time.time() - t0, 1)
        single_result = page.evaluate(
            "() => { const el = document.getElementById('singleResult'); return el ? el.innerText : ''; }")
        (SHOTS / "single-result-text.txt").write_text(single_result, encoding="utf-8")
        page.screenshot(path=str(SHOTS / "shot2-single.png"), full_page=True)
        note("shot2-single", seconds=single_secs)

        # 截图 3：批量分诊清单（3 条示例）
        t0 = time.time()
        page.click("#btnExamples")
        page.wait_for_function(
            "() => document.getElementById('batchStatus').textContent.includes('已载入')",
            timeout=30_000)
        page.click("#btnBatch")
        wait_status(page, "batchStatus", "完成", 900_000)
        batch_secs = round(time.time() - t0, 1)
        try:
            rows = page.evaluate("() => currentRows")
        except Exception:
            rows = None
        if rows:
            (BASE / "outputs" / "parse-batch-3examples-live-20261027.json").write_text(
                json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
        page.screenshot(path=str(SHOTS / "shot3-batch.png"), full_page=True)
        note("shot3-batch", seconds=batch_secs, rows=len(rows) if rows else None)

        # 导出并保存（截图 4 的素材）
        with page.expect_download(timeout=30_000) as dl:
            page.click("#btnExportMd")
        dl.value.save_as(str(EXPORTS / "helplight-triage.md"))
        with page.expect_download(timeout=30_000) as dl:
            page.click("#btnExportCsv")
        dl.value.save_as(str(EXPORTS / "helplight-triage.csv"))
        note("exports-saved")

        # 截图 4：导出的 Markdown 打开画面
        page2 = ctx.new_page()
        page2.goto((EXPORTS / "helplight-triage.md").as_uri())
        page2.wait_for_timeout(800)
        page2.screenshot(path=str(SHOTS / "shot4-export.png"), full_page=True)
        page2.close()
        note("shot4-export")

        # 截图 5：E12 捐赠反转（失败案例，原样呈现）
        t0 = time.time()
        page.bring_to_front()
        page.fill("#singleInput", E12_TEXT)
        page.click("#btnSingle")
        wait_status(page, "singleStatus", "完成", 600_000)
        e12_secs = round(time.time() - t0, 1)
        page.screenshot(path=str(SHOTS / "shot5-e12.png"), full_page=True)
        note("shot5-e12", seconds=e12_secs)

        # 截图 6：模型运行证据（/api/health）
        page.goto(APP + "/api/health")
        page.wait_for_timeout(600)
        page.screenshot(path=str(SHOTS / "shot6-health.png"))
        note("shot6-health")

        video = page.video.path() if page.video else None
        ctx.close()
        browser.close()
        log["video_raw"] = str(video)
        note("done", video_raw=video)

    (BASE / "capture-log-20261027.json").write_text(
        json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
