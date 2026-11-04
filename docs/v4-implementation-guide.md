# v4 实施指南（给编码 agent 和组员直接上手用）

更新：2026-11-04 · 基于 main `71ad236` · 负责人：Z = 邢桢岩 Zhenyan，T = 刘恫铠 Tongkai，S = 谭斯允 Siyun

这份文件是 v4 改造的**唯一入口**：背景、必须遵守的规则、目标架构、每个任务改哪些文件、怎么算完成、怎么跑测试，都在这里。拿到一个任务 ID（例如 `Z4`）就可以开始。

---

## 0. 怎么用这份文件

1. **先读第 1～3 节**：背景、不能违反的规则、现有代码地图。
2. **找到任务**：在第 7 节找到自己的任务 ID，确认依赖的任务已经合并。
3. **按第 8 节开分支、开发、测试、开 PR**。一个任务一个 PR。
4. **只改自己组件的代码**（第 5 节）。需要别的组件配合时，只通过第 6 节约定的接口；接口不够用就在 PR 里提出，由该组件的负责人改。
5. **遇到这份文件没写清楚的地方**：不要猜，在 PR 描述里写明你的假设，交给负责人确认。

---

## 1. 背景和目标

**现状（v3.1）**：一个班、5 个健康主题的隐私感知混合 AI 助教。
- **处理流程**：每个问题先过隐私过滤，再由路由决定用本地模型还是云端模型。
- **检索**：MedlinePlus 和教师上传的资料。
- **个性化**：BKT 学习者模型。
- **教师端**：面板只能看班级汇总。
- **部署**：SQLite，Docker 跑 api + web。

**客户的要求**（11-03 会议，客户 Abbas 教授）：
- **原型阶段结束**：冬季学期给他的全部学生做 beta 测试，链接放在 Brightspace 里，界面质量要像正式产品。
- **不只做健康**：支持任何课程，以**整门课程的资料**为中心，包括大纲、项目要求、模板和讲义。
- **教师自己建课程、建主题**。
- **教师端 AI**：生成项目方向、示例提案等。
- **学生个人概览**：教师能看到每个学生的情况，并制定学习计划。
- **部署**：放在客户自己的环境。

**v4 目标**：在现有代码上**改造**（不重写），变成多课程、多教师的课程助教产品：
- 隐私规则按课程类型切换；
- 增加教师端 AI；
- 用一套 Docker Compose 部署。

**示例课程**：健康课（现有 5 个主题作为 5 个章节，补齐整门课的资料）和 **ELG 5902**（工程课，用来验证跨学科兼容性）。

**不做的事**：
- 中文相关的开发；
- 研究伦理审批（按教授要求推进）；
- 现阶段的数据库备份和硬盘加密；
- 云端服务商比较（以后用 GPT、Claude 或 Cohere，由客户决定）。

---

## 2. 不能违反的规则

改代码前必须读。违反任何一条的 PR 不能合并。

### 2.1 隐私
1. **不保存提问原文**：`privacy.log_raw_text` 必须是 `false`；日志、数据库、指标、错误信息里都不能出现学生原文或个人信息。
2. **原文只能发给"可信本地"模型**：只有被标为可信本地的模型连接（默认的 vLLM）可以收到原文和完整的学习者档案。外部模型（云端、教师自己填的 API、网络搜索）只能收到通过云端关口的内容。v4 里由模型网关强制执行（Z6）。
3. **云端关口对所有路由都生效**（`backend/app/pipeline/steps/generate.py`）：个人病情问题按 `privacy.health_detail_policy` 处理；泄露检查拦截任何个人信息、学号、题目 ID、误解文字；被拦截或云端失败时用本地模型回答，并告诉学生原因。
4. **学习者档案永远不发给云端**；`profile_leak` 和 `pii_leak` 检查必须开着。
5. **隐私规则的修改必须重跑 E6**（`eval/privacy-filter/`），结果不能退步；改了识别器而不跑评估的 PR 不合并。
6. **网络搜索的查询只能来自隐私模块的 `search_query()`**（Z11），搜索代码拿不到原文。

### 2.2 权限
7. **课程是权限边界**：每个接口先检查"当前用户在这门课里是什么角色"，再做事。教师 A 不能看教师 B 的课，学生不能看别人的数据。每个新接口都要有越权测试。
8. **前端不做任何权限判断**：前端只显示后端返回的内容，后端不该返回的就不返回。
9. **教师看单个学生**只在课程选了"方案 B"、并且这个学生没有选择不公开时才允许，每次查看都写审计记录（第 4.6 节）。

### 2.3 工程
10. **不提交密钥**：API key、密码只放 `.env`（已在 `.gitignore`）或 Docker secrets；不要写进代码、测试、文档和提交信息。
11. **每个组件只有一个负责人**（第 5 节）；不在别人的组件里改代码。
12. **CI 必须通过**：后端测试（两遍：默认 BKT 和 `TEST_LEARNER_KNOWLEDGE=rule`）、ruff、评估的冒烟测试、前端构建和测试、Docker 构建。
13. **隐私相关的固定值不进普通配置**：`log_raw_text`、必须开的检查项、识别器内部参数，留在代码或隐私档案里。

---

## 3. 现有代码地图（main `71ad236`）

