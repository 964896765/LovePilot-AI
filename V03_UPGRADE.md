# LovePilot AI V0.3

基于 V0.2 增量升级：消息幂等（message_id）、联系人结构化事实记忆、读取记忆 API、删除时清理记忆、可选 LangGraph 状态图、可选 Mem0 适配器。

## 测试
`python -m unittest discover -s tests -v`

## 运行
设置 `LOVEPILOT_TOKEN` 与 `DEEPSEEK_API_KEY`，运行 `python -m agent_server.server`。默认仅监听 127.0.0.1:8768。

- `POST /contacts`: `{"contact_id":"test-a","alias":"测试联系人","consent":true}`
- `POST /facts`: `{"contact_id":"test-a","key":"共同话题","value":"电影"}`
- `GET /memory?contact_id=test-a`: 查看历史与事实（需 Bearer Token）
- `POST /draft`: `{"contact_id":"test-a","message":"你好","message_id":"unique-message-1"}`；相同 message_id 不会重复调用模型。
- `POST /delete`: `{"contact_id":"test-a"}` 删除联系人、消息、事实与幂等缓存。

## 可选组件
`pip install langgraph mem0ai`，调用 `agent_server.graph_adapter.build_graph(agent)` 取得 LangGraph 工作流；Mem0 仅在明确启用后写入用户授权的事实，默认不传输聊天内容。

## 尚未完成
安卓端未接通本地 HTTP 服务；没有已验证的 APK；未实现微信自动发送；未验证 DeepSeek 实际调用。服务仅监听本机，手机连接需要额外的安全网络方案，不能直接将服务暴露公网。数据库未加密，正式使用前需加密与完善线程安全。未经授权不要导入他人聊天记录。
