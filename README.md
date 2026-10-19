# DeepInsight Lite — London Office Market Agent

> **GitHub source snapshot:** this checkout contains the application source,
> tests, and a saved public-evidence fixture. The accepted local frozen release
> under `docs/delivery/`, live databases, original documents, and credentials
> are intentionally not published. For a fresh clone, use the explicit offline
> source path in [PUBLISHING.md](PUBLISHING.md); the formal local launch below
> requires the separately verified frozen release. The integration boundary
> is documented in
> [CURRENT_RUNTIME_AND_INTEGRATION.md](docs/architecture/CURRENT_RUNTIME_AND_INTEGRATION.md).

在原验收主机上的正式本地产品地址为 **http://127.0.0.1:3105**，API 为 **http://127.0.0.1:7788**。该主机的冻结版本由 Git 忽略的 `docs/delivery/ACTIVE_RELEASE.json` 指定；全新克隆不会自动取得它。

- [公开源码的运行及资料边界](PUBLISHING.md)
- [当前运行架构与整合边界](docs/architecture/CURRENT_RUNTIME_AND_INTEGRATION.md)
- [Agno 运行结构图](docs/architecture/agno-runtime-audit-20261019-v2.html)
- [面向评审的固定演示链接与发布前后检查](docs/operations/DEMO_LINK_CONTRACT.md)

正式版本的运行说明、真实浏览器和模型验收、文件哈希与独立复核资料保存在原验收主机的 `docs/delivery/unified-release-20261019-r1/`，本公开源码仓库不包含该目录。不能用这些历史记录直接证明本次 GitHub 提交已通过相同验收。

本项目面向伦敦办公地产市场的证据查询、AI 分析、报告与监测。技术栈是 Agno 2.9.0 / AgentOS、FastAPI、SQLite、Next.js。当前市场数据仍有覆盖、口径和人工审核缺口；功能链路通过不等于市场结论全部满足发布或投资决策条件。

## 正式版本如何运行

Windows 的 `app/Start-London-Market.cmd`、`scripts/run.ps1`、`scripts/run-chat-models.ps1` 与兼容入口 `app/scripts/product-launch.ps1` 均使用正式发布指针。启动前验证清单哈希、冻结文件哈希和前端 BUILD_ID；验证失败就停止，不回退到工作目录或离线模板。`GET /api/market/release` 返回正在执行的源目录、版本哈希、构建 ID、运行模式和原生 Workflow ID；它本身不代表已经发生模型调用。

项目使用现有独立 Python 环境 `app/.venv` 与锁定依赖。正式前端依赖使用本机现有 `app/frontend/node_modules` 的 junction，运行数据库与原文位于 `app/data/product`。该交付目录是在当前 Windows 主机验证的发布版本，不是已验证可独立搬到另一台机器的安装包。不要直接修改其中的冻结源码或构建；修改后应建立并验收新的候选版本。

本轮已由 Codex 完成启动和验收，无需用户手动执行命令。维护时正式入口为：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\run.ps1
```

已占用端口会明确拒绝启动，不会终止未知进程。进程记录位于被 Git 忽略的 `app/data/personal-model-launch/processes.json`。

## 模型、个人连接与附件

后端读取 `LONDON_MODEL_CONFIG` 指定的受保护 JSON 文件；本机默认指向 Git 忽略的 `secrets/model.deepseek-acceptance-20261019.json`。配置字段为 `model`、`base_url`、`api_key`，此文件不能进入源码或提交。真实验收使用用户已授权的官方 DeepSeek 服务和 `deepseek-flash`；没有为验收扩购额度或使用未授权服务。

用户在页面的 Models & API keys 中管理个人连接；服务端按浏览器 owner 隔离并用 Windows DPAPI 保护保存的密钥，前端只得到掩码和连接元数据。真实生成请求从后端发出。上传 PDF、TXT、Markdown、CSV 也按 owner 隔离，保留原件，仅把有界文本片段加入用户选择模型的请求；上传不改变事实的审核状态。

正式启动关闭 Scheduler、自动监测分析、外部通知与付费搜索。监测与通知能力的历史工程/本机测试结果不应被解释为本版本已向外部收件人投递成功。

## Agent、Workflow、Skill 的运行证据

普通 AI 问答执行真实 Agno Agent；模型先调用 `load_market_skills` 按需加载，再调用 `search_market_evidence`。Skill 的源文件/引用哈希、SDK 实际读取记录、操作约束投影与工具次序均保留在验收目录中。未加载或不匹配的 Skill 会被检索门禁拦截。

保存查询的范围和报告上下文、后台研究、周期报告使用真正的 Agno Workflow 并持久化 Run 与步骤。验收将浏览器中的提交、业务 Job、原生 Agent/Workflow Run、Provider 响应 ID 和 usage 逐一关联；写有 Skill 文档、工程测试通过或 HTTP 健康不单独算真实模型成功。

## 数据与结论边界

报告保留地域、统计期、指标定义、单位、原始引用、审核状态和缺口。题目提供的数值不能冒充独立来源核验；不同发布机构和指标口径不能自动合并。当前正式数据库不能独立证明 West End Q1 2026 的 6.8%，因此不得宣称已完成 6.8%→6.7% 的历史变化核验。Canary Wharf 2026 年 10 月的缺失数据也不应用其他子市场替代。

较早的 `chat-models-*`、`skill-runtime-*` 和 `reports/` 验收材料属于历史版本，不能覆盖当前正式指针。离线兼容运行需显式 `scripts/run.ps1 -Offline`；Linux `scripts/run.sh` 也是历史离线入口，其结果不构成本正式版本的真实 AI 验收。兼容旧 `app/scripts/product-launch.ps1 -Legacy` 保留供历史诊断使用。
