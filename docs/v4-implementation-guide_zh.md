# v4 实施指南（中文版）

> 这是 [v4-implementation-guide.md](v4-implementation-guide.md) 的中文对照版，方便组员阅读。**编码 agent 以英文版为准**（规则 14）。修改英文版时，请在同一个 PR 里同步修改本文件；来不及同步的话，就在本文件顶部注明"已过时"。
>
> 对应英文版：2026-11-04，基于 main `d774dfe`。

负责人：Z = 邢桢岩 Zhenyan，T = 刘恫铠 Tongkai，S = 谭斯允 Siyun

这份文件是 v4 改造的**唯一入口**，包括：背景、必须遵守的规则、目标架构、每个任务改哪些文件、怎么算完成、怎么测试。拿到一个任务 ID（例如 `Z4`）就可以开始。

本指南包含两份设计文档（目前只有英文版）：
- [design/course-structure.md](design/course-structure.md)：课程是什么、账号和角色、入学、学习者数据的范围、按课程的设置、数据库、迁移（任务 Z1，已决定）。
- [design/api-v2.md](design/api-v2.md)：HTTP 接口 v2 及其版本规则。

---

## 0. 怎么用这份文件

1. **先读第 1～3 节**：背景、规则、现有代码地图。
2. **找到任务**：在第 7 节找到自己的任务，确认它依赖的任务已经合并。
3. **按第 8 节**开分支、开发、测试、开 PR。一个任务一个 PR。
4. **只改自己组件的代码**（第 5 节）。需要别的组件配合时，只通过第 6 节的接口；接口不够用就在 PR 里提出，由负责人修改。
5. **这份文件或设计文档没写清楚的地方**，不要猜：在 PR 描述里写明你的假设，交给负责人确认。

---

## 1. 背景和目标

**现状（v3.1）**：一个班、5 个健康主题的隐私感知混合 AI 助教。
- **处理流程**：每个问题先过隐私过滤，再由路由选择本地模型还是云端模型。
- **检索**：MedlinePlus 和教师上传的资料。
- **个性化**：BKT 学习者模型。
- **教师端**：面板只能看班级汇总。
- **部署**：SQLite，Docker 跑 api + web。

**客户的要求**（11-03 会议，客户 Abbas 教授）：
- **原型阶段结束**：冬季学期给他的全部学生做 beta 测试，链接放在 Brightspace 里，界面要像正式产品。
- **不只做健康**：支持任何课程，以**整门课程的资料**为中心，包括大纲、项目要求、模板和讲义。
- **教师自己建课程。**
- **教师端 AI**：生成项目方向、示例提案等。
- **学生个人概览**：教师能看到每个学生的情况，并制定学习计划。
- **部署**：放在客户自己的环境。

**v4 目标**：在现有代码上**改造**（不重写），变成多课程、多教师的课程助教 **PACT**（Privacy-Aware Course Tutor，2026-11-17 定名）：
- 隐私规则按课程类型切换；
- 增加教师端 AI；
- 用一套 Docker Compose 部署。

**示例和测试课程**：8 门公开课程（MIT OpenCourseWare 和哈佛 CS50x，许可都是 CC BY-NC-SA 4.0），医学、生命科学、ECE、计算机科学各两门，以 zip 形式放在 `data/demo_courses/archives/`，使用前先运行 `python scripts/fetch_open_courses.py unpack` 解压（说明见 `data/demo_courses/README.md`）。课程包里有讲义、大纲、日历、作业和考试；答案单独放在 `instructor_only/`，永远不能当课程资料上传。**之后所有测试、评估和演示都用这些课程**（2026-11-12 决定，取代 ELG 5902）。虚构的 "General Medical Knowledge" 只留给 v3 迁移用。

**现阶段不做**：
- 中文界面，以及"兼容中文输入"以外的中文功能（规则 14）；
- 研究伦理审批（按教授的要求推进）；
- 数据库备份和硬盘加密；
- 云端服务商比较（以后用 GPT、Claude 或 Cohere，由客户决定）。

---

## 2. 不能违反的规则

改代码前必须读。违反任何一条的 PR 不能合并。

### 2.1 隐私
1. **不保存提问原文**：`privacy.log_raw_text` 必须是 `false`；日志、数据库、指标、错误信息里都不能出现学生原文或个人信息。
2. **原文只能发给"可信本地"模型**：只有标为可信本地的模型连接（默认的 vLLM）可以收到原文和完整的学习者档案。外部模型（云端、教师自己填的 API、网络搜索）只能收到通过云端关口的内容。v4 里由模型网关强制执行（Z6）。
3. **云端关口对所有路由都生效**（`backend/app/pipeline/steps/generate.py`）：个人病情问题按 `privacy.health_detail_policy` 处理；泄露检查拦截任何个人信息、学号、题目 ID、误解文字；被拦截或云端失败时用本地模型回答，并告诉学生原因。
4. **学习者档案永远不发给云端**；`profile_leak` 和 `pii_leak` 检查必须开着。
5. **修改隐私规则必须重跑 E6**（`eval/privacy-filter/`），结果不能变差；改了识别器却不跑评估的 PR 不合并。
6. **网络搜索的查询只能来自隐私模块的 `search_query()`**（Z11），搜索代码拿不到原文。

### 2.2 权限
7. **课程是权限边界**：每个接口先检查调用者在这门课里的角色。教师 A 看不到教师 B 的课，学生看不到别人的数据。每个新接口都要有这方面的测试。
8. **前端不做任何权限判断**：只显示后端返回的内容；不该显示的，后端就不返回。
9. **教师看单个学生**：只有课程用的是方案 B、并且这个学生没有选择不公开时才允许，而且只能看 `visible_since` 之后的数据；每次查看都写审计记录（course-structure.md 4.5）。

### 2.3 工程
10. **不提交密钥**：API key 和密码只放 `.env`（已在 git 忽略列表里）或 Docker secrets；不要写进代码、测试、文档和提交信息。
11. **每个组件只有一个负责人**（第 5 节）；不改别人组件的代码。
12. **CI 必须通过**：后端测试（跑两遍：默认 BKT 和 `TEST_LEARNER_KNOWLEDGE=rule`）、ruff、评估的冒烟测试、前端构建和测试、Docker 构建。
13. **隐私相关的固定值不进配置**：`log_raw_text`、必须开的检查项、识别器内部参数，留在代码或隐私档案里。
14. **只有功能代码为了兼容中文输入时才能出现中文；注释里永远不能有中文。**
    - **允许**：功能代码为了处理中文输入而需要的中文字面量（例如 `privacy/recognizers/zh_person.py` 里的规则、`recognizers/student_id.py` 的上下文词、`routing/evidence.py` 里的全角标点），以及测试这些功能用的中文测试输入和评估数据。直接写中文字符，不要写成 `\u` 转义。
    - **不能影响英文**：中文规则只能匹配中文文本。新增或修改中文规则的 PR，要说明英文测试和英文 E6 结果没有变化。
    - **必须用英文的**：注释和 docstring（中文规则用英文描述，例如"中文自我介绍后面跟名字"）、标识符、日志和报错信息、提交信息、PR 描述，以及 `docs/` 以外的所有 `.md` 文件。
    - **可以用法语的**：只有法语界面文字（`frontend/src/i18n/fr.ts`）、后端给用户看的固定文字的法语目录（`backend/app/api/v2/fr.yaml`，由 `app/api/v2/localize.py` 读取；Python 代码里不能写法语），以及法语识别器和这个目录的法语测试文本。
    - **`docs/` 不受此限**：可以放给组员看的中文对照文件，命名为 `<文件名>_zh.md`。agent 以英文文件为准；修改英文文档的人，要在同一个 PR 里同步修改对应的 `_zh` 文件，或者在 `_zh` 文件顶部注明"已过时"。
    - **清理**：注释里和 `docs/` 以外 Markdown 里的中文由 Z15 和 T14 清理。
15. **只在 API v2 上开发**（design/api-v2.md）：`/api/v1` 已冻结，新接口和新字段都放进 `/api/v2`。v2 里只允许增加；不兼容的修改要开 `/api/v3`，由 Z 决定。

---

## 3. 现有代码地图（main `d774dfe`）

