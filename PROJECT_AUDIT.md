> 本文为 P0 开发前的历史审计基线。当前开发进度与验收边界见 `docs/DEVELOPMENT_STATUS.md`。原始运行日志仅保留在本地。

# LovePilot AI P0 工程审计报告

审计日期为 2026 年 11 月 10 日，时区为 Asia/Shanghai。

## 1. 阶段结论

**P0 审计工作已完成，产品化验收暂未通过。当前阶段保留为 P0。**

本次实际执行了依赖安装、13 个 Python 模块导入、原生服务启动、HTTP 接口测试、SQLite 并发及重启探针、LangGraph 工作流、Mem0 本地存储探针、AstrBot SDK 探针、Android APK 构建、签名检查和 Lint。

三个核心问题的结论如下。

| 核心问题 | 结论 | 实际证据 |
| --- | --- | --- |
| 后端 Agent 的完整智能能力 | 部分实现 | HTTP 主入口调用 `Agent.decide`。LangGraph 独立图可运行，主入口尚未使用该图。8 个 Skill 以策略字符串保存。Mem0 检索适配器存在 API 兼容缺陷。DeepSeek 真实推理待密钥验收 |
| 安卓安装、使用和功能管理 | 构建通过，功能部分实现 | 已生成并验证 Debug APK。当前为单个 Activity 和原生控件，版本号为 0.7.0。五导航、Skills 管理、Bot 管理等尚待开发。设备列表为空，实机安装和使用待验收 |
| AstrBot + iLink 真实微信收发 | 部分实现，真实账号待验收 | AstrBot 4.29.4 SDK 导入和事件处理探针已运行，复现消息 ID、异常日志和会话 ID 截断缺陷。扫码、真实消息收发和掉线恢复需要合资格微信账号 |

新增的 HTTP 测试使用真实 TCP 服务、临时数据库和合成模型回复。SDK 探针使用真实 AstrBot 类与模拟 HTTP 响应。Mem0 探针使用实际 Mem0、Qdrant 和 SQLite，同时注入合成向量并采用 `infer=False`。这些结果分别用于接口、兼容性和存储验证。DeepSeek 回复质量、语义检索质量与微信真实收发分别保留为待验收项。

运行输出、复现探针源码、依赖快照与构建日志保存在 `docs/P0_EVIDENCE.log`。

## 2. 工程与环境基线

项目根目录为 `C:\Users\<user>\Desktop\LovePilotAI-Agent-V1.0-source`。当前目录包含后端、Android、插件、测试与文档，Git 元数据缺失，无法提供提交 SHA 或 Git 回滚点。审计证据中记录业务源码 SHA-256，便于核对本次快照。

| 项目 | 实测结果 |
| --- | --- |
| `python --version` | Python 3.10.11 |
| `py -3.12 --version` | Python 3.12.10，用户已安装 |
| JDK | Microsoft OpenJDK 17.0.10 |
| 审计 Python 环境 | 基于现有 3.12 创建的独立 venv |
| 审计依赖 | LangGraph 1.2.20、mem0ai 2.2.1、AstrBot 4.29.4、httpx 0.28.1 |
| 依赖一致性 | `pip check` 通过 |
| 依赖漏洞查询 | OSV 对审计环境 175 个发行包返回 0 项已知命中，范围限于本次查询的包版本 |
| Gradle | 下载并实际使用 Gradle 8.9，工程 AGP 为 8.7.3、Kotlin 为 2.0.21 |
| Android SDK | 原有 platform 36，审计安装 platform 35。构建过程按已有许可安装 build-tools 34.0.0 |
| 项目配置与数据 | 有 `.env.example`，实际 `.env` 和既有业务数据库均未发现 |
| 认证与模型凭据 | 进程环境中 `LOVEPILOT_TOKEN`、`DEEPSEEK_API_KEY`、`OPENAI_API_KEY` 均缺失。服务测试使用临时随机令牌 |
| 安卓设备 | `adb devices -l` 返回空列表 |