| 部分 | 位置 | 说明 |
|---|---|---|
| 配置 | `config.yaml`、`backend/app/core/config.py` | pydantic 设置；环境变量 `SECTION__FIELD` 覆盖 yaml |
| 服务装配 | `backend/app/core/services.py` | `build_services()`；`reconfigure()` 会替换全局对象（v4 要改，见第 4.4 节） |
| 注册表 | `backend/app/core/registry.py` | 路由、检索、知识模型、检查项、处理步骤都按名字注册，由配置选择 |
| 处理流程 | `backend/app/pipeline/runner.py`、`steps/*.py` | 步骤列表在 `config.yaml` 的 `pipeline`，共享一个 `RequestContext`（`core/schemas.py`） |
| 隐私 | `backend/app/privacy/`（`analyzer.py`、`recognizers/`、`generalize.py`、`llm_check.py`、`policy.py`、`session_health.py`） | Presidio + spaCy `en_core_web_lg` + 自定义识别器 |
| 云端关口 | `backend/app/pipeline/steps/generate.py`、`backend/app/llm/cloud_guard.py` | 所有路由共用 |
| 模型客户端 | `backend/app/llm/`（`ollama_client.py`、`openai_compat.py`、`factory.py`、`fake.py`） | 测试用 `fake.py` |
| 路由 | `backend/app/routing/`（`semantic.py`、`evidence.py`、`methods/`、`train.py`、`prepare.py`） | MiniLM + LR/SVM；模型文件在 `data/routing/models` |
| 检索 | `backend/app/rag/`（`medical_hybrid.py`、`documents.py`） | BM25 + TF-IDF；按主题建索引 |
| 学习者 | `backend/app/learner/`（`knowledge/`、`preference/`、`recommender.py`、`content.py`、`understand.py`） | `KnowledgeModel` 接口在 `knowledge/interface.py` |
| 检查 | `backend/app/verify/checkers/`（`grounding.py`、`medical_safety.py`、`leaks.py`） | `medical_safety` 目前是必选（`admin/runtime_config.py` 的 `REQUIRED_CHECKERS`） |
| 存储 | `backend/app/storage/`（`db.py`、`models.py`） | SQLAlchemy + SQLite；没有迁移工具 |
| 账号 | `backend/app/auth/` | Argon2 密码哈希；服务器端会话；cookie 有 `SameSite=lax`，`Secure` 由 `cookie_secure` 控制 |
| 教师端后端 | `backend/app/admin/`、`backend/app/api/v1/admin*.py` | 全局设置、资料上传、班级汇总、日志 |
| 内容 | `content/topics/<topic>/{kcs,items,misconceptions}.yaml` | 启动时加载；草稿/审核状态在 `reviewed_by` |
| 前端 | `frontend/src/`（`pages/`、`pages/admin/`、`components/`、`i18n/en.ts`、`i18n/fr.ts`、`api/schema.d.ts`） | React 18 + Vite + Tailwind 3 + TanStack Query；API 类型由 `npm run gen:api` 从 `frontend/openapi.json` 生成 |
| 评估 | `eval/`（`privacy-filter/` E6、`privacy-audit/` E4、`learner-sim/` E2、`personalization/` E3） | CI 里跑冒烟模式 |
| 部署 | `docker-compose.yml`、`backend/Dockerfile`、`frontend/Dockerfile` | 现在是 api + web 两个服务 |
| CI | `.github/workflows/ci.yml` | backend、frontend、docker 三个任务 |

**还没合并、但计划依赖的**：PR #16（谭斯允的课程 PDF 按页检索和检索评估脚本 `eval/course_rag_benchmark.py`）。S1 合并它。

**已知问题**：
- 回答里的 `**粗体**` 前端显示成星号（T3 修）。
- 回答里的引用编号 `[i]` 按段落编号，Sources 列表按文件去重后重新编号，两者可能对不上（S3 修）。
- 截图时 `understand` 步骤连续两次 5 秒超时（Z2/Z6 的压测会给出合适的超时）。

---

## 4. 目标架构（v4）

### 4.1 改造还是重写

**以改造为主，局部重写**。处理流程、注册表、隐私、路由、模型客户端、检查项、学生端都保留，主要是多传一个课程参数。下面几块因为前提变了，要重写或大改：

| 模块 | 处理 |
|---|---|
| `storage/` | 重写：PostgreSQL + Alembic，所有表加课程维度（测试仍可用 SQLite） |
| `core/topics.py`、`learner/content.py` | 重写为**课程目录服务**：内容存在数据库里，由教师在网页上建 |
| `admin/runtime_config.py`、`core/services.py` 的 `reconfigure` | 重写为**设置分层 + 按请求取值**（4.4） |
| `rag/medical_hybrid.py` | 改造并改名为课程检索器：按课程 + 主题建索引，支持课程级资料 |
| 教师端前端页面 | 大部分新写 |

### 4.2 部署：一套 Docker Compose

```
浏览器 ──HTTPS 443──► proxy（Caddy：自动 HTTPS，提供前端，/api 转给 api）
                       │
                       ├─ api     FastAPI
                       ├─ worker  同一个镜像，跑后台任务（索引、教师端 AI 生成、评估、每日用量重置）
                       ├─ db      PostgreSQL（数据卷）
                       └─ 监控    Prometheus + Grafana（可选的 monitoring 配置）
api / worker ──► vLLM 本地模型服务（单独部署，不在 compose 里；OpenAI 兼容 API + API key；可信本地）
api / worker ──► 外部模型 API（云端模型、教师自己的 OpenAI 兼容 API；只收脱敏内容）
```

- **两个 Docker 网络**：
  - 对外网络：proxy、api、worker；
  - 内部网络：`internal: true`，db 只在这里，api 和 worker 两边都接。
- **端口**：只映射 443（80 只用来跳转）；db 和监控不映射到主机。
- **vLLM 的连接**：用 API key；vLLM 主机的防火墙只允许应用主机访问；如果两台机器之间经过公网，就走 HTTPS。
- **本地开发**：模型地址指向 Ollama 或任何 OpenAI 兼容地址即可。
- **应用主机**：不需要 GPU。

### 4.3 组件

| 组件 | 职责 |
|---|---|
| 身份和权限 | 账号、登录身份（密码；以后 Microsoft Entra ID / Brightspace LTI）、会话、课程角色、越权检查 |
| 课程目录 | 课程、主题、知识点图、检测题、误解、资料、草稿/审核状态 |
| 设置取值 | 系统设置 + 课程设置 + 配置文件 + 硬上限 → 本次请求的有效设置 |
| 提问流程 | 按配置的步骤运行（4.5） |
| 学习者服务 | 课程级知识模型、偏好、学习计划、可见性方案、不公开状态 |
| 隐私服务 | 隐私档案注册表、识别、脱敏/还原、云端关口、改写、`scan_document()`、`search_query()` |
| 模型网关 | 模型连接注册表（可信本地 / 外部）、排队、超时、计量、按 token 流式输出、防 SSRF |
| 检索服务 | 解析（pdf、docx、pptx、html、md、txt）、分段、按课程 + 主题建索引 |
| 检查服务 | 由隐私档案决定启用哪些检查项 |
| 教师端 AI | 四档功能；草稿 → 审核 → 发布 |
| 网络搜索 | 可信网站白名单、结果清洗；查询只来自 `search_query()` |
| 可观测 | `/metrics`、结构化日志（不含个人信息）、审计记录 |

### 4.4 设置分层

| 层 | 内容 | 谁能改 |
|---|---|---|
| 1. 代码常量 | 安全不变量（`log_raw_text=false`、必须开的检查项、识别器内部参数） | 只能改代码 |
| 2. `config.yaml` | 默认值和**硬上限**（新增 `limits` 段，见下表） | 部署的人 |
| 3. 环境变量 / `.env` / Docker secrets | 数据库地址、API key、会话密钥 | 部署的人 |
| 4. `system_settings` 表 | 默认模型连接、启用了哪些课程类型 | 系统管理员（网页） |
| 5. `course_settings` 表 | 课程类型、可见性方案、只用本地模型、路由偏好、课程自己的模型连接、用量（现在都允许为空） | 课程教师（网页） |

**取值规则**：只通过一个函数取值，例如 `effective_settings(course_id)`。从第 5 层往上找第一个有值的层，最后按第 2 层的硬上限截断；第 1 层不能被覆盖。业务代码不要直接读 `settings.xxx` 里属于第 2、4、5 层的值。

**用量限制**：先只用配置文件，`course_settings` 里的用量字段全部为空；以后开放给教师时只加界面，不改表结构。计数从一开始就按"学生 + 课程 + 日期"存。

**要搬进 `limits` 段的写死值**（Z5）：

| 现在的位置 | 常量 |
|---|---|
| `admin/materials.py` | `MAX_BYTES` |
| `rag/documents.py` | `MAX_FILE_BYTES`、`MAX_TEXT_CHARS`、`MAX_PDF_PAGES` |
| `rag/medical_hybrid.py` | 每个主题 2,000,000 字符的上限、`_MAX_CHARS` |
| `privacy/generalize.py` | `MAX_CHARS` |
| `learner/checks.py` | `DIAGNOSTIC_MAX` |
| `learner/misconceptions.py` | `MAX_IN_PROMPT` |
| `api/v1/survey.py` | `MIN_AGGREGATE_SIZE` |
| `admin/llm_server.py` | `TIMEOUT_S` |
| `admin/logs.py` | `MAX_PAGE_SIZE` |
| 新增 | 本地模型的并发数、排队上限、排队超时；云端每日调用和费用上限；每个学生每分钟、每天的提问次数和云端次数；登录失败上限和锁定时间 |

### 4.5 提问流程（v4）

| # | 步骤 | 变化 |
|---|---|---|
| 0 | API 层 | 登录检查 + **课程角色检查** + **用量检查** |
| 1 | `privacy_filter` | 按课程类型加载**隐私档案**（基础层 + 学科档案） |
| 2 | `understand` | 不变；"课程事务问题 / 知识问题"由路由模型的新输出给出（T5） |
| 3 | `learner_context` | 按课程读；带上教师的**学习计划**；课程事务问题跳过个性化 |
| 4 | `analyze_route` | 输出多一个"问题类型"字段 |
| 5 | `retrieve` | 检索"课程级资料 + 当前主题资料"；事务问题优先检索大纲和项目要求 |
| 6 | `route` | 加入课程设置："只用本地模型"、路由偏好 |
| 6a | `web_search`（新，可选） | 只在走云端并需要最新信息时运行；查询来自 `search_query()`；只访问白名单网站 |
| 7 | `generate` | 只通过**模型网关**调用模型；网关检查可信级别；支持按 token 流式输出 |
| 8 | `restore` | 不变 |
| 9 | `verify` | 检查项由隐私档案决定（只有医学课开 `medical_safety`） |
| 10 | `attach_check` | 课程事务问题不附检测题 |
| 11 | `record` | 另外记录用量计数和指标；仍然不存原文 |
| 12 | `update_learner` | 用课程级知识模型；学习者状态按课程存 |