| 部分 | 位置 | 说明 |
|---|---|---|
| 配置 | `config.yaml`、`backend/app/core/config.py` | pydantic 设置；环境变量 `SECTION__FIELD` 覆盖 yaml |
| 服务装配 | `backend/app/core/services.py` | `build_services()`；`reconfigure()` 会替换全局对象（v4 删除，见 4.4） |
| 注册表 | `backend/app/core/registry.py` | 路由、检索、知识模型、检查项、处理步骤都按名字注册，由配置选择 |
| 处理流程 | `backend/app/pipeline/runner.py`、`steps/*.py` | 步骤列表在 `config.yaml` 的 `pipeline`；共享一个 `RequestContext`（`core/schemas.py`） |
| 隐私 | `backend/app/privacy/`（`analyzer.py`、`recognizers/`、`generalize.py`、`llm_check.py`、`policy.py`、`session_health.py`） | Presidio + spaCy `en_core_web_lg` + 自定义识别器 |
| 云端关口 | `backend/app/pipeline/steps/generate.py`、`backend/app/llm/cloud_guard.py` | 所有路由共用 |
| 模型客户端 | `backend/app/llm/`（`ollama_client.py`、`openai_compat.py`、`factory.py`、`fake.py`） | 测试用 `fake.py` |
| 路由 | `backend/app/routing/`（`semantic.py`、`evidence.py`、`methods/`、`train.py`、`prepare.py`） | MiniLM + LR/SVM；模型文件在 `data/routing/models` |
| 检索 | `backend/app/rag/`（`medical_hybrid.py`、`documents.py`） | BM25 + TF-IDF；每个主题一个索引；PR #16 之后支持 PDF 页码 |
| 学习者 | `backend/app/learner/`（`knowledge/`、`preference/`、`recommender.py`、`content.py`、`understand.py`） | `KnowledgeModel` 接口在 `knowledge/interface.py` |
| 检查 | `backend/app/verify/checkers/`（`grounding.py`、`medical_safety.py`、`leaks.py`） | `medical_safety` 目前是必选（`admin/runtime_config.py` 的 `REQUIRED_CHECKERS`） |
| 存储 | `backend/app/storage/`（`db.py`、`models.py`） | SQLModel + SQLite；没有迁移工具 |
| 账号 | `backend/app/auth/` | Argon2 哈希；服务器端会话；cookie `SameSite=lax`，`Secure` 由 `cookie_secure` 控制 |
| 教师端后端 | `backend/app/admin/`、`backend/app/api/v1/admin*.py` | 全局设置、上传、班级汇总、日志 |
| 内容 | `content/topics/<topic>/{kcs,items,misconceptions}.yaml` | 启动时加载；`reviewed_by`（v4 删除） |
| 前端 | `frontend/src/`（`pages/`、`pages/admin/`、`components/`、`i18n/en.ts`、`i18n/fr.ts`、`api/schema.d.ts`） | React 18 + Vite + Tailwind 3 + TanStack Query；API 类型由 `npm run gen:api` 从 `frontend/openapi.json` 生成 |
| 评估 | `eval/`（`privacy-filter/` E6、`privacy-audit/` E4、`learner-sim/` E2、`personalization/` E3、`course_rag_benchmark.py`） | CI 里跑冒烟模式 |
| 部署 | `docker-compose.yml`、`backend/Dockerfile`、`frontend/Dockerfile` | 现在是 api + web |
| CI | `.github/workflows/ci.yml` | backend、frontend、docker 三个任务 |

**已知问题**：
- 回答里的 `**粗体**` 前端显示成星号（T3）。
- 回答里的引用编号 `[i]` 按段落编号，Sources 列表按文件去重后编号，两者可能对不上（S3）。
- 截图时 `understand` 连续两次 5 秒超时（Z2/Z6 的压测会定出合适的超时）。
- 开发用的 `.env` 里如果有 `CONTENT__SERVE_UNREVIEWED=true`，会让约 20 个测试失败（Z4 会删掉这个设置）。

---

## 4. 目标架构（v4）

### 4.1 改造，不重写

处理流程、注册表、隐私、路由、模型客户端、检查项、学生端前端都保留，大多数改动只是多传一个参数（课程）。下面几块因为前提变了，要重写或大改：

| 模块 | 改动 |
|---|---|
| `storage/` | 重写：PostgreSQL + Alembic；处处加课程字段 |
| `core/topics.py`、`learner/content.py` | 重写为**课程目录**：内容存数据库，由教师创建 |
| `admin/runtime_config.py`、`services.reconfigure` | 重写为**设置分层 + 按请求取值**（4.4） |
| `rag/medical_hybrid.py` | 改造并改名为课程检索器：每门课一个磁盘索引，资料分课程级和模块级 |
| 教师端前端页面 | 大部分新写 |

### 4.2 部署：一套 Docker Compose

```
浏览器 ──HTTPS 443──► proxy（Caddy：自动 HTTPS，提供前端，/api 转给 api）
                       │
                       ├─ api     FastAPI
                       ├─ worker  同一个镜像，跑后台任务（索引、教师端 AI、评估、每日用量重置）
                       ├─ db      PostgreSQL（数据卷）
                       └─ 监控    Prometheus + Grafana（可选的 compose 配置）
api / worker ──► vLLM 本地模型服务（单独部署，不在 compose 里；OpenAI 兼容 API + API key；可信本地）
api / worker ──► 外部模型 API（云端模型、教师自己的 OpenAI 兼容 API；只收脱敏内容）
```

- **两个 Docker 网络**：
  - 对外网络：proxy、api、worker；
  - 内部网络：`internal: true`，db 只在这里，api 和 worker 两边都接。
- **端口**：只映射 443（80 只用来跳转）；db 和监控不映射到主机。
- **vLLM**：设 API key；vLLM 主机的防火墙只允许应用主机访问；经过公网时用 HTTPS。
- **本地开发**：把 `VLLM_BASE_URL` 指向实验室的 vLLM，或你自己的任何 OpenAI 兼容服务即可。
- **应用主机**：不需要 GPU。

### 4.3 组件

| 组件 | 职责 |
|---|---|
| 身份和权限 | 账号、登录身份（密码；以后 Microsoft Entra ID / Brightspace LTI）、会话、系统角色和课程角色、权限检查 |
| 课程目录 | 课程、模块、知识点图、检测题、误解、资料、成员、邀请码 |
| 设置 | 系统设置 + 课程设置 + 配置文件 + 硬上限 → 本次请求的有效设置 |
| 提问流程 | 按配置的步骤运行（4.5） |
| 学习者服务 | 课程级知识模型、偏好、学习计划、可见性方案、不公开状态 |
| 隐私服务 | 隐私档案注册表、识别、脱敏/还原、云端关口、改写、`scan_document()`、`search_query()` |
| 模型网关 | 模型连接注册表（可信本地 / 外部）、排队、超时、计量、按 token 流式输出、防 SSRF |
| 检索服务 | 解析（pdf、docx、pptx、html、md、txt）、分段、每门课一个磁盘索引 |
| 检查服务 | 由隐私档案决定启用哪些检查项 |
| 教师端 AI | 四档功能；草稿 → 接受 |
| 网络搜索 | 可信网站白名单、清洗结果；查询只来自 `search_query()` |
| 可观测 | `/metrics`、不含个人信息的结构化日志、审计记录 |

### 4.4 设置分层

| 层 | 内容 | 谁能改 |
|---|---|---|
| 1. 代码常量 | 安全不变量（`log_raw_text=false`、必须开的检查项、识别器内部参数） | 只能改代码 |
| 2. `config.yaml` | 默认值和**硬上限**（新增 `limits` 段，见下表） | 部署的人 |
| 3. 环境变量 / `.env` / Docker secrets | 数据库地址、API key、会话密钥 | 部署的人 |
| 4. `system_settings` 表 | 默认模型连接、启用的课程类型、可选的检查项、弱证据、等级阈值 | 管理员（网页） |
| 5. `course_settings` 表 | course-structure.md 6.4 节列出的字段，全部允许为空 | 课程教师（网页） |

**取值规则**：只通过 `effective_settings(course_id)` 取值；API 层把结果放进 `RequestContext.settings`，各步骤只读这一份。从第 5 层往上找第一个有值的层，再按第 2 层的硬上限截断；第 1 层不能被覆盖。

**怎样做到又省又稳**（详见 course-structure.md 第 6 节）：
- **设置页面上的任何设置都不用重启**：
  - 改"值"（阈值、课程类型等），下一个请求就生效；
  - 改"组件"（知识模型、可选检查项、默认路由方法、默认模型连接），每个进程在后台建好新组件再切换过去；在所有进程都换好之前，这行设置是锁定的（返回 423，保存按钮不可点），失败或超时会自动回滚；
  - `services.reconfigure` 删掉。
