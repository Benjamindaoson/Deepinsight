# B0 原版 Agent UI 功能审计

冻结源码：`upstream/agent-ui@6dad9593fca6756e1813e4f4b3b2620be6377691`。以下路径相对该目录。方法：先 CodeGraph 定位运行路径，再读取相关源码，并以真实浏览器及 API 交互核验。没有重新设计前端。

## 页面与执行路径

单一 `src/app/page.tsx` 组合 Sidebar 和 ChatArea；`layout.tsx` 提供字体、NuqsAdapter、Toaster 与全局样式。浏览器直接向配置的 AgentOS endpoint 发请求，没有另一套自建 BFF。主路径为：ChatInput → `useAIStreamHandler` → `useAIResponseStream` → AgentOS SSE → Zustand messages → Messages/Markdown/多媒体组件。恢复历史走 `useSessionLoader` 与 Session runs API。

| 类别 | 实现位置 | 已有 / 实测 | 后端契约 | B1+ 处置 |
|---|---|---|---|---|
| Layout / 页面 | `src/app/page.tsx`、`layout.tsx`、`globals.css` | 存在；首页 HTTP 200、浏览器正常 | 首页与静态资源 | MODIFY：扩展产品导航和页面布局 |
| Sidebar | `src/components/chat/Sidebar/Sidebar.tsx` | endpoint、状态、折叠、新聊天、模型信息；已实测 | `/health` | KEEP 核心连接/聊天区，MODIFY 业务导航 |
| 输入与消息 | `ChatArea/ChatInput/ChatInput.tsx`、`Messages/Messages.tsx` | Enter、Shift+Enter、IME 判断、空输入和流中禁用；真实对话实测 | POST Agent/Team runs，FormData | KEEP；不要重写聊天系统 |
| Agent 发现/切换 | `Sidebar/EntitySelector.tsx`、`useChatActions.ts` | B0 Agent 与 Skills Agent 可发现；B0 Agent 执行实测 | `GET /agents` | KEEP；产品只展示允许的业务实体 |
| Team | `Sidebar/ModeSelector.tsx`、EntitySelector、流处理 hook | Team 模式、发现、选择、执行均实测 | `/teams`、`/teams/{id}/runs` | KEEP；MODIFY 成员/委派详情展示 |
| Workflow | ModeSelector / `src/api/routes.ts` | 只有 `agent` / `team` 分支，没有 Workflow selector/run route | 后端 `/workflows` 和 runs 已通过 | ADD 调用/记录页；后端继续原生 Workflow |
| Tool Calls | `Messages.tsx` 的 ToolComponent，`types/os.ts`、流处理 hook | 显示工具名 pill；真实 ADD_NUMBERS / DELEGATE_TASK_TO_MEMBERS 截图 | SSE ToolCallStarted/Completed，Run tools | KEEP 标签；MODIFY 参数、结果、耗时、错误详情 |
| Sessions | `Sidebar/Sessions/*`、`hooks/useSessionLoader.tsx`、`api/os.ts` | 列表、打开、刷新、服务重启恢复已验证；删除只读审计未执行 | `/sessions`、`/sessions/{id}/runs`，`db_id` 和类型参数 | KEEP；按项目/报告增加业务组织能力 |
| References | `Messages.tsx` 的 References、ReferenceItem | 来源列表/链接代码存在；没有真实 Knowledge 检索引用生成测试 | Run extra_data / references | KEEP 组件，MODIFY 来源版本/抓取时间等证据字段 |
| Markdown / 表格 | `ui/typography/MarkdownRenderer/*` | react-markdown + GFM + raw 后 sanitize；文字/格式渲染实测 | 模型文本 | KEEP；无完整市场数据表产品 |
| 多媒体输出 | `Messages/Multimedia/Images`、`Audios`、`Videos`，`lib/audio.ts` | 输出图片/音视频组件存在；未生成媒体做端到端测试 | Run images/audio/video | DISABLE 业务首版不需要的入口；需要时再验收 |
| 文件输入 | `ChatInput.tsx` | 实际只有文本输入/发送，无文件上传和附件管理控件 | 后端能力需独立业务契约 | ADD（若产品需要）；不能因能显示图片就宣称能上传文档 |
| 状态管理 | `src/store.ts` | Zustand；消息/实体/stream/错误等内存状态；localStorage 只 partialize selectedEndpoint | 会话内容仍由 Runtime DB/API 恢复 | KEEP；不可误称聊天历史保存在 localStorage |
| URL 状态 | Nuqs；hooks/EntitySelector/SessionItem | agent、team、db_id、session 可追踪；实测 URL 恢复 | 对应 Session 和实体 | KEEP；后续增加产品实体与权限约束 |
| 认证与 endpoint | `Sidebar/AuthToken.tsx`、Sidebar Endpoint、`api/os.ts` | Bearer token 注入源码存在；本轮 Runtime loopback 无认证，未测试 JWT | 直接 Runtime fetch | MODIFY 生产认证；模型 API Key 严禁放前端 |
| 主题与基础组件 | Tailwind、shadcn/Radix、Framer Motion、`src/components/ui/*` | button/select/dialog/textarea/skeleton/tooltip/typography 等存在 | 无 | KEEP；图表、复杂筛选、业务表单需 ADD |
| 错误处理 | `api/os.ts`、`useAIResponseStream.tsx`、`useAIStreamHandler.tsx` | toast、网络/非成功状态、streamingError 标记；CORS 失败有真实证据 | fetch、SSE、HTTP errors | MODIFY 产品级错误、断线恢复、受控重试；不能假定已有通用超时/自动重连 |

