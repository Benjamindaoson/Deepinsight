# B0 原生功能目录

范围：冻结 Agno 2.9.0 与 UI SHA；状态是本轮证据状态，不是宣传性功能清单。源码路径均相对 `D:\deepinsight-lite\upstream\agno`；前端路径相对 `upstream/agent-ui`。

| 能力 | 原生实现与依赖 | 使用方法 / 证据 | 后端状态 | 开源 UI |
|---|---|---|---|---|
| Agent | `libs/agno/agno/agent/agent.py`；模型 SDK | `Agent.run/arun`，`POST /agents/{id}/runs`；T01 | SUPPORTED AND TESTED | 选择、对话、流、恢复均实测 |
| Tools | `libs/agno/agno/tools/function.py`；类型化 Python callable | `tools=[add_numbers]`；T02 run tools、Python JSONL、UI SSE | SUPPORTED AND TESTED | 显示工具名；原始参数/结果看事件/API |
| Native Skills | `skills/agent_skills.py`、`skills/loaders/local.py`；官方 sample_skills | `Skills(loaders=[LocalSkills(...)])`，真实 `get_skill_instructions('code-review')`；T06 | SUPPORTED AND TESTED | 可通过 Skills Agent 对话；无 Skill 管理页 |
| Sequential Workflow | `workflow/workflow.py`、`workflow/step.py`；原生 `Step/Workflow` | Draft→Review；下一步 user input 包含上一完整输出；T04 | SUPPORTED AND TESTED | NOT SUPPORTED / GAP |
| Team | `team/team.py`；官方 `TeamMode.broadcast` | 两名成员、各自 Run ID、最终合成；T05 | SUPPORTED AND TESTED | Team 发现/执行/显示实测 |
| Sessions | `db/sqlite/sqlite.py`、`session/*`、`os/routers/session` | SQLite；Session API，刷新和服务重启恢复；T03/T08 | SUPPORTED AND TESTED | 列表、打开、恢复实测；删除仅源码审计 |
| 会话上下文 | Agent `add_history_to_context` / `num_history_runs` | 同 Session 记住测试标记；T03 | SUPPORTED AND TESTED | 提问与展示已有记录。不是长期用户 Memory 测试 |
| Scheduler | `scheduler/manager.py`、`poller.py`、`executor.py`，`db/sqlite/sqlite.py` | 原生 Cron/API，create/enable/disable/trigger/history；T07 | SUPPORTED AND TESTED | 无管理页；本地 Swagger/API 可用 |
| Agent/Team/Workflow Run History | 原生数据库、`os/routers/*` | T08 / Session runs API；Run ID 可关联 | SUPPORTED AND TESTED | Agent/Team 历史可用；Workflow 无入口 |
| Tool Call History | Run tools/messages/events | T02、UI 原始 SSE；工具名、参数、结果、tool_call_id | SUPPORTED AND TESTED | 工具标签；不等同完整审计详情页 |
| Tracing | `tracing/*`、`os/routers/traces`，本地 tracing DB | `AgentOS(tracing=True)`；`GET /traces` 与 trace detail，重启持久化核查 | SUPPORTED AND TESTED（本地写入/读取） | 无 Trace dashboard；未评估所有 span 语义 |
| Memory | `memory/*`，DB 与可能的模型调用 | 存在 `/memories` 等原生 API；未创建/更新长期用户记忆 | SUPPORTED BUT NOT TESTED | 无管理页 |
| Knowledge | `knowledge/*`、vector DB/embedding 等按配置依赖 | 存在 `/knowledge/*` API；未导入或检索内容 | SUPPORTED BUT NOT TESTED | 引用渲染组件存在；检索能力未实测 |
| Evaluations | `evals/*`、`/eval-runs` | 源码与 API 可发现；未运行 eval | SUPPORTED BUT NOT TESTED | 无管理页 |
| HITL / approvals / checkpoints / resume | SDK 与 Runtime OpenAPI 可发现 | 此 B0 未主动验证暂停、恢复、审批流程 | SUPPORTED BUT NOT TESTED | 不推定 UI 完整覆盖 |
| Runtime component registry | `/components`、`/registry` | 仅发现 API 与源码；未验证 runtime builder 生命周期 | SUPPORTED BUT NOT TESTED | 不从 Docker 模板/Control Plane 反推 UI |
| 多模态展示 | UI `Messages/Multimedia` | images/audio/video 渲染代码存在；未生成多模态内容 | SUPPORTED BUT NOT TESTED（UI 渲染） | 源码支持输出展示；输入区无上传控件 |

T07 正向：5 字段 Cron，自然触发一次，`status=success`，Schedule Run 与 Agent Run 可关联；观测首次 claim 后即 disable，完成后再次核实停用。反向：对不存在的 Agent 手动 trigger，HTTP 404 被记录为 `failed`，这是预期的负面测试成功，没有模型调用。调度历史在服务重启后仍存在。没有安装 APScheduler，没有自行实现调度执行器。

`SUPPORTED BUT NOT TESTED` 不等于 PASS，也不等于当前配置能直接运行业务；尤其 Knowledge 所需 embedding/vector store、Memory 的语义更新、评估标准均未纳入本轮正式能力证明。
