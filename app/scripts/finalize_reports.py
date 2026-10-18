"""Build evidence-linked reports. Hard gates remain BLOCKED/FAIL, never inferred PASS."""
import json,sys,hashlib,xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime,timezone
from collections import Counter
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from london_data.extraction import ROOT
from london_data.pipeline import repository

repo=repository();docs=repo.all('documents');facts=[o for o in repo.observations(True) if o['status']!='superseded'];comparisons=repo.current_comparisons()
tests=ET.parse(ROOT/'b1/evidence/tests/junit.xml').getroot().find('testsuite').attrib
commands=json.loads((ROOT/'b1/evidence/tests/command-results.json').read_text(encoding='utf-8-sig'))
usage=json.loads((ROOT/'b1/evidence/g0/extraction-usage-summary.json').read_text(encoding='utf8'))
stamp=datetime.now(timezone.utc).isoformat()
entries=[
('01','BLOCKED','数据源资格','两期真报告、三个数值族均已定位；City rent 缺少官方时间分母。备选未获完整资格，未换源。','b1/docs/G0_SOURCE_QUALIFICATION_REPORT.md'),
('02','PASS','真实获取与快照','主PDF与真实HTML均保存原件/hash/发布时间/采集时间/分段；实际 Fetch→Parse 已运行。','b1/evidence/g0/source-qualification-details.json; b1/data/source-registry.json'),
('03','BLOCKED','六条完整事实','当前6条候选、4条自动 validated、2条租金 needs_review；全部 pending_review，尚不能签6条正式正确事实。','b1/data/fact-review-provisional.json; b1/docs/FACT_REVIEW.md'),
('04','PASS','原文可定位','六条核心候选逐字引用匹配本地PDF第3页；页内规范化偏移、sha保留；错绑和错期负例拒收。','b1/docs/FACT_REVIEW.md; b1/evidence/tests/junit.xml; b1/evidence/source-pages/'),
('05','PASS','原生Extract','真实Agent run、get_skill_instructions、结构化原始输出、配置hash、独立derived输出和provider账目已保存。','b1/evidence/extractions/; b1/evidence/api/live-20261017-192745/live-1.json'),
('06','BLOCKED','持久化与查询','过滤/状态/稳定ID功能与数据库验证通过；Given要求的6条经过完整核验的事实仍未满足。','app/london_data/store.py; app/london_data/runtime.py; b1/evidence/tests/junit.xml'),
('07','BLOCKED','三组真实比较','空置率0.0pp；take-up +500000 sqft、20%；租金 not_comparable，禁止计算真实变化率。','b1/outputs/latest/result.json'),
('08','BLOCKED','完整结果包','JSON/Markdown/hash/本地原文与Run关联已导出，但要求完整3组可比结果的业务前提不足。','b1/outputs/latest/result.json; b1/outputs/latest/result.md; b1/outputs/latest/manifest.json'),
('09','PASS','缺失值','null不补0；缺值/未知口径拒绝比较并保留原因，构造负例明确标记。','app/tests/test_foundation.py::test_validation_requires_exact_value_and_unit_and_location'),
('10','PASS','单位和归属歧义','真实租金未知时间分母进入 needs_review；错指标、错季度、YTD及长引用错绑均拒收。','app/tests/test_review_regressions.py; b1/outputs/latest/result.json'),
('11','PASS','不兼容口径','来源/系列/地域/定义/方法/档次/币种/基础/状态/单位独立负例均not_comparable且变化为空。','app/tests/test_foundation.py::test_incompatible_dimensions_fail_closed'),
('12','PASS','时期边界','同季、倒序、跨季缺口、未知期间均拒绝，不交换输入。','app/tests/test_foundation.py::test_quarter_direction_and_continuity'),
('13','PASS','单位转换和零基数','冻结 sqm→sqft 常量；保留原值/公式/转换；旧值0相对为空且ZERO_BASE。','app/tests/test_foundation.py::test_unit_conversion_and_unknown_rejected; test_compare_rent_and_pp_and_zero'),
('14','PASS','重复导入','真实API第3次导入cached=true、新attempt=0；同内容别名URL在独立SQLite测试复用document ID。','b1/evidence/api/live-20261017-192745/live-3.json; b1/evidence/g0/live-verified.log'),
('15','PASS','冲突和历史','真实SQLite构造新内容冲突保留两版；旧比较不再作为current，重新判定not_comparable；历史ID仍恢复原输入。','app/tests/test_review_regressions.py::test_conflict_invalidates_current_comparison_but_keeps_history'),
('16','PASS','配置版本','新配置生成attempt/观察修订，旧原始输出保留；配置hash包括Skill/schema/模型ID/profile/抽取/解析/校验/deadline源码。','app/tests/test_boundaries.py::test_reprocessing_keeps_only_one_current_validated_fact; b1/evidence/extractions/'),
('17','PASS','下载解析失败','网络超时/类型/大小/损坏/扫描PDF构造故障拒收；实际未登记文档API失败、CLI非零、原生失败历史保留。','app/tests/test_boundaries.py; app/tests/test_foundation.py; b1/evidence/api/live-20261017-192745/live-invalid-workflow.json; b1/evidence/g0/cli-negative.log'),
('18','PASS','非法模型输出','首次真实schema错误与本地处理失败保留；错数/错引用/schema不符拒收；原始文件未改写为成功。','b1/evidence/extractions/g0-structured-probe-02.json; app/tests/test_review_regressions.py; b1/evidence/evaluations/'),
('19','PASS','预算和超时','provider调用/流式逐块计数；单请求180s、文档480s、4请求/60k输入/8k输出、40页。慢流、阻塞I/O、迟到输出、额度故障回归通过；原生Step零自动重试/失败即停。','app/tests/test_review_regressions.py; app/tests/test_boundaries.py; b1/evidence/g0/extraction-usage-summary.json'),
('20','PASS','指令隔离','真实模型处理公开报告文本扰动副本，改数/外传canary指令未执行，无额外写/外传工具；不是市场真实报告。','b1/evidence/g0/real-injection-result.json'),
('21','PASS','事务失败与恢复','实际SQLite注入首条写后中断，事务回滚；attempt失败含结束时间/错误类型，重试成功只1条有效事实。','app/tests/test_review_regressions.py::test_persist_failure_is_visible_after_rollback; app/tests/test_foundation.py::test_storage_idempotence_atomicity_and_recovery'),
('22','PASS','服务重启恢复','真实停止/启动后facts、comparisons、documents、native runs和浏览器会话逻辑内容均相等，恢复未调用模型。','b1/evidence/api/restart-shipped.json; b1/evidence/api/state-before-shipped-restart.json; b1/evidence/api/state-after-shipped-restart.json'),
('23','PASS','来源/密钥边界','HTTPS/host/path/DNS/redirect/私网/file负例拒绝；最终106个受保护文件与3个上游身份匹配；输出未检出实际relay key。B0日志追加事件有恢复收据。','b1/evidence/g0/final-boundary-check.json; b1/evidence/g0/b0-log-restoration-receipt.json'),
('24','PASS','三种时间','季度起止、发布时间和采集时间分开，未知不替代；UI明确历史事实与人工待审。','app/london_data/validation.py; b1/outputs/latest/result.json; b1/evidence/screenshots/'),
('25','PASS','百分点','明确构造8%→9%得到1pp，主变化无相对百分比；真实8.4→8.4端点结果0pp。','app/tests/test_foundation.py::test_compare_rent_and_pp_and_zero'),
('26','FAIL','原始评测门槛','三轮原流程分别5/12、11/12、3/12逐次达标；冻结03修复后零调用重放12/12。原流程门槛失败不能改写；已接触留出资料不再未见。人工gold仍pending_review。','b1/evidence/evaluations/frozen-01/results.json; b1/evidence/evaluations/frozen-02/results.json; b1/evidence/evaluations/frozen-03/results.json; b1/evidence/evaluations/frozen-03/replay-results.json'),
('27','PASS','原生Workflow','Agno2.9.0原生7步通过AgentOS真实运行，Q1/Q2均7步success；Run/attempt/产物可追溯；业务租金门禁依旧阻止正式闭环PASS。','b1/evidence/api/live-20261017-192745/live-1.json; b1/evidence/api/live-20261017-192745/live-2.json'),
('28','PASS','原版UI','实际浏览器London Data Agent读取6条候选/3个判定；固定take-up comparison ID返回两条冻结输入/来源/公式；刷新和服务重启恢复。失败查询另留截图。','b1/evidence/screenshots/; b1/evidence/api/browser-final.json'),
('29','PASS','调用和失败账目','成功/失败/重复实际执行均有记录；异常usage未知为空，使用估算占预算，安全错误类型；48个抽取执行记录计95个provider请求；货币费用N/A。UI调用另在原生history。','b1/evidence/g0/extraction-usage-summary.json; b1/evidence/g0/live-verified.log; b1/evidence/tests/junit.xml'),
('30','PASS','交付复现与范围','独立venv、65包精确锁；实际安装/检查/启动/停止/CLI/API/浏览器命令与证据；30项状态逐项披露，没有B2/UI改造/生产部署声明。','b1/evidence/tests/command-results.json; b1/docs/B1_RUNBOOK.md'),
]
results=[dict(id='AC-'+n,status=s,title=t,actual=a,evidence=e.split('; '),criterion_source='docs/superpowers/specs/2026-10-17-b1-market-data-foundation-acceptance.md#AC-'+n,input_identity={'artifact_manifest':'b1/delivery/manifest.json','registry_sha256':hashlib.sha256((ROOT/'b1/data/source-registry.json').read_bytes()).hexdigest(),'fixture_note':'Synthetic negative inputs are explicitly labelled in referenced test source; exact fixture/code hashes are in the manifest. Real source snapshots use the frozen registry and source qualification receipts.'},executor='Codex',reviewer='project owner (pending_review)',recorded_at=stamp) for n,s,t,a,e in entries]
counts=dict(Counter(r['status'] for r in results))
summary={'conclusion':'BLOCKED','recorded_at':stamp,'counts':counts,'human_review_status':'pending_review','final_reviewer':'project owner (user)','ac':results}
(ROOT/'b1/evidence/acceptance-results.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf8')
table=['| AC | 状态 | 实际结果 | 证据（相对项目根） |','|---|---|---|---|']+[f"| {r['id']} {r['title']} | **{r['status']}** | {r['actual']} | {'; '.join(r['evidence'])} |" for r in results]
report=['# B1 验收报告','','**最终结论：BLOCKED，不能宣称 B1 G0–G4 全部通过。**',f"记录时间：{stamp}。30项已逐项执行或按实际前提判定：{counts}。PASS表示该项已列的工程/行为证据成立，不覆盖其他业务硬门槛。",'执行者：Codex；最终人工审阅者：项目负责人本人；人工状态：pending_review。','',
'## 阶段结论','','| 阶段 | 状态 | 结果 |','|---|---|---|','| G0 | BLOCKED | 真源与格式已核查；租金年度分母缺官方依据；金标准未签收 |','| G1 | PASS（工程） | 契约、安全Fetch/Parse、快照及失败路径已测试 |','| G2 | PARTIAL | 原生真实抽取/存储可用，4条自动validated、2条租金待复核；原始评测门槛失败 |','| G3 | PARTIAL | 原生7步、只读UI、导出成功；只有2组真实可比结果 |','| G4 | BLOCKED | 确定性/浏览器/重启/交付检查已执行；业务门禁与人工签收尚缺 |','',
'已在源资格失败时保持业务阻断，后续开发结果属于用户授权的不依赖租金单位的工程验证，不表示 G0 曾正式放行。','',
'## 当前真实结果','','| 指标 | 地域 | Q1 2026 | Q2 2026 | 比较判断 |','|---|---|---:|---:|---|','| Prime rent | City | £92.50 /sqft，时间分母未知 | £95 /sqft，时间分母未知 | needs_review / not_comparable，变化为空 |','| Overall vacancy | Central London | 8.4% | 8.4% | 自动可比，0.0 pp；人工待审 |','| Quarterly take-up | Central London，deals >1000 sqft | 2,500,000 sqft | 3,000,000 sqft | 自动可比，+500,000 sqft，+20.00%；人工待审 |','',
'## AC-01–AC-30','','这些记录使用真实输出与明确构造故障样例分开计证。AC-03/06/07/08未借其他地域、时期或机构凑数。','']+table+['',
'## 必须保留的失败与边界','','- 原始评测5/12、11/12、3/12，不能用修复重放12/12覆盖。评测后的留出资料已暴露；下一次正式评测应在人工签收、新版本冻结后使用新的未见留出资料。','- 真实浏览器曾让一次Skill加载耗尽工具额度，未返回数据；已用原生tool_choice强制只读数据工具，并回归和真实重验。失败截图03保留。','- 原生Workflow曾因默认on_error=skip在步骤失败时仍COMPLETED；已设置on_error=fail、max_retries=0；实际异常API返回失败，CLI非零。','- B0旧UI自动追加105字节日志；追加内容另存B1，按执行前hash恢复原592字节。最终受保护hash一致；没有把这次事件隐藏成从未发生。','- 480s控制阻止调用方继续等待或发布迟到事实，并尽力关闭传输；不保证服务商已停止服务端计费。没有用本地超时证据承诺生产SLA。','- 原版UI的Images.tsx既有风险未在本阶段修改；本地7778无公网认证/部署验证，不作为生产安全通过。','- 未执行并发负载/跨机器/容器生产部署；冻结源码、B0证据与密钥的最终边界检查另有凭据。','',
'## 交接与下一次放行条件','','本次停止于B1，不进入B2。请集中查看 B1_HUMAN_REVIEW_CHECKLIST.md、FACT_REVIEW.md、G0_SOURCE_QUALIFICATION_REPORT.md 与 B1_PENDING_DECISIONS.md。人工签收不能代替租金单位证据，也不能将已失败的原始评测改记成功。获得有效来源依据/明确换源决定后，需显式版本化重处理，再补正式未见留出评测。']
(ROOT/'b1/docs/B1_ACCEPTANCE_REPORT.md').write_text('\n'.join(report),encoding='utf8')

technical=['# B1 技术测试报告','',f"最终确定性测试：**{tests['tests']} tests，failures={tests['failures']}，errors={tests['errors']}，skipped={tests['skipped']}**。证据：b1/evidence/tests/junit.xml 和 pytest.log。",'工程可运行与业务正式通过分开：B1整体BLOCKED。','',
'## 实际环境与命令','','Windows Python3.12.10，app/.venv；Agno/AgentOS2.9.0；SQLAlchemy/SQLite；原版UI冻结6dad9593fca6756e1813e4f4b3b2620be6377691。65个依赖精确锁于 app/requirements.lock.txt；没有全局安装项目包。','',
'| 命令（cwd app） | 实际退出码 | 日志 |','|---|---:|---|']+[f"| `{c['command']}` | {c['exit_code']} | {c['log']} |" for c in commands]+['',
'## 真实端到端路径','','AgentOS POST /workflows/london-foundation/runs：Q1原生Run b1ef27f7-69a2-407a-8665-4983cf5aa522，22.443秒；Q2 cd0ec03e-1f91-4114-82ea-dcec3e168f9f，25.702秒；各7步success。重复Q2 Run8293eff7-fa50-4a6e-a84f-64f34efd92d6，4.671秒，cached=true，新增attempt0。以上为本机观测，不是SLA或只选择最快一次。其他探测和失败记录保留。',
'原生Extract Run：Q1 8839c7b3-1034-4fe2-a627-a355d32e3146；Q2 35190dfa-b179-439f-922c-a8711e05e493。Extract实际加载get_skill_instructions，RawExtraction结构化候选与deterministic precision独立保存。','业务当前6条候选、4条自动validated、2条rent needs_review；历史修订另外保留。Compare返回2个comparable、1个not_comparable。','',
'## 正常、异常与恢复覆盖','','- Fetch/Parse：真HTML/PDF；明确host/path/公网IP重定向约束；超时、大小、内容类型、坏PDF、扫描/空页、私网/file/DNS故障。','- Extract/Validate：真实模型成功、真实schema失败、原始处理失败、失真/缺值/错引用/错指标/错季度/YTD、未知单位、文档指令扰动。','- Compare：逐个口径差异拒收、连续季度方向、面积换算、零基数、pp与四舍五入；真实源差异不由模型覆盖。','- Persist：实际临时SQLite写中断rollback、失败attempt可见、重试/幂等、冲突降级、历史比较固定ID恢复；生产库与Agno库分离。','- Runtime/UI：真HTTP与浏览器；固定ID结果、刷新、实际服务重启前后逻辑状态相等；未靠重新LLM生成恢复。','',
'## 原始评测与处理修复','','| 冻结批次 | 四份真实资料各3次 | 首次流程逐次达标 | 修复后结果 |','|---|---|---:|---|','| frozen-01 | 12次 | 5/12 | 失败保留，未改记 |','| frozen-02 | 12次 | 11/12 | 1次披露精度错误保留 |','| frozen-03 | 12次 | 3/12 | 相同12份原始响应经确定性修复重放12/12；0次新增模型调用 |','',
'frozen03每次修复重放Precision=1.0、Recall=1.0，评分记录含各字段/引用核对与原始文件hash。precision来自原文数值字面量，不由人工修改预测值。首次失败依旧失败；不能据此声称当前未见留出原始端到端达标。金标准初标由Codex完成，指定人工负责人未签收。','',
'## 预算与费用','','已保存抽取执行48份、provider请求95次，报告输入tokens291693、输出tokens70948，处理失败记录12份；每执行请求≤4。统计不含UI查询，UI调用在Agno原生history中另存，未作为零成本。费用 **N/A**，没有账单验证，不能将token换算为已支付费用。完整逐次账目 b1/evidence/g0/extraction-usage-summary.json。','失败请求usage无法取得时为null，并用保守估算占预算；不记录敏感异常正文。调用方绝对deadline有阻塞/慢流回归，但远端是否停止计费不可证明。','',
'## 审阅修复记录','','独立只读审阅提出5项Important：证据错绑、陈旧比较、固定ID查询缺失、失败账目、总deadline。均有RED→GREEN回归与实际集成验证；另修复解析/校验版本缓存身份。后续真实QA还修复原生错误策略、UI工具选择及Windows CLI编码。未把独立审阅的49个受限只读测试当成本轮完整确定性测试。','完整验收逐项见 B1_ACCEPTANCE_REPORT.md；人工清单与源资格分别交付；本报告不代签数据或声称生产可靠性。']
(ROOT/'b1/docs/B1_TEST_REPORT.md').write_text('\n'.join(technical),encoding='utf8')