### 4.6 数据表（PostgreSQL，Z1 定稿）

- **身份**：
  - `account`：用户名、可选学校邮箱、系统角色（系统管理员 / 普通）；
  - `login_identity`：登录方式 + 外部标识 → 账号；
  - `auth_session`：登录会话；
  - `course_member`：课程、账号、课程角色（教师 / 助教 / 学生）、不公开标记。
- **课程目录**：
  - `course`：代码、名称、学期、课程类型、状态；
  - `course_settings`：每门课一行，字段可为空；
  - `topic`：主题；
  - `kc`、`kc_prerequisite`：知识点和依赖关系；
  - `check_item`、`misconception`：都带状态和审核人；
  - `material`：资料，属于课程级或某个主题；记录数据卷路径、扫描结果、索引状态；
  - `index_version`：每门课检索索引的版本号。
- **学习者**（都带 `course_id`）：
  - `learner_state`：知识点级状态 + 课程级整体能力；
  - `learner_preference`：学习偏好；
  - `learning_plan`：教师定的学习计划；
  - `evidence_log`：作答证据；
  - `learner_misconception`：学生的误解；
  - `consent`：同意记录，按课程，记录同意时的方案版本。
- **运行**：
  - `request_log`：不含原文；
  - `usage_counter`：学生 + 课程 + 日期；
  - `job`：后台任务队列；
  - `audit_log`：审计记录；
  - `model_endpoint`：地址、模型名、可信级别、加密后的 API key、属于系统还是某门课；
  - `system_settings`：系统设置；
  - `config_history`：设置修改记录。
- **教师端 AI**：
  - `ai_draft`：类型、内容、来源资料、状态；
  - `eval_run`：第四档评估的结果。

### 4.7 隐私档案（按课程类型）

- **基础层（所有课程）**：
  - 姓名、学号、邮箱、电话、地址、出生日期、证件号、成绩；
  - 轻量的个人健康和特殊情况识别：任何课里都可能出现"我生病了能不能延期"。
- **首批档案**：

| 课程类型 | 额外识别 | 其他随档案变化 |
|---|---|---|
| 医学（medical science） | 现有完整的病情规则（`health_detail`、`health_context`、读数、跨消息病情、`generalize` 改写） | `medical_safety` 检查、"不是医疗建议"提示 |
| 生命科学（life science） | 研究参与者和样本的编号、实验室里的个人身份信息；生物学术语不当作个人病情 | 不加医疗安全检查 |
| 电气与计算机工程（ECE） | 代码里的密钥、令牌、密码、私有仓库地址、内网 IP、连接字符串；MAC 地址、序列号；电路和信号数值（V、mA、kΩ、Hz、dB）不当作个人读数 | 代码片段原样保留 |
| 通用（默认） | 只有基础层 | — |

- **扩展方式**：每个档案是一个配置文件（例如 `backend/app/privacy/profiles/ece.yaml`），列出启用的识别器、词表、策略、检查项和界面提示。新的识别器按现有的注册方式加。
- **每个档案的测试集**：每个档案要附一个标注测试集，再加一个"其他学科术语"的反例集，用来测误遮挡。

### 4.8 可见性方案（每门课由教师选择）

- **方案 A**：教师只看班级汇总（现在的做法）。
- **方案 B**：教师可以看个人概览：
  - 内容：各知识点的掌握程度和趋势、检测题记录、误解、偏好、活跃程度；
  - 提问原文仍然不保存，所以也看不到；
  - 教师可以定学习计划：重点知识点、学习目标、调整难度、备注。
- **透明**：学生在选课、入学问卷、"What I know"页面都能看到当前方案，也能看到老师看到的内容和老师定的计划。
- **切换方案**：
  - B → A 立即生效；
  - A → B 要先通知学生，学生重新确认后才对他生效，而且**只显示切换之后的数据**。
- **学生单独退出**：方案 B 下学生可以选择不公开。实现方式是 `course_member` 上的一个标记 + 权限检查里的一个条件。退出后：
  - 老师看到"该学生选择不公开"；
  - 他的数据只计入班级汇总；
  - 老师不能给他定学习计划；
  - 系统的自动个性化照常进行。
- **审计**：教师每次查看个人概览都写一条审计记录。

### 4.9 教师端 AI（四档）

| 档 | 功能 | 规则 |
|---|---|---|
| 1 | 根据课程资料生成项目方向和项目清单（附难度、知识点、交付物）、示例提案或写作指南、FAQ（截止日期、评分标准） | 结果是草稿，教师确认后才对学生可见 |
| 2 | 从讲义起草知识点、依赖关系、检测题、误解 | 走"草稿 → 审核"流程（沿用 `reviewed_by`） |
| 3 | 班级洞察：学生集中在问哪些知识点、哪些误解最多 | 只用知识点标签和统计数字，不返回原文 |
| 4 | 评估本地模型能否胜任这门课：用课程资料生成测试题（教师可以抽查修改），本地模型和云端模型都带 RAG 作答，评审模型打分 + 教师抽样复核，按章节和题型出报告，记录延迟和费用 | 测试题是生成的，不涉及学生；发课程资料给云端前要教师同意 |

