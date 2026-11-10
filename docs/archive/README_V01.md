# LovePilot AI — Android V0.1 源码

## 当前真正实现
- 原生 Android 项目（Kotlin），Android 8.0+，Android 13 可测试。
- 微信通知监听：**只记录是否存在 RemoteInput 快捷回复动作**，不读取或保存微信聊天正文。
- 手动创建联系人档案；SQLite 本地保存、查看、全部删除。
- 粘贴消息后调用 DeepSeek 生成**待人工确认**的中文回复；支持复制。
- 敏感词人工接管、日志与清除功能。
- 无需 Root，不修改微信。

## 当前没有实现（不能误认为已完成）
- 不会自动发送微信消息；没有读取完整微信历史；没有多轮长期记忆自动提取；没有自动关联微信联系人；没有稳定的后台自动聊天。
- 本项目是可继续开发的最小功能原型，**未在此环境编译成 APK，也未经真实红米/微信验证**。
- 未提供 Gradle Wrapper 二进制；首次用 Android Studio 导入，安装本机 Gradle 8.9 或使用 IDE 配置合适 Gradle Wrapper。

## 编译安装
1. 安装 Android Studio（JDK 17、Android SDK 35、Android Gradle Plugin 8.7.3 所需环境）。
2. File > Open，选择本目录；首次同步需要下载 Gradle 与依赖。可通过 Android Studio 配置 Gradle 8.9。
3. 在手机开启开发者选项与 USB 调试，`adb devices` 应显示 `device`。
4. Android Studio 选择真机，Build > Build APK(s)，然后通过 IDE Run 安装，或 `adb install -r app/build/outputs/apk/debug/app-debug.apk`。
5. 启动 App，授予通知使用权，确保微信允许显示通知；测试联系人发送微信消息。
6. 在 PowerShell 使用 `adb logcat -s LovePilot:D`（当前版本日志主要在 App 的“查看微信通知兼容性日志”中）。
7. 在 App 输入 API Key 和**虚构测试消息**，生成并检查回复建议。

## 重要技术约束
- `replyAvailable=true` 仅说明通知携带自由文本 RemoteInput，不等于可稳定送达。
- 不能可靠匹配联系人身份时不得自动发送。
- 若未来增加自动发送，应限制在知情授权联系人，默认关闭，提供人工接管、发送去重、失败恢复、节流、撤销开关和完整测试。
- 本地 SQLite 目前未加密，**不要存真实敏感聊天**；正式版须增加加密、细粒度删除、数据保留期与明确告知。
- API Key 仅保存在当前 Activity 内存中，应用被销毁后需重新输入。
- 微信个人号非官方自动化可能违反平台规则；不保证最新版微信支持通知回复。

## 推荐下一步
P1：实机验证通知可见性与 RemoteInput。P2：联系人明确绑定、去重与发送回执测试。P3：Room/加密/长期记忆。P4：联系人授权、风险策略和端到端验收。
