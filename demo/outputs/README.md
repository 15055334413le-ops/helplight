# Demo 真实输出归档 — 来源说明

> 采集时间：2026-10-23 17:30:24–17:33:01（CST）。本目录全部文件来自一次
> 真实运行：应用连接本机 Ollama 上的 Spark-X2.6-4B 实际推理，无 stub 数据。

## 运行环境（本次采集）

| 项 | 值 |
|---|---|
| 模型 | `XHToken/Spark-X2.6-4B`，HF revision `66e3ae7bee54e0a523d692cb8ef841f35409807b` |
| 量化文件 | 官方 GGUF Q4_K_M（`models/Spark-X2.6-4B-Q4_K_M.gguf`，sha256 已校验，见 `logs/model-runtime.md`） |
| 推理服务 | Ollama 0.40.9，端点 `http://127.0.0.1:11434/v1`，登记名 `spark-x2.6-4b`（digest `59b057c0aa6d41f5576fa112621254633e8169f79c2a2ded58f51f6cc0ac27ad`） |
| 应用启动 | `MODEL_ENDPOINT=http://127.0.0.1:11434/v1 MODEL_NAME=spark-x2.6-4b MODEL_TIMEOUT=900 python3 server.py`（`app/` 目录，监听 127.0.0.1:8000） |
| 抽取 Prompt | v1（`app/model_client.py` 的 SYSTEM_PROMPT；v2 复测后已回滚，与 `model_client.py.v1` 逐字节一致，见 `app/PROMPT-CHANGELOG.md`） |
| 采集方式 | 脚本依次调用 `GET /api/examples`、`POST /api/parse`、`POST /api/parse-batch`、`POST /api/parse`，响应体原样落盘为 JSON；示例文本与前端「一键载入示例」同源（`app/examples.py`） |

## 文件清单

| 文件 | 生成方式 | 耗时 | 标记 |
|---|---|---|---|
| `parse-single-flood.json` | `POST /api/parse`，输入为内置洪涝示例，响应体原样保存 | 43.66 秒 | retried=false，parse_failed=false，urgency=高，8 字段齐全 |
| `parse-batch-3examples.json` | `POST /api/parse-batch`，输入为 3 条内置示例以空行分隔，响应体原样保存 | 89.03 秒 | 3 条均为 retried=false、parse_failed=false；紧急度 高/高/高，同级保持输入顺序 |
| `helplight-triage.md` | 由上条批量真实结果生成：按前端 `app/static/index.html` 中 `buildMarkdown` 的逻辑逐字复刻（未走浏览器 UI），格式与界面「导出 Markdown」下载文件一致 | — | 含边界声明、清单表格与原文列表 |
| `helplight-triage.csv` | 同上，按前端 `buildCsv` 逻辑复刻生成；UTF-8 带 BOM、`\r\n` 行尾，与界面「导出 CSV」下载文件一致 | — | Excel 可直接打开 |
| `parse-e12-donation.json` | `POST /api/parse`，输入为评估样本 E12 原文（取自 `eval/gold.json`），响应体原样保存 | 24.39 秒 | retried=false，parse_failed=false；**已知失败复现**（见下） |

## E12 本次复跑与 v1 评估输出的对照

- **核心错误复现**：needs = [饮用水， 方便面]——把捐赠方拟捐出的物资列为
  需求（标准答案为空），语义方向反转与 v1 评估（`eval/results.json` 中 E12
  条目、`eval/EVAL-REPORT.md` 第 6 节案例 1）一致。
- 细节形态略有不同：本次中文摘要主语正确（「社区拟向淝河镇安置点捐赠……」），
  但仍含「需对接送餐事宜」的歪曲（原文是对接捐赠，非送餐）；英文摘要把
  淝河拼作「Fenhe」。v1 评估输出则是摘要主语错位 +「Ansettlement」拼写误。
  录制讲解时以本文件实际内容为准，v1 原稿作对照。
- urgency 判「低」正确（与标准答案一致）。

## 备注

- 本次采集时模型已热加载，耗时（单条 43.66 秒、批量约 30 秒/条）短于冷
  启动联调记录（单条约 90–125 秒）；耗时取决于硬件与模型驻留状态，抽取
  内容口径不变。视频中标注耗时请以录制当次实际为准。
- 采集结束后 app server 已关闭，Ollama 保持运行。
