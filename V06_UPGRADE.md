# LovePilot AI V0.6 — Agent 工作流与记忆安全升级

## 新增
- LangGraph 五节点工作流：授权检查 → 风险判断 → 上下文检索 → 草稿生成；敏感内容转人工。
- Mem0 适配器新增显式授权门槛、按联系人检索、删除入口。
- 五项新增测试（其中 LangGraph 依赖缺失时跳过）。

## 安装可选依赖
在 Python 虚拟环境中运行：

```powershell
python -m pip install langgraph
python -m unittest discover -s tests -v
```

Mem0 可选：`python -m pip install mem0ai`。**不建议在未确认向量库、模型供应商及数据存储位置前开启 Mem0**。目前 HTTP 服务仍调用标准库 Agent；LangGraph 通过独立适配器调用测试，尚未作为服务默认执行引擎。Mem0 尚未接入在线写入链路。

## 限制
- 未编译 APK、未在真实红米手机上测试。
- 未实现微信自动发送或主动发消息。
- SQLite 当前未做静态加密，勿录入真实敏感聊天。
- 默认仅生成需人工确认的草稿。
- 不能仅凭微信通知昵称安全识别联系人。