- **写入**：每张表的每行都有 `version`；写入时检查版本，被别人改过就返回 409，避免互相覆盖。写入在一个事务里完成，同时写一条 `config_history` 和一条审计记录；历史可以恢复。
- **读取**：每个请求只做一次主键查询，再加一个按版本号做键的进程内缓存。所以每个进程在下一次请求时就能看到修改，不需要定时器，进程之间也不用互发消息。
- **快照**：一个请求（或一个后台任务）从开始到结束都用同一份设置快照。

**用量限制**：现在只用配置文件；课程表里的 `usage_*` 字段先保持为空、不在界面上开放。用量计数从一开始就按"学生 + 课程 + 日期"存。

**要搬进 `limits` 的写死值**（Z5）：

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
| 新增 | 本地模型并发数、排队上限、排队超时；云端每日调用和费用上限；每个学生每分钟、每天的提问次数和每天的云端次数；登录失败上限和锁定时间；允许的邮箱域名；导出文件保留时间；邀请码有效期 |

### 4.5 提问流程（v4）

| # | 步骤 | 变化 |
|---|---|---|
| 0 | API 层 | 登录 + **课程角色检查** + **用量检查**；生成 `ctx.settings` 和 `ctx.profile` |
| 1 | `privacy_filter` | 按课程类型加载**隐私档案**（基础层 + 学科档案） |
| 2 | `understand` | 不变；"事务问题还是知识问题"由路由的新输出给出（T5） |
| 3 | `learner_context` | 按课程读取；带上教师的**学习计划**；事务问题跳过 |
| 4 | `analyze_route` | 多一个输出字段 `question_kind` |
| 5 | `retrieve` | 课程级资料 + 所选模块（或整门课）；事务问题优先检索大纲和项目要求 |
| 6 | `route` | 课程设置：`local_only`、`routing_preference`、`routing_threshold` |
| 6a | `web_search`（新，可选） | 只在走云端、需要最新信息时运行；查询来自 `search_query()`；只访问白名单网站 |
| 7 | `generate` | 只通过**模型网关**调用模型，网关检查可信级别；支持按 token 流式输出 |
| 8 | `restore` | 不变 |
| 9 | `verify` | 检查项由隐私档案决定（只有医学课开 `medical_safety`） |
| 10 | `attach_check` | 事务问题不附检测题 |
| 11 | `record` | 另外记录用量计数和指标；仍然不存原文 |
| 12 | `update_learner` | 用课程级知识模型；学习者状态按课程存 |

### 4.6 数据模型

在 [design/course-structure.md](design/course-structure.md) 第 3～11 节（只用 PostgreSQL）。要点：
- 系统角色：admin / instructor / student；
- 一个 uOttawa 邮箱一个账号；
- 课程 → 模块，两层；
- CSV 导入 + 邀请码；
- 学习数据按 `student_id` + `course_id` 存，偏好和同意书是全局的；
- 结束学期 = 先导出，再删除这门课的学生数据。

### 4.7 隐私档案（按课程类型）

- **基础层（所有课程）**：
  - 姓名、学号、邮箱、电话、地址、出生日期、证件号、成绩；
  - 一个轻量的个人健康和特殊情况识别（任何课里都可能出现"我生病了能不能延期"）。
- **首批档案**：

| 课程类型 | 额外识别 | 其他不同 |
|---|---|---|
| 医学 | v3 完整的病情规则（`health_detail`、`health_context`、读数、跨消息病情、`generalize` 改写） | `medical_safety` 检查、"不是医疗建议"提示 |
| 生命科学 | 研究参与者和样本编号、实验室里的个人信息；生物学术语不当作个人病情 | 不加医疗安全检查 |
| 电气与计算机工程（ECE） | 代码里的密钥、令牌、密码、私有仓库地址、内网 IP、连接字符串；MAC 地址、序列号；电路和信号数值（V、mA、kΩ、Hz、dB）不当作个人读数 | 代码片段原样保留 |
| 通用（默认） | 只有基础层 | — |

- **扩展**：每个档案是一个配置文件（例如 `backend/app/privacy/profiles/ece.yaml`），列出识别器、词表、策略、检查项和界面提示。新识别器按现有方式注册。
- **测试集**：每个档案附一个标注测试集，加一个"其他学科术语"集，用来测误遮挡。

### 4.8 可见性方案（每门课由教师选）

- **方案 A**：教师只看班级汇总（和 v3 一样）。
- **方案 B**：教师可以看个人概览：
  - 知识点掌握程度和趋势、检测题记录、误解、偏好、活跃程度；
  - 提问原文仍然不保存，所以看不到；
  - 教师可以制定学习计划（重点知识点、目标、难度、备注）。
- **透明**：学生在加入课程、入学问卷、"What I know"页面都能看到当前方案，也能看到老师看到的内容和计划。
- **切换**：
  - B → A 立即生效；
  - A → B 要先通知学生，学生确认后才对他生效，而且**只显示确认之后的数据**。
- **不公开**：方案 B 下学生可以隐藏自己的数据。教师看到"该学生选择不公开"；他的数据只计入班级汇总；不能给他定学习计划；系统的自动个性化照常。
- **审计**：每次查看个人概览都记录。
- **小测结果**遵守同样的规则（course-structure.md 4.6）：班级汇总要达到最小组人数才显示；个人结果只在方案 B、学生已确认、没有选择不公开、且是 `visible_since` 之后的作答时才显示，并记录审计。

### 4.9 教师端 AI（四档）

| 档 | 功能 | 规则 |
|---|---|---|
| 1 | 根据课程资料：项目方向和项目清单（难度、知识点、交付物）、示例提案或写作指南、FAQ（截止日期、评分） | 草稿；教师接受后学生才看得到 |
| 2 | 从讲义起草知识点、依赖关系、检测题、误解 | 草稿 → 接受后进入正式表 |
| 3 | 班级洞察：学生最常问哪些知识点、最常见的误解 | 只有标签和数字，不返回原文 |
| 4 | 本地模型能不能胜任这门课？用资料生成测试题（教师可抽查），本地和云端模型都带 RAG 作答，评审模型打分 + 教师抽查，按模块和题型出报告，带延迟和费用 | 只用生成的题目，不涉及学生；把课程资料发给云端前要教师同意 |

另外：
- **小测**（任务 Q1）：教师自己写，或由本地模型根据课程资料起草选择题和判断题（任务 `quiz.draft`，只走可信的本地连接，不涉及学生数据）；教师审阅后发布；AI 起草的题没审阅就不能发布；
- 教师端的提问不走个性化，也不写入学习者模型；
- 生成功能只通过模型网关调用模型；
- 上传的文件先过 `scan_document()`（文件里可能有学生名单）。

**"数据可能发往云端"的提示**：
- **学生端**：同意书、聊天页常驻提示、每条回答的"本地 / 云端"标签；
- **教师端**：使用生成功能前提示；
- **课程设置**："本课程只用本地模型"。

### 4.10 课程级知识模型

- **分层模型**：
  - 每个学生在每门课有一个**整体能力值**（类似 Elo/IRT，每次作答在线更新）；
  - 在它的基础上，知识点级用 BKT 或 PFA 修正；
  - 沿依赖图传播（基础知识点弱，后续知识点的估计也往下调）。
- **规则模型**：只在出错时兜底，不做主要模型。
- **接口**：实现现有的 `KnowledgeModel` 接口（`backend/app/learner/knowledge/interface.py`，增加 `course_id` 参数），按名字注册，以后可以换成深度知识追踪模型。

### 4.11 模型连接

- **默认**：系统有一个可信本地模型（部署时配置的 vLLM）。
- **可以修改**：教师可以改成自己的 OpenAI 兼容 API（地址、模型名、API key）；云端模型同理。
- **隐私提示**：设置页要提醒"把本地模型指向别人的服务，学生原文就会发到那里"，并要教师确认这个服务归他控制。
- **防 SSRF**：
  - 拒绝链路本地地址（`169.254.0.0/16`，含云平台元数据地址）；
  - 拒绝本系统的服务名和地址（db、proxy 等）；
  - 外部连接还要拒绝私有地址段。
- **API key**：加密存储，只显示后几位，修改写审计记录。
- **GPU 规格**：能跑 9B 模型；通过 OpenRouter 对比 27B（Z2）。OpenRouter 只发生成的测试题。

---

## 5. 组件归属

