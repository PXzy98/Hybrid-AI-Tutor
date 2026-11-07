# ELG5902 v4 — Siyun 工作交接与团队配合（中文）

**日期：** 2026-11-05
**唯一交付分支：** `feature/siyun-v4-integration-20261105`
**仓库：** https://github.com/PXzy98/Hybrid-AI-Tutor
**本机：** `F:\5902_v4_integration`

**英文技术合同及完整验收标准：** [SIYUN_TEAM_HANDOFF_Z_T_2026-11-05.md](SIYUN_TEAM_HANDOFF_Z_T_2026-11-05.md)。请 Zhenyan 和 Tongkai 以英文版接口签名、具体任务和测试标准为准。

## 一、结论

**Siyun 的个人核心逻辑已基本实现，并通过虚构数据单元测试；尚不能认为整套 v4 已端到端上线。** 代码已统一在个人分支，不再要求针对每一个 S 任务另开分支，也不修改团队 `main`。Ollama、vLLM、Model Gateway、Docker、平台权限和数据库建设不是 Siyun 的分工。

v4 正式分工（`docs/v4-implementation-guide.md`）：
- **Siyun：** RAG/课程知识库、Instructor AI Tier 1–3 后端、课程级 Learner Model、教师学生概览/学习计划/可见性、检索评测、交接。
- **Zhenyan：** PostgreSQL/Alembic、课程与用户数据结构、权限、Privacy Scanner、模型网关/模型部署、后台任务、Docker、Instructor AI Tier 4。
- **Tongkai：** Routing、Web Search、前端所有页面与 UX、Demo 脚本、用户文档、API TypeScript 类型生成。

## 二、S1–S12 交付状态

| 任务 | Siyun 已实现 | 仍需完成或依赖 |
|---|---|---|
| S1–S3 | PDF/PPTX 章节/页/幻灯片溯源、文档和引用编号修复 | Tongkai 的前端翻译、v2 展示衔接 |
| S4 | 课程级/模块级 RAG 索引、版本管理、检索隔离、Worker 可调用函数、隐私扫描失败保护 | Zhenyan 的数据库、Worker、Privacy Scanner、权限、v2 API |
| S5 | 五个医学主题的虚构演示资料包；没有公开真实课程讲义 | Gita 批准 ELG5902 真正教学资料的使用 |
| S6 | 课程 Project Ideas、Sample Proposal、FAQ 的 AI 草稿生成核心 | Zhenyan 的真实模型网关、AI Draft 存储、授权生成和审核发布流程 |
| S7 | KC、选择题、misconception 草稿生成与医学题库修订 | AI Draft 正式发布接口；Lavin 二次审阅 |
| S8 | 学生课程能力值、每个 KC 的 BKT、先修知识影响、模拟测试 | 课程数据库持久化、在线 Pipeline 接入、正式模型评估 |
| S9 | Mode A/B、同意/退出、visible_since、教师查看保护、学习计划规则 | Zhenyan 的权限+审计数据库、正式 API |
| S10 | 按课程汇总 KC 和 misconception 标签计数，小样本抑制 | 真实课程学习记录与教师只读 API |
| S11 | 双课程 RAG CSV 评测工具，Precision/Recall/MRR/可追溯性/延迟测试 | 两门获授权课程数据与独立人工标注 |
| S12 | 个人交接、测试和状态文档 | 等待真正的团队集成与验收 |

## 三、Zhenyan 需要配合的具体事项

1. **优先完成 Z3/Z4/Z9/Z10：** `course`、`module`、`material`、`index_version`、`job`、`ai_draft`、`learner_kc_state`、`evidence_log`、`learning_plan`、`course_member` visibility 字段和 `audit_log`。提供稳定的授权查询和写入接口。
2. **完成 Z11：** `privacy_profile(course_type)` 和 `scan_document(text, profile) -> ScanResult`。S4 接收扫描结果严格为 True 的适配器；测试中虚构数据使用的 `scan=lambda _: True` **绝对不能部署**。
3. **完成 Z6：** `gateway.complete("local", messages, settings=..., trust_required="trusted_local", stream=False)`。S6/S7 已将其抽象为可注入接口；真实网关必须明确处理不可用/超时，不能偷偷转云端。
4. **提供索引 Worker：** 上传文档时先鉴权、存储与扫描，通过后才重建版本化索引。失败时保持上一个可用版本。数据库 `index_version` 必须在构建成功后更新。
5. **提供教师可见性与审计事务：** 学生未同意、退出或属于其他课程时，教师不应拿到任何个人记录；`visible_since` 以前的数据不可回溯显示。
6. **防止医学题库误发布：** Lavin 审核的是**原题**，后来修改了 30 道题尚未二次签字。v4 将删除旧 `reviewed_by` 字段，迁移时必须保留这些修改题目的 Draft/未批准状态，不能默认发布到学生侧。

