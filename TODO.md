# TODO

更新：2026-10-19 · 详细背景见 [docs/DISCUSSION_NOTES.md](docs/DISCUSSION_NOTES.md)（集成分支审查 + 网络搜索调研）。
负责人：Z = Zhenyan，T = Tongkai，S = Siyun。截止：MVP 10/21 · Beta 11/11 · 视频 11/25 · Design Day 12/3 · Final 12/13。

---

## 0. 按 MVP 评分要求调整后的隐私子系统计划（10/19 起，负责人 Z，分支 `feature/privacy-eval`）

依据：`DTI_ELG_GNG 5902 - MVP.pdf` 与 `Instructions_Project_MVP2`（B1 指标 + 同指标对比测试，B2 方案评分表，B3 子功能流程图，
B4 原型用于验证关键假设、结果用"预期 vs 实际"表格，B5 Jira 单一负责人、不重叠、依赖）。

- [x] E6 测试集 140 条（`eval/privacy-filter/make_cases.py` → `cases.jsonl`）— Jira G1-81
- [x] E6 评估 + 对比测试（Presidio 原版 / 我们 + 小模型 / 我们 + 大模型 / + 本人身份）— Jira G1-82
  - 结果：应用配置泄漏率 1.2%（及格线）、最低类型召回 95.2%、误屏蔽 0%、病情判断 97.7%、延迟 5 ms；Presidio 原版泄漏 65.9%
- [x] 安装 `en_core_web_lg`；本地 `.env` 改用大模型（小模型泄漏 8.5%）
- [x] 隐私过滤流程图 `docs/diagrams/privacy-filter.{drawio,svg,png}`（生成脚本 `make_privacy_filter.py`）
- [x] 报告章节草稿 `docs/report/privacy_subsystem.md`（目标值表、对比测试、方案评分表、详细设计、关键假设、预期 vs 实际）
- [ ] 把章节并入 MVP 报告（10/21）— Jira G1-83（进行中）
- [ ] 客户反馈会：病情去身份后能否上云、补哪些类型、目标值是否可接受（10/22–10/23）— G1-84
- [x] 修复"my blood pressure meds"漏检 — G1-85（10/19 提前完成）
- [x] 补识别器：健康卡号、邮编、SIN/病历号、生日、地址、法语（人名/病情/成绩）— G1-86（10/19 提前完成；待客户确认优先级）
- [x] 测试集扩到 404 条（正例、反例、难例、法语、多轮、范围外）+ 两个独立留出集（gemma4 写、人工标注）— G1-87
- [x] 比较升级方案：大模型 / trf / GLiNER / 规则+GLiNER / 规则+Qwen 二次检查；逐条消融；屏蔽对回答质量影响；E4 端到端 — G1-88
- [ ] **留出集结论：规则对身份类（学号/电话/邮箱/人名）泛化好，对病情和成绩泛化差** → 决定是否上 Qwen 二次检查（C5）或"病情一律本地"兜底 — 讨论
- [ ] 留出集 v2 的 7 条有争议标注请组员复核（`eval/privacy-filter/holdout_review.md`）；50 条抽检也请人工复核（`spot_check.md`）— 组员
- [ ] 留在本地的个人病情问题：存储的回答仍可能单独出现病情词（"inhaler"、"150/95"），因为屏蔽的是较长的片段（"my inhaler"）→ 存储前对 HEALTH_DETAIL 片段里的病情词/读数也做替换（E4 `--e6` 发现）— Z
- [ ] 预先存在的 19 个测试失败（内容未审核相关，HEAD 上同样失败）— 另开任务
- [ ] Jira 子任务表单加上 Start date / Due date 字段（项目设置 → Issue types），再把描述里的计划日期填进去 — Z
- [ ] Jira 其他任务按实际进度更新日期（作业 B5.4 要求）— 全员

---

## 1. 集成分支 `feature/rag-materials-sync-tongkai的最新的`（合并前必须完成）

