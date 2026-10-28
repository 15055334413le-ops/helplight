#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""重拍截图 5（E12 捐赠反转）：首版 capture.py 误用了一段非评估集的捐赠文本，
本脚本改用 gold.json cases 中正式评估的 E12 原文（合肥市包河区淝河镇，20 箱）
在真实端点重跑并覆盖 shot5-e12.png。"""
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = Path(__file__).resolve().parent
E12_TEXT = ("你好，咨询一下，我们社区在合肥市包河区淝河镇这边，想给安置点捐一批"
            "矿泉水和方便面，大概20箱，请问送到哪里、找谁对接？")

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 1440, "height": 1050})
    page.goto("http://127.0.0.1:8000")
    page.wait_for_load_state("networkidle")
    t0 = time.time()
    page.fill("#singleInput", E12_TEXT)
    page.click("#btnSingle")
    page.wait_for_function(
        "() => document.getElementById('singleStatus').textContent.startsWith('完成')",
        timeout=600_000)
    secs = round(time.time() - t0, 1)
    text = page.evaluate(
        "() => document.getElementById('singleResult').innerText")
    (BASE / "shots" / "e12-live-result-text.txt").write_text(text, encoding="utf-8")
    page.screenshot(path=str(BASE / "shots" / "shot5-e12.png"), full_page=True)
    print(f"shot5 reshot in {secs}s")
    print(text)
    browser.close()
