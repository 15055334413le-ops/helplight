# 援光 HelpLight × Spark-X2.6-4B 真实端点联调记录

> 日期：2026-10-23（CST）。目的：把 app（纯标准库 Web 应用）与真实 Spark-X2.6-4B 推理服务
> （Ollama OpenAI 兼容端点）端到端跑通，验证单条/批量抽取的字段真实性、排序与耗时。
> 模型运行细节见 `logs/model-runtime.md`；原始响应全文见本目录
> `integration-single-20261023.json`、`integration-batch-20261023.json`、
> `integration-batch-v2-20261023.json`。

## 1. 联调配置

| 项 | 值 |
|---|---|
| 推理服务 | Ollama 0.40.9，`ollama serve`（pid 7843，测试前已在运行，未重启） |
| 模型端点 | `http://127.0.0.1:11434/v1`（OpenAI 兼容） |
| 模型 | `spark-x2.6-4b`（官方 GGUF Q4_K_M，sha256 已校验，见 model-runtime.md） |
| 探活 | `GET /api/tags` 与 `GET /v1/models` 均正常返回，模型已登记 |
| app 启动 | `MODEL_ENDPOINT=http://127.0.0.1:11434/v1 MODEL_NAME=spark-x2.6-4b MODEL_TIMEOUT=900 python3 server.py`（监听 127.0.0.1:8000；MODEL_TIMEOUT 由默认 120 放大到 900 以容纳 VM 慢速推理） |
| app 健康检查 | `GET /api/health` 返回的 endpoint / model_name 与配置一致 |
| 测试数据 | app 内置 3 条脱敏虚构示例（洪涝被困 / 地震安置点 / 独居老人断药） |

## 2. 代码改动（本次联调共 2 处，均在 app 层）

### 2.1 `model_client.py`：请求体补 `reasoning_effort: "none"`（关思考模式）

- **问题**：原 `_chat_completion` 未带该参数。Spark-X2.6 聊天模板默认开思考，
  不关时输出全进 reasoning 通道、content 为空且单条耗时 ~680 秒（冒烟测试第一轮实测，见 model-runtime.md）。
- **改法**：`payload` 中条件附加 `"reasoning_effort": "none"`，**仅当 `MODEL_NAME` 小写含
  `"spark"` 时才附加**。理由：本应用只为 Spark-X2.6-4B 而写，真实部署的模型名
  （Ollama 登记名 `spark-x2.6-4b`、HF 名 `Spark-X2.6-4B`）都含 spark，覆盖全部真实场景；
  而对不认识该字段的严格 OpenAI 兼容端点平白附加未知参数有被拒（400）的风险，
  换其它模型联调时不应受此影响。代码注释已写明此理由。
- **效果验证**：联调全部请求一次成功（见下，retried 全为 false），耗时回落到 ~90–122 秒/条，
  与冒烟测试关思考后的 124 秒一致，确认参数已生效。

### 2.2 `model_client.py`：SYSTEM_PROMPT 的 summary_en 措辞微调（详见第 5 节）

字段定义未动，仅给 summary_en 加了一句质量要求；改动前后全文差异与复测对比见第 5 节。

## 3. 单条联调（POST /api/parse，洪涝示例）