## 界面与协议验证

首页/组件发现：截图 `01-ui-connected.png`。真实 Agent 问答：`02-ui-agent-reply.png`。UI SSE 与工具：`ui-tool-stream-new-session.json`，16 个真实事件，含模型请求开始/完成、工具参数 17/25、工具结果 42、最终答案 42。前端显示工具 pill；并没有把后台事件中的全部详细字段都展示给用户。

Team：`09-ui-team-selector.png`、`10-ui-team-reply.png` 和 `ui-team-stream.json`。它证明 UI 能使用 Team；后端 T05 保存两位成员的执行记录。Workflow 的 API 记录截图是后端证据，不冒充 UI Workflow 页面。

Session：`06-session-before-refresh.png`、`07-session-after-refresh.png`、`08-session-after-runtime-restart.png` 对应同一 ID `489ed5fa-1f60-40dc-9907-14af720ed95e`，显示相同标记及历史。API 比对另见 T08。

## 审计发现与限制

- 开源 UI 不含 Skills 管理、Cron 任务配置/启停、Tracing dashboard、评估、Memory/Knowledge 管理、报告中心、市场指标图。AgentOS Runtime 和商业 Control Plane 的功能不得算入此 UI。
- `src/api/routes.ts` 中 `DeleteTeamSession` 定义了可疑的 `/v1//teams/.../sessions/...` 路径；当前 SessionItem 实际使用通用 deleteSessionAPI，未在本轮执行删除，因此这里只记为潜在遗留路由，不宣称已复现删除故障。
- `Multimedia/Images/Images.tsx` 的图片加载失败 fallback 使用字符串插值设置 `innerHTML`，其中含 image URL。若后续允许不可信媒体，应独立验证属性/URL 注入风险并在 B1+ 修复；B0 不修改官方源码，不声称做过漏洞利用验证。
- token 状态目前不在 Zustand localStorage partialize 中；README 的笼统“stored locally”不能扩张成已验证刷新持久化。此处没有模型密钥；模型密钥仅后端读取。
- 一次多轮工具测试最终回答偏离问题，而工具确实返回 42。原始 SSE 已保存；新会话同一问题通过。该异常来自后端模型响应，未通过改 UI 掩盖。
- 表格可用 Markdown 渲染并不等于具备可排序的市场指标表；现有 Sidebar 不是市场产品导航；已有 Team 模式不是 Workflow 管理能力。

## 质量检查

冻结安装成功；原版 lint、typecheck、format 通过，输出在 `logs/ui-*.log`、退出码在 `logs/ui-check-exits.tsv`。生产 build 是额外门禁，最终状态见 B0_TEST_REPORT 与实际 `ui-build.log`。没有禁用类型检查、lint 或运行时校验。
