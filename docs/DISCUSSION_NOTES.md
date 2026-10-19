# 讨论记录：Tongkai/Siyun 集成分支 + 网络搜索调研

日期：2026-10-19 · 对象分支：`origin/feature/rag-materials-sync-tongkai的最新的`（95a83a3，含 Siyun 的 `feature/rag-siyun-clean` 和 `integration/main-rag-semantic-routing`）
状态：**仅记录，尚未修改任何代码**。

---

## A. 已决定的方向（待实现）

| # | 决定 | 要点 |
|---|---|---|
| A1 | 个人病情：从"强制本地"改为**可选的"假设化改写"** | 把"我有哮喘，能运动吗？"改写成"一个有哮喘的人能运动吗？"再发云端；改写失败或不确定时仍留在本地。见 §C1 |
| A2 | 泄漏检查：隐私执行**放在云端发送关口**，不放在路由器里 | 路由器保持只看"能力/证据"（符合 Tongkai 的范围）；发送前检查恢复并增加"个人病情"规则。见 §C2 |
| A3 | 云端不可用 → **退回本地回答，并给出明确提示** | 区分三种原因：未配置云端 / 云端出错或超时 / 被隐私检查拦下。见 §C3 |

## B. 需要和 Tongkai、Siyun 讨论的问题

### B1. 必须改（合并前）
1. **隐私**：语义路由下删除了 `cloud_safe` 强制本地，并跳过了发送前泄漏检查（`generate.py` 中 `found = [] if semantic`）。→ 按 A1/A2 处理。
2. **测试覆盖**：`conftest.py` 让所有测试强制用 stub 路由，原有隐私测试（包括强制上云的端到端测试）没有覆盖语义路由。→ 增加语义路由下的隐私测试；E4 审计要真正走语义路由。
3. **出错默认方向**：任何故障都选云端，且云端失败不回退本地，直接 503；`analyze_route` 出错会终止整个请求。没有云端 key + 模型未下载时，大量问题会报错。→ 按 A3 处理；`analyze_route` 出错改为跳过。
4. **云端回答拿不到课程资料**：判定云端时检索被跳过；路由还会把 `ctx.passages` 改写成"仅通过验证的段落"（可能为空）。→ 检索总是执行；资料筛选作为独立步骤，云端请求也带上已通过的课程资料。
5. **启动依赖**：`app.rag` 加载所有检索器，`medical_hybrid` 在导入时需要 sklearn，没装时整个程序起不来（即使配置 stub）。→ 重依赖改为用到时才导入。
6. **追问超长报错**：MiniLM 约 256 词元上限，超出抛错 → 判云端。→ 截断历史，而不是报错。

### B2. 建议改 / 需要讨论
7. **路由职责**：路由器直接给出 `target`，分数是事后填的；生成、检索里出现多处 `if impl == "semantic"`。是否回到"路由器只打分、系统按阈值决策"？
8. **学生自选 LR/SVM**：属于实现细节，建议改为教师设置或仅用于实验。
9. **进度面板**：默认对学生显示"云端需求 23%"等内部数值。建议默认关闭或只显示简化阶段。
10. **流式接口只推进度不推回答**；学习记录更新放在流里，客户端断开会丢失。
11. **训练标签是人为设定的策略**（`prototype_policy`），95% 准确率只代表学会了规则。需要 E5（用真实本地模型回答评分）来证明路由价值。
12. **"需要最新证据"标签**：云端模型并不比本地"新"，除非接入网络搜索（见 §D）。
13. **检索查询拼接了历史发言**：可能被前面的话题带偏，需 Siyun 确认。
14. **两次问题分析**（understand 用 Qwen、analyze_route 用 MiniLM），以后考虑合并。
15. **延迟**：交叉编码器在 CPU 上最多 32 个窗口，需实测完整流程（冒烟：首次 3.6 s，之后约 0.45 s，不含证据验证全量）。
16. **代码库卫生**：移除 `restore_git.ps1`、`BASE_VERSIONS.json`、`setup_local.py`、`开始使用.md` 等交接文件；`.env.example` 改回通用值；分支名避免中文。
17. **资料来源**：MedlinePlus（NLM）内容，报告中注明出处。
18. **E3/E4 评估程序与 CI**：评估程序用真实配置（语义路由），CI 中没有模型资产且没有云端 key，E3 快速测试很可能失败。

---

## C. 三个决定的具体做法（草案）

### C1. 个人病情的"假设化改写"
- **目的**：现在病情被替换成 `<HEALTH_DETAIL_1>`，云端看不到病情，回答质量差；完全留本地又浪费云端能力。改写后病情保留、与"我"的关联去掉。
- **示例**：
  - "我有哮喘，跑步前要注意什么？" → "一个有哮喘的人跑步前一般要注意什么？"
  - "我妈妈血压 150/95，严重吗？" → "成年人血压读数在 150/95 左右通常意味着什么？"（读数也是个人健康数据，改写为范围或一般描述）