审计工具位于临时目录 `C:\Users\<user>\AppData\Local\Temp\lovepilot-p0-20261110-7f31`，依赖安装在该目录的 `venv` 中。全局 Python 的依赖探测结果与该独立环境分别记录。

## 3. 真实完成度分类

### 3.1 已实现并取得运行证据

- Bearer 令牌鉴权、localhost 服务启动、联系人创建和更新、事实写入和覆盖、草稿接口、联系人导出、撤销与逻辑删除。
- 单一 `Memory` 实例下的并发消息去重。32 次相同消息 ID 请求只执行一次模型调用，写入两条对话记录。
- 当前 SQLite 查询路径的联系人数据过滤。HTTP 测试和数据库探针验证 A 的事实、历史不会出现在 B 的导出中。
- SQLite 重启后恢复联系人事实、历史和去重缓存。`integrity_check` 为 `ok`，`foreign_key_check` 为空。
- 当前数据库五张表中的联系人级逻辑删除。删除后 `contacts`、`messages`、`facts`、`processed`、`audit` 对应行数均为 0。
- 敏感关键词人工接管、模型错误的通用提示、已完成撤销后拒绝缓存草稿。
- LangGraph 独立图的授权、敏感词、检索、草稿及转人工路径。正常路径实际输出节点为 `authorize → guard → retrieve → draft`。
- Android Debug APK 构建及 v2 签名验证。

### 3.2 部分实现

- **Agent 决策**。具备联系人授权、最近 20 条消息、显式事实和关键词守卫，情绪分析、意图分析、工具选择和质量审查尚待实装。
- **长期记忆**。`facts` 支持按联系人保存和覆盖字符串，`messages` 支持顺序历史。Mem0 具有独立包装类，业务 HTTP 路径使用 SQLite。实际 Mem0 SDK 的本地过滤、重启恢复和删除已验证。
- **Skills**。`SKILLS` 内有 8 项说明，模型提示没有按 Skill 执行模块化路由。humor-assistant、flirting-assistant、voice-assistant、personal-style 四项缺失。
- **Android**。现有页面提供本地联系人、直接 DeepSeek 建议、Agent 健康检查、授权同步、撤销、导出和草稿入口。网络地址固定为 `127.0.0.1:8768`，需要 USB 与 `adb reverse` 配合。
- **AstrBot 插件**。具备 `/help`、`/start`、`/pause`、`/forget` 分支及私聊转发逻辑，默认自动回复配置为 false。该配置下仍会向原会话发送带标记的回复建议。真实插件加载生命周期和微信渠道运行有待联调。
- **安全**。SQL 查询主要使用参数绑定，有 HTTP 请求体长度上限、联网超时和基础授权。发布包禁用明文流量，本地数据库与管理权限仍需完善。

### 3.3 未实现

- HTTP 主入口的 LangGraph 编排，完整节点体系、持久化执行轨迹和可视运行监控。
- 主链路中的 Mem0 集成，候选记忆提取、事实来源和用户确认流程、语义合并、权重与时间衰减、记忆单项删除和可靠恢复。
- 12 项独立可开关、可升级且有执行契约的 Skill，个人风格偏好的确认与学习流程。
- Compose 五个主导航、Bot/Skills/工作流管理、运行日志管理、模型供应商配置和完整权限页面。
- 密钥保险库、联系人资料加密、正式数据库迁移、角色权限、全局自动回复控制、可靠备份恢复与保留期策略。
- 插件发送队列、发送回执持久化、失败重试与告警、插件级掉线恢复及媒体理解链路。
- 三端真实环境端到端验收，以及安卓崩溃与后台恢复实机验证。

### 3.4 存在缺陷

下表将可重复运行的结果标为“实测”，将代码路径检查结果标为“源码”。优先级按发布阻断、高、常规区分。

