# B0 独立审阅与修正凭据

2026-10-17，在 requesting-code-review Skill 要求下，由独立只读审阅者检查 b0/scripts、b0/smoke-tests、用户需求与后端凭据。未读取密钥，未访问 A 路线，未运行模型或控制服务。根目录不是 Git 仓库，审阅对象为新增验证文件，不伪造 commit 范围。

初次结论要求修正六类问题：停止脚本对同解释器进程的归属校验不足；UI 检查退出码可能误报；调度清理失败后仍可保留 PASS；历史校验引用固定 Team Session；T02 没有检查完成回答；汇总未覆盖手动调度失败状态。

修正后，同一审阅者只读复核，结论为 **限定范围 harness 审阅通过，无仍需阻止提交的 Critical/Important 问题**。此结论不等于全 B0 PASS，也不替代浏览器/构建验收。

修正措施及运行证据：

| 问题 | 修正 | 验证 |
|---|---|---|
| 进程归属 | stop-runtime 必须匹配记录 launcher/直接子进程及运行命令；stop-ui 核对 cwd+祖先链 | 本轮正常停止/重启及 Session 恢复记录 |
| 检查退出码 | check-ui 汇总非零；history 和 evidence 检查失败返回非零 | ui-check-exits.tsv；最终语义脚本退出码 |
| Scheduler 清理 | 成功判据包含 verified disabled；异常保存并 FAIL，非零退出 | T07 两份真实凭据；最终 disabled 状态读取 |
| 历史身份 | 从 T04/T05 读取 Session，比较非空 Agent/Team/Workflow/Scheduler，核对预期 Run IDs；trace detail 持久化 | T08-restart-checks.json |
| Tool 证据 | completed+最终42、原生参数/结果、Python执行日志时窗关联 | verified-backend-checks.json |
| 调度负面测试 | 手动trigger、预期failed、最终停用均纳入汇总 | T07-scheduler-failure.json |
| 旧凭据残留 | run前归档同名旧receipt，网络错误保存ERROR；Session重跑归档关联旧receipt | harness负面HTTP检查、脚本语法与源码审阅 |

第二轮提到的 cd fail-fast 和空历史相等问题也已收紧。工具 JSONL 当前仍采用参数/结果及 ±2 秒时窗关联，适用于本轮串行最小测试；不将它宣传为未来并发下无碰撞的审计关联机制。原生 Run 的 tool_call_id 与 UI SSE 另提供直接调用身份。

没有因审阅修正任何官方业务源码。未为“测试脚本测试”发起额外模型请求。
