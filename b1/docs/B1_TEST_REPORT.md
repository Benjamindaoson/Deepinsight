# B1 技术测试报告

最终确定性测试：**73 tests，failures=0，errors=0，skipped=0**。证据：b1/evidence/tests/junit.xml 和 pytest.log。
工程可运行与业务正式通过分开：B1整体BLOCKED。

## 实际环境与命令

Windows Python3.12.10，app/.venv；Agno/AgentOS2.9.0；SQLAlchemy/SQLite；原版UI冻结6dad9593fca6756e1813e4f4b3b2620be6377691。65个依赖精确锁于 app/requirements.lock.txt；没有全局安装项目包。

| 命令（cwd app） | 实际退出码 | 日志 |
|---|---:|---|
| `uv pip sync --python .venv/Scripts/python.exe requirements.lock.txt` | 0 | D:\deepinsight-lite\b1\evidence\tests\locked-environment.log |
| `uv pip check --python .venv/Scripts/python.exe` | 0 | D:\deepinsight-lite\b1\evidence\tests\dependency-compatibility.log |
| `.venv/Scripts/python.exe -m compileall -q london_data scripts tests` | 0 | D:\deepinsight-lite\b1\evidence\tests\compile.log |
| `.venv/Scripts/python.exe -m pytest -q --junitxml=../b1/evidence/tests/junit.xml` | 0 | D:\deepinsight-lite\b1\evidence\tests\pytest.log |
| `openspec validate b1-market-data-foundation --strict` | 0 | D:\deepinsight-lite\b1\evidence\tests\openspec.log |
| `.venv/Scripts/python.exe -m london_data.cli query` | 0 | D:\deepinsight-lite\b1\evidence\tests\cli-query.log |
| `.venv/Scripts/python.exe scripts/verify_delivery.py` | 0 | D:\deepinsight-lite\b1\evidence\tests\boundaries.log |

## 真实端到端路径

AgentOS POST /workflows/london-foundation/runs：Q1原生Run b1ef27f7-69a2-407a-8665-4983cf5aa522，22.443秒；Q2 cd0ec03e-1f91-4114-82ea-dcec3e168f9f，25.702秒；各7步success。重复Q2 Run8293eff7-fa50-4a6e-a84f-64f34efd92d6，4.671秒，cached=true，新增attempt0。以上为本机观测，不是SLA或只选择最快一次。其他探测和失败记录保留。
原生Extract Run：Q1 8839c7b3-1034-4fe2-a627-a355d32e3146；Q2 35190dfa-b179-439f-922c-a8711e05e493。Extract实际加载get_skill_instructions，RawExtraction结构化候选与deterministic precision独立保存。
业务当前6条候选、4条自动validated、2条rent needs_review；历史修订另外保留。Compare返回2个comparable、1个not_comparable。

## 正常、异常与恢复覆盖

- Fetch/Parse：真HTML/PDF；明确host/path/公网IP重定向约束；超时、大小、内容类型、坏PDF、扫描/空页、私网/file/DNS故障。
- Extract/Validate：真实模型成功、真实schema失败、原始处理失败、失真/缺值/错引用/错指标/错季度/YTD、未知单位、文档指令扰动。
- Compare：逐个口径差异拒收、连续季度方向、面积换算、零基数、pp与四舍五入；真实源差异不由模型覆盖。
- Persist：实际临时SQLite写中断rollback、失败attempt可见、重试/幂等、冲突降级、历史比较固定ID恢复；生产库与Agno库分离。
- Runtime/UI：真HTTP与浏览器；固定ID结果、刷新、实际服务重启前后逻辑状态相等；未靠重新LLM生成恢复。

## 原始评测与处理修复

| 冻结批次 | 四份真实资料各3次 | 首次流程逐次达标 | 修复后结果 |
|---|---|---:|---|
| frozen-01 | 12次 | 5/12 | 失败保留，未改记 |
| frozen-02 | 12次 | 11/12 | 1次披露精度错误保留 |
| frozen-03 | 12次 | 3/12 | 相同12份原始响应经确定性修复重放12/12；0次新增模型调用 |

frozen03每次修复重放Precision=1.0、Recall=1.0，评分记录含各字段/引用核对与原始文件hash。precision来自原文数值字面量，不由人工修改预测值。首次失败依旧失败；不能据此声称当前未见留出原始端到端达标。金标准初标由Codex完成，指定人工负责人未签收。

## 预算与费用

已保存抽取执行48份、provider请求95次，报告输入tokens291693、输出tokens70948，处理失败记录12份；每执行请求≤4。统计不含UI查询，UI调用在Agno原生history中另存，未作为零成本。费用 **N/A**，没有账单验证，不能将token换算为已支付费用。完整逐次账目 b1/evidence/g0/extraction-usage-summary.json。
失败请求usage无法取得时为null，并用保守估算占预算；不记录敏感异常正文。调用方绝对deadline有阻塞/慢流回归，但远端是否停止计费不可证明。

## 审阅修复记录

独立只读审阅提出5项Important：证据错绑、陈旧比较、固定ID查询缺失、失败账目、总deadline。均有RED→GREEN回归与实际集成验证；另修复解析/校验版本缓存身份。后续真实QA还修复原生错误策略、UI工具选择及Windows CLI编码。未把独立审阅的49个受限只读测试当成本轮完整确定性测试。
完整验收逐项见 B1_ACCEPTANCE_REPORT.md；人工清单与源资格分别交付；本报告不代签数据或声称生产可靠性。