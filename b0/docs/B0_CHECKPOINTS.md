# B0 检查点凭据

## 第一检查点

阶段：环境与版本。

完成事项：检查空目录、创建指定布局、检查 WSL/工具/端口、下载三个官方仓库、固定候选 A。

实际命令：`environment.sh`；`git clone` UI/Agno/Docker；完整 Agno clone 失败后 `git clone --depth 1 --branch v2.9.0`；`git remote -v / rev-parse HEAD / status --short`；CodeGraph init/status。

运行结果：源码下载成功；官方 UI 声明 v2，实际选用 Agno 2.9.0；默认 pnpm 11 frozen 安装失败，10.34.5 成功；Python 环境独立。

通过项：来源/身份/目录/隔离；失败项：完整历史 clone TLS 中断（精确标签浅克隆已恢复），旧 DeepSeek 配置不可用（未使用其推理）。

证据位置：`evidence/logs/environment.log`、`versions/repositories.json`、`versions/package-source-checks.json`。

源码是否修改：无官方 tracked 业务源码修改。

下一步：最小原版 Runtime 与 UI 启动。

## 第二检查点

阶段：原版前后端启动。

完成事项：最小官方 AgentOS 副本运行、独立 native fixtures、UI 连接、真实模型对话。

实际命令：`start-runtime.ps1`、`start-runtime.ps1 -NativeTests`、`check-api.py`、`start-ui.sh`、`pnpm dev --turbopack --port 3100`、浏览器发送两个指定问题。

运行结果：health/info/config/docs/discovery 200；真实模型响应与 Run ID；原版 UI 在3100展示对话。

通过项：前后端服务/连接/真实回复；失败项：默认 CORS400已用官方环境配置修正、Webpack dev编译停滞已用官方Turbopack参数恢复。

证据位置：`quickstart-api.json`、`runtime-api.json`、`cors-before/after.json`、`ui-tool-stream*.json`、截图01–05。

源码是否修改：只调整 b0 运行副本环境配置，无官方源码改动。

下一步：T01–T08 与会话重启恢复。

## 第三检查点

阶段：原生能力测试。

完成事项：Agent、Tool、Sessions、Workflow、Team、Skills、Scheduler；Run/Tool/Schedule History；本地 Tracing。

实际命令：`run_native_tests.py agent/tools/sessions/workflow/team/skills`（逐次参数运行）；`test_scheduler.py`；`test_scheduler_failure.py`；`check-history.py before/after`；`verify-evidence.py`；浏览器刷新/重启恢复与Team执行。

运行结果：每项原生后端通过；真实 Cron 自然触发success；预期负面手动触发failed记录可查；所有任务停用；Agent/Team/Workflow/Schedule与trace重启持久化通过。

通过项：上述限定行为；失败项：一次多轮模型最终回复偏题已保留，新Session成功，未掩盖该服务风险。

证据位置：T01–T08 JSON、后端语义门禁、browser-acceptance、截图06–14。

源码是否修改：仅 b0 中性验证代码，未改官方业务源码。

下一步：UI审计与产品差距表。

## 第四检查点

阶段：产品 UI 审计。

完成事项：CodeGraph/源码对照页面、状态、通信、流、工具、Sessions、Agent/Team、引用、多媒体、错误与基础组件；完成KEEP/MODIFY/DISABLE/ADD表。

实际命令：CodeGraph explore；相关源码读取；浏览器Agent/Team实际操作；`check-ui.sh`。

运行结果：开源UI可复用聊天/Session/Agent/Team；无Workflow与Scheduler管理页；London八个业务页面均未实现，不填成已有。

通过项：组件审计交付、lint/typecheck/format；失败项：默认生产构建另列额外质量检查，不影响源码审计事实。

证据位置：UI_AUDIT、GAP_ANALYSIS、FUNCTION_CATALOG、architecture JSON/HTML及校验凭据。

源码是否修改：无官方业务源码修改；未开发业务页面。

下一步：最终完整性、报告和证据验收。

## 最终检查点

阶段：B0验收报告。

完成事项：八份规定报告及兼容调整别名、复现脚本、独立审阅修正、版本/凭据/截图索引与hash清单。

实际命令：compileall、OpenSpec strict、verify-evidence、verify-browser-evidence、原仓库diff/status、finalize-receipts；生产build按实际日志独立分类。

运行结果/通过项/失败项：以 B0_FINAL_REPORT 的最终交付状态与 `logs/final-verification.log` 为准；不存在把未结束build写成通过的规则。

证据位置：`artifact-manifest.json`、`repositories-final.json`、TEST_REPORT、FINAL_REPORT。

源码是否修改：最终 Git diff核验三仓库tracked业务源码未修改；本地索引未跟踪。

下一步：停止在B0，等待负责人审核，不自动进入B1。