| 编号 | 优先级 | 位置 | 问题与证据 | 修复验收要求 |
| --- | --- | --- | --- | --- |
| P0-01 | 发布阻断 | 插件 `main.py:87` | 实测 `WeixinOCMessageEvent.message_id` 为缺失值，真实消息 ID 位于 `message_obj.message_id`。转发请求中的 `message_id` 为 null | 对正式 SDK 取出稳定消息 ID，验证重复投递经过插件与后端均只处理一次 |
| P0-02 | 发布阻断 | 插件 `main.py:103`、`:106` | 实测 Context 没有 `logger` 属性。后端 503 导致异常处理再次抛出 AttributeError，用户兜底回复中断 | 使用当前 SDK 支持的日志入口，覆盖连接异常、超时、HTTP 错误和畸形响应 |
| P0-03 | 发布阻断 | 插件 `main.py:45` | 实测两个长度超过 100 的不同统一会话来源，截断后成为同一 contact_id | 使用稳定且抗碰撞的会话映射，按平台实例与会话隔离，处理已有映射迁移 |
| P0-04 | 高 | `mem0_adapter.py:19` | 实测 Mem0 2.2.1 拒绝 `search(query, user_id=...)`，要求 `filters={'user_id': ...}` | 锁定支持版本，使用正式 API，覆盖真实适配器的新增、检索和删除 |
| P0-05 | 高 | `core.py:80`、`:55` | 两个 Memory 实例连接同一 SQLite，处理相同消息 ID 时调用模型两次、写入四条历史，最终缓存只有一行 | 实现数据库层幂等占位和状态管理，验证跨连接、跨进程和崩溃后的重试 |
| P0-06 | 高 | `core.py:89`、`:106` | 模型失败的 handoff 被按消息 ID 永久缓存。模型恢复后，同一 ID 重试仍返回 handoff。失败前已提交用户消息 | 区分可重试失败与终态，保证重试和历史一致，保留可观测错误类型 |
| P0-07 | 高 | `core.py:82` | 模型调用持有所有联系人共享的 RLock。实测撤销在模型运行时被阻塞，原请求仍产出 draft | 设计撤销版本或授权代次、短事务和发送前复核。覆盖进行中请求的撤销与取消 |
| P0-08 | 高 | `core.py:65` | 实测保存 1005 条历史，导出只有最近 1000 条。导出数据缺少可恢复备份结构，恢复接口缺失 | 支持完整分页导出、版本化备份和恢复校验，核对恢复前后行数及隔离 |
| P0-09 | 高 | `core.py:16`、`Store.kt:7` | 实测后端 SQLite 文件可直接读到联系人资料标记。Android 数据库也使用普通 SQLite | 明确加密密钥生命周期、数据库与备份保护。验证删除范围覆盖索引、缓存和备份 |
| P0-10 | 高 | 依赖与启动配置 | 工程缺少后端依赖声明和 Python 版本约束。默认 Python 3.10 导入 graph_adapter 抛出 NotRequired ImportError，原测试将此错误归为依赖缺失并跳过。3.12 下模块导入通过 | 明确 Python 3.12 运行基线和可重建依赖锁，区分缺依赖与模块自身 ImportError |
| P0-11 | 高 | 插件 `main.py:27`、`:42` | 源码仅按私聊过滤，未限定所选微信 Bot 实例。实际事件处理后 `is_stopped()` 为 false | 在真实 AstrBot 分发链验证授权前、暂停后、命令后的行为，按需终止后续默认 LLM 和其他处理器 |
| P0-12 | 常规 | `server.py:16` | 实测 `/memory?contact_id=native-synthetic&limit=1` 被当成完整联系人 ID，返回 404 | 使用标准 query 解析，覆盖附加参数、URL 编码和重复参数 |
| P0-13 | 高 | `server.py`、`AgentClient.kt`、插件 | 单一全权令牌，缺少角色权限、请求限流与服务端读取超时。插件超时默认 25 秒，后端模型超时为 30 秒 | 对齐超时预算与取消行为，限制请求并发和管理权限，验证超时后的幂等重试 |
| P0-14 | 常规 | `MainActivity.kt:86`、`Store.kt:18` | 源码“清除所有联系人、日志与记忆”按钮只操作手机本地 SQLite，服务端数据具有独立删除入口。客户端向后台线程直接读取 EditText，生命周期取消和数据库关闭存在竞态风险 | 明确本地与服务端删除范围，补齐删除流程和 UI 生命周期实机回归 |
| P0-15 | 高 | 数据库初始化、`Store.kt:13` | 后端使用 CREATE TABLE IF NOT EXISTS，`PRAGMA user_version=0`，Android onUpgrade 为空，正式迁移链缺失 | 引入版本化迁移和既有数据夹具，验证升级、失败回滚和重启恢复 |