- **实现思路**：
  1. 新配置 `privacy.health_detail_policy: local_only | generalize`，默认 `local_only`。
  2. `generalize` 时由本地模型（Qwen，隐私边界内）改写为第三人称一般性问题；规则只做兜底。
  3. 改写后**再跑一遍隐私过滤**，并检查：没有第一人称 + 病情的组合（我/我的/我妈…有 X）、没有具体读数/剂量/日期、没有姓名等。任何一项不通过 → 留本地。
  4. 医疗安全的"建议就医"仍按**原始问题**判断（已经是这样：`needs_referral` 看原始的 PII 识别结果）。
  5. 云端回答是第三人称，学生端直接展示即可；不需要"还原"病情。
- **风险与待确认**：
  - 罕见病 + 小班级仍有理论上的再识别风险（云端不知道是谁，但仍属于健康信息外流）。
  - 是否符合课程伦理要求，需要问教授；默认保持 `local_only`，`generalize` 作为可选项并在报告里说明。
  - 需要评估：E4 增加"第一人称病情不出边界"检查；用 E3 方式比较改写前后回答质量。

### C2. 泄漏检查要改的地方
1. **恢复**语义路由下的发送前检查（删掉 `[] if semantic` 分支）。
2. 发送前检查增加 **个人病情规则**：
   - `local_only`：只要原始问题里识别到 `HEALTH_DETAIL`，就不发云端，退回本地并提示。
   - `generalize`：检查改写后的问题（C1 第 3 点），不通过就退回本地。
   - 这样隐私规则在"发送关口"统一执行，路由器里不需要任何隐私分支。
3. 发送后检查器（pii_leak/profile_leak）同样覆盖语义路由；新增"病情泄漏"检查器（或并入 pii_leak）。
4. **测试**：conftest 不再强制所有测试用 stub；隐私测试至少各跑一遍 stub 和 semantic；端到端测试覆盖"病情问题 + 语义路由判云端"。
5. **E4 审计**：
   - 走真实（语义）路由；
   - 新增检查：原问题含病情时，云端记录里不能有第一人称病情表述（`local_only` 下根本不能有记录）；
   - 进度事件（SSE）里不能出现问题原文或资料原文。
6. 检查确认：云端请求（`CloudRequest`）没有加入历史发言或路由诊断（目前分支里没有，保持）。

### C3. 云端不可用时退回本地并提示
- **行为**：语义路由选择云端，但云端未配置 / 出错 / 超时 / 被隐私检查拦下 → 用本地模型回答，不报错。
- **提示（按原因区分）**：
  - 未配置云端："当前未连接云端模型，这个问题由本地模型回答。"
  - 云端出错或超时："云端模型暂时不可用，这个回答由本地模型生成。"
  - 隐私拦截："为保护隐私，这个问题只在本地处理。"
  - 路由判断本地能力不足时额外加一句："这个问题可能超出本地模型的能力范围，请结合下方资料来源核对。"
- **记录**：日志记录"路由选云端、实际本地回答、原因"，教师日志页显示（现有 "answered by" 已支持）；流式进度增加 `fallback` 事件。
- **配置**：保留 `llm.cloud.fallback_to_local`（默认 true）；做路由实验时可关掉。这满足 Tongkai "不要静默回退"的要求——回退是公开提示的。

---

## D. 网络搜索调研（2026-10）

### D1. 为什么要考虑
语义路由有"需要最新证据"一项，但云端大模型本身不联网，并不比本地"新"。要真正回答"最新指南"类问题，需要**检索层**接入外部来源，而不是靠路由到云端。

### D2. 选项对比

| 类型 | 服务 | 价格（以官网为准） | 隐私/数据保留 | 备注 |
|---|---|---|---|---|
| 权威医学源（免费） | **MedlinePlus Health Topics Web Service**（NLM） | 免费，无需注册 | 公共服务 | 关键词检索，返回排序后的健康主题摘要；每天更新（周二至周六）；限速 85 次/分钟/IP；须注明来源为 MedlinePlus.gov |
| | **PubMed E-utilities**（NCBI） | 免费 | 公共服务 | 无 key 3 次/秒，有 key 10 次/秒；分支里已有 `pubmed.py`（只发送固定主题词） |
| 通用搜索 API | **Brave Search API** | 约 $5/千次 | 标准套餐查询记录最多保留 90 天；企业套餐可零保留（ZDR） | 唯一自有独立索引 |
| | **Tavily** | 约 $0.005–0.008/次（按 credit） | 官方 FAQ 声称零保留，第三方说法有冲突，需书面确认 | 返回已清洗、适合 LLM 的内容；据称 2026 年被 Nebius 收购 |
| | **Exa** | 约 $7/千次 | 需确认 | 语义搜索 |
| | **Perplexity Search API / Sonar** | Search API 约 $5/千次；Sonar 另按 token 计费 | 官方文档称 Sonar API 零保留，只保留计费元数据 | Sonar 直接返回带引用的答案 |
| 模型自带搜索 | **OpenAI `web_search` 工具** | 各来源报价不一（约 $10–25+/千次 + token） | 默认存储 30 天（store=true），零保留需组织级 ZDR（第三方来源，需核实） | 和云端模型绑定 |
| | **Gemini 搜索接地** | 早期 $35/千次；Vertex AI 新价约 $14/千次（2026-01 起） | 需确认 | 和 Gemini 绑定 |

