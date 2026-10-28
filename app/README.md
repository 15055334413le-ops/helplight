# 援光 HelpLight — 灾害求助信息结构化与分诊台

HER Hack-Astron #7 参赛作品。把散落在社交平台、群聊、电话记录里的口语化灾害求助文本，
逐条抽取为结构化字段（地点、人数、人员构成、需求、紧急程度、联系方式、中英双语摘要），
生成按紧急程度排序的分诊清单，供一线社区志愿者与民间救援协调员人工复核后使用。

抽取、紧急程度研判与摘要全部由 **Spark-X2.6-4B 在本地推理**完成，应用本身不调用任何云端 API。

> **边界声明**：本工具为原型工具，**不替代 110 / 119 / 120 与官方救援调度**；
> 模型抽取结果**必须经人工复核**后才能用于救援行动；
> 联系方式等个人信息**仅在本机处理**，不上传任何云端。

## 环境要求

- Python 3.10 或更高版本（仅用标准库，**无第三方依赖，无需 pip install**）
- 一个 OpenAI 兼容的本地推理端点（提供 Spark-X2.6-4B 服务），或先用仓库自带 stub 联调
- 任意现代浏览器

## 目录结构

```
app/
├── server.py        # Web 应用主服务（标准库 http.server）
├── model_client.py  # 模型接入层：端点配置、抽取 Prompt、JSON 解析与重试
├── examples.py      # 3 条内置脱敏虚构示例（洪涝 / 地震 / 独居老人断药）
├── stub_server.py   # 联调用假端点（关键词启发式，不代表模型真实效果）
└── static/
    └── index.html   # 单页前端（原生 HTML/CSS/JS，无外部资源）
```

## 快速开始（先用 stub 跑通全流程）

开两个终端：

```bash
# 终端 1：启动 stub 假端点（默认 127.0.0.1:8080）
cd app
python3 stub_server.py

# 终端 2：启动应用（默认 127.0.0.1:8000）
cd app
python3 server.py
```

浏览器打开 http://127.0.0.1:8000 ：

1. 在「② 批量分诊清单」点 **一键载入 3 条示例**，再点 **解析全部并生成清单**，
   应看到 3 条按紧急程度排序的清单（stub 启发式下：洪涝=高、独居老人断药=高、地震安置点=中）；
2. 在「① 单条求助解析」粘贴任意一条求助文本，点解析，应看到结构化卡片；
3. 点 **导出 Markdown / 导出 CSV**，浏览器会下载 `helplight-triage.md` / `helplight-triage.csv`。

## 配置

全部配置走环境变量，在启动 `server.py` 前设置：

| 环境变量 | 默认值 | 说明 |
|---|---|---|
| `MODEL_ENDPOINT` | `http://127.0.0.1:8080/v1` | OpenAI 兼容端点基地址；应用向 `{MODEL_ENDPOINT}/chat/completions` 发 POST 请求 |
| `MODEL_NAME` | `Spark-X2.6-4B` | 请求体中的 `model` 字段，须与推理服务加载的模型名一致 |
| `MODEL_TIMEOUT` | `120` | 单次模型请求超时（秒） |
| `HOST` / `PORT` | `127.0.0.1` / `8000` | 应用监听地址（默认仅本机可访问） |
| `STUB_HOST` / `STUB_PORT` | `127.0.0.1` / `8080` | 仅 stub_server.py 使用 |

## 切换到真实模型端点（Spark-X2.6-4B）

stub 只用于联调界面与流程，抽取质量不代表模型效果。真实运行时：

1. 用任一 OpenAI 兼容方式在本地起 Spark-X2.6-4B 推理服务，例如：
   - **llama.cpp**：将模型转为 GGUF 后
     `llama-server -m Spark-X2.6-4B-Q4_K_M.gguf --host 127.0.0.1 --port 8080`
     （llama-server 原生提供 `/v1/chat/completions` 兼容接口）
   - **Ollama**：`ollama serve` 后默认端点为 `http://127.0.0.1:11434/v1`，
     需把 `MODEL_NAME` 设为 Ollama 中的实际模型名
2. 按端点地址设置环境变量再启动应用，例如 llama.cpp 默认端口：

   ```bash
   MODEL_ENDPOINT=http://127.0.0.1:8080/v1 MODEL_NAME=Spark-X2.6-4B python3 server.py
   ```

3. 启动后先访问 http://127.0.0.1:8000/api/health ，确认返回的
   `model_endpoint` / `model_name` 与预期一致，再进行解析。

模型版本（复现实验时请对齐）：`XHToken/Spark-X2.6-4B`，
Hugging Face revision `66e3ae7bee54e0a523d692cb8ef841f35409807b`。

## 抽取 Prompt 与输出约定

系统提示词固定在 `model_client.py` 的 `SYSTEM_PROMPT` 常量中（复现时请勿改动，
改动会改变抽取结果）。模型被要求**只输出一个 JSON 对象**，字段固定为：

| 字段 | 类型 | 说明 |
|---|---|---|
| `location` | string | 求助地点，未提及为 `"未知"` |
| `people_count` | int | 被困/受影响人数，未知为 0 |
| `people_notes` | string | 人员构成（老人、儿童、伤病员等） |
| `needs` | string[] | 需求列表 |
| `urgency` | string | 只能是 `高` / `中` / `低` |
| `contact` | string | 联系方式，没有则为空串 |
| `summary` | string | 一句话中文摘要（≤40 字） |
| `summary_en` | string | 一句话英文摘要 |

健壮性处理（`model_client.py`）：

- 输出会被尝试解析为 JSON（兼容 ```json 代码块围栏与前后杂文的截取兜底）；
- **解析失败自动重试一次**（追加「只输出 JSON」的提醒），结果中以 `retried=true` 标注；
- 两次都失败（或端点不可用）时返回兜底记录并标注 `parse_failed=true` 与失败原因，
  前端会以红色警告提示人工核对原文——**绝不静默丢弃任何一条求助**。

## 接口一览

| 方法与路径 | 请求体 | 响应 |
|---|---|---|
| `GET /` | — | 单页前端 HTML |
| `GET /api/health` | — | `{"ok": true, "model_endpoint": ..., "model_name": ...}` |
| `GET /api/examples` | — | `{"examples": [{"tag": ..., "text": ...}, ...]}` |
| `POST /api/parse` | `{"text": "一条求助文本"}` | `{"result": {结构化记录}}` |
| `POST /api/parse-batch` | `{"text": "多条文本，以空行分隔"}` | `{"results": [记录...], "count": n}`，已按紧急程度 高>中>低 排序 |

结构化记录在上表字段之外还包含 `original`（原文）、`retried`、`parse_failed`、`error`。

批量分隔规则：以空行（两个及以上换行，中间可含空白）分隔每条求助文本。

## 导出格式

- **Markdown**：`helplight-triage.md`，含边界声明、分诊表格与原文列表；
- **CSV**：`helplight-triage.csv`，UTF-8 带 BOM，Excel 可直接打开；
  两个导出均在浏览器端由当前清单数据生成，不经过服务器。

## 局限（诚实评估）

- 4B 量级模型在复杂口语、方言、多地点混杂的文本上仍可能抽错字段，
  这正是本工具坚持「人工复核」定位的原因；
- 紧急程度是模型依据提示词规则的研判，不等同于专业分诊结论；
- 批量解析为逐条串行调用，条数很多时耗时较长；
- stub 模式仅验证流程，其启发式结果不可用于评估模型效果。
