# 产品化阶段验收记录

## P0 修复轮次

日期为 2026 年 11 月 10 日。

- 已修复消息 ID 读取、SDK 日志入口、长会话映射冲突、微信渠道过滤、默认 LLM 继续处理、Mem0 search 契约和 HTTP 查询解析。
- 数据库迁移 1 接管原有表，迁移 2 增加授权版本、会话租约和查询索引。
- Memory 存储从 core 拆出并保留原有导入接口。跨连接租约在短事务内取得，模型调用期间允许撤销和删除，返回后使用授权版本和租约所有者进行核验。
- 模型失败可按同一消息 ID 重试，成功时历史和缓存原子提交。导出覆盖全部历史。
- 原有 45 项测试与新增 8 项存储回归已运行通过。SDK 回归随后单独记录。
- 修改范围包含 agent_server、微信桥接插件与新增回归测试。完整原始审计保存在 PROJECT_AUDIT.md。
- 修改前源码回滚快照保存在 `C:\Users\<user>\AppData\Local\Temp\lovepilot-before-productization-20261110\source.zip`。数据库正式升级前应保留原文件和 WAL 的一致性备份。
- 后续阶段继续处理字段加密、权限、备份恢复、界面和完整工作流。外部账号与设备验收按实际结果记录。
- P0 修复轮次最终执行 57 项自动化测试，全部通过，其中 4 项使用 AstrBot 4.29.4 真实 SDK 类。

## P1 Agent 引擎

- HTTP 与直接调用共同使用真实 LangGraph，包含接收、联系人识别、记忆检索、情绪线索、意图、Skill 路由、生成、审核、人工接管与记忆写入节点。
- 迁移 3 增加 runs 表，保存节点名和执行时长。缓存命中复用原结果。
- 集成后原有与新增 57 项回归全部通过，额外增加工作流持久化断言。
- 情绪初始分析使用可解释的表达线索，结果明确携带 uncertain 标记。真实模型语义质量继续单列验收。

## P2 长期记忆

- 迁移 4 增加候选项、确认状态、事实来源和权重元数据。候选项仅从联系人原话中的明确自述提取，重复原话合并，确认前不参与事实提示。
- Mem0 2.2.1 已接入中文 BAAI/bge-small-zh-v1.5 本地模型，实际生成 512 维向量并运行联系人限定检索和删除。证据位于实际语义运行日志。
- 加密 SQLite 为持久化事实源，Mem0 使用内存 Qdrant 和内存历史库，在启动时按已确认事实重建索引，向量索引不持久化私人明文。
- 候选确认、拒绝、隔离、备份、恢复、冲突回滚和重启已加入回归。恢复联系人要求重新授权。

## P3 Skills

- 建立 12 项独立版本化 JSON Skill 契约，共享执行器负责输入、开关、模型调用、审核和异常处理。
- 所有 12 项 Skill 已执行自动化路由测试，另有禁用技能和已确认风格进入提示的测试。
- 语音 Skill 接受确认后的转写文本，安卓系统语音识别与真实设备可用性在客户端阶段验收。
- 此时完整后端回归为 66 项全部通过。真实模型生成质量仍需有效模型凭据。

## P4 微信 Bot

- 使用 AstrBot 4.29.4 真实 SDK，增加持久化消息占位、跨实例去重、错误重试、发送前授权复核、全局开关、活动上报与渠道限制。
- 发送改为等待 SDK 的 event.send 完成，再提交本地处理状态。微信远端的实际送达与崩溃窗口需要真实账号验收。
- 二维码登录由 AstrBot 官方适配器管理。当前阶段继续开展 SDK、模拟适配器与本地 HTTP 链路测试。

## 2026 年 11 月 11 日修复与验收

### 修改范围与架构