另外：
- 教师端的提问不走学习者个性化，也不写入学习者模型；
- 生成功能都只通过模型网关调用模型；
- 上传的资料先过 `scan_document()`（可能夹带学生名单）。

**"数据可能发往云端"的提示**：
- **学生端**：入学同意书、聊天页常驻提示、每条回答的"本地 / 云端"标签；
- **教师端**：使用生成功能前提示；
- **课程设置**：可以选"本课程只用本地模型"。

### 4.10 课程级知识模型

- **模型**：分层模型。
  - 每个学生在每门课有一个**整体能力值**（类似 Elo/IRT，每次作答在线更新）；
  - 在它的基础上，知识点级用 BKT 或 PFA 修正；
  - 沿知识点依赖图传播：基础知识点掌握差，后续知识点的估计也往下调。
- **规则模型的位置**：只在出错时兜底，不作为主要模型。
- **接口**：实现现有的 `KnowledgeModel` 接口（`backend/app/learner/knowledge/interface.py`），按名字注册，以后可以换成深度知识追踪模型。

### 4.11 模型连接

- **默认**：系统默认连好一个可信本地模型（部署时配置的 vLLM）。
- **可修改**：教师可以改成自己的 OpenAI 兼容 API（地址、模型名、API key）；云端模型也一样。
- **隐私边界提示**：设置页必须提示"把本地模型改成别人的服务，学生原文就会发到那里"，并要教师确认这个服务归他自己控制。
- **防 SSRF**：
  - 禁止填链路本地地址（`169.254.0.0/16`，含云平台元数据地址）；
  - 禁止填本系统内部的服务名和地址（db、proxy 等）；
  - 外部连接还要禁止私有地址段。
- **API key**：加密存储，界面上只显示后几位；修改写进审计记录。
- **GPU 规格**：按能跑 9B 模型配置；通过 OpenRouter 对比 27B（Z2）。OpenRouter 只发生成的测试问题。

---

## 5. 组件归属

| 组件 | 负责人 |
|---|---|
| 平台（存储、课程目录、设置分层、账号和登录、课程管理和批量导入的后端、用量、越权检查、CSRF、登录限流） | Z |
| 隐私（档案、识别、云端关口、改写、`scan_document()`、`search_query()`、同意书内容） | Z |
| LLM 部署和测试（模型网关、vLLM 连接和压测、流式输出、9B / 27B 对比、教师端 AI 第四档） | Z |
| Docker 部署和运维（compose、proxy、监控、CI 漏洞扫描、运维手册） | Z |
| 检索和课程内容（`.pptx`、引用编号、课程检索器、示例课程资料、检索评估） | S |
| 教师端 AI 第一到第三档（后端） | S |
| 学习者（课程级知识模型、学习计划、可见性方案、个人概览、不公开、审计的后端） | S |
| 路由和网络搜索（ECE 路由评估和训练、问题类型分类、网络搜索） | T |
| 前端界面和体验（全部页面、改版、英法文字、改名、无障碍、界面测试） | T |
| 演示材料和用户文档（演示数据脚本、使用手册、视频、Lavin 的法语审核） | T |

**T 的组件选择原则**：
- 不碰权限和隐私判断；
- 有明确的对错标准；
- 和别人的代码隔离；
- 容易回退。

所以给 T 用的 agent 要特别遵守第 2.1、2.2 节；网络搜索只能用 `search_query()`。

---

## 6. 接口约定（Z1 定稿时写成代码里的类型和 OpenAPI）

| 提供方 | 接口 | 使用方 |
|---|---|---|
| Z | `effective_settings(course_id) -> EffectiveSettings` | 所有人 |
| Z | `require_course_role(user, course_id, roles)`（FastAPI 依赖） | 所有后端接口 |
| Z | `check_usage(user, course_id, kind)` / `record_usage(...)` | API 层、生成步骤 |
| Z | 模型网关：`gateway.complete(endpoint_role, messages, *, trust_required, stream=False)`；`endpoint_role` 是 `local`、`cloud` 或 `judge` | S（教师端 AI）、T（网络搜索后的生成）、处理流程 |
| Z | `scan_document(text, profile) -> ScanResult` | S（资料上传） |
| Z | `search_query(ctx) -> str \| None` | T（网络搜索） |
| Z | `privacy_profile(course_id) -> PrivacyProfile` | 处理流程、检查服务 |
| Z | 课程、主题、选课、设置、用量的 REST 接口 + OpenAPI | T（前端） |
| S | `CourseRetriever.retrieve(course_id, topic_id, query, k)` | 处理流程 |
| S | `learner.profile_for_instructor(viewer, course_id, student_id)`（内部再检查方案和不公开） | 教师端接口 |
| S | 教师端 AI、学习者、检索管理的 REST 接口 + OpenAPI | T（前端） |
| T | `SemanticAnalysis.question_kind: Literal["concept", "logistics"]` | 处理流程 |
| T | `web_search(query, allowlist) -> list[Passage]` | 处理流程 |

**怎么并行开发**：Z1 合并后，提供方先交接口签名和返回假数据的实现，使用方先按假数据开发，不用等真正实现。

---

## 7. 任务清单

**Sprint 安排**：