| 组件 | 负责人 |
|---|---|
| 平台（存储、课程目录、设置分层、账号和登录、课程和成员后端、用量、权限检查、CSRF、登录限流） | Z |
| 隐私（档案、识别、云端关口、改写、`scan_document()`、`search_query()`、同意书内容） | Z |
| LLM 部署和测试（模型网关、vLLM 连接和压测、流式输出、9B / 27B 对比、教师端 AI 第四档） | Z |
| Docker 部署和运维（compose、proxy、监控、CI 漏洞扫描、运维手册） | Z |
| 检索和课程内容（`.pptx`、引用编号、课程检索器、示例课程资料、检索评估） | S |
| 教师端 AI 一到三档（后端） | S |
| 学习者（课程级知识模型、学习计划、可见性方案、个人概览、不公开、审计，后端） | S |
| 路由和网络搜索（ECE 路由评估和训练、问题类型分类、网络搜索） | T |
| 前端界面和体验（全部页面、改版、英法文字、改名、无障碍、界面测试） | T |
| 演示材料和用户文档（演示数据脚本、使用手册、视频、Lavin 的法语审核） | T |

**为什么 T 负责这些**：
- 不涉及权限和隐私判断；
- 对错容易检查；
- 和其他代码隔离；
- 容易回退。

给 T 用的 agent 要特别遵守 2.1、2.2 节；网络搜索只用 `search_query()`。

---

## 6. 接口约定

具有约束力的函数签名在 [design/course-structure.md](design/course-structure.md) 第 9 节；HTTP 接口和负责人在 [design/api-v2.md](design/api-v2.md)。

| 提供方 | 接口 | 使用方 |
|---|---|---|
| Z | `effective_settings(course_id)` | 所有人 |
| Z | `require_course_role(...)`、`require_system_role(...)`（FastAPI 依赖） | 所有后端接口 |
| Z | `check_usage(...)` / `record_usage(...)` | API 层、生成步骤 |
| Z | 模型网关 `complete(role, messages, *, settings, trust_required, stream=False)`；角色 `local`、`cloud`、`judge` | S（教师端 AI）、T（网络搜索后的生成）、处理流程 |
| Z | `privacy_profile(course_type)`、`scan_document(text, profile)`、`search_query(ctx)` | 处理流程、S（上传）、T（网络搜索） |
| Z | 课程、模块、知识点、成员、设置、用量的接口 + OpenAPI | T（前端） |
| S | `CourseRetriever.retrieve(course_id, module_id, query, k)` | 处理流程 |
| S | `profile_for_instructor(viewer, student_id)`（内部检查方案、不公开和 `visible_since`） | 教师端接口 |
| S | 检索、教师端 AI、学习者的接口 + OpenAPI | T（前端） |
| T | `SemanticAnalysis.question_kind`（`"concept"` 或 `"logistics"`） | 处理流程 |
| T | `web_search(query, allowlist)` | 处理流程 |

**并行开发**：提供方先合并接口签名和返回示例数据的假实现；使用方按假实现开发，不用等真正的实现。

---

## 7. 任务

| Sprint | 日期 | 课程节点 |
|---|---|---|
| S4 | 11/4–11/10 | Beta 11/11 |
| S5 | 11/11–11/17 | |
| S6 | 11/18–11/24 | 视频 11/25 |
| S7 | 11/25–12/2 | Design Day 12/3 |
| S8 | 12/3–12/13 | Final 12/13 |

"独立"表示不依赖 Z1 的代码，可以马上开始。

### 7.1 邢桢岩 Z

