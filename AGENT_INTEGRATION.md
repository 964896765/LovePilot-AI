# LovePilot AI · Agent 集成说明（V0.2）

## 已实现
- 可运行的 Python Agent 服务（标准库 HTTP API，默认仅监听 127.0.0.1:8768）
- 8 个内置 Skill 策略说明；联系人授权白名单、SQLite 持久化消息、独立上下文、删除、审计
- DeepSeek API 回复草稿；敏感话题人工接管；错误兜底
- LangGraph / Mem0 可选依赖探测（**尚未接入其工作流或记忆 API**）
- 安卓 V0.1 工程保留；**安卓端尚未接通本服务**，微信自动发送尚未实现

## Windows 启动（PowerShell）
```powershell
cd C:\Users\<user>\Desktop\LovePilotAI
$env:LOVEPILOT_TOKEN = '换成随机的长令牌'
$env:DEEPSEEK_API_KEY = '你的密钥'
python -m unittest discover -s tests -v
python -m agent_server.server
```
不要把令牌/API Key 写入 Git 或 APK。默认监听 localhost，手机无法直接访问；后续需建立经认证的安全通道，禁止把这个原型服务直接暴露公网。

## API 示例（另一个 PowerShell 窗口）
```powershell
$headers = @{Authorization="Bearer $env:LOVEPILOT_TOKEN"}
Invoke-RestMethod http://127.0.0.1:8768/health -Headers $headers
Invoke-RestMethod http://127.0.0.1:8768/contacts -Method Post -Headers $headers -ContentType 'application/json; charset=utf-8' -Body '{"contact_id":"test-1","alias":"测试联系人","consent":true,"notes":"喜欢电影"}'
Invoke-RestMethod http://127.0.0.1:8768/draft -Method Post -Headers $headers -ContentType 'application/json; charset=utf-8' -Body '{"contact_id":"test-1","message":"今天过得怎么样？"}'
```

## 下一阶段必须完成
1. Android HTTPS 客户端与安全令牌配置；真实联系人可靠绑定，拒绝只用通知昵称自动识别。
2. LangGraph 状态图与 Mem0 适配器（当前仅有可测试的本地 SQLite 记忆实现）。
3. 经过对方知情同意的测试联系人，验证微信通知是否提供 RemoteInput；不保证最新版微信兼容。
4. 密钥安全、数据库加密、可导出删除、访问频率限制、敏感词语义审核、崩溃恢复。
5. 安卓 Gradle 编译、真实手机测试；当前**未编译 APK**。