此外，服务访问日志会记录 GET 查询中的 contact_id，模型错误日志只保存 `model_error`，具体错误类型与关联 ID 缺失。实测请求日志未出现测试令牌或消息正文。脱敏规则和可排障日志需要一并设计。

## 4. 自动化测试与接口覆盖

### 测试结果

| 执行环境 | 用例数 | 结果 |
| --- | --- | --- |
| 审计开始时，Python 3.10 原有套件 | 29 | 26 通过，3 跳过 |
| 新增 HTTP 测试后，Python 3.10 最终套件 | 45 | 42 通过，3 跳过 |
| 安装依赖后的 Python 3.12 最终套件 | 45 | 45 通过，0 跳过 |

原有 29 项测试全部保留。本次新增 `tests/test_http_api.py` 的 16 项测试，覆盖真实 HTTP 服务的鉴权、输入校验、联系人隔离、事实读写、草稿、去重、敏感内容、撤销、导出和删除。测试启动真实子进程，数据库使用临时目录，模型响应使用合成文本。

新增测试首次在 Windows 3.12 venv 中运行时遇到子进程关闭后的日志文件占用，导致 tearDownClass 失败。测试夹具已改为通过 stdin 结束服务、关闭数据库后正常退出，最终在 3.10 和 3.12 均复跑通过。该问题属于本次新增测试夹具。

### HTTP 接口矩阵

原有测试主要直接调用 Memory、Agent 或图对象，HTTP Handler 级测试数为 0。

| 入口 | 新增运行覆盖 | 保留验收边界 |
| --- | --- | --- |
| GET `/health` | 正常响应与鉴权 | 当前只探测模块可见性，模型及 Bot 可用性需独立健康检查 |
| GET `/skills` | 正常响应 | 列表返回与各 Skill 实际执行分别验收 |
| GET `/memory?contact_id=...` | 事实与历史读取、删除后 404 | 查询解析缺陷见 P0-12 |
| POST `/contacts` | 保存、授权、非法 ID/字段、鉴权 | 版本化授权记录和角色权限待实现 |
| POST `/facts` | 写入、读取、非法内容、缺失联系人 | 用户确认、来源校验和语义能力待实现 |
| POST `/draft` | 正常草稿、重复消息、敏感与未授权、错误字段 | 模型回复使用合成输出，DeepSeek 真调用待验收 |
| POST `/revoke` | 撤销后缓存失效、缺失联系人 | 进行中请求的撤销见 P0-07 |
| POST `/export` | 联系人隔离、导出、删除后 404 | 完整备份与恢复见 P0-08 |
| POST `/delete` | 删除和重复删除 404 | 当前只覆盖 SQLite 逻辑行删除 |

既有测试全部通过与本报告中的缺陷复现可以同时成立。跨连接去重、SDK 错误分支、Mem0 版本兼容、完整导出等路径超出了既有套件的覆盖范围。

## 5. Android 构建与实机状态

