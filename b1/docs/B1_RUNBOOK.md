# B1 本地运行与复核手册

本手册对应 Windows 项目 `D:\deepinsight-lite` 和 WSL `/mnt/d/deepinsight-lite`。B1 当前可运行，正式业务结论 **BLOCKED**。不要将租金单位、原始评测或人工签收的缺口理解为已解决。只运行B1，不启动B2监测/定时/推送。

## 版本、配置与文件

- 后端：Windows Python3.12.10、Agno/AgentOS2.9.0，独立环境 `D:\deepinsight-lite\app\.venv`。
- 精确依赖：`app/requirements.lock.txt`，65项。`app/config.example.json` 只有路径/保护线说明，无密钥。
- 现有授权模型配置：`D:\deepinsight-lite\secrets\model.json`，由代码只读加载。不复制到前端、日志或文档；没有新建、修改或替换该密钥。服务返回模型名是relay观测身份，底层模型来源未独立验证。
- 原版 Agent UI：`upstream/agent-ui`，冻结 `6dad9593fca6756e1813e4f4b3b2620be6377691`；pnpm10.34.5、Next/Turbopack沿用上游锁定环境。未修改官方tracked源码。
- 领域数据库：`b1/data/market.db`；原生会话/运行数据库：`b1/data/agno.db`。SQLite WAL开启；迁移 `app/migrations/001_initial.sql`，初始化采用幂等建表与schema_versions=1。
- 逻辑表：sources、documents、attempts、observations、comparisons；各有稳定id、唯一identity和JSON payload。文档bytes/hash与URL别名独立于attempt；尝试、观察修订与比较冻结输入分别保留。
- 原件 `b1/data/raw/`、内容寻址快照 `b1/data/snapshots/`、评测 `b1/evidence/evaluations/`、模型原始记录 `b1/evidence/extractions/`。冻结评测目录不可用新运行覆盖。
- 权威的设计与30项AC仍位于 `docs/superpowers/specs/`；本地OpenSpec change位于 `app/openspec/changes/b1-market-data-foundation/`。

## 已实际验证的安装和静态/测试检查

以下是 PowerShell 命令。现有 `.venv` 已建立并安装，重跑sync不升级锁定版本；若在全新副本缺环境时，可先执行 `py -3.12 -m venv .venv`，本机已建立环境的建环境动作使用uv执行，不能把这个备用命令误称为本轮另做了一次干净安装。

```powershell
Set-Location -LiteralPath 'D:\deepinsight-lite\app'
uv pip sync --python .venv/Scripts/python.exe requirements.lock.txt
uv pip check --python .venv/Scripts/python.exe
.venv/Scripts/python.exe -m compileall -q london_data scripts tests
.venv/Scripts/python.exe -m pytest -q --junitxml=../b1/evidence/tests/junit.xml
openspec validate b1-market-data-foundation --strict
```

一键执行同一组检查（另含只读CLI及边界检查）：

```powershell
Set-Location -LiteralPath 'D:\deepinsight-lite'
& app/scripts/verify-local.ps1
```

实际命令、时间、退出码及日志：`b1/evidence/tests/command-results.json`。没有安装或执行未存在的mypy/lint脚本，不将compileall当类型检查或业务验收。测试包含明确标注的构造故障，不把这些样例当真实市场数据。

## 启动后端

```powershell
Set-Location -LiteralPath 'D:\deepinsight-lite'
& app/scripts/start-runtime.ps1
Invoke-RestMethod -Uri 'http://127.0.0.1:7778/health'
```

start脚本是非阻塞启动，刚返回时可能尚未health ready；实际服务通常几秒内ready，可检查 `b1/evidence/logs/runtime-*.err.log`。若7778被占用，脚本拒绝重复启动，应先核对占用进程，不随意杀掉其他服务。B0使用的7777不是B1目标。

前台诊断入口（不要与已启动服务并行占用7778）：

```powershell
Set-Location -LiteralPath 'D:\deepinsight-lite\app'
.venv/Scripts/python.exe -m london_data.runtime
```

后端只监听127.0.0.1:7778，CORS仅本地3100，B1 scheduler=False。没有公网认证、TLS或容器部署验收。

## 启动原版UI

从 Windows PowerShell：

```powershell
wsl.exe bash /mnt/d/deepinsight-lite/app/scripts/start-ui.sh
```

等价WSL入口：

```bash
bash /mnt/d/deepinsight-lite/app/scripts/start-ui.sh
```

脚本检查冻结HEAD/3100占用，使用已存在的Node24路径和 `npm exec --yes --package=pnpm@10.34.5 -- pnpm dev --turbopack --port 3100`，后台日志写 `b1/evidence/logs/`。本机首次请求曾触发SWC WASM回退/编译，用时约34秒；启动日志保留警告。后续已真实200和浏览器验证。不要改用B0启动脚本，否则可能向B0日志继续追加；也不要升级pnpm、修改upstream或用默认Webpack路径替换。