- 后端修改 `memory.py`、`models.py`、`service.py`、`control.py`，新增共享设置校验模块 `settings.py`。HTTP 保存和备份恢复共用相同校验规则。
- 微信桥接修改 `main.py`，可重试模型失败会释放消息占位与冷却记录，成功回复继续持久化去重。
- Android 修改 `Store.kt`，使用查询 API 执行返回结果的 PRAGMA，修复红米 Android 13 的迁移异常。页面轮询改用生命周期协程，并在离开页面后取消。
- 部署修改 `Start-Agent.ps1` 与 `.env.example`，后台启动检查使用实际配置端口，健康检查带认证，控制接口区分 HTTP 拒绝和网络不可达。
- 自动化回归修改 Bot、备份测试，新增控制命令测试与显式启用的官方二维码设备测试。

### 数据库与恢复

- 本轮服务端数据库结构继续为迁移版本 6，本地 Android 数据库继续使用版本 2。
- 备份仍兼容 version 1 文档，新增的已处理消息 ID 字段为可选项。备份中的事实时间和权重会恢复，用于继续计算时间衰减。
- 恢复联系人继续要求重新授权。可迁移设置包含模型地址、模型名称、Skill 开关和个人风格。本机访问凭据、模型密钥、Bot 管理地址及通道活动信息由目标设备保管。

### 已执行验证

- 后端完整回归 91 项通过，依赖 `pip check` 通过。
- Debug APK、设备测试 APK、JVM 测试和 Lint 实际构建执行。JVM 测试 5 项通过，Lint 为 0 errors、9 warnings。
- 红米 Android 13 的 4 项设备测试通过，耗时 72.072 秒，覆盖旧数据加密迁移、五导航、设置返回、联系人创建、聊天建议、记忆确认与撤销授权。这轮外部 LLM 使用明确标记的测试响应，Mem0、中文本地向量、HTTP、LangGraph 与加密数据库实际运行。
- 独立临时数据库验证了 Windows 后台服务自定义端口启动、重复启动复用、强制中断后重启与认证优雅停止，均通过。首次测试脚本因 Windows 子进程继承输出管道而超时，改用文件接收子进程输出后重跑通过。
- 正式 Agent 与 AstrBot 已重新启动，USB 反向转发和手机凭据配置已执行。

### 证据、问题与后续验收

- 本机证据保存在 `data/verification-20261111/`，包括后端测试、构建、设备测试、测试后端摘要和生命周期测试结果。该目录包含设备运行信息，已排除在公开仓库外。
- 四项设备测试之后调整了界面轮询，最新构建设备复测与原生官方扫码页测试继续进行。此前扫码页测试因启动等待未完成而终止，不能将这些运行计作通过。
- DeepSeek 真实调用需要用户在 App 中保存有效密钥。微信账号登录、真实消息送达、多媒体与远端断线恢复继续按真实账号结果验收。
- P7 全链路正式验收继续进行，当前版本维持 `2.0.0-dev`。

### 回滚

- 本轮修改基于 Git 提交 `8384dc4`，可在独立目录检出该提交以恢复先前源码。回滚前保留当前加密备份和本机数据密钥。
- 本轮没有新增数据库结构迁移，恢复旧版源代码时数据库结构版本保持一致。Android 加密迁移已提交的数据应继续使用支持版本 2 的构建读取。


## 安全双模式的独立功能开发

日期为 2026 年 11 月 11 日。

### 架构与功能

- Agent 的单回复接口继续支持既有调用。人工工作台通过 reply_mode=three_options 请求三条独立建议，字段包含稳定类型、文本、原因以及事实、推测和未知信息。
- 三个候选分别经过格式、差异和敏感词检查。新增必需的 reply-quality-checker 契约，与原有语音模块共同组成 13 项 Skills。
- regenerate 请求复用上下文并保存执行记录，原始历史在重新生成时保持两条。长度与语气调整通过显式参数进入本次 Prompt。
- Android 提供编辑、确认复制、查看原因、取消和打开微信入口。网络请求失败时保留尚未提交成功的输入。
- 安全中心提供本机暂停与服务端同步。服务端使用已有联系人授权版本使暂停前进行中的生成失效，暂停后旧消息缓存不能重新变成可发送建议。
- 个人微信受限自动入口维持关闭，开放前继续验证双方许可、可靠身份、平台发送方式与送达状态。

### 依赖和迁移