| ID | 任务 | Sprint | 依赖 | 主要文件 | 完成标准 |
|---|---|---|---|---|---|
| Z1 | 课程结构和接口约定（设计文档已完成）+ 代码里的接口签名和假实现；`RequestContext` 加上 `course_id`、`module_id`、`settings`、`profile` | S4，**11/7 前** | — | `docs/design/`、`backend/app/core/schemas.py`、新的 `backend/app/platform/` | S、T 确认；假实现已合并 |
| Z2 | 9B vs 27B：27B 走 OpenRouter，同一批课程问题、都带 RAG；给出 vLLM 机器规格和费用 | S4–S5 | 独立 | 新的 `eval/model-compare/` | 对比报告 |
| Z3 | PostgreSQL + Alembic；Postgres 测试夹具和 CI 服务；去掉 SQLite | S5 | Z1 | `backend/app/storage/`、新的 `backend/alembic/`、`.github/workflows/ci.yml` | CI 在 Postgres 上跑 |
| Z4 | 课程目录：course-structure.md 第 10 节的表；知识点、检测题、误解从 YAML 进数据库；v3 迁移脚本（第 11 节）；删除 `serve_unreviewed` 和 `reviewed_by` | S5 | Z3 | `storage/models.py`、`core/topics.py`、`learner/content.py`、`scripts/` | 现有测试在迁移后的"General Medical Knowledge"课程上通过 |
| Z5 | 设置分层（course-structure.md 第 6 节）：带版本的 `system_settings`、`course_settings`，版本检查、历史和恢复、按版本的缓存、`effective_settings()`、`limits`（4.4 的表）；迁移 v3 最新一条 `config_history`；组件的在线切换，包括应用状态、锁定和回滚（第 6.5 节），以及 `process_status` 心跳；删除 `services.reconfigure`；各步骤读 `ctx.settings` | S5 | Z3 | `core/config.py`、`core/services.py`、`admin/runtime_config.py`、`pipeline/steps/*`、`config.yaml` | 不再直接读这些常量；两门课互不影响 |
| Z6 | 模型网关：连接注册表、可信级别、教师的 OpenAI 兼容 API、API key 加密、防 SSRF、排队和超时、按 token 流式输出；vLLM 压测 | S5–S6 | Z5 | `backend/app/llm/`（新的 `gateway.py`）、`admin/llm_server.py` | 内部地址被拒绝；外部连接收不到原文（有测试）；压测报告 |
| Z7 | 隐私档案框架：基础层 + 档案配置文件 + 识别器注册；按课程类型选档案 | S5 | Z5 | `backend/app/privacy/`（新的 `profiles/`） | 加新档案只需一个配置文件；E6 不变差 |
| Z8 | Docker Compose 骨架：proxy（Caddy）、api、worker、db；两个网络 | S5 | — | `docker-compose.yml`、新的 `deploy/Caddyfile` | 本地一条命令起全套 |
| Z9 | API v2：认证（用邀请码激活）、管理员、课程、成员（CSV 导入）、邀请码、结束学期和导出、模块、知识点、检测题、误解、YAML 导入导出、设置；`login_identity` | S6 | Z4 | 新的 `backend/app/api/v2/`、`backend/app/auth/` | OpenAPI 交给 T；权限测试 |
| Z10 | 用量计数和限制；所有接口的权限测试；CSRF；登录限流；改密码和退出让所有会话失效 | S6 | Z4 | `backend/app/auth/`、`backend/app/platform/` | 权限测试覆盖所有接口 |
| Z11 | 医学档案（迁入 v3 规则）+ ECE 档案 + ECE 测试集；`scan_document()`；`search_query()`；同意书内容 | S6 | Z7 | `privacy/profiles/`、`eval/privacy-filter/` | E6 不变差；ECE 有结果 |
| Z12 | 教师端 AI 第四档：本地 vs 云端评估 | S7 | Z6、S4 | 新的 `backend/app/instructor_ai/eval/` | 能对一门课出按模块的报告 |
| Z13 | 整套部署到测试主机；监控（应用 `/metrics`、vLLM 指标、Grafana、告警）；CI 扫描（`pip-audit`、`npm audit`、`bandit`、镜像扫描） | S7 | Z8 | `docker-compose.yml`、`deploy/`、`.github/workflows/ci.yml` | 客户和 Lavin 能试用；能看到指标 |
| Z14 | 部署和运维手册、交接文档、压测 | S8 | — | `docs/` | 新人照着能部署 |
| Z15 | Z 代码的规则 14：`privacy/recognizers/zh_person.py` 和 `recognizers/grade.py` 的 docstring 改成英文（中文规则保留）；补测试，证明中文规则不改变英文输入的结果；`eval/model-boundary-test/` 的 `README.md` 和 `TEST_PLAN.md` 改成英文；重跑 E6 | S5 | — | 上述文件 | 注释、docstring 和 `docs/` 以外的 Markdown 里没有中文；英文测试和英文 E6 结果不变 |
| Z16 | 按学科回答（审查 B1、B2）：隐私配置决定系统提示词和检查器；非医学课程不再用健康教育提示词和医学安全检查 | S8 | Z7 | `prompts/`、`privacy/profiles/`、`pipeline/steps/verify.py` | 非医学课程的端到端测试验证提示词和检查器；E6 不变差 |
| Z17 | 本地模型调用走网关（审查 B3）：understand、generalize 改写和 `llm_check` 用课程的可信本地连接，不再固定用 Ollama | S8 | Z6 | `llm/`、`pipeline/steps/` | 三处调用在 OpenAI 兼容服务（vLLM）上可用 |
| Z18 | 仓库清理（审查 B5、第 7 节）：已合并分支、无用文件，过时文档移到 `docs/history/` | S8 | — | 仓库根目录、`docs/` | 审查列出的无用文件都已处理；链接仍然有效 |
| Z19 | 答案里的课程来源（11/16 截界面图时发现）：证据步骤丢掉了课程检索的全部段落（主题是 `course:<id>`，问题的主题是模块代码或 `general`），答案没有来源 | S8 | — | `routing/evidence.py` | 本次请求所在课程的段落能进答案；别的课程的段落永远不能 |
| Z20 | vLLM 上的结构草稿（11/16 截界面图时发现）：可信本地的 OpenAI 兼容连接收到 JSON schema，而不只是 `json_object`；第 2 层草稿可用 4,096 个输出 token；schema 只允许引用已接受的知识点；无效的前置知识点链接去掉，不再整份草稿作废 | S8 | Z6 | `llm/`、`instructor_ai/structure_drafts.py` | 知识点、检查题、迷思草稿在测试主机的 vLLM 上都能成功 |
| Z21 | 文档更新到当前状态（2026-11-17）：v3 的实施日志移到 `docs/history/`；v3 设计和隐私报告加状态说明；HANDOVER、OPERATIONS、MODEL_CONNECTIONS、ACCESSIBILITY 更新到 2026-11-17 | S8 | — | `docs/`、`AGENTS.md`、`README.md` | `docs/` 里 `history/` 以外的文档不把过去的状态写成现状 |
| Z22 | v4 还缺的隐私过滤测试（2026-11-17 发现）：ECE 规则冻结之后再写、再标注的 ECE 留出集（现有 47 题是对着规则写的）；`life_science` 和 `general` 配置的测试集；E6 给 v4 新类型（`SECRET`、`INTERNAL_ADDRESS`、`REPO_URL`，现在只有 ECE 集测）打分；新的医学留出集，测现在规则的泄漏率（v4 只证明了 E6 没有变差） | S8 | Z11 | `eval/privacy-filter/` | 每个新集在 `eval/privacy-filter/results/` 有报告；由此改的规则重跑 E6 |
| Z23 | vLLM 容量（2026-11-17 发现）：`eval/load-test/run.py` 记录每个回答的输出 token 数，报告每个请求和合计的 token/秒；在测试主机上用 `--stream` 和较长的回答（`--max-tokens 400`）跑 1、4、8、16、32 并发；按结果定 `limits.models.max_concurrent`（现在 4）和 `queue_timeout_seconds`（现在 60）的默认值（检查题草稿要 45–50 秒）；在 vLLM 上给一次提问的每一步计时（Z2）；写明超过 5 个学生同时提问需要什么显卡 | S8 | Z6 | `eval/load-test/`、`backend/app/core/config.py`、`docs/OPERATIONS.md` | 有每档并发的 token/秒报告；OPERATIONS.md 的限制和显卡建议以它为准 |
| Z24 | 部署默认的本地模型就是它的 vLLM（审查 A4、I9；PR #107）：用 `VLLM_BASE_URL` 和 `VLLM_KEY` 取代 `OLLAMA_URL`（以及它指向团队内网的默认地址）；回答和 understand 两个本地客户端都走 OpenAI 兼容接口，并且是可信本地（关闭思考、按 JSON schema 输出）；可信本地 OpenAI 兼容服务的回答记为本地，不再记成云端；健康检查、v1 服务器测试、`setup_local.py` 和 E1/E3/E6 评估脚本都用同一台服务器 | S8 | Z17 | `core/config.py`、`llm/`、`admin/llm_server.py`、`eval/` | 只有 vLLM 的部署不用登记模型连接就能本地回答；除了 `ollama` 类型的模型连接，不再有 `OLLAMA_URL` |
| Z25 | 课程资料的文档扫描（2026-11-17 发现）：CS50x 课程包的 `assignments/pset_5.md` 是公开的课程内容，上传时却被当成学生数据（`GRADE`）拒绝。找出是哪段文字触发的，统计八个公开课程包所有文件被拒的情况，只拒绝真正的学生数据 | S8 | Z7 | `backend/app/privacy/`、`backend/app/rag/index_jobs.py` | 八个课程包没有文件被拒；E6 分数不变差 |
| Z26 | 让模块的 guideline 起作用（2026-11-17 发现）：Modules 页上的 **Guideline for the tutor** 会保存、导出、导入，但提问流程的每一步都不读它，所以对回答没有影响（v3 也一样）；教师手册第 3 节却说它会用在回答里。问题限定在某个模块时，把这个模块的 guideline 交给生成回答的模型（本地和云端都可以；这是教师写的文字，不是学生数据），限制长度，放在基础规则之后，不能覆盖基础规则 | S8 | Z16 | `backend/app/pipeline/steps/generate.py`、`backend/app/prompts/` | 有测试：模块的 guideline 进了关于这个模块的问题的提示词，不进其他模块或整门课的问题；手册那句话属实 |
| Z27 | 整个系统的网络安全审查（2026-11-17 提出）：登录和会话（cookie、密码存储、频率限制、退出登录）、CSRF、每个接口的角色检查（规则 3 和 9）、模型连接和网页搜索的 SSRF、上传（压缩包、XML、大小限制、文档扫描）、通过课程资料和搜索结果的提示词注入、存储的 API key、代理的安全头和 TLS（CSP、HSTS）、Compose 的两个网络和外部能访问到什么、数据库和 worker 是否暴露、日志（不含问题原文）、依赖和镜像扫描、仓库历史里有没有密钥 | S8 | Z10, Z13 | 新的 `docs/SECURITY_REVIEW.md`；修复在各负责人的组件里 | 有报告，每个发现写明风险和负责人；高风险的已修或已开任务 |

**落后时按这个顺序往后推**：Z12 → Z13 里的 Grafana 和告警 → `login_identity`。

### 7.2 谭斯允 S（都是后端）

