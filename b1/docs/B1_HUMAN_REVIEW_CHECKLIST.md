# B1 人工复核清单

最终审阅者：项目负责人本人。全部 **pending_review**；此清单不是签收证明。技术已通过的validated仅指自动规则，人工结论独立记录于 b1/data/manual-review-queue.json。

## 先核查六条核心事实

两份原件：b1/data/raw/bnp-q1-2026.pdf、bnp-q2-2026.pdf；原件hash及发布时间见G0报告。下列摘录均定位PDF第3页；逐字完整引用、页内偏移和补充4份资料共12项见FACT_REVIEW.md。

| 事实 / 地域 / 时期 | 原文摘录 | 原值与规范化 | 自动状态 / 人工状态 |
|---|---|---|---|
| rent / City / 2026Q1 | Prime rents in the City also increased 8.8%, to £92.50 per sq ft. | 92.50 → 92.5 GBP/sqft/unknown；披露增量0.01 | needs_review / pending_review；ID b53980e0-8e19-4d29-ae7c-892848114523 |
| vacancy / Central London / 2026Q1 | Central London office vacancy stood at 8.4% as of Q1 2026, falling below the five-year average of 10.6%. | 8.4 → 8.4 percent；披露增量0.1 | validated / pending_review；ID c9db689e-1978-4075-b31f-bbdc7f53c450 |
| takeup / Central London / 2026Q1 | Central London office take-up reached 2.5m sq ft in Q1 2026, a y-o-y decline of 19.7%. *Take-up figures based on all deals over 1,000 sq ft. | 2.5m → 2500000 sqft；披露增量100000 | validated / pending_review；ID 27df0770-84ef-4f97-966a-7a3dca656796 |
| rent / City / 2026Q2 | Prime rents in the City increased at a greater rate of 8.6%, to £95 per sq ft. | 95 → 95 GBP/sqft/unknown；披露增量1 | needs_review / pending_review；ID 5cc5b049-cabd-468b-95ed-6c092c5d984a |
| vacancy / Central London / 2026Q2 | Central London office vacancy stood at 8.4% as of Q2 2026, well below the five-year average of 10.4%. | 8.4 → 8.4 percent；披露增量0.1 | validated / pending_review；ID 46ca9a00-8f30-4fc5-a403-44a59a3bf56d |
| takeup / Central London / 2026Q2 | Central London office take-up reached 3.0m sq ft in Q2 2026, a y-o-y increase of 26.0%, and bringing H1 levels to 5.5m sq ft. | 3.0m → 3000000 sqft；披露增量100000 | validated / pending_review；ID 296f1397-034d-4832-aea2-c9a26d7e5709 |

## 三个比较判定

| 指标 | 冻结输入 | 兼容性 / 公式 / 结果 | 人工动作 |
|---|---|---|---|
| rent | 92.5 → 95；2026Q1→2026Q2 | not_comparable；禁止计算：时间分母未确认；原因['NOT_VALIDATED', 'UNKNOWN_UNIT_BASIS'] | pending_review；结果ID 1eec43c3-0552-45ac-a132-854de6b56fa8 |
| vacancy | 8.4 → 8.4；2026Q1→2026Q2 | comparable；8.4 - 8.4 = 0.0 pp；这是披露端点差；原因[] | pending_review；结果ID 4f4e606c-04a5-4b4b-8dd5-181ebfbc7796 |
| takeup | 2500000 → 3000000；2026Q1→2026Q2 | comparable；3000000 - 2500000 = 500000 sqft；500000 / 2500000 × 100 = 20.00%；原因[] | pending_review；结果ID 7e7ab7a7-9c6c-4de8-a6e6-56a3a20fb09e |

## 四份资料的12个机会

| 文件 | 目标值（rent / vacancy / take-up） | 位置和审阅重点 |
|---|---|---|
| BNP Q1 2026 PDF | 92.50 / 8.4% / 2.5m sqft | p3；City prime与Central London overall分开；rent无时间分母 |
| BNP Q2 2026 PDF | 95 / 8.4% / 3.0m sqft | p3；H1 5.5m不可替Q2；26%叙述差异 |
| BNP Q3 2024 HTML | 82.50 / 10.1% / c.2.75m sqft | FACT_REVIEW列出HTML segment；vacancy段继承明确报表标题地域；约数标记不抹去 |
| BNP Q4 2024 PDF | 82.50 / 9.71% / 3.05m sqft | p1完整Key Stats；不能改用HTML的9.7%、3.1m舍入值 |

## 集中确认项

1. 确认摘录、数值、地域、期间、物业类型/定义与各自原件相符；不满意项逐条指出观察ID。
2. 租金年度单位仍无足够官方依据，维持needs_review，不计算变化率；签收数值本身不会放行该单位。
3. 确认take-up相同>1000sqft门槛、vacancy整体市场及披露精度；未披露的底层样本修订不得推断。
4. 确认采用披露端点结果，并接受将26%、2bps等出版物叙述差异单列，而非强行改数。
5. Q3/Q4 2024曾在冻结03作为留出，但执行后已暴露并参与确定性修复诊断；不得把本次签收当成新版本未见留出通过。
6. 请明确签收哪些事实/判定，或给出逐项问题。未经你确认，gold和人工队列保持pending_review。