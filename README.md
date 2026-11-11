# LovePilot AI

个人微信 AI 沟通助手，默认生成建议后由用户编辑、确认并发送，采用 Kotlin、Jetpack Compose、Python、LangGraph 和 Mem0。AstrBot 与官方 iLink 保留为可选独立 Bot 集成及受控测试对端。

**当前为 V2.0 开发快照 `2.0.0-dev`。** 最新后端 103 项回归通过，DeepSeek 官方接口已实际生成三种回复。红米通知入口读到过真实受控测试消息，该条通知没有快捷回复动作。最新编辑复制、安全中心页面待实机复测，完整验收范围见 `docs/DEVELOPMENT_STATUS.md`。

## 当前功能

- 五个主导航，包含首页、聊天、联系人、记忆与我的。
- 模型配置、个人风格、12 项可配置 Skill、工作流、审计日志和 Bot 管理页面。
- 实际 LangGraph 消息工作流与节点执行记录。
- 三种回复方案，区分事实、推测和未知信息，支持编辑、确认复制、取消、重新生成与语气及长度调整。
- 安全中心与暂停控制，暂停会取消本机生成并阻止服务端进行中请求写入旧结果。
- 默认人工确认，受限个人微信自动模式保持关闭，等待联系人识别、许可和发送能力验收。
- 联系人授权、跨连接消息幂等、进行中授权撤销及人工接管。
- 从明确原话提取候选记忆，经用户确认后保存。
- Mem0 与中文本地向量模型，按联系人隔离检索。
- 服务端字段加密、Android Keystore 凭据保护、数据库迁移与密码加密备份。
- AstrBot 官方 iLink 适配器桥接，支持 `/start`、`/pause`、`/forget`、`/help`。
- 官方微信二维码申请和扫码状态管理接口。

本项目使用明确标识的独立 AI Bot。微信渠道由 AstrBot 官方适配器提供，联系人通过 `/start` 授权。

## 环境

| 组件 | 要求 |
| --- | --- |
| Python | 3.12 |
| JDK | 17 |
| Android SDK | Platform 35 |
| Gradle | 8.9，仓库提供 Wrapper |
| Android | 最低 Android 8，实机测试设备为红米 Android 13 |
| AstrBot | 4.29.4 |

## Windows 安装

在项目根目录运行 PowerShell。

```powershell
./scripts/Setup.ps1 -WithAstrBot
./scripts/Start-Agent.ps1
```

安装程序创建 `.venv` 和本机 `.env`，生成随机管理、Bot 和只读令牌。模型密钥可在 Android 的模型设置中填写，应用保存的模型密钥使用服务端加密存储。

`requirements.lock` 记录本次 Windows 环境的完整依赖版本，供重现开发快照使用。

服务默认监听 `127.0.0.1:8768`。远程部署使用带认证的 HTTPS 入口。

后台运行与停止命令如下，后台恢复流程的实测状态见阶段记录。

```powershell
./scripts/Start-Agent.ps1 -Background
./scripts/Stop-Agent.ps1
```

## 构建与连接 Android

```powershell
./gradlew.bat :app:assembleDebug
adb install -r app/build/outputs/apk/debug/app-debug.apk
adb reverse tcp:8768 tcp:8768
```

打开 App，在“我的 → 连接与权限”中设置服务地址和 `.env` 中的 `LOVEPILOT_TOKEN`。本机 USB 联调地址为 `http://127.0.0.1:8768`。应用使用 Android Keystore 加密保存连接凭据。

随后配置模型供应商，建立已授权联系人，即可生成待确认的回复建议。聊天页默认提供三种表达，编辑后确认复制，再到微信核对原会话并发送。候选记忆在“记忆”页确认保存。“我的 → 安全中心”提供暂停和权限状态，“微信接入验证”提供受控通知测试。

## 微信 Bot

```powershell
./scripts/Start-Bot.ps1
```

官方 AstrBot 控制台默认位于 `http://127.0.0.1:6185`。本机管理凭据以加密形式保存在 `data/astrbot` 中，操作员可在本机查看。

```powershell
./scripts/Show-Bot-Login.ps1
```

Android 的 Bot 页面提供官方扫码入口。电脑端扫码辅助入口如下。

```powershell
./.venv/Scripts/python.exe -m agent_server.bot_login
```

首次登录需要微信账号支持官方 Bot 功能并由本人扫码确认。全局自动回复开关默认暂停，参与者还需要发送 `/start`。图片理解、语音转写、语音发送与掉线恢复按实际适配器支持情况单独验收。

`LOVEPILOT_AUTO_REPLY` 是插件的通道开关。完整回复同时受 App 中的全局开关、会话授权及安全审核控制。当前默认配置可在 `.env.example` 中查看。

## 测试

```powershell
./.venv/Scripts/python.exe -m unittest discover -s tests -v
./gradlew.bat :app:testDebugUnitTest :app:lintDebug
./gradlew.bat :app:assembleDebugAndroidTest
```

部分接口与设备测试使用明确标记的外部模型测试响应。设备测试后端位于 `tests/phone_backend.py`，使用独立临时数据库。真实模型与微信账号验收分别记录。

`tests/phone_notification_acceptance.py` 是显式启用的受控通知测试，要求已授权的通知监听器和唯一的已同意独立 Bot 测试会话。它通过安装后的 App 页面建立随机测试码，使用官方 API 发送该测试码，并核对手机诊断结果。个人微信发送成功继续由实际会话结果验收。

## 数据与源码

- `.env`、数据库、密钥文件、模型缓存、登录二维码、设备截图及本机原始日志保存在开发机器。
- GitHub 仓库包含源码、测试、迁移、部署入口与脱敏开发文档。
- 正式备份通过 App 生成，使用独立密码加密。恢复联系人后需要重新授权。
- Mem0 的派生索引保存在内存中，由已确认的持久化事实重建。
- AstrBot 的账号会话、媒体缓存和凭据存储遵循其上游实现，部署时需一并管理。

历史原型说明见 `docs/archive/README_V01.md`，开发前审计见 `PROJECT_AUDIT.md`。