### 1.1 隐私（决定：隐私规则放在"发往云端的关口"，路由器不含隐私分支）
- [x] 恢复语义路由下的发送前泄漏检查（删除 `generate.py` 中 `found = [] if semantic`）— Z（10/19，在 `feature/rag-siyun-mvp-validation`）
- [x] 发送前检查增加"个人病情"规则：`local_only` 模式下原问题含 `HEALTH_DETAIL` → 不发云端，本地回答并提示 — Z
- [x] 新配置 `privacy.health_detail_policy: local_only | generalize`，默认 `local_only` — Z
- [x] `generalize` 模式：本地 Qwen 把问题改写成第三人称一般性问题（"一个有哮喘的人……"）— Z（`app/privacy/generalize.py`）
  - [x] 改写后再跑隐私过滤；检查无"第一人称 + 病情"、无具体读数/剂量/日期、无姓名；不通过 → 留本地
  - [x] "建议就医"仍按原始问题判断（`needs_referral` 看原始问题的识别结果，不受改写影响）
  - [ ] 问教授：改写后把病情（去身份）发云端是否符合课程伦理要求
- [x] 发送后检查器（pii_leak / profile_leak）覆盖语义路由（它们只看实际发出的 CloudRequest，与路由器无关）
- [ ] 新增发送后的病情泄露检查 — Z
- [ ] 确认 `CloudRequest` 没有混入历史发言或路由诊断（保持现状）— Z

### 1.2 测试与审计
- [ ] `conftest.py` 不再强制所有测试用 stub 路由；隐私测试在 stub 和 semantic 下各跑一遍 — Z/T
- [ ] 新增端到端测试："病情问题 + 语义路由判云端" — Z
- [ ] E4 审计：现在固定用 stub 路由把所有问题送到云端路径（语义路由会把多数问题留在本地，云端路径测不到）；另加一轮走语义路由的审计；新增检查：原问题含病情时云端记录无第一人称病情；SSE 进度事件不含问题/资料原文 — Z
- [ ] 修复 E3/E4 评估程序在语义路由下的配置（CI 中无模型资产、无云端 key 时不能失败）— Z/T
- [ ] 装好新依赖后跑全量测试 + E2/E3/E4，确认通过 — Z（10/19：后端 481 通过，21 个失败为既有的内容问题；前端 21 通过；E4/E6 smoke 通过）
- [ ] 本机缺证据验证模型（交叉编码器）→ 路由器丢弃所有资料，回答没有来源；运行 `python -m app.routing.prepare` 下载 — T/Z

### 1.3 可用性与逻辑
- [x] 云端不可用 → 退回本地回答并按原因提示（不再 503）— Z（10/19；Tongkai 的测试已改为新行为）
  - [x] 未配置云端："当前未连接云端模型，这个问题由本地模型回答。"
  - [x] 云端出错/超时："云端模型暂时不可用，这个回答由本地模型生成。"
  - [x] 隐私拦截："为保护隐私，这个问题只在本地处理。"
  - [x] 路由判断本地能力不足时附加："这个问题可能超出本地模型的能力范围，请结合下方资料来源核对。"
  - [x] 日志记录"路由云端、实际本地、原因"；保留 `llm.cloud.fallback_to_local` 开关
  - [ ] SSE 增加 `fallback` 事件
- [ ] `analyze_route` 出错改为跳过（`on_error: skip`），不终止请求 — T
- [ ] 检索总是执行；资料筛选做成独立步骤；云端请求也带上已通过验证的课程资料 — T/S
- [ ] 路由器不改写 `ctx.passages` — T
- [ ] 重依赖（sklearn、torch、transformers）改为用到时才导入；stub 配置下不装也能启动 — S/T
- [ ] 追问历史超过编码器上限时截断，而不是报错转云端 — T

### 1.4 需要讨论后决定
- [ ] 路由器回到"只打分、系统按阈值决策"，还是保留直接给 `target`？— Z/T
- [ ] 学生自选 LR/SVM → 改为教师设置或仅实验用 — T
- [ ] 进度面板默认关闭或只显示简化阶段（不对学生显示"云端需求 23%"等）— T
- [ ] 流式接口：是否推送回答本身；学习记录更新移出流（客户端断开不丢失）— T/Z
- [ ] "需要最新证据"标签的含义（见第 4 节网络搜索）— T
- [ ] 检索查询是否拼接历史发言 — S
- [ ] understand（Qwen）与 analyze_route（MiniLM）两次问题分析是否合并 — Z/T
- [ ] 实测完整流程延迟（含交叉编码器证据验证）— T

