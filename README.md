# LovePilot AI

Android AI 沟通助手与独立微信 AI Bot，采用 Kotlin、Jetpack Compose、Python、LangGraph、Mem0 和 AstrBot。

**当前为 V2.0 开发快照 `2.0.0-dev`。** 已执行本地自动化测试、APK 构建与部分红米 Android 13 实机测试。真实 DeepSeek 回复质量、微信账号登录后的收发与新增扫码界面仍有待验收项目，详细范围见 `docs/DEVELOPMENT_STATUS.md`。

## 当前功能

- 五个主导航，包含首页、聊天、联系人、记忆与我的。
- 模型配置、个人风格、12 项可配置 Skill、工作流、审计日志和 Bot 管理页面。
- 实际 LangGraph 消息工作流与节点执行记录。
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

随后配置模型供应商，建立已授权联系人，即可生成待确认的回复建议。候选记忆在“记忆”页确认保存。

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

## 数据与源码

- `.env`、数据库、密钥文件、模型缓存、登录二维码、设备截图及本机原始日志保存在开发机器。
- GitHub 仓库包含源码、测试、迁移、部署入口与脱敏开发文档。
- 正式备份通过 App 生成，使用独立密码加密。恢复联系人后需要重新授权。
- Mem0 的派生索引保存在内存中，由已确认的持久化事实重建。
- AstrBot 的账号会话、媒体缓存和凭据存储遵循其上游实现，部署时需一并管理。

历史原型说明见 `docs/archive/README_V01.md`，开发前审计见 `PROJECT_AUDIT.md`。