| ID | 任务 | Sprint | 依赖 | 主要文件 | 完成标准 |
|---|---|---|---|---|---|
| S1 | PR #16 收尾：页码标签由前端翻译（后端只返回页码）；`docs/RAG_COURSE_BETA.md` 改用相对路径 | S4 | 独立 | `backend/app/api/v1/ask.py`、`docs/RAG_COURSE_BETA.md` | 已合并 |
| S2 | `.pptx`：`python-pptx` 读取每页的文字、表格和演讲者备注；每段记录 `slide N`；页标题作为分段标题；检查解压后大小；全是图片时给出明确错误；用虚构的 3 页 PPT 测试 | S4–S5 | S1 | `backend/app/rag/documents.py`、`admin/materials.py` | 测试通过；来源显示 slide N |
| S3 | 引用编号和 Sources 列表对齐 | S5 | S1 | `backend/app/api/v1/ask.py`、`backend/app/prompts/render.py` | 有测试 |
| S4 | 课程检索器：课程级和模块级资料；每门课一个磁盘索引，带 `index_version`；后台任务重建；上传时调用 `scan_document()` | S5–S6 | Z4、Z11（先用假实现） | `backend/app/rag/`（`medical_hybrid.py` 改名并改造） | 大纲和项目要求能被检索到 |
| S5 | 示例课程资料：`data/demo_courses/` 里的 8 个公开课程包（Z 已做好，见 7.5）；剩下的是确认每个课程包都能通过课程检索器上传和检索 | S5 | 独立 | `data/`（目录按 course-structure.md 第 7 节） | 8 门课都能上传和检索 |
| S6 | 教师端 AI 第一档后端，通过模型网关 | S6 | S4、Z6 | 新的 `backend/app/instructor_ai/` | 教师接受后学生才看得到 |
| S7 | 教师端 AI 第二档后端（知识点、检测题、误解；草稿 → 接受）；课程摸底题也用它（D3） | S6–S7 | Z4、S4 | 同上 | 新课程可以由 AI 起草，接受后用于个性化 |
| S8 | 课程级知识模型（4.10）。**已完成**（#87）：`learner.knowledge: course`，设为默认；`app/learner/knowledge/course.py` | S6–S7 | Z4 | `backend/app/learner/knowledge/` | 和现有 BKT 的对比评估（`eval/learner-sim/`） |
| S9 | 可见性方案 A/B、个人概览、学习计划、不公开、审计；结束学期导出的内容 | S6–S7 | Z4、Z10 | `backend/app/learner/`、`backend/app/api/v2/` | 测试覆盖"不该看到的不返回" |
| S10 | 教师端 AI 第三档：班级洞察后端 | S7 | S8 | `backend/app/instructor_ai/` | 不返回原文 |
| S11 | 公开课程包的检索评估，八个课程包都已在 `eval/course-rag-packs/` 完成（题集、`run.py`、`results/report.md`）；`eval/course_rag_benchmark.py`（人工标注段落）是另一个独立的评估程序，不属于这一项 | S7 | S5 | `eval/` | 八个课程包都有结果 |
| S12 | 自查和交接文档 | S8 | — | `docs/` | 自查清单 |
| S13 | 面向全课程的学习档案（2026-11-17 提出）：现在入门流程要学生先选一个模块，只做那个模块的诊断题（`pages/student/Start.tsx`，`GET .../onboarding/{module_id}`）；学习档案、班级汇总和教师看到的学生情况都按模块分开列（`api/v2/learner.py` 的 `ModuleProfile`）。档案应该描述学生在整门课里的情况：每门课只做一次入门，诊断题从所有模块里抽；最上面是全课程的汇总（总体水平、最强和最弱的话题、未解决的误解），按模块的细节放在下面。API v2 只做加法（规则 8）；前端部分（入门、My progress、教师看学生的页面）和 T 一起做 | S8 | S8 | `backend/app/learner/`、`backend/app/api/v2/learner.py`、`frontend/src/pages/student/` | 每门课一次入门；My progress 和教师看到的页面先显示全课程汇总；访问测试不变 |
| S14 | 再审一遍检索怎样把课程资料交给本地模型，特别是教学大纲和其他课程级文件（2026-11-17 提出）：关于大纲的问题不能因为换了个说法就答不出。检查课程级文件怎么切块（章节、日程和评分这类 Markdown 表格）、T5 对课程事务问题的加权实际检索到什么、有多少段落和哪些部分进了提示词、回答是在哪一步丢的（检索、证据判断、提示词）。测试集：对公开课程包大纲里的每条信息写几种换说法的问题，其中一些不用大纲原文里的词；测检索命中率和本地模型回答的正确率。开发服务器上发现的实例（2026-11-17，CS50x）："When does the course end?" 只检索到作业的求助说明（大纲原文是 "deadline to complete the course"）；"Whats couse deadline" 大纲排第 1，但证据检查给了 0 分把它丢掉了；只写在表格某一行里的日期（Quiz 2）输给了同一张表的另一行；之后回答说没有课程资料，好像课程本来就没有。可以用一份虚构的 CS50x 学期大纲（日期、迟交规定、AI 规则）做测试文件 | S8 | S11, T5 | `backend/app/rag/`、`backend/app/pipeline/steps/retrieve.py`、`eval/course-rag-packs/` | 每个课程包有换说法报告；大纲里每条信息的各种说法都能检索到写着它的段落，本地模型能答对 |
| S15 | 演示课程里的学习数据（2026-11-17 发现）：演示脚本只给公开课程包建模块和文件，所以 CS50x 和 6.002 没有知识点、检查题、误区和测验；"我的进度"是空的，测验答题也改变不了掌握度。给 `scripts/build_demo.py` 加一个选项：用教师 AI 起草这些内容、接受草稿、每门课发布一份测验。再加一个测试：有同意时，测验作答会改变题目所属知识点的掌握度，没有同意时不变（现在只检查了证据记录） | S8 | S9、Q1 | `scripts/build_demo.py`、`backend/tests/test_quizzes_v2.py` | 演示构建之后，学生做完测验能在"我的进度"里看到水平变化 |
| S16 | CS50x 课程包的课程类型（2026-11-17 发现）：清单里写的是 `ece`，计算机课用了 ECE 的学科提示词（一个讲递归的回答说自己用的是"电气与计算机工程"知识）。给每个课程包选合适的类型，或者加一个计算机类的配置 | S8 | Z16 | `data/demo_courses/`、`backend/app/privacy/profiles/` | CS50x 的回答说的是计算机科学，不是 ECE |
| Q1 | 小测和学期末问卷，2026-11-12 导师会议后新增（第 9 节）：小测（选择题和判断题，本地模型起草，审阅，发布，自动评分，结果遵守可见性规则，`final` 小测 = 后测，和课程诊断（前测）对比）；学期末问卷（时间窗口、匿名打分、最小组人数）；结束学期时两者都以汇总形式导出，然后删除 | S7 | S9、S6 | `backend/app/learner/quizzes.py`、`backend/app/api/v2/quizzes.py`、`backend/app/api/v2/survey.py`、`backend/app/instructor_ai/quiz_drafts.py`、`backend/app/platform/end_of_term.py`、迁移 0013 | `backend/tests/test_quizzes_v2.py` 通过；每个接口都有访问测试；api-v2.md 3.9、3.10 |

**落后时按这个顺序往后推**：S10 → S9 里的学习计划部分。

### 7.3 刘恫铠 T

| ID | 任务 | Sprint | 依赖 | 主要文件 | 完成标准 |
|---|---|---|---|---|---|
| T1 | Beta 路由评估（G1-105）和 Beta 报告（G1-108） | S4 | — | `eval/` | 按时交付 |
| T2 | 前端改版设计稿：用 v0 出几版；选定 AI Elements 或 assistant-ui（7.4） | S4–S5 | 独立 | 设计稿 | Z、S 和客户认可 |
| T3 | 升级到 Tailwind 4 和 React 19，引入 shadcn/ui；现有页面改版；回答用 Markdown 渲染（修好粗体） | S5 | T2 | `frontend/` | 现有前端测试通过；截图对比 |
| T4 | ECE 和计算机科学的路由评估：用 `data/demo_courses/` 里 ECE 和计算机科学的课程包写问题并标注，做评估；需要时补训练数据、重新训练。评估部分已完成：`data/routing/ece_cs_questions.jsonl` 里有 160 个问题，程序和报告在 `eval/routing-ece/`（现有路由把 48% 到 50% 的问题送云端，标注为云端的只有 19%，主要原因是分布外检查；用新数据重新训练的候选权重在两个评估集上都更好，放在 `eval/routing-ece/results/candidate/`，等负责人决定是否采用） | S5–S6 | S5 | `backend/app/routing/`、`data/routing/`、`eval/` | 报告；工程问题不会全部被送云端（已满足） |
| T5 | 问题类型分类（concept / logistics）：标注数据，路由模型多一个输出。已完成：单独的分类头 `data/routing/models/question_type.npz`（现有路由不动；训练用 `python -m app.routing.question_type_train`），数据在 `data/question_type/`，报告在 `eval/question-type/`（按课程留出：准确率 0.93；留一门课：0.97）；路由步骤设置 `SemanticAnalysis.question_kind`（`RequestContext.question_type`），不改变路由决定；事务问题检索时课程级文件不降权并加权（课程检索器的 `question_kind`），Markdown 表格（日历）按行索引，每行带列名（S11 数字见 `eval/question-type/report.md`） | S6 | T4 | `backend/app/routing/` | 准确率报告 |
| T6 | 新页面：选课程、加入页（邀请码）、课程管理、成员导入、课程设置 | S6 | Z9 的 OpenAPI | `frontend/src/pages/` | 主要流程有界面测试 |
| T7 | 新页面：教师端 AI（四档）、个人概览、学习计划、可见性方案和不公开。新前端**没有每条回答后的评分**，回答下面也**没有"更详细 / 更简短 / 先举例 / 先讲概念"按钮**（决定见第 9 节）：评价只有学期末问卷 | S6–S7 | S6～S10、Z12 的 OpenAPI | `frontend/src/pages/` | 同上 |
| T8 | "数据可能发往云端"的提示（文字由 Z 提供）；所有新页面的英法文字，包括小测和问卷；已删除的每条回答评分和风格按钮不再需要文字 | S6–S7 | Z11 | `frontend/src/i18n/` | 三处都有提示 |
| T9 | 演示账号和示例数据脚本（只通过 API）；两门课的演示流程 | S6 | Z9、S5 | `scripts/` | 一条命令建好演示环境 |
| T10 | 视频（11/25）；把法语界面截图发给 Lavin 审核并改回 | S6 | T3 | — | 按时交付 |
| T11 | 改名为 **PACT**（Privacy-Aware Course Tutor，2026-11-17 定名，由 Z 代做，见 7.5）；无障碍自查（键盘、屏幕阅读器、对比度、放大）（**已完成**，见 [ACCESSIBILITY.md](ACCESSIBILITY.md)；axe 测试在 `frontend/src/test/Accessibility.test.tsx`） | S7 | 定名 | `frontend/` | 自查清单 |
| T12 | **进行中**：学生使用手册（[STUDENT_MANUAL.md](STUDENT_MANUAL.md)）和教师使用手册（[INSTRUCTOR_MANUAL.md](INSTRUCTOR_MANUAL.md)，含 course-structure.md 3.4 关于助教的说明）已完成；路由、前端、网络搜索的交接文档未完成 | S8 | — | `docs/` | 新教师照着能用 |
| T13 | 网络搜索（G1-92）+ 评估（G1-106）。**搜索已完成**（#88；见 [WEB_SEARCH.md](WEB_SEARCH.md)：部署时选择 `off`、外部 `api` 或自建 `searxng`）；评估还没做：搜索 API、白名单、清洗结果、作为资料交给生成步骤；查询只用 `search_query()`；出网只走统一的出网函数 | S7 | Z11、Z6 | 新的 `backend/app/websearch/`、`config.yaml` 的 pipeline | E4 审计：搜索请求里没有个人信息；评估报告 |
| T14 | 清除 `docs/` 以外 Markdown 里的中文（规则 14）：按第 7 节用英文重写 `TODO.md`；把仓库根目录的中文版入门文档挪到 `docs/GETTING_STARTED_zh.md` 并修好链接；删掉 `README.md`、`GETTING_STARTED.md` 里的中文行。`frontend/src/test/Routing.test.tsx` 里的中文测试文本保留（它测试的是中文输入） | S5 | — | 上述文件 | `docs/` 以外的 Markdown 里没有中文 |
| T15 | 分学科的路由（2026-11-17 发现）：路由分类头只用 `data/routing/seed.jsonl` 的 500 道医学题训练，所有课程共用一个阈值；ECE 课上较难的问题没有来源（证据被判为不需要，或能力判断在检索之前就送云端）。把其他学科的问题加进训练数据（像 T5 一样按课程划分），或按课程类型定阈值；同时决定 T4 的候选权重（`eval/routing-ece/results/candidate/`）是否采用 | S8 | T4 | `backend/app/routing/`、`data/routing/`、`eval/routing-ece/` | T4 的 ECE/CS 和医学路由评估不变差；较难的 ECE 问题有课程来源 |
| T16 | 看过历史对话之后开新对话（2026-11-17 报告）：学生点开历史记录里的一个对话后，回不到一个全新的空白对话。侧栏有 **New chat**（`components/shell/CourseNav.tsx` 从 URL 去掉 `c`，`pages/student/chat/Chat.tsx` 应该重建对话区），所以先复现在哪种情况下失败（桌面或手机布局、选了模块、发过问题以后） | S8 | F1 | `frontend/src/components/shell/`、`frontend/src/pages/student/chat/` | 有界面测试：打开一个历史对话，再开新对话，对话区为空，下一个问题开始新的对话 |
| T17 | 走云端的课程问题也要带上课程资料（2026-11-17 发现）："Can I use ChatGPT for the problem sets?" 和 "Am I allowed to use AI tools for problem sets?" 超出了路由训练数据的范围，能力判断在检索之前就把它们送去云端，回答说课程没有相关规定，其实大纲里有。课程安排类问题（T5）一律检索课程级文件，通过云端关卡的内容随问题一起发送；不放宽训练范围外的判断（2026-11-13 的决定） | S8 | T5 | `backend/app/routing/`、`backend/app/pipeline/steps/` | 关于课程规定的问题，走本地还是云端都能根据大纲回答 |

