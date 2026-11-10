# LovePilot AI V0.7 — 联调修复版

## 已修改
- 修复 Android AgentClient 的 POST 白名单遗漏 `/revoke` 和 `/export`，此前界面按钮会在请求发出前抛出异常。
- 增加 `/health` 授权连通性诊断按钮，检查 Windows Agent 是否可通过 `adb reverse` 访问。
- 增加 Android 通知监听授权状态诊断按钮。授权状态不等于微信通知/RemoteInput 可用。
- 统一界面与 Gradle 版本号为 0.7.0。

## 运行
Windows PowerShell（在工程根目录）：
```powershell
$env:LOVEPILOT_TOKEN = '自行设置随机长令牌'
$env:DEEPSEEK_API_KEY = '你的API密钥'
python -m unittest discover -s tests -v
python -m agent_server.server
```
另开终端：
```powershell
adb devices
adb reverse tcp:8768 tcp:8768
```
Android Studio 打开工程，安装 Debug 版，填入同一令牌，点击「检测 Agent 服务连通性」。

## 限制
未在当前环境编译 APK（缺 Android SDK/Gradle），未在真实微信上测试 RemoteInput。当前只提供 AI 草稿，不自动发送；LangGraph/Mem0 仍需安装依赖并进行端到端验证。请勿将测试 HTTP 服务暴露公网。