| Sprint | 日期 | 课程节点 |
|---|---|---|
| S4 | 11/4–11/10 | Beta 11/11 |
| S5 | 11/11–11/17 | |
| S6 | 11/18–11/24 | 视频 11/25 |
| S7 | 11/25–12/2 | Design Day 12/3 |
| S8 | 12/3–12/13 | Final 12/13 |

"独立"表示不依赖 Z1，可以马上开始。

### 7.1 邢桢岩 Z

| ID | 任务 | Sprint | 依赖 | 主要文件 | 完成标准 |
|---|---|---|---|---|---|
| Z1 | **课程结构和接口约定**：第 4.6 节的表、第 6 节的接口签名和假数据实现、`course_id` 进入 `RequestContext` 的方式 | S4，**11/7 前** | — | `docs/` 设计文档、`backend/app/core/schemas.py`、新的 `backend/app/platform/` | S、T 确认；假数据实现合并 |
| Z2 | 9B vs 27B 对比：OpenRouter 跑 27B，同一批课程问题、都带 RAG；给出 vLLM 机器的规格和费用 | S4–S5 | 独立 | `eval/model-compare/`（新） | 对比报告 |
| Z3 | PostgreSQL + Alembic；SQLite 导数据脚本；测试仍可用 SQLite | S5 | Z1 | `backend/app/storage/`、`backend/alembic/`（新） | CI 在两种数据库上都通过 |
| Z4 | 课程目录：课程、主题、选课、授课表；知识点、检测题、误解从 YAML 迁入数据库；5 个主题导入健康课 | S5 | Z3 | `storage/models.py`、`core/topics.py`、`learner/content.py` | 现有测试在"一门课"下全部通过 |
| Z5 | 设置分层 + `effective_settings()` + `limits` 段（第 4.4 节的表）；替换 `runtime_config.py` 和 `services.reconfigure` | S5 | Z3 | `core/config.py`、`core/services.py`、`admin/runtime_config.py`、`config.yaml` | 业务代码不再直接读这些常量；两门课的设置互不影响 |
| Z6 | 模型网关：连接注册表、可信级别、教师自定义 OpenAI 兼容 API、API key 加密、防 SSRF、排队和超时、按 token 流式输出；vLLM 压测 | S5–S6 | Z5 | `backend/app/llm/`（新 `gateway.py`）、`admin/llm_server.py` | 填内部地址被拒绝；外部连接收不到原文（有测试）；压测报告 |
| Z7 | 隐私档案框架：基础层 + 档案配置文件 + 识别器注册；按课程类型选择档案 | S5 | Z5 | `backend/app/privacy/`（新 `profiles/`） | 加新档案只需一个配置文件；E6 不退步 |
| Z8 | Docker Compose 骨架：proxy（Caddy）、api、worker、db；两个网络 | S5 | — | `docker-compose.yml`、`deploy/Caddyfile`（新） | 本地一条命令起全套 |
| Z9 | 课程管理和批量导入（CSV）的后端接口；`login_identity` 表（预留 OAuth） | S6 | Z4 | `backend/app/api/v1/`、`backend/app/auth/` | OpenAPI 交给 T；越权测试 |
| Z10 | 用量计数和限制；每个接口的越权测试；CSRF；登录限流；退出和改密码让所有会话失效 | S6 | Z4 | `backend/app/auth/`、API 依赖 | 越权测试覆盖所有接口 |
| Z11 | 医学档案（现有规则迁入）+ ECE 档案 + ECE 测试集；`scan_document()`；`search_query()`；同意书内容 | S6 | Z7 | `privacy/profiles/`、`eval/privacy-filter/` | E6 不退步；ECE 测试集有结果 |
| Z12 | 教师端 AI 第四档：本地 vs 云端评估 | S7 | Z6、S4 | `backend/app/instructor_ai/eval/`（新） | 能对一门课出按章节的报告 |
| Z13 | 整套部署到测试主机；监控（应用 `/metrics`、vLLM 自带指标、Grafana、告警）；CI 漏洞扫描（`pip-audit`、`npm audit`、`bandit`、镜像扫描） | S7 | Z8 | `docker-compose.yml`、`deploy/`、`.github/workflows/ci.yml` | 客户和 Lavin 能试用；能看到指标 |
| Z14 | 部署和运维手册、交接文档、压测 | S8 | — | `docs/` | 接手的人照着能部署 |

**落后时往后推的顺序**：Z12 → Z13 的 Grafana 和告警 → `login_identity`。

### 7.2 谭斯允 S（都是后端）

