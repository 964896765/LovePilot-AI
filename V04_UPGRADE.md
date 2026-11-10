# LovePilot AI V0.4 — Android ↔ Agent 联调版

## 新增
- 安卓端 AgentClient，使用 POST /contacts 和 POST /draft；支持授权联系人同步与 AI 草稿显示。
- 授权事实纳入模型提示词，联系人间隔离；补充自动化测试。
- 调试版仅通过 USB adb reverse 映射 localhost:8768。正式版禁用明文 HTTP；不暴露服务器公网端口。
- 仍不自动发送微信消息，不抓取微信历史，不以昵称自动绑定联系人。

## Windows 运行
```powershell
cd C:\Users\<user>\Desktop\LovePilotAI
$env:LOVEPILOT_TOKEN = "请使用随机长令牌"
$env:DEEPSEEK_API_KEY = "你的密钥"
python -m unittest discover -s tests -v
python -m agent_server.server
```
另开终端：
```powershell
adb devices
adb reverse tcp:8768 tcp:8768
```
用 Android Studio 打开项目并构建 debug APK，安装到 USB 连接的安卓手机。在 App 中填写同一令牌、手动联系人 ID、备注、测试消息，先点“同步授权联系人到 Agent”，再点“通过 Agent 生成长期记忆回复”。

## 重要限制
- 本环境未安装 Android SDK，未编译 APK；Kotlin 需在 Android Studio 中构建验证。
- Android 调试 HTTP 仅限 adb reverse 映射本机服务，切勿在公网或不可信网络上使用。
- 不要将 API Key 写入源码或上传 Git。
- V0.4 仍使用可测试的标准库 Agent；LangGraph/Mem0 仍为待验证可选适配器。
- 不支持个人微信自动发送；如后续验证通知快捷回复，需要独立进行用户知情授权及实机测试。
