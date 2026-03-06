# codex2api 待办清单

> 更新日期: 2026-03-06

## 已确认（2026-03-06）

- `browser` 注册模式预检已恢复通过（`--target 1` 成功），生日填写与账号落库链路正常。
- 待继续执行的重点仍是 `http` 纯接口模式稳定性，不再把“生日未填写”作为主阻塞项。

## P0 - 模型真值测试（待执行）

目标：确认“声明模型名”与“真实上游执行模型”是否一致，识别回退映射。

1. 启动链路
- 启动 `chat2api`、`backend`、`frontend`（或确认现有进程可用）
- 确认 `/v1/chat/completions` 可用

2. 模型列表采样
- 记录 `/v1/models` 返回的完整模型列表
- 标注来源：静态声明 / 上游探测 / 历史 usage

3. 逐模型探针（非流式）
- 对候选模型逐个发送同一提示词（最小 payload）
- 记录 HTTP 状态码、错误码、响应 `model` 字段

4. 映射日志核对
- 对照 chat2api 日志中的 `Model mapping: origin_model -> req_model`
- 输出分类：
  - `真实支持`
  - `别名映射`
  - `回退到其他模型`
  - `不可用`

5. 验收产物
- 生成“模型真值矩阵”文档（模型名 / 实际 req_model / 可用性 / 备注）

## P0 - 纯 HTTP 注册流程实测（待执行）

目标：验证 `registration.mode=http` 在真实环境可用性与失败模式。

1. 配置切换
- 在配置页将 `registration.mode` 切换为 `http`
- 保持 TalentMail、OAuth 参数、代理参数一致

2. 单次链路跑通
- 执行一次 `/api/pipeline/register`
- 记录每一步耗时、失败点与错误原文

3. 关键节点验证（图5路径）
- `chatgpt.com /api/auth/*`
- `auth.openai.com /authorize`
- `auth0.openai.com /oauth/token`
- 对齐 `csrf/cookie/state/code_verifier` 关联关系

4. 稳定性小样本
- 连续跑 5 次，统计成功率
- 分类失败原因：turnstile、邮箱验证码、about-you、token 兑换

5. 对比结论
- 与 `browser` 模式对比：
  - 成功率
  - 平均耗时
  - 失败可恢复性
- 给出是否继续投入 `http` 路线的决策建议