queue={'review_status':'pending_review','reviewer':'project owner (user)','signed_at':None,'observations':{o['id']:{'status':'pending_review','automatic_validation':o['status']} for o in facts},'comparisons':{c['id']:{'status':'pending_review','automatic_comparability':c['status']} for c in comparisons},'frozen_gold_sha256':hashlib.sha256((ROOT/'b1/evidence/evaluations/frozen-03/gold-provisional.json').read_bytes()).hexdigest()}
(ROOT/'b1/data/manual-review-queue.json').write_text(json.dumps(queue,ensure_ascii=False,indent=2),encoding='utf8')
human=['# B1 人工复核清单','','最终审阅者：项目负责人本人。全部 **pending_review**；此清单不是签收证明。技术已通过的validated仅指自动规则，人工结论独立记录于 b1/data/manual-review-queue.json。','',
'## 先核查六条核心事实','','两份原件：b1/data/raw/bnp-q1-2026.pdf、bnp-q2-2026.pdf；原件hash及发布时间见G0报告。下列摘录均定位PDF第3页；逐字完整引用、页内偏移和补充4份资料共12项见FACT_REVIEW.md。','',
'| 事实 / 地域 / 时期 | 原文摘录 | 原值与规范化 | 自动状态 / 人工状态 |','|---|---|---|---|']
for o in facts:
    human.append(f"| {o['metric']} / {o['geography']} / {o['period']} | {o['evidence']['quote']} | {o.get('reported_number_literal',o['value'])} → {o['value']} {o['unit']}；披露增量{o['precision']} | {o['status']} / pending_review；ID {o['id']} |")
human+=['',
'## 三个比较判定','','| 指标 | 冻结输入 | 兼容性 / 公式 / 结果 | 人工动作 |','|---|---|---|---|']
for c in comparisons:
    formula='禁止计算：时间分母未确认' if c['status']!='comparable' else ('8.4 - 8.4 = 0.0 pp；这是披露端点差' if c['old']['metric']=='vacancy' else '3000000 - 2500000 = 500000 sqft；500000 / 2500000 × 100 = 20.00%')
    human.append(f"| {c['old']['metric']} | {c['old']['value']} → {c['new']['value']}；{c['old']['period']}→{c['new']['period']} | {c['status']}；{formula}；原因{c['reasons']} | pending_review；结果ID {c['id']} |")
human+=['',
'## 四份资料的12个机会','','| 文件 | 目标值（rent / vacancy / take-up） | 位置和审阅重点 |','|---|---|---|','| BNP Q1 2026 PDF | 92.50 / 8.4% / 2.5m sqft | p3；City prime与Central London overall分开；rent无时间分母 |','| BNP Q2 2026 PDF | 95 / 8.4% / 3.0m sqft | p3；H1 5.5m不可替Q2；26%叙述差异 |','| BNP Q3 2024 HTML | 82.50 / 10.1% / c.2.75m sqft | FACT_REVIEW列出HTML segment；vacancy段继承明确报表标题地域；约数标记不抹去 |','| BNP Q4 2024 PDF | 82.50 / 9.71% / 3.05m sqft | p1完整Key Stats；不能改用HTML的9.7%、3.1m舍入值 |','',
'## 集中确认项','','1. 确认摘录、数值、地域、期间、物业类型/定义与各自原件相符；不满意项逐条指出观察ID。','2. 租金年度单位仍无足够官方依据，维持needs_review，不计算变化率；签收数值本身不会放行该单位。','3. 确认take-up相同>1000sqft门槛、vacancy整体市场及披露精度；未披露的底层样本修订不得推断。','4. 确认采用披露端点结果，并接受将26%、2bps等出版物叙述差异单列，而非强行改数。','5. Q3/Q4 2024曾在冻结03作为留出，但执行后已暴露并参与确定性修复诊断；不得把本次签收当成新版本未见留出通过。','6. 请明确签收哪些事实/判定，或给出逐项问题。未经你确认，gold和人工队列保持pending_review。']
(ROOT/'b1/docs/B1_HUMAN_REVIEW_CHECKLIST.md').write_text('\n'.join(human),encoding='utf8')
print(json.dumps({'tests':tests,'counts':counts,'formal_acceptance':'BLOCKED','review_status':'pending_review'},ensure_ascii=False))
