# Spark-X2.6-4B 本地运行记录（HER Hack-Astron #7 · 援光 HelpLight）

> 记录日期：2026-10-23（CST）。本文件记录模型来源、运行路线、冒烟测试全过程与真实输出，保证可复现。

## 1. 路线调查（为什么选这条路线）

| 路线 | 调查结果 | 结论 |
|---|---|---|
| Ollama 官方库 `SparkLLM/Spark-X2.6-4B` | 存在，但只有 `latest` 一个 tag，其 manifest 的模型层是 **BF16 GGUF 8,229,921,024 字节（≈8.2GB）**，超过本机 VM 内存（7GB），且下载量过大 | ✗ 本机不可用（PC 32GB 或可，但先走 VM 路线） |
| HF 官方 GGUF `XHToken/Spark-X2.6-4B-GGUF` | 官方仓库，提供 Q4_K_M（3.54GB）/ Q8_0（4.38GB）/ BF16（8.23GB）三种量化 | ✓ **选用 Q4_K_M** |
| llama.cpp `convert_hf_to_gguf.py` 自行转换 | 上游 llama.cpp 自 **b10828** 起原生支持 `spark2_5` 架构（官方 README 注明）；但官方已提供现成 GGUF，无需自转 | 备选（未用） |
| transformers + 自定义代码（trust_remote_code） | 需下载 5 个 safetensors 分片（BF16 ≈8GB）+ torch/transformers，VM 内存不足以 BF16 推理 | ✗ 本机不可用（PC 备选） |

**最终路线**：官方 Q4_K_M GGUF → 导入本机 Ollama（其内置 llama.cpp 引擎）→ OpenAI 兼容接口推理。

## 2. 模型来源与版本

- 权重源头（比赛指定）：Hugging Face `XHToken/Spark-X2.6-4B`，revision（commit sha）`66e3ae7bee54e0a523d692cb8ef841f35409807b`
  - 架构 `Spark2_5ForCausalLM`（model_type `spark2_5`，自定义代码 modeling_spark.py / configuration_spark.py），36 层，hidden 2560，vocab 131072，原始精度 BF16，Apache-2.0
- 实际使用的 GGUF：Hugging Face 官方仓库 `XHToken/Spark-X2.6-4B-GGUF`，revision `fe31f8d64890302cc3a1d365d700357b4b75ba77`
  - 文件 `Spark-X2.6-4B-Q4_K_M.gguf`，精确大小 **3,543,441,312 字节**，Q4_K_M 量化
  - **完整性校验通过**：本地 sha256 `91cb2811aebb47ac916aa619d27d4cdd7f4143106b7917accb8ead4cd7f5cbd9` 与 HF LFS 官方哈希一致
  - 下载地址：`https://huggingface.co/XHToken/Spark-X2.6-4B-GGUF/resolve/fe31f8d64890302cc3a1d365d700357b4b75ba77/Spark-X2.6-4B-Q4_K_M.gguf`（经 hf-mirror 跳转同一 CDN 对象；长连接会被代理中途掐断，最终用 `models/download_gguf.sh` 以 HTTP Range 分 18 块下载、逐块校验大小后合并）
  - 本地路径：`~/workspace/spark-her/models/Spark-X2.6-4B-Q4_K_M.gguf`
- 运行框架：**Ollama 0.40.9**（官方要求 ≥0.34.1；服务端内置 llama.cpp 引擎，GGUF 格式）
- 本地模型名：`spark-x2.6-4b`（由 `models/Modelfile` 导入，`num_ctx 8192`）

## 3. 硬件与环境

- 本机 VM：2 核 CPU / 7 GB RAM / 95 GB 空闲磁盘，Ubuntu，Python 3.12.3；纯 CPU 推理，无 GPU
- 网络：出网经运行时 egress 代理（环境变量 `http_proxy/https_proxy`）——**关键坑**：Ollama 的 systemd 服务不继承代理环境变量，直连 registry.ollama.ai 时报 `tls: first record does not look like a TLS handshake`；解决办法是停用 systemd 服务，改用脚本以当前 shell 环境（带代理变量）启动 `ollama serve`

## 4. 启动命令（可复现）

```bash
# 1) 启动推理服务（带代理 env；不要用 systemd 的 ollama.service）
bash ~/workspace/spark-her/app/run-model-server.sh
# 服务端点：OpenAI 兼容 http://127.0.0.1:11434/v1 （原生 API http://127.0.0.1:11434/api）

# 2) 首次导入模型（只需一次）
cd ~/workspace/spark-her/models && ollama create spark-x2.6-4b -f Modelfile

# 3) 冒烟测试
python3 ~/workspace/spark-her/app/smoke_test.py
```