**期望 Zhenyan 返回：** 以上数据库实体与读写方法、模型 Gateway 真实签名、扫描结果字段、Worker 回调、权限和 Audit 方法、YAML 迁移时 Draft 的处理决定。

## 四、Tongkai 需要配合的具体事项

1. **Sources 显示：** PDF 页码、PPTX 幻灯片序号由前端本地化；回答中的 `[1]`、`[2]` 与 Sources 列表必须一一对应，重复引用同一文件也不能错号。
2. **T4/T5 Routing：** 区分 `concept` 和 `logistics`。后者优先查询 syllabus / project requirements / 模板，而非错误更新 KC 学习状态。
3. **T6/T7 UI：** 课程资料上传/索引状态、Instructor AI Draft 编辑与 Accept、教师查看学生概览、学习计划、学生 Consent/Opt-out 页面。权限由后端提供，前端只展示结果。
4. **T8 Privacy Notices：** 清楚提示数据可能发往云端；每条回答的 local/cloud 标记必须与真实服务状态匹配。
5. **API 对接：** 在 Zhenyan 的 v2 API 和 Siyun 的后端接口完成后，更新 OpenAPI、运行 `npm run gen:api`，再做前端回归。不可给冻结的 `/api/v1` 继续加入新功能。
6. **Demo：** 先用虚构医学资料和虚构学生账号；ELG5902 的真实幻灯片等候 Gita 书面许可。

**期望 Tongkai 返回：** 新 Sources 组件的字段需求、`question_kind` 数据合同、v2 的 UI/类型需求，以及 S6–S10 对应前端页面缺失字段。

## 五、明确不能冒充的完成项

- 无真实 Z4/Z6/Z10/Z11 接口，**不能声称已完成真实多课程产品的端到端测试**。
- 单元测试中的 Fake Gateway、Fake Scanner 只服务虚构测试，不能部署到课堂。
- S11 的虚构测试不代表真实医学课程的 Recall/Precision 达标。
- E2 的 8 个模拟学生 × 8 次交互 smoke test 只能证明模拟脚本可运行，不能据此选 BKT 或 Rule 生产模型。
- Lavin 修改后的题目需要再次审核；来源可追踪不等于医学正确性。
- 用户原始问题与个人健康信息不得写入日志、模型请求外传或班级分析。

## 六、交接顺序及验收

**Z 课程数据库/权限 → Z Privacy Scanner + Worker → S CourseRetriever 接入 → Z Model Gateway → S Instructor AI Draft + Learner API 接入 → T Routing/Frontend → Gita/Lavin 审核 → S11 真实评测 → 全量测试及课堂 Beta。**

全量验证要求包括后端两种 Learner 配置测试、Ruff、前端 Build 与测试、E6 Privacy Eval、跨课程与越权 API 测试、拒绝扫描测试、索引版本更新，以及授课教师认可的真实 RAG 评估。

**最新完整技术内容、接口签名和测试命令，以英文交接文档为准。**

## 七、最新补充：直接衔接 Zhenyan 的 v4 接口

S4 已增加 `backend/app/rag/privacy_adapter.py`，使用 Z1 的真实
`ScanResult(scanned, findings)` 类型。只有 `scanned=True` 且没有敏感信息
finding 才允许建索引。扫描失败、扫描未实现、返回数据不合法时全部拒绝。
Zhenyan 需要提供真正的 Z11 Scanner，并确定人工审核和例外政策。

S6/S7 已直接对接 **Z1 的 FakeGateway 接口**测试：传入
`effective_settings(course_id)`，要求 `trusted_local`，不会错误调用 cloud。
这些仍是离线测试，不等于 Z6 真实模型部署完成。

另外增加了 S4/S6/S7/S8/S9/S10/S11 的**跨模块虚构数据 Smoke Test**，
验证个人各模块能够连贯工作。真实 API、DB、CSRF、角色鉴权以及医学审核
仍然必须由对应负责人完成。

S11 增加完整 Precision/Recall@K 和索引来源完整性校验；虚构测试结果
不代表临床正确性，也不代表正式课程指标达标。

## 八、最终测试结果（2026-11-05）

- Backend 默认 BKT：**766 passed，1 deselected**。
- Backend Rule 模式：**766 passed，1 deselected**。
- Ruff：通过。
- Frontend Production Build：通过。
- Frontend：**28 passed（8 个文件）**。
- E2 模拟学生 Smoke Test：五个医学主题均执行成功，报告见
  `docs/S8_E2_SIMULATED_SMOKE_2026-11-05.md`。它仅使用少量虚构数据，
  **不能据此认定 BKT/Rule 哪种模型更好**。

上述结果证明你负责的已交付组件在测试条件下可共同运行；
**不代表 Zhenyan 尚未完成的真实接口或 Tongkai 前端集成已经验收**。
