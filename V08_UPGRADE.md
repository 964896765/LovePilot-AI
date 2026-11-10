# LovePilot AI V0.8

## 已完成
- 联系人撤销授权（含 `/contacts` 将 consent 设为 false）会清除重复消息缓存。
- Agent 决策与授权变更使用同一进程的重入锁，防止并发通知产生重复草稿。
- 删除联系人时同步删除其审计记录。
- 模型错误不再将异常详情（可能包含凭据）直接返回安卓客户端。
- API 拒绝非 JSON 对象及非布尔类型的 consent。
- 增加五项回归测试。

## 限制
- 单进程 SQLite 原型；多个服务进程之间不共享 Python 锁。
- 模型调用时持有联系人数据库锁，牺牲并发吞吐换取原型一致性；正式版应采用每联系人任务队列。
- 未实现数据库加密、安卓 APK 编译、真机验证、微信自动发送。
- LangGraph 和 Mem0 适配器仍需在安装依赖后验证，未宣称已投入生产。

## Windows 运行
```powershell
python -m unittest discover -s tests -v
$env:LOVEPILOT_TOKEN = '替换为随机长令牌'
$env:DEEPSEEK_API_KEY = '替换为你的密钥'
python -m agent_server.server
```
服务仅监听 127.0.0.1:8768。不要直接开放到公网。