### 1.5 代码库清理
- [ ] 删除交接文件：`restore_git.ps1`、`BASE_VERSIONS.json`、`setup_local.py`、`start_*.ps1`、`开始使用.md`（或移到 docs 并改英文名）— T
- [ ] `.env.example` 改回通用值（OLLAMA_URL、模型名）— T
- [ ] 新分支名不用中文 — 全员
- [ ] 报告中注明 RAG 资料来源（MedlinePlus / NLM）— S

---

## 2. 已知 Bug（Jira）
- [ ] G1-58 医疗安全检查误拦一般性问题（"医生怎么诊断高血压"）— T/Z
- [ ] G1-60 模型重新加载后首个请求在 understand 步骤超时 → 启动预热 + Ollama `keep_alive` — Z
- [ ] G1-62 上传资料未被索引 → 集成分支已实现 ingest，合并后关闭 — S

## 3. 待做的决定
- [ ] 知识模型：按 E2 结论换成 `rule`，还是给 BKT 加遗忘后重新比较（先问教授）— Z
- [ ] understand 步骤是否换成 `gemma4:e4b`（E1：更快更准，多占显存）— Z
- [ ] 是否开启弱证据（E2：对 rule 有帮助）— Z

## 4. 网络搜索（"最新证据"来源）
- [ ] 确定需求：课程场景里"最新证据"具体指什么 — T/Z
- [ ] 首选方案：MedlinePlus Health Topics Web Service（免费，85 次/分钟/IP，须注明来源）+ PubMed E-utilities（分支已有 `pubmed.py`）接入检索层，结果走证据验证 — S
- [ ] 只发送一般化查询（主题 + 关注点的固定词表），绝不发送学生原句 — S/Z
- [ ] 结果标记"未审核来源"、显示出处、限定可信域名（medlineplus.gov、nih.gov、cdc.gov、who.int、canada.ca）；结果缓存 — S
- [ ] 如需通用搜索：比较 Brave（约 $5/千次，ZDR 企业版）与 Tavily（零保留需书面确认），看官网确认价格和保留政策 — S
- [ ] 不使用云端模型自带的搜索（OpenAI web_search、Gemini 接地）— 约定

## 5. MVP（10/21）前
- [ ] 确认 MVP 提交要求（演示 / 录屏 / 报告 / 代码链接）— Z
- [ ] 确认演示时 GPU 服务器（192.168.2.25）能否访问，准备备用方案 — Z
- [ ] 按 `docs/DEMO.md` 完整排练一次；在演示机上跑 `docker compose up` — 全员
- [ ] 云端 API key + 消费上限 — Z/教授
- [ ] 安装 `en_core_web_lg`（约 400 MB）— Z
- [ ] Abbas 医生审核高血压内容（`docs/review/high_blood_pressure_review.csv`）— Z 联系
- [ ] Jira：删除旧的 G1-1～G1-4；启动 Sprint 2；更新 Story 状态 — Z
- [ ] PPT：项目 Key 由 `PAHT` 改为 `G1`；补全组员全名（Tongkai Liu、Siyun Tan）— Z

## 6. Beta 及以后
- [ ] E5 评估（本地 / 云端 / 混合 的质量与延迟）— Z/T
- [ ] 另外四个主题的知识点、选择题、误解清单 + Abbas 审核 — S/Z
- [ ] E1 测试集扩到 120–150 条（五个主题）— Z
- [ ] E3：Abbas 医生对 30 组样本评分（`eval/personalization/results/abbas_sample.csv`）— Z 联系
- [ ] 云端费用控制：每学生提问频率限制 + 每日云端调用上限 — Z
- [ ] 回答流式输出（逐字显示）— Z/T
- [ ] "有据可依"检查升级（向量相似度或本地模型判断）— Z
- [ ] 内容审核页面（Abbas 在网页上逐条审核）— Z
- [ ] 删除已上传资料 — S
- [ ] Alembic 数据库迁移 — Z
- [ ] Playwright 端到端测试 — Z
- [ ] 课程结束批量删除学生数据的脚本 — Z
- [ ] 视频（11/25）、Design Day 海报/幻灯片（12/3）、最终报告（12/13）— 全员