### 7.3a 前端 v2（任务 F1）

| ID | 任务 | Sprint | 依赖 | 主要文件 | 完成标准 |
|---|---|---|---|---|---|
| F1 | 基于 API v2 的前端，**已完成**（#71、#78；界面升级 U1～U5 #81～#85，计划见 [design/ui-upgrade.md](design/ui-upgrade.md)；包含 T6、T7 和 T8 的文字）：**学生端**（聊天、我的进度、小测、问卷）和**教师端**（班级概览、每个学生的进度（遵守可见性规则）、小测、资料、设置）。没有每条回答后的评分，没有回答风格按钮；不使用 `/api/v1/survey`。用 `data/demo_courses/` 里的八个开放课程包测试 | S7 | Z9、Q1、S6～S10、Z12 的 OpenAPI | `frontend/` | `npm run build && npm test`；两个端在演示课程包上都能用 |

### 7.4 前端技术栈（T）

**保留** React + Vite + TypeScript + Tailwind + TanStack Query + React Router，不换 Next.js。**加这些库**：

| 用途 | 库 |
|---|---|
| 基础组件 | **shadcn/ui**（Radix UI + Tailwind；组件代码复制进项目；自带无障碍） |
| 聊天组件 | **AI Elements**（Vercel，基于 shadcn）或 **assistant-ui**；要能接我们自己的 SSE 后端 |
| 回答渲染 | **react-markdown + remark-gfm** 或 **Streamdown**；**KaTeX**（公式）、**Shiki**（代码高亮） |
| 图标 / 动画 / 提示消息 | **lucide-react** / **Motion** / **sonner** |
| 表格 / 图表 / 表单 | **TanStack Table** / **Recharts** / **react-hook-form + zod** |
| 字体 | Inter 或 Geist |
| 设计稿 | **v0** |

**界面要点**：
- **布局**：左侧栏放课程、模块、对话；对话区居中限宽；底部圆角输入框和建议问题；深色模式。
- **回答**：
  - 逐字显示（Z6 完成后；之前一次性显示）；
  - 路由过程做成可折叠的"思考过程"面板，默认收起；
  - 来源做成小卡片（文件名和页码或幻灯片号，鼠标移上去显示原文段落）；
  - 每条回答有"本地 / 云端"标签，配隐私图标。
- **教师端**：shadcn 仪表盘样式（侧栏、统计卡片、数据表格、图表）。
- **注意**：
  - shadcn 和 AI Elements 的最新版需要 Tailwind 4（多数组件按 React 19 写），先升级；版本以官方文档为准；
  - 前端不做权限判断（规则 8）。

---

### 7.5 Z 代做的其他人任务

以下是 Z 作为组长决定代做的（2026-11-08），每项一个 PR，**由原负责人审查**：负责人审查并批准 PR，之后这部分仍归原负责人（规则 11 其他方面不变）。

| 任务 | 负责人 | Z 做了什么 | PR | 负责人要做的 |
|---|---|---|---|---|
| T14 | T | 按第 7 节用英文重写 `TODO.md`；中文入门文档挪到 `docs/GETTING_STARTED_zh.md`；`README.md`、`GETTING_STARTED.md` 里不再有中文 | #54 | 审查文字 |
| T 的一部分（bandit B615，Z13 扫描发现） | T | 路由和证据模型固定到 Hugging Face 的 commit（`app/routing/revisions.py`，Docker 构建也用它） | #56 | 审查；和 Z 一起升级到 `transformers` 5 |
| S4 的一部分（Z11 的后续） | S | 资料索引只在扫描发现学生数据时拒绝（`ScanResult.blocking`）：写了老师名字的课程资料不再被拒 | #55 | 审查 |
| S 的一部分（bandit B314，Z13 扫描发现） | S | PubMed 返回的 XML 改用 `defusedxml` 解析 | #55 | 审查 |
| 学习者数据按课程（course-structure.md 4.1、4.4） | S | `learner_kc_state`、`learner_topic_level`、`evidence_log`、`learner_misconception` 加 `course_id`（已有的行归到演示课程）；每门课一个 `LearnerRepository`；`app/learner/course_data.py` 导出和删除一门课的学习者数据 | #60 | 审查 |
| S9（API v2 接口和数据库部分） | S | `app/api/v2/learner.py`：检查题、课程诊断、个人档案、可见性选择、删除自己在一门课的数据、班级汇总、个人概览、学习计划；`app/learner/course_views.py` 在数据库上实现 `LearnerViewStore`、可见性变更和计划（`learning_plan`，迁移 0012） | #62 | 审查 |
| S5 的一部分（11-12 顾问会议） | S | `data/demo_courses/archives/` 里的 8 个公开课程包（讲义、大纲、日历、作业、考试；答案只给教师），带清单、署名和许可；`scripts/fetch_open_courses.py` 用来解压和重建；`tests/test_open_course_packs.py` | #64 | 审查；S5、S11、T4 都用这些课程包 |
| Q1（新增：小测和学期末问卷；S9 的问卷、S6 的教师端 AI 里的小测起草） | S | `app/learner/quizzes.py`、`app/api/v2/quizzes.py`、`app/api/v2/survey.py`、`app/instructor_ai/quiz_drafts.py`、结束学期的导出和删除、迁移 0013；api-v2.md 3.9、3.10 | #66 | 审查 |
| F1（前端 v2：学生端和教师端；包含 T6、T7 和 T8 的文字） | T | `frontend/` | #71、#78、#81～#85 | 审查 |
| S4（API v2 部分） | S | 上传资料先扫描再存储、删除、重建索引的后台任务 | #67 | 审查 |
| S6、S7、S10（API v2 部分） | S | 教师端 AI 草稿作为后台任务、接受进课程内容、班级洞察 | #70 | 审查 |
| S9（概览里的回答风格） | S | 概览显示学生开始共享之后设置的回答风格 | #77 | 审查 |
| S11 | S | 在全部 8 个公开课程包上做检索评估（`eval/course-rag-packs/`） | #72 | 审查 |
| T4 | T | ECE 和计算机科学问题的路由评估（`eval/routing-ece/`）；重新训练的候选模型没有采用 | #75 | 审查 |
| T5 | T | 问题类型（概念 / 课程事务）；课程事务问题先检索课程级文件 | #80 | 审查 |
| T9 | T | `scripts/build_demo.py`：通过 API v2 用课程包建演示课程 | #69 | 审查 |
| S8（接进系统） | S | 分层模型注册为 `course` 并设为默认；更新从存储的估计值开始，前置知识点的上限只在显示时生效；三种模型都跑了全部测试 | #87 | 审查 |
| T13（搜索） | T | 三种部署模式的网页搜索、`route` 之后的 `web_search` 步骤、按课程类型的白名单、SearXNG 的 Compose profile | #88 | 审查 |
| Z19（证据） | T | 在 `assess_evidence` 和 `select_passages` 里，本次请求所在课程的段落算作同一主题 | 见 PR | 审查 |
| Z20（结构草稿） | S | 4,096 个输出 token，schema 里知识点名字是枚举，无效的前置知识点链接去掉（以前整份草稿作废） | 见 PR | 审查 |
| T11（改名） | T | 界面（英文和法文）、网页标题、API 标题、README、AGENTS.md、手册、界面设计示意图、文件开头的注释和 Grafana 看板里的产品名改为 PACT；内部名字（数据库用户 `tutor`、`tutor_*` 指标、包名、仓库名）和历史文档不变 | 见 PR | 审查 |
| T11（无障碍部分）、T12（手册） | T | 无障碍自查和 axe 测试；学生手册和教师手册 | #74、#73 | 审查 |