- **耗时：121.67 秒**（含模型推理；与冒烟测试 124.38 秒同量级，VM 2 核 ~1.7 tok/s 所致）
- **retried：false**（一次解析成功；模型输出带 ```json 围栏，app 的围栏剥除解析实测兼容）
- **parse_failed：false**
- 原始输出（app 归一化后的记录）：

```json
{
  "location": "临江市望江区滨江街道幸福里小区3号楼一楼",
  "people_count": 4,
  "people_notes": "两位老人，一个三岁小孩",
  "needs": ["饮用水", "食物", "冲锋舟"],
  "urgency": "高",
  "contact": "138****2167",
  "summary": "临江市幸福里小区3号楼一楼一家四口被困，有老人小孩，急需救援。",
  "summary_en": "A family of four is trapped on the first floor of Building 3, Xingfuli Community, in Wangjiang District, Linjiang City, with elderly and a three-year-old child, and urgently needs rescue."
}
```

- **8 字段逐项核对（对照原文）**：
  - location ✓ 精确到楼栋楼层，与原文一致
  - people_count = 4 ✓（原文「一家四口」）
  - people_notes ✓（两位老人 + 三岁小孩；原文构成无误）
  - needs ✓ 三项（饮用水 / 食物 / 冲锋舟）覆盖原文全部诉求，无遗漏无编造
  - urgency = 高 ✓（被困 + 水淹一楼半 + 老人幼儿，符合提示词「高」的判定规则）
  - contact ✓ 脱敏号码原样保留
  - summary ✓ 32 字（≤40 字要求），准确无幻觉
  - summary_en ✓ 内容准确、语法通顺
- **结论：8/8 字段正确。**

## 4. 批量联调（POST /api/parse-batch，3 条示例）— 第一轮（原提示词）

- **总耗时：274.54 秒**（约 4.6 分钟，3 条串行；平均约 92 秒/条——短文本比洪涝条快）
- **3 条均为 retried=false、parse_failed=false**
- 排序结果：洪涝（高）→ 地震（高）→ 老人断药（高），同级保持输入顺序（稳定排序符合代码预期）。
  本批 3 条真实模型判定均为「高」，**没有出现中/低样本，跨级排序未能用真实输出验证**；
  跨级排序逻辑已由此前 stub 联调覆盖（stub 口径：洪涝=高、老人=高、地震=中，排序正确），
  且排序为服务端纯代码稳定排序（`URGENCY_RANK`）。如实记录为本轮覆盖缺口。
- 逐条字段核对：
  - **条 1 洪涝**：与单条结果逐字一致，8/8 正确。
  - **条 2 地震安置点**：location ✓；people_count = 60 ✓（原文「大概60名」）；
    people_notes「包含学生、受伤老师」✓（略简：原文为十几名学生、一位老师腿伤）；
    needs 四项 ✓（担架 / 急救药品 / 帐篷 / 棉被，原文全覆盖）；contact ✓；
    summary 34 字 ✓；summary_en ✓ 准确通顺。
    **urgency = 高**：README 中 stub 启发式的预期是「中」，真实模型判「高」。
    对照提示词规则——「存在人身危险、被困、重伤**或急需医疗**为高」，
    原文有伤员且明确急需担架与急救药品，判「高」是规则的正确适用，**不是口径漂移**；
    stub 的「中」只是关键词启发式的粗糙预期，不作为真实口径。
  - **条 3 独居老人断药**：location ✓ 精确到门牌；people_count = 1 ✓；
    people_notes「78岁，有高血压」✓；needs = [降压药] ✓（原文核心需求；「送药上门」的配送动作未单列，可接受）；
    urgency = 高 ✓（78 岁高血压、断药一日、头晕厉害，属急需医疗，符合规则）；
    contact ✓ 连「（邻居张阿姨）」备注都完整保留；
    summary ✓ 准确（约 33 字）。
    **summary_en 有一处明确语法错误**：`"...who is severely dizziness."`
    （severely 后误用名词 dizziness，应为 severely dizzy / suffering from severe dizziness）。
    内容真实无幻觉，但语法错误成立 → 触发第 5 节的提示词修正。

## 5. 提示词修正与复测（仅允许改 SYSTEM_PROMPT 措辞，字段定义不变）

- **改动**（`model_client.py` SYSTEM_PROMPT，summary_en 字段行）：
  - 改前：`- summary_en：上面摘要的一句话英文版本`
  - 改后：`- summary_en：上面摘要的一句话英文版本（须为语法正确、用词自然的完整英文句子）`
  - 字段名、类型、其余 7 个字段定义、urgency 判定规则**全部未动**；改前全文已留存备查。
- **复测**：重启 app 后重跑同一批量 3 条，**总耗时 291.59 秒**，3 条仍全部
  retried=false、parse_failed=false。原始记录：`integration-batch-v2-20261023.json`。
- **改动前后差异**：
  - 条 3 summary_en：`severely dizziness` 的错误句 →
    `"The requester is away from home, and a 78-year-old with hypertension has run out of antihypertensive medication and is dizzy, needing community volunteers to deliver medication."`
    **语法正确、语义完整，目标问题已修正** ✓。条 3 的 summary 中文也随之改写，仍准确（33 字内）。
  - 条 2：全部字段与摘要和改前**逐字一致**，无漂移。
  - 条 1：结构化字段与改前一致；summary / summary_en 为同义改写、内容准确。
    一处如实记录的微瑕：新版 summary_en 用 `"A family of four ... and urgently need rescue"`
    （集合名词 family 后接 need，主谓一致在严格语法下略有瑕疵，英式用法可接受），
    与改前版本（`needs rescue`）属同量级小问题，**不构成退化**。
- **结论：保留改动。** 目标语法错误修复，其余字段零退化。
  同时说明 4B 模型英文摘要仍偶有微瑕，投稿的「诚实评估」部分应如实写明。

## 6. 结论

- **联调通过**：app 与真实 Spark-X2.6-4B 端点端到端跑通——单条 1 次、批量 2 轮共 7 次真实
  抽取全部一次解析成功（retried 全 false、parse_failed 全 false），无一次触发兜底记录。
- 抽取质量：本轮 3 条示例 × 8 字段，结构化字段（地点/人数/构成/需求/紧急度/联系方式）
  **全部正确**；中文摘要全部达标；英文摘要 1 处语法错误经提示词微调后修复。
- 性能（VM 2 核 / 7GB，Q4_K_M CPU 推理）：单条 ~92–122 秒，批量 3 条 ~275–292 秒。
  速度瓶颈在 VM 算力（~1.7 tok/s），非应用或模型问题；正式 Demo 建议迁移到用户 PC
  （32 线程）录制，或在视频中如实标注耗时。
- 未改动：模型与量化（仍为官方 Q4_K_M GGUF）、字段定义、urgency 判定规则、app 其他逻辑。

## 7. 进程处置（测试后状态）

- **app server：已关闭**（测试用进程 pid 13466 已终止，8000 端口已释放）。
  重新启动命令见第 1 节配置表（在 `~/workspace/spark-her/app/` 下执行）。
- **Ollama 模型服务：保留运行**（`ollama serve`，pid 7843，端点 127.0.0.1:11434），
  供后续评估样本与 Demo 录制直接使用；探活 `curl http://127.0.0.1:11434/api/tags`。
