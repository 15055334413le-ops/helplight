# 援光 HelpLight — 应用自测记录

- 时间：2026-10-23（本地 VM，Python 3.12.3）
- 方式：stub 假端点（app/stub_server.py，127.0.0.1:8080）+ 应用本体（app/server.py，127.0.0.1:8000，默认配置未改）
- 说明：本轮验证的是**全流程联调**；stub 用关键词启发式生成抽取结果，其质量不代表 Spark-X2.6-4B 真实效果。真实模型联调待端点就绪后另行记录。

## 步骤与结果

### 0. 语法与启动
- `python3 -m py_compile server.py model_client.py examples.py stub_server.py` → 通过。
- 启动 stub 与应用均无报错；应用启动日志打印端点 `http://127.0.0.1:8080/v1`、模型名 `Spark-X2.6-4B`。

### 1. 健康检查 GET /api/health
- 返回 `{"ok": true, "app": "HelpLight", "model_endpoint": "http://127.0.0.1:8080/v1", "model_name": "Spark-X2.6-4B"}` → ✅ 与默认配置一致。

### 2. stub 端点直连 POST /v1/chat/completions
- 以洪涝示例文本请求，返回标准 chat.completion 结构，`message.content` 为合法 JSON 字符串：
  location=临江市望江区滨江街道幸福里小区3号楼一楼，people_count=4，people_notes=老人、儿童，
  needs=[饮用水，食物，药品，冲锋舟，救援队]，urgency=高，contact=138****2167 → ✅ 形状与字段齐全。
  （注：needs 中「药品」「救援队」为 stub 关键词误触发，属已知的 stub 启发式噪声，真实模型不适用此结论。）

### 3. 单条解析 POST /api/parse（洪涝示例）
- 返回结构化记录与 stub 抽取一致，附加标注 `retried=false, parse_failed=false, error=""`，`original` 原文完整回带 → ✅
- 前端对应渲染为结构化卡片（含紧急程度徽标），代码路径已核对。

### 4. 示例载入 GET /api/examples
- 返回 3 条：洪涝被困 / 地震安置点 / 独居老人断药，均为脱敏虚构文本 → ✅
- 前端「一键载入」按钮将其以空行连接填入批量框，代码路径已核对。

### 5. 批量解析 POST /api/parse-batch（3 条示例，空行分隔）
- 返回 `count=3`，排序结果：① 洪涝（高）② 独居老人断药（高）③ 地震安置点（中）→ ✅ 符合 高>中>低、同级保持输入顺序。
- 各条字段完整：地震条 people_count=60、contact=139****8803；断药条 location=安澜市南桥区桂中花园7栋502、urgency=高 → ✅

### 6. 前端页面与导出（静态核对）
- `GET /` 返回完整单页；页面含顶部边界声明与页脚声明（「不替代 110 / 119 / 120」「抽取结果需人工复核」「仅在本机处理」均在位）。
- 导出逻辑在位：`buildCsv` / `buildMarkdown` / `download`（Blob 浏览器下载，CSV 带 BOM）函数齐全，导出按钮在批量解析成功后才启用。
- ⚠️ 未做真实浏览器点击导出实测（本机无浏览器自动化环境），列入 Demo 录制前的人工验收项。

### 7. 异常路径：模型端点不可用时的标注
- 另起应用实例（端口 8001），`MODEL_ENDPOINT` 指向无服务端口模拟端点宕机，POST /api/parse：
- 返回兜底记录 `parse_failed=true, retried=true`，`error="URLError: <urlopen error [Errno 111] Connection refused>"`，summary 为原文前 40 字兜底 → ✅ 符合「重试一次 + 明确标注、绝不静默丢弃」的设计。

## 结论

单条解析、批量分诊排序、示例载入、健康检查、异常标注全部通过；导出为浏览器端实现，已完成静态核对，待 Demo 阶段在真实浏览器中做一次点击验收。自测后所有测试进程已关闭、端口已释放。