（价格和保留政策多来自第三方文章，彼此有出入；选型前必须看各家当前官网和隐私条款。）

### D3. 隐私和质量要点
- **任何搜索查询都会离开隐私边界**：只能发送去除个人信息、并且"一般化"的查询（同 C1），最好用固定词表（主题 + 关注点），像 `pubmed.py` 那样不发送学生原句。
- 优先选择**零数据保留**的服务，并在报告中说明。
- 网络结果**未经审核**，和"只给学生看审核过的内容"原则冲突：应标记为"未审核来源"、显示出处、限定可信域名（medlineplus.gov、nih.gov、cdc.gov、who.int、canada.ca 等；各服务是否支持域名限制需逐一确认）。
- 结果应缓存，避免重复查询。

### D4. 初步建议
1. **首选**：MedlinePlus Web Service + PubMed（免费、权威、和课程主题一致，PubMed 已有代码），作为"最新证据"的检索来源，结果走现有证据验证流程。
2. **需要更广的网络搜索时**：Brave（价格低、独立索引、有 ZDR 选项）或 Tavily（返回内容适合 LLM），只发送一般化查询，限定可信域名。
3. **不建议**直接用云端模型自带的搜索：查询会和学生问题一起发给模型提供方，隐私控制更难。
4. 成本估计：假设 50 名学生 × 每人 20 问 × 10% 需要最新资料 ≈ 100 次搜索，按 $5/千次 不到 1 美元。