- 第一次使用 Gradle 8.9 执行 `:app:assembleDebug`，Google Maven 的 `gradle-api:8.7.3.module` 下载读取超时，2 分 44 秒后失败。
- 在保持工程仓库配置的情况下，将连接与读取超时调为 60000 毫秒重试，4 分 36 秒后 `BUILD SUCCESSFUL`，执行 33 项任务。日志中出现一次 Kotlin daemon 启动异常，Gradle 后续完成编译和打包。
- `:app:lintDebug :app:testDebugUnitTest` 执行成功。Lint 为 0 errors、27 warnings，涉及目标 SDK 时效、Android 12+ 数据迁移规则、应用图标和界面字符串国际化。
- `testDebugUnitTest` 标记为 `NO-SOURCE`，当前 Android 自动化单元测试数量为 0。
- `apksigner verify --verbose` 通过，v2 签名有效。`aapt dump badging` 确认包名 `com.lovepilot.ai`、versionCode 7、versionName 0.7.0、minSdk 26、targetSdk 35。

构建产物为 `app/build/outputs/apk/debug/app-debug.apk`，大小 833101 字节。

SHA-256 为 `4050609980f5c2fcf110a33be5686140e553740fb82be21c6da8ec29413e9642`。

实机验收需要红米 Android 13 设备出现在 adb 列表中，随后验证安装、冷启动、USB 反向端口、鉴权失败提示、联系人生命周期、旋转与重启、后台恢复和数据删除。本次设备列表为空，以上项目均保留待验收。

## 6. AstrBot、腾讯 iLink 与 DeepSeek

### AstrBot 和 iLink

本次从 PyPI 的当前版本字段取得 AstrBot 4.29.4，其 Python 要求为 >=3.12，并实际安装该版进行 SDK 检查。GitHub Releases latest 查询返回 403 rate limit exceeded，最新发布信息未进行 GitHub 交叉确认。

SDK 探针构造真实 Context 和 WeixinOCMessageEvent，Context 的管理器依赖使用空夹具，HTTP 使用 MockTransport。验证范围包含模块导入、装饰器导入、对象构造和事件处理函数，完整 AstrBot 服务生命周期留待真实部署验收。

当前官方 AstrBot 适配器文档列出下列能力，本项目插件对媒体的处理另行列出。文档能力均需账号实测复核。

| 消息类型 | 官方适配器文档 | 当前 LovePilot 插件 |
| --- | --- | --- |
| 文本 | 可接收、可发送 | 使用 message_str 转发并返回文本结果，真实微信送达待测 |
| 图片 | 可接收、可发送 | 缺少图片内容上传或模型视觉分析路径，空文本事件直接返回 |
| 语音 | 可接收并使用云端转写，发送语音暂不支持 | 可能处理适配器提供的转写文本，音频理解与转写可用性待账号实测 |
| 视频与文件 | 可接收、可发送 | 缺少对应理解和传输链路 |

二维码申请、扫码状态、token 保存和长轮询属于 AstrBot 平台适配器职责。项目只有转发插件及部署说明，账号运行配置和登录态待部署。掉线恢复、微信侧授权撤销、token 失效与微信发送回执均需真实账号验收。