从 2026-11-11 起，按同样的决定，Z 也用这种方式做 7.2 和 7.3 里 S 和 T 剩下的任务（每个任务一个 PR，开 PR 时加到上表）。还没开始的（2026-11-15）：网页搜索的评估（T13，G1-106）；视频（T10）；改名（T11）2026-11-17 开始，名字是 PACT；路由、前端和网页搜索的交接说明（T12）；CI 扫描报告的 `transformers` 5、`react-router` 7 和 `vite`/`vitest` 升级。

## 8. 开发流程

### 8.1 分支和 PR
- **从 `main` 开分支**：`<类型>/<任务ID>-<简述>`，例如 `feature/z4-course-catalog`、`fix/s3-citation-numbers`、`docs/t12-user-manual`。
- **一个任务一个 PR。** 描述里写：
  - 任务 ID；
  - 改了什么；
  - 怎么测的（贴结果）；
  - 对隐私或权限的影响（没有就写"无"）。
- **提交信息**沿用现在的风格：`<范围>: <做了什么>`，例如 `privacy: ...`、`feat(rag): ...`、`docs: ...`。只用英文（规则 14）。
- **合并前**：CI 全绿，并且所有审查评论都已解决（`main` 上会强制检查这两项）。其他组员审查是欢迎的，但不强制。

### 8.2 运行和测试
- **安装**（第一次）：

  ```bash
  python -m venv .venv && .venv/Scripts/python -m pip install -e "backend[dev]"
  ```

  ```bash
  .venv/Scripts/python -m spacy download en_core_web_sm
  ```

  完整功能还需要 `en_core_web_lg` 和路由模型（在 `backend/` 下运行 `python -m app.routing.prepare`）。
- **数据库**：Z3 合并之前，测试照旧用 SQLite。Z3 之后测试需要 PostgreSQL：用 `docker compose up -d db` 启动，并设置 `TEST_DATABASE_URL`（Z3 之后见 `.env.example`）；测试夹具会自动建立和删除临时数据库。
- **后端测试**在 `backend/` 下运行。**不要让开发用的 `.env` 影响测试**（例如在 Z4 删掉这个设置之前，`CONTENT__SERVE_UNREVIEWED=true` 会让约 20 个测试失败）：把 `.env` 改名，或在没有它的工作树里跑。

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
- **前端**在 `frontend/` 下运行。后端接口改了以后，先在 `backend/` 下运行 `python -m app.export_openapi`（更新 `frontend/openapi.json`），再在 `frontend/` 下运行 `npm run gen:api`。

  ```bash
  npm ci
  ```

  ```bash
  npm run build && npm test
  ```

- **整套系统**：

  ```bash
  docker compose up --build
  ```

  模型地址在 `.env` 里配置（参考 `.env.example`）。
- **开发用的模型**：每个人用**自己准备的** OpenAI 兼容 API（本机的 Ollama、OpenRouter 或其他服务），只写在自己的 `.env` 里。团队的 GPU 服务器在外面访问不到。规则：
  - 不要提交 key，也不要贴进 issue、PR、日志或测试里；
  - 发给外部 API 的只能是虚构的测试数据，不能是真实学生的数据；
  - 单元测试和 CI 不调用真实模型（用 `backend/app/llm/fake.py`）；需要真实模型的测试放在 `eval/` 下，没有配置 key 时自动跳过。

### 8.3 测试要求
- **新接口**：正常流程 + 权限测试（其他课程的教师、其他学生、未登录）。
- **隐私**：只用虚构数据；真实学生信息不能出现在测试、评估集或提交里。
- **模型**：单元测试用假模型（`backend/app/llm/fake.py`）；需要真实模型的评估放在 `eval/` 下单独跑。

---

## 9. 已决定 / 待决定 / 现阶段不做

**已决定**：

| 事项 | 决定 |
|---|---|
| 课程结构、账号、入学、数据范围、设置、数据库、迁移、API 版本 | [design/course-structure.md](design/course-structure.md) 第 1 节、[design/api-v2.md](design/api-v2.md) |
| 示例和测试课程 | `data/demo_courses/` 里的 8 门公开课程（医学、生命科学、ECE、计算机科学各两门）；"General Medical Knowledge" 只用于 v3 迁移 |
| 首批隐私档案 | 医学、生命科学、ECE |
| 部署 | 一套 Docker Compose；vLLM 单独部署，通过 API 连接 |
| 数据库 | 只用 PostgreSQL |
| 用量限制 | 先用配置文件；课程级字段已预留 |
| 可见性 | 每门课选方案；学生可以不公开；切换前的数据不显示 |
| 对导师系统的评价（2026-11-12） | 只有学期末问卷。每条回答后的评分和"更详细 / 更简短 / 先举例 / 先讲概念"按钮从新前端删除；`/api/v1/survey` 保留（API v1 已冻结），但新前端不使用 |
| 可见性和不公开（2026-11-12） | 方案 A/B 和不公开保留 |
| 本学期的小测（2026-11-12） | 只做选择题和判断题，自动评分，不计成绩，只看进度；AI 由本地模型根据课程资料起草，教师审阅后才能发布；`final` 小测是后测，和课程诊断（前测）对比；结果遵守可见性规则（4.8） |
| 针对个别学生的资料（2026-11-12） | 下学期；本学期只有带备注的学习计划（S9） |
| 两个端（2026-11-12） | 学生端（聊天、我的进度、小测、问卷）和教师端（班级概览、每个学生的进度（遵守可见性规则）、小测、资料、设置） |
| 登录 | 现在用自建账号；预留 `login_identity` 给 OAuth |
| 教师端 AI | 四档都做 |
| 知识模型 | 课程级分层模型；规则模型只兜底 |
| 网络搜索 | 归 T，按规则 6 做 |
| 语言 | 只有处理中文输入的功能代码和测试数据可以有中文，且不能改变英文的行为；注释和 `docs/` 以外的 Markdown 里不能有中文；`docs/` 里可以有 `*_zh.md` 中文对照（规则 14） |
| 以后的维护者 | 接手这个项目的学生团队 |

**待决定**：
- 项目名：候选 HALO（Hybrid Adaptive Learning Orchestrator）、COMPASS、CAIRN、MAPLE；
- vLLM 机器一直开着，还是只在上课时间开；
- 本学期的交付范围（和 Ismaeel 教授、Abbas 教授确认）。

**现阶段不做**：中文界面、伦理审批、备份和硬盘加密、云端服务商比较。