### 来源
- [Best web search APIs for AI agents in 2026 (dev.to)](https://dev.to/tonywangca/best-web-search-apis-for-ai-agents-in-2026-42jf)
- [Eden AI: best web search APIs for AI agents](https://www.edenai.co/post/best-web-search-apis-for-ai-agents)
- [Tavily alternatives (websearchapi.ai)](https://websearchapi.ai/blog/tavily-alternatives)
- [OpenAI web search tool docs](https://developers.openai.com/api/docs/guides/tools-web-search)
- [OpenAI community: web search pricing](https://community.openai.com/t/how-can-i-accurately-know-the-number-of-times-web-search-tool-is-used-in-a-single-response-api-call/1365861)
- [Parallel: OpenAI web search vs Parallel vs Exa vs Tavily](https://parallel.ai/articles/openai-web-search-vs-parallel-vs-exa-vs-tavily-how-to-choose.md)
- [MedlinePlus web service (NLM)](https://www.nlm.nih.gov/medlineplus/webservices.html)
- [MedlinePlus for developers](https://medlineplus.gov/about/developers)
- [Tavily FAQ](https://docs.tavily.com/faq/faq)
- [Tavily community: data storage](https://community.tavily.com/t/how-tavily-api-store-data-related-to-user-information-query-and-query-response/284)
- [Brave: Search API zero data retention](https://brave.com/blog/search-api-zero-data-retention/)
- [Brave Search API privacy notice](https://api-dashboard.search.brave.com/privacy-policy)
- [Perplexity API privacy & security](https://docs.perplexity.ai/guides/privacy-security)
- [NCBI E-utilities documentation](https://www.ncbi.nlm.nih.gov/books/NBK25497/)
- [Google: Grounding with Google Search launch](https://developers.googleblog.com/gemini-api-and-ai-studio-now-offer-grounding-with-google-search/)
- [Vertex AI pricing](https://cloud.google.com/vertex-ai/generative-ai/pricing?hl=it)

---

## E. 按 MVP 评分要求调整隐私计划（2026-10-19）

依据课程 MVP 讲义和 Deliverable B 说明：
- **B1**：指标带单位；对比测试与目标值用**同一套可测量指标**；目标值有理想值与及格值并说明理由。
- **B2**：每个子系统多个方案，用计算/模拟对照目标值评估，选出方案；征求客户意见。
- **B3**：软件原型要有每个子功能的流程图及其连接；列出关键假设、资源、时间。
- **B4**：MVP 用来**验证关键假设**，不必做最终原型；测试结果用"预期 vs 实际"表格。
- **B5**：Jira；每个任务一个负责人；同一人任务不重叠；依赖任务排在前置之后；按进度更新日期。

调整：升级方案（LLM 二次检查、GLiNER、假设化改写）推到 MVP 之后，作为 B2 的候选方案；MVP 前只做 E6 基线评估、
对比测试、流程图和报告章节。

### E6 结果（`eval/privacy-filter/results/report.md`）

| 配置 | 泄漏率（正例） | 难例泄漏率 | 最低类型召回 | 误屏蔽 | 病情判断 | 延迟 p50 |
|---|---|---|---|---|---|---|
| Presidio 原版 | 65.9% | 60.0% | 0% | 11.4% | 81.1% | 5 ms |
| 我们 + 小模型 | 8.5% | 40.0% | 80.0% | 0% | 97.7% | 4 ms |
| 我们 + 大模型 | 1.2% | 33.3% | 95.2% | 0% | 97.7% | 5 ms |
| **我们 + 大模型 + 本人身份（应用配置）** | **1.2%** | **20.0%** | **95.2%** | **0%** | **97.7%** | **5 ms** |

- 唯一正例漏检："My blood pressure meds make me dizzy"（所有权规则只允许"my"和药物之间隔一个词）。
- 难例漏检：逐位空格的学号、无分隔符电话、"AT … DOT" 写法的邮箱。
- 超出范围类型 2/8 被识别（地址、生日、健康卡号、邮编、年龄等未覆盖）。
- 结论：关键假设 A2–A5 成立；A1（泄漏率）达到及格线，未达理想值；必须使用大模型。

（上表是第一版 140 条测试集的结果，已被下面的完整评估取代。）

### E6 完整评估（10/19，用户要求做完整流程）

测试集：主集 404 条（开发用，规则在它上面调过，数字偏乐观）+ 两个留出集各 102 条（gemma4 自由写、人工标注；
v2 在规则冻结后才生成，是最终无偏测试）。

| 配置（留出集 v2） | 问题级泄漏 | 发往云端：身份信息 / 个人病情 | 病情敏感度 / 特异度 | 误屏蔽 | 延迟 p50 |
|---|---|---|---|---|---|
| Presidio 原版 | 92.5% | 54.8% / 86.0% | 0% / 100% | 0% | 7 ms |
| MVP 配置 | 68.8% | 3.2% / 48.4% | 43.8% / 100% | 0% | 7 ms |
| **全部规则（A5，现应用配置）** | **47.3%** | **1.1% / 21.5%** | **75.0% / 100%** | **0%** | **7 ms** |
| + spaCy trf | 68.8% | 1.1% / 48.4% | 43.8% / 100% | 0% | 28 ms |
| 规则 + GLiNER | 30.1% | 0% / 20.4% | 76.2% / 54.5% | 44.4% | 90 ms |
| **规则 + 本地 LLM 二次检查** | **34.4%** | **0% / 12.9%** | **85.0% / 90.9%** | **0%** | **627 ms** |

结论（要和组员、客户讨论）：
1. **身份信息（姓名、学号、邮箱、电话）已经基本解决**：留出集上只有 1.1% 的问题会把身份信息带到云端，加 LLM 后为 0。
2. **个人病情和成绩是真正的短板**：学生描述自己病情的方式太多样，词表规则在自由文本上只认出约 3/4 的个人病情问题；
   漏掉的会**去掉身份后**发往云端（约 1/5）。加本地 LLM 二次检查降到约 1/8，但每次云端请求多约 0.6 秒。
3. GLiNER 误屏蔽太多（普通问题 20–44% 被改），Transformer 模型对我们的类型没有提升 → 都不采用。
4. 回答质量：占位符对身份信息影响小（4.37/5）；把病情词遮掉会明显变差（3.07）；"假设化改写"（一个有哮喘的人…）保持 4.47。
   → 病情问题要么留本地（现状），要么改写成假设问题再上云（需客户/伦理同意），不要简单遮掉。
5. 决策矩阵：按现权重 A5 规则得分最高（3.75），隐私权重提到 50% 时 LLM 方案追平或领先 → **由客户决定能接受多少残余风险**。
6. 端到端（E4 跑 E6 的 274 道题）：身份/画像/字段泄漏 0；217 个云端请求里 15 个含 PII、61 个个人病情问题里 5 个上云，正好是 E6 预测的那批漏检（混淆写法、小写人名、错别字、多轮追问）。
   另外发现并修复：存储的回答用区分大小写的替换，"Asthma is…" 没被屏蔽 → 已改为不区分大小写的整词替换。剩余：本地回答单独提到的病情词（"inhaler"）仍会存储，见 TODO。