官方文档注明 AstrBot 的个人微信适配器自 v4.22.0 引入，并列出 Android 微信 >=8.0.69、iOS 微信 >=8.0.70 及 ClawBot 插件要求。腾讯仓库协议还包含登录状态、context_token、错误码与媒体流程，实际接入以当前适配器实现和账号可用性共同判断。[AstrBot 文档](https://github.com/AstrBotDevs/AstrBot/blob/master/docs/zh/platform/weixin_oc.md) [腾讯仓库](https://github.com/Tencent/openclaw-weixin) [协议文档](https://github.com/Tencent/openclaw-weixin/blob/main/docs/protocol.md)

### DeepSeek

原生 `python -m agent_server.server` 已实际启动。缺少令牌时启动退出码为 1，提供临时随机令牌后 `/health` 返回 200。缺少 DeepSeek 密钥时，已授权联系人的 `/draft` 返回模型失败的 handoff，随后删除测试联系人成功。

代码中的 DeepSeek URL 和模型名有明确实现，后端请求超时为 30 秒。有效密钥、计费状态、真实成功响应和回复质量均待验收。供应商 URL 固定，当前只允许通过环境变量调整模型名，通用供应商配置待实现。

### Mem0 运行补充

默认 `Mem0Adapter()` 在缺少 OpenAI 凭据时抛出 OpenAIError。配置本地 Qdrant、合成密钥和本地禁用网络地址后可初始化，通过注入合成 embedding 避免外部模型调用。使用 SDK 正确的 `filters` 参数验证 A、B 各自只返回本人的合成事实，关闭并重开后 A 数据仍存在，删除 A 后 B 数据保留。

适配器本身的 `search` 仍按 P0-04 报错。适配器的 `add_consented_fact` 使用默认 `infer=True`，LLM 提取能力需要后续真实供应商配置和验证。本次额外发现 spaCy 与 fastembed 可选组件缺失，运行时输出关键词与语言处理能力降级提示。

## 7. 本阶段交付与回滚

### 文件清单

| 文件 | 本次变化 |
| --- | --- |
| `PROJECT_AUDIT.md` | 新增本审计报告、验收结论和修复清单 |
| `tests/test_http_api.py` | 新增 16 项真实 HTTP 回归测试，修复夹具的 Windows 退出清理问题 |
| `docs/P0_EVIDENCE.log` | 新增运行日志、探针源码、环境与依赖快照 |
| `app/build/outputs/apk/debug/app-debug.apk` | 本次实际生成的 Debug 构建产物 |
| `app/build/reports/lint-results-debug.*` | 构建工具生成的 Lint 报告 |

业务架构沿用现有 HTTP、Agent、SQLite、原生 Activity 和 AstrBot 转发插件。正式数据库迁移数为 0，审计创建的数据全部为隔离目录中的合成数据。后台缺陷和 SDK 兼容问题保留在修复清单，避免在审计阶段同时改写多个子系统。

审计附加测试和报告可按上述文件清单移除。构建缓存位于项目 `.gradle`、`app/build` 和用户 Gradle 缓存，临时 Python 环境与 Gradle 位于前述审计目录。SDK platform 35 和 build-tools 34.0.0 作为已安装开发工具保留。Git 回滚需要先建立可追溯的仓库基线。

### 复跑命令

在项目根目录运行以下 PowerShell 命令，可重现最终测试与构建检查。

```powershell
$auditRoot = 'C:\Users\<user>\AppData\Local\Temp\lovepilot-p0-20261110-7f31'
& "$auditRoot\venv\Scripts\python.exe" -m pip check
& "$auditRoot\venv\Scripts\python.exe" -m unittest discover -s tests -v
& "$auditRoot\gradle-8.9\bin\gradle.bat" --no-daemon --console=plain :app:assembleDebug
& "$auditRoot\gradle-8.9\bin\gradle.bat" --no-daemon --console=plain :app:lintDebug :app:testDebugUnitTest
adb devices -l
```

临时审计环境被清理后，可用 `py -3.12 -m venv` 新建环境，再按证据中的版本快照安装依赖。业务正式启动仍需要单独配置有效令牌、模型凭据和可写数据库目录。`.env.example` 的内容需要显式注入进程环境，当前服务读取 `os.environ`。

## 8. P0 收口与后续阶段入口

1. 先修复消息 ID、异常日志与会话映射三项插件阻断缺陷，并增加对应回归测试。
2. 固定 Python 3.12、后端依赖及 SDK 支持范围，修复 Mem0 search 契约，恢复可重复部署能力。
3. 修复数据库跨连接幂等、可重试错误缓存、进行中授权撤销和完整导出，结合正式迁移保存既有数据。
4. 验证微信渠道的事件分发与默认 LLM 行为，检查暂停和未授权状态，建立真实账号验收夹具。
5. 提供有效 DeepSeek 运行环境、合资格微信 Bot 登录和已连接红米 Android 13 手机，完成各项真实验收。
6. P0 修复与验收通过后进入 P1，接通 HTTP 主入口的 LangGraph 状态图、节点契约和执行记录，再按 P2 到 P7 顺序推进。

以上列表作为下一轮 P0 修复清单和后续阶段入口，最终产品验收继续以真实模型、实机安装和真实微信收发证据为准。
