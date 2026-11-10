# LovePilot AI V0.5 — 授权与记忆管理

## 新增
- 安卓端明确授权勾选（默认关闭），撤销授权与导出联系人记忆按钮。
- 后端 `/revoke` 和 `/export` 接口（POST，需 Bearer 令牌）。
- 撤销授权会清除消息去重缓存，防止旧草稿绕过撤销状态。
- 新增 4 项授权生命周期单元测试。

## 运行
```powershell
python -m unittest discover -s tests -v
$env:LOVEPILOT_TOKEN = "设置随机长令牌"
$env:DEEPSEEK_API_KEY = "你的密钥"
python -m agent_server.server
```

## 限制
- 仍未接入真实 LangGraph / Mem0，适配器仅供参考。
- 未编译 APK、未做真实微信实机测试、未实现微信自动发送。
- 安卓端仅调试 HTTP + adb reverse；不要将服务暴露公网。
- 当前数据库未做静态加密，勿存放敏感个人信息；导出数据也须谨慎保管。
- 联系人 ID 必须手动绑定，不得仅凭微信昵称自动识别。