## 5. 冒烟测试（求助信息结构化抽取）

- 固定系统提示：「你是灾害求助信息整理助手。从求助文本中抽取信息，只输出 JSON，字段：location（地点）、people_count（人数，数字，未知填 null）、people_notes（人员构成）、needs（需求数组）、urgency（紧急程度：高/中/低）、contact（联系方式，无则 null）、summary（一句话中文摘要）、summary_en（一句话英文摘要）。」
- 样例输入（虚构脱敏）：「急！芜湖市南陵县三里镇这边河水涨上来了，我家一楼进水，我和我妈还有一个三岁小孩被困在二楼，家里没吃的了，孩子有点发烧，我妈腿脚不方便走不了路。我的电话是138xxxx0000，快点来人！」
- 推理参数：temperature 0.0，max_tokens 1024，num_ctx 8192

### 第一轮（思考模式未关 — 失败，重要教训）
- 参数：temperature 0.0，max_tokens 1024，未设置 reasoning 控制
- 结果：耗时 **680.59 秒**，生成满 1024 token 被截断，`content` 为**空字符串**，JSON 解析失败
- 原因：Spark-X2.6 的聊天模板默认开启思考模式（官方 README："Thinking is enabled by default"），全部输出进了 reasoning 通道。**抽取类任务必须关思考**：Ollama 原生 API 用 `"think": false`，OpenAI 兼容端点用 `"reasoning_effort": "none"`（均已实测有效，短问答验证：关思考后直接回答「合肥」，2 token / 总耗时 6.9 秒）
- 原始记录：`logs/smoke-test-20261023-071248.json`

### 第二轮（关思考 — 成功 ✅）
- 参数：temperature 0.0，max_tokens 1024，`reasoning_effort: "none"`，端点 `POST http://127.0.0.1:11434/v1/chat/completions`
- 耗时：**124.38 秒**（prompt 161 token，生成 194 token；纯生成速度约 1.7 token/s —— 2 核 VM 的真实速度，批量场景慢，正式演示建议在用户 PC 上跑或接受单条约 2 分钟）
- 模型原始输出（原文，含 ```json 代码围栏，应用层需剥围栏后再解析）：

```json
{
  "location": "芜湖市南陵县三里镇",
  "people_count": 3,
  "people_notes": "1名成年人、1名老人（腿脚不便）、1名三岁小孩",
  "needs": ["紧急救援", "食物补给", "儿童发烧处理"],
  "urgency": "高",
  "contact": "138xxxx0000",
  "summary": "芜湖市南陵县三里镇有3人因河水上涨被困二楼，存在食物短缺、儿童发烧及老人行动不便的紧急情况，需尽快救援。",
  "summary_en": "Three people are trapped on the second floor in Sanli Town, Nanling County, Wuhu City due to rising water, with food shortage, a child with fever and an elderly person with mobility issues, requiring urgent rescue."
}
```

- 原始记录：`logs/smoke-test-20261023-071526.json`（脚本 `app/smoke_test.py` 自动保存 raw + parsed + 耗时 + usage）

### 输出质量评估
- **JSON 合法性**：合法（剥除代码围栏后可直接 `json.loads`），8/8 字段齐全，无多余字段
- **字段正确性**：location 精确到镇 ✓；people_count=3 ✓（我+母亲+三岁小孩）；people_notes 构成与原文一致并标注老人腿脚不便 ✓；needs 三项（紧急救援/食物补给/儿童发烧处理）覆盖原文全部诉求 ✓；urgency=高（被困+幼儿发烧+老人行动不便，判定合理）✓；contact 原样保留脱敏号码 ✓；中英摘要均准确无幻觉 ✓
- **注意点**：① 输出带 ```json 围栏，应用层解析前需剥除；② 本机速度约 1.7 tok/s，单条抽取约 2 分钟，为 VM 2 核所限，非模型问题；③ 内存占用：模型加载后进程常驻约 3.9 GB（`ollama ps` size 3,906,679,602），VM 7 GB 内存可运行但余量小

## 6. 运维备注
- Ollama 安装：官方脚本装至 /usr/local，版本 0.40.9；`systemctl` 的 ollama.service 已停用（不带代理 env 会拉取失败），统一用 `app/run-model-server.sh` 启动
- 模型在 Ollama 中的登记：`spark-x2.6-4b:latest`，ID `59b057c0aa6d`，family `spark2_5`，参数量 4.4B，量化 Q4_K_M，runner llamacpp，context 8192
- 零成本确认：全程本地推理，未调用任何付费/云端 API；未做任何公开发布或 GitHub 写操作