- 复用现有 Kotlin、Compose、Python 3.12、LangGraph、Mem0 和 DeepSeek 客户端依赖。
- 服务端继续使用正式迁移版本 6，Android 旧库采用版本 2。回复方案和暂停设置保存在已有加密字段中，备份文档兼容可选扩展字段。
- Room 消息数据库与通知身份绑定继续列为待开发项目。

### 自动化和实际运行

- 完整后端测试 103 项通过，包含真实 TCP HTTP、三方案、重新生成不重复写入、暂停期间请求失效、恢复后阻止旧缓存重放及原有功能回归。
- 官方 DeepSeek 的 deepseek-chat 实际返回三条不同回复，三类分析齐全。实际重新生成后历史条数为 2，暂停动作返回 paused，复合话题返回 handoff。本轮耗时 5.547 秒。
- Debug APK、设备测试 APK、5 项 JVM 测试和 Lint 已构建运行。当前 Lint 为 0 errors、10 warnings，最终构建结果继续按构建日志核对。
- 设备测试已扩充编辑、复制和取消动作。晚间手机 USB 断开，最新页面的设备测试尚待运行，当前通过记录覆盖此前五导航及通知探针构建。
- 本机证据包括 safe-mode-tests.log、safe-mode-build.log、real-safe-mode-acceptance.json、notification-device-tests.log 和 personal-wechat-p0.json，位于被忽略的 data/verification-20261111 目录。

### 已知问题与后续

- 受控 Bot 通知已实际读取，RemoteInput 数量为 0。普通好友通知、锁屏、折叠、通知权限撤销与个人微信送达仍需逐项测试。
- MIUI 在安装或测试后曾阻止监听服务绑定，刷新已授权连接后恢复。后台稳定性仍需设备验收。
- 最新编辑复制与安全中心需要手机重连后安装验证。HTTPS 正式部署、Room 队列、可靠联系人绑定和 Windows 管理界面继续开发。
- 回滚基线为 Git 提交 8384dc4。回滚源码前保存加密备份和本机密钥，在独立目录检出基线核对数据兼容性。

### 相对基线的修改文件

- `.env.example`
- `PROJECT_AUDIT.md`
- `README.md`
- `agent_server/control.py`
- `agent_server/core.py`
- `agent_server/graph_adapter.py`
- `agent_server/memory.py`
- `agent_server/models.py`
- `agent_server/service.py`
- `agent_server/settings.py`
- `agent_server/skills/__init__.py`
- `agent_server/skills/reply-quality-checker.json`
- `app/src/androidTest/java/com/lovepilot/ai/NavigationTest.kt`
- `app/src/androidTest/java/com/lovepilot/ai/NotificationProbeTest.kt`
- `app/src/main/AndroidManifest.xml`
- `app/src/main/java/com/lovepilot/ai/AgentViewModel.kt`
- `app/src/main/java/com/lovepilot/ai/NotificationProbe.kt`
- `app/src/main/java/com/lovepilot/ai/SecurePrefs.kt`
- `app/src/main/java/com/lovepilot/ai/Store.kt`
- `app/src/main/java/com/lovepilot/ai/WeChatListener.kt`
- `app/src/main/java/com/lovepilot/ai/ui/LovePilotApp.kt`
- `app/src/main/java/com/lovepilot/ai/ui/NotificationProbeScreen.kt`
- `app/src/main/java/com/lovepilot/ai/ui/SafetyScreen.kt`
- `app/src/main/java/com/lovepilot/ai/ui/SettingsScreens.kt`
- `app/src/main/java/com/lovepilot/ai/ui/Theme.kt`
- `app/src/main/java/com/lovepilot/ai/ui/Workspaces.kt`
- `docs/DEVELOPMENT_STATUS.md`
- `docs/PHASE_ACCEPTANCE.md`
- `integrations/astrbot_plugin_lovepilot/main.py`
- `scripts/Start-Agent.ps1`
- `tests/phone_backend.py`
- `tests/phone_bot_acceptance.py`
- `tests/phone_notification_acceptance.py`
- `tests/test_bot_bridge.py`
- `tests/test_control.py`
- `tests/test_http_api.py`
- `tests/test_memory_security.py`
- `tests/test_reply_options.py`