| ID | 任务 | Sprint | 依赖 | 主要文件 | 完成标准 |
|---|---|---|---|---|---|
| S1 | PR #16 收尾：页码由前端翻译（后端只返回页码）、文档里的本机路径改成相对路径；合并 | S4 | 独立 | `backend/app/api/v1/ask.py`、`docs/RAG_COURSE_BETA.md` | 已合并 |
| S2 | `.pptx` 支持：`python-pptx` 读取每页的文字、表格、演讲者备注；每段记录 `slide N`；页标题作为分段标题；检查解压后大小；全是图片时给出错误提示；测试（虚构的 3 页 PPT） | S4–S5 | S1 | `backend/app/rag/documents.py`、`admin/materials.py` | 测试通过；来源显示 slide N |
| S3 | 引用编号和 Sources 列表一一对应 | S5 | S1 | `backend/app/api/v1/ask.py`、`backend/app/prompts/render.py` | 有测试 |
| S4 | 课程检索器：资料分课程级和章节级；按课程检索；上传时调用 `scan_document()`；索引带版本号 | S5–S6 | Z4、Z11（可先用假实现） | `backend/app/rag/`（`medical_hybrid.py` 改名并改造） | 大纲、项目要求能被检索到 |
| S5 | 两门示例课程的资料：健康课补大纲、项目要求、模板、讲义；ELG 5902（先征得 Gita 教授同意） | S5 | 独立 | `data/`（按 Z1 的目录约定） | 两门课都能上传并检索 |
| S6 | 教师端 AI 第一档的后端 | S6 | S4、Z6 | `backend/app/instructor_ai/`（新） | 生成结果是草稿，确认后才可见 |
| S7 | 教师端 AI 第二档的后端（起草知识点、检测题、误解；草稿 → 审核） | S6–S7 | Z4、S4 | 同上 | AI 起草、教师审核后可用于个性化 |
| S8 | 课程级知识模型（第 4.10 节） | S6–S7 | Z4 | `backend/app/learner/knowledge/`（新实现） | 和现有 BKT 对比的评估（`eval/learner-sim/`） |
| S9 | 可见性方案 A/B、个人概览、学习计划、学生不公开、审计的后端（第 4.8 节） | S6–S7 | Z4、Z10 | `backend/app/learner/`、`backend/app/api/v1/` | 测试覆盖"不该看到的看不到" |
| S10 | 教师端 AI 第三档：班级洞察的后端 | S7 | S8 | `backend/app/instructor_ai/` | 不返回原文 |
| S11 | 两门课的检索评估（`eval/course_rag_benchmark.py`） | S7 | S5 | `eval/` | 两门课都有结果 |
| S12 | 自查和交接文档 | S8 | — | `docs/` | 自查清单 |

**落后时往后推的顺序**：S10 → S9 里的学习计划部分。

### 7.3 刘恫铠 T

| ID | 任务 | Sprint | 依赖 | 主要文件 | 完成标准 |
|---|---|---|---|---|---|
| T1 | Beta 路由评估（G1-105）和 Beta 报告（G1-108） | S4 | — | `eval/` | 按时交付 |
| T2 | 前端改版设计稿：用 v0 出几版样式；决定用 AI Elements 还是 assistant-ui（第 7.4 节） | S4–S5 | 独立 | 设计稿 | Z、S 和客户认可 |
| T3 | 升级到 Tailwind 4 和 React 19，引入 shadcn/ui；现有页面按设计稿改版；回答用 Markdown 渲染（修好粗体） | S5 | T2 | `frontend/` | 现有前端测试通过；截图对比 |
| T4 | ECE 路由评估：用 ELG 5902 资料写工程问题并标注，评估；必要时补训练数据，重训路由模型 | S5–S6 | S5 | `backend/app/routing/`、`data/routing/`、`eval/` | 评估报告；工程问题不会全部被送云端 |
| T5 | 问题类型分类（concept / logistics）：准备标注数据，在路由模型里多训练一个输出 | S6 | T4 | `backend/app/routing/` | 准确率报告 |
| T6 | 新页面：选课程、课程管理、批量导入、课程设置 | S6 | Z9 的 OpenAPI | `frontend/src/pages/` | 界面测试覆盖主要流程 |
| T7 | 新页面：教师端 AI（四档）、个人概览、学习计划、可见性方案和学生不公开 | S6–S7 | S6～S10、Z12 的 OpenAPI | `frontend/src/pages/` | 同上 |
| T8 | "数据可能发往云端"的提示界面（文字由 Z 提供）；所有新页面的英法文字 | S6–S7 | Z11 | `frontend/src/i18n/` | 三处界面都有提示 |
| T9 | 演示账号和示例数据脚本（只通过 API 写入）；两门示例课程的演示流程 | S6 | Z9、S5 | `scripts/` | 一条命令建好演示环境 |
| T10 | 视频（11/25）；把法语界面截图发给 Lavin 审核并改回 | S6 | T3 | — | 按时交付 |
| T13 | 网络搜索（G1-92）+ 评估（G1-106）：搜索服务调用、可信网站白名单、结果清洗、作为资料交给生成步骤；查询只用 `search_query()`；出网只走统一的出网函数 | S7 | Z11、Z6 | `backend/app/websearch/`（新）、`config.yaml` 的 pipeline | E4 审计里搜索请求没有个人信息；评估报告 |
| T11 | 改名（定名后）；无障碍自查（键盘、屏幕阅读器、对比度、放大） | S7 | 定名 | `frontend/` | 自查清单 |
| T12 | 学生使用手册、教师使用手册；路由、前端、网络搜索的交接文档 | S8 | — | `docs/` | 新教师照着能用 |

### 7.4 前端技术栈（T）

**保留** React + Vite + TypeScript + Tailwind + TanStack Query + React Router，不换 Next.js。**加这些库**：

| 用途 | 库 |
|---|---|
| 基础组件 | **shadcn/ui**（Radix UI + Tailwind；组件代码复制进项目；自带无障碍） |
| 聊天组件 | **AI Elements**（Vercel，基于 shadcn）或 **assistant-ui**，二选一；要能接我们自己的 SSE 后端 |
| 回答渲染 | **react-markdown + remark-gfm** 或 **Streamdown**；**KaTeX**（公式）、**Shiki**（代码高亮） |
| 图标 / 动画 / 提示消息 | **lucide-react** / **Motion** / **sonner** |
| 表格 / 图表 / 表单 | **TanStack Table** / **Recharts** / **react-hook-form + zod** |
| 字体 | Inter 或 Geist |
| 出设计稿 | **v0** |