浏览器入口：[Agent UI](http://localhost:3100/)。AgentOS endpoint选 `http://localhost:7778`，MODE为AGENT，选择 **London Data Agent**。使用本地默认无token；没有把relay key填入Auth Token。

已验证会话：[最终B1查询会话](http://localhost:3100/?db_id=b1-runtime&agent=london-data-agent&session=b22caacc-8577-46a0-a550-ffc478026005)。可问：

> Show the saved Q1 and Q2 2026 indicators, all three comparison records, source URLs and page numbers.

固定真实结果查询：

> Retrieve exact comparison ID 7e7ab7a7-9c6c-4de8-a6e6-56a3a20fb09e with its frozen inputs, source pages and formulas.

查询只读；租金应为needs_review/not_comparable/变化N/A，不能因自然语言要求而强行计算。`validated`仅表示自动规则检查；人工金标准保持pending_review。原版表格有水平滚动条，可向右查看完整证据ID；没有为B1改造UI。

## 显式真实导入与重复导入

该命令会真实抓取登记URL；相同内容和配置已有成功attempt时复用，不额外抽取。内容、模型、Skill、schema、解析/校验器或profile身份变化可能产生新的真实模型调用。不要在未理解变更时批量重跑。

```powershell
Set-Location -LiteralPath 'D:\deepinsight-lite\app'
.venv/Scripts/python.exe -m london_data.cli sources
.venv/Scripts/python.exe -m london_data.cli ingest --document bnp-q1-2026
.venv/Scripts/python.exe -m london_data.cli ingest --document bnp-q2-2026
.venv/Scripts/python.exe -m london_data.cli query
```

原生AgentOS HTTP接口已真实验证，参数 `message`是JSON字符串，`stream=false`：

```powershell
Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:7778/workflows/london-foundation/runs' -ContentType 'application/x-www-form-urlencoded' -Body @{ message='{"document_key":"bnp-q2-2026"}'; stream='false' }
```

该等价PowerShell POST示例来自实际已验证的httpx表单；本轮直接执行的HTTP测试命令是：

```powershell
.venv/Scripts/python.exe scripts/verify_live.py --execute-real-models
```

脚本运行Q1、Q2、重复Q2与未登记输入负例，保存独立时间目录。不要把真实未登记输入500视为服务崩溃；这是负例，正常请求必须同时检查7个step success及结果内容。7步依次为Fetch、Parse、Extract、Validate、Persist、Compare、Export；Step设置max_retries=0/on_error=fail，不容忍静默跳过。

核心非缓存真实Workflow与Extract IDs见验收报告。CLI与API均持久化native run；domain attempt还保存workflow_run_id/extraction run_id；缓存复用的抽取Run保持原ID，当前Workflow Run另保存在导出包。

## 评测、故障与人工复核

确定性零模型重放（不能用来改写原始失败）：

```powershell
.venv/Scripts/python.exe scripts/replay_evaluation.py frozen-03
.venv/Scripts/python.exe scripts/build_review_pack.py
.venv/Scripts/python.exe scripts/verify_delivery.py
```

`scripts/evaluate.py --execute-real-models --label NEW_UNIQUE_LABEL`会进行12次真实抽取并消耗已授权模型额度；本轮已执行frozen-01/02/03，不能覆盖这些label。当前4份资料已经暴露，不能把重新执行称作新版本未见留出；正式重验应等待人工金标准签收、版本冻结及新的留出资料。单执行保护线为4个provider请求、60k输入、8k输出、180秒请求、480秒文档、40页/12MiB。超限失败保留，不无限重试。费用缺账单为N/A。

注入/断写/慢流/私网等故障样例使用独立临时数据库与明确的synthetic标记。`scripts/real_fault_probe.py`会再发真实模型请求，本轮已有PASS凭据，不需为了复核截图重复消耗调用。

人工集中复核先读 `B1_HUMAN_REVIEW_CHECKLIST.md`，详细原文见 `FACT_REVIEW.md`；逐ID结论写入单独审阅回执，不覆盖冻结gold/raw模型文件。租金年度定义未确认时，即使数值抄录签收也不放行比较。显式配置重处理产生新attempt，失败attempt不可改写为成功；来源冲突会使当前事实待审并失效旧current比较，历史comparison ID仍可查询。

最新审阅包在 `b1/outputs/latest/`，JSON/Markdown/manifest可离线复核，原件仍位于raw和snapshots。不要向公网分发有许可限制的原件。

## 停止和恢复

```powershell
Set-Location -LiteralPath 'D:\deepinsight-lite'
& app/scripts/stop-runtime.ps1
wsl.exe bash /mnt/d/deepinsight-lite/app/scripts/stop-ui.sh
```

停止脚本检查归属，只终止B1记录的runtime和精确UI目录对应的进程。启动与停止已多次实测；重启后不删除SQLite/WAL/snapshots。不要复制正在写入的db文件作为一致备份；使用SQLite backup或停止服务后一并处理数据库与WAL。交付时一致备份和hash见 `b1/delivery/` 与证据清单。

预期未解决：G0租金时间单位、负责人金标准签收、原始留出评测门槛。技术细节与每项AC的PASS/FAIL/BLOCKED详见B1_TEST_REPORT.md和B1_ACCEPTANCE_REPORT.md。B2业务未启动。