- app 运行日志：`logs/app-server.log`；ollama 日志：`logs/ollama-serve.log`。

## 8. 遗留问题

1. **跨级排序未获真实输出验证**：本轮 3 条示例真实判定全为「高」。后续评估样本（PLAN 计划
   ≥10 条）应刻意包含中/低紧急度文本，补齐高>中>低的真实排序证据。
2. **英文摘要偶有微瑕**：提示词已加质量要求且复测达标，但 4B 模型仍可能出现主谓一致等
   小问题；投稿时在局限部分如实声明，产品定位坚持「人工复核」。
3. **VM 推理慢**：单条约 2 分钟。批量大样本评估（≥10 条约 20 分钟+）与 Demo 录制建议
   迁移到用户 PC 执行，VM 仅作开发与小样验证。
4. README 中 stub 预期的「地震安置点=中」与真实模型「高」不一致——这是 stub 启发式与
   真实模型按规则研判的正常差异（见第 4 节），README 描述的是 stub 行为，不需修改，
   但向评委演示时勿用 stub 结果代表模型效果（README 已有此声明）。
5. `MODEL_TIMEOUT` 代码默认仍为 120 秒：真实端点部署时必须按第 1 节放大（本次用 900），
   否则 VM 上单条必然超时走兜底。后续可考虑把默认值改到 600 并同步 README 配置表。