**界面要点**：
- **布局**：左侧栏放课程、主题、历史对话；对话区限宽居中；底部是圆角输入框和建议问题；支持深色模式。
- **回答**：
  - 逐字显示（等 Z6 的流式输出，之前先一次性显示）；
  - 路由过程做成可折叠的"思考过程"面板，默认收起；
  - 来源做成小卡片，显示文件名和页码或幻灯片号，鼠标移上去显示原文片段；
  - 每条回答有"本地 / 云端"标签，配隐私图标。
- **教师端**：shadcn 仪表盘样式，包括侧栏、统计卡片、数据表格、图表。
- **注意**：
  - shadcn 和 AI Elements 的最新版需要 Tailwind 4（多数组件按 React 19 写），先升级再引入；以官方文档为准。
  - 前端不做任何权限判断（规则 8）。

---

## 8. 开发流程

### 8.1 分支和 PR
- **从 `main` 开分支**，名字用 `<类型>/<任务ID>-<简述>`，例如 `feature/z4-course-catalog`、`fix/s3-citation-numbers`、`docs/t12-user-manual`。
- **一个任务一个 PR**。PR 描述要写：
  - 任务 ID；
  - 改了什么；
  - 怎么测的（贴测试结果）；
  - 对隐私或权限的影响（没有就写"无"）。
- **提交信息**沿用现在的风格：`<范围>: <做了什么>`，例如 `privacy: ...`、`feat(rag): ...`、`docs: ...`。
- **合并前**：CI 全绿，并经过组件负责人以外至少一个人看过。

### 8.2 本地运行和测试
- **安装**（第一次）：

  ```bash
  python -m venv .venv && .venv/Scripts/python -m pip install -e "backend[dev]"
  ```

  ```bash
  .venv/Scripts/python -m spacy download en_core_web_sm
  ```

  完整功能还需要 `en_core_web_lg` 和路由模型（`python -m app.routing.prepare`，在 `backend/` 下运行）。
- **后端测试**：在 `backend/` 下运行。**不要让开发用的 `.env` 影响测试**（例如 `CONTENT__SERVE_UNREVIEWED=true` 会让约 20 个测试失败）：临时把 `.env` 改名，或在没有 `.env` 的工作树里跑。

  ```bash
  python -m pytest -q
  ```

  ```bash
  TEST_LEARNER_KNOWLEDGE=rule python -m pytest -q
  ```

  ```bash
  python -m ruff check . ../scripts
  ```

  行宽上限 110（`backend/pyproject.toml`）。
- **评估的冒烟测试**（和 CI 一样）：

  ```bash
  python ../eval/privacy-audit/run.py --smoke --out ../eval-out/e4
  ```

  ```bash
  python ../eval/privacy-filter/run.py --smoke --out ../eval-out/e6
  ```

  改了隐私规则还要跑完整的 E6（`eval/privacy-filter/README.md`）。
- **前端**：在 `frontend/` 下运行。后端接口变了以后，先在 `backend/` 下运行 `python -m app.export_openapi` 更新 `frontend/openapi.json`，再在 `frontend/` 下运行 `npm run gen:api`。

  ```bash
  npm ci
  ```

  ```bash
  npm run build && npm test
  ```

- **完整运行**：

  ```bash
  docker compose up --build
  ```

  模型地址在 `.env` 里配置（参考 `.env.example`）。

### 8.3 测试要求
- **新接口**：正常流程 + 越权测试（其他课程的教师、其他学生、未登录）。
- **隐私相关**：用虚构数据；不要把真实学生信息写进测试、评估集或提交里。
- **模型相关**：单元测试用 `backend/app/llm/fake.py` 里的假模型，不依赖真实模型；需要真实模型的评估放在 `eval/` 下单独运行。

---

## 9. 已决定 / 待决定 / 不做

**已决定**：

| 事项 | 决定 |
|---|---|
| 示例课程 | 健康课 + ELG 5902 |
| 首批隐私档案 | 医学、生命科学、ECE |
| 部署 | 一套 Docker Compose；vLLM 单独部署、通过 API 连接 |
| 数据库 | PostgreSQL |
| 用量限制 | 先用配置文件，结构上为课程级设置留好位置 |
| 可见性方案 | 每门课选择，学生可以单独不公开 |
| 切换到方案 B | 之前的数据不显示 |
| 登录 | 现在用自建账号，预留 OAuth |
| 教师端 AI | 四档都做 |
| 知识模型 | 课程级分层模型，规则模型只兜底 |
| 网络搜索 | 归 T，按规则 6 做 |
| 以后的维护者 | 接手的学生团队 |

**待决定**：
- 项目名：候选 HALO（Hybrid Adaptive Learning Orchestrator）、COMPASS、CAIRN、MAPLE；
- vLLM 机器一直开着还是只在上课期间开；
- ELG 5902 材料的使用许可（Gita 教授）；
- 本学期交付范围（和 Ismaeel 教授、Abbas 教授确认）。

**不做（现阶段）**：中文、伦理审批、备份和硬盘加密、云端服务商比较。
