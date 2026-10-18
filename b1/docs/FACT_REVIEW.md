# B1 事实复核工作表（待人工签收）

执行者：Codex。最终审阅者：项目负责人本人（用户已指定）。状态：pending_review，不能作为人工金标准已签收的证明。
数值来自本地官方快照；以下引用为逐字抽取定位和代码核对，尚未由项目负责人或指定人员签收。
本表不改变 gold-provisional.json，不修正模型原始候选；租金缺少时间分母。

## bnp-q1-2026

- 来源：https://www.realestate.bnpparibas.co.uk/sites/default/files/2026-05/Q12026CentralLondonMarketUpdate.pdf
- 本地原件：D:\deepinsight-lite\b1\data\raw\bnp-q1-2026.pdf
- SHA-256：8255a921c15294718433e5a893e6616593ab730904de4be452ba74d0c27bde7c
- 发布：2026-05-18；季度：2026Q1；用途：development（执行后已暴露，不能再作为新版未见留出集）

### rent / City
值：92.5；单位：GBP/sqft/unknown；披露增量：0.01；状态：needs_review
定义：prime_office_rent；物业档次：prime；统计方法标识：BNP-UK-prime-office-v1；期间基础：quarter_end
位置：p3，页 3，规范化文本偏移 806
> Prime rents in the City also increased 8.8%, to £92.50 per sq ft.
校验说明：['UNKNOWN_RENT_TIME_BASIS', 'NO_ANNUAL_UNIT_EVIDENCE']
人工结论：待填写；审阅者：待填写；签收时间：待填写。

### vacancy / Central London
值：8.4；单位：percent；披露增量：0.1；状态：validated
定义：overall_office_vacancy；物业档次：all；统计方法标识：BNP-UK-overall-vacancy-v1；期间基础：quarter_end
位置：p3，页 3，规范化文本偏移 443
> Central London office vacancy stood at 8.4% as of Q1 2026, falling below the five-year average of 10.6%.
校验说明：[]
人工结论：待填写；审阅者：待填写；签收时间：待填写。

### takeup / Central London
值：2500000；单位：sqft；披露增量：100000；状态：validated
定义：quarterly_office_takeup；物业档次：all；统计方法标识：BNP-UK-deals-over-1000sqft-v1；期间基础：quarter
位置：p3，页 3，规范化文本偏移 302
> Central London office take-up reached 2.5m sq ft in Q1 2026, a y-o-y decline of 19.7%.
校验说明：[]
人工结论：待填写；审阅者：待填写；签收时间：待填写。

## bnp-q2-2026

- 来源：https://www.realestate.bnpparibas.co.uk/sites/default/files/2026-08/Q22026CentralLondonMarketUpdate.pdf
- 本地原件：D:\deepinsight-lite\b1\data\raw\bnp-q2-2026.pdf
- SHA-256：3dd8de05ccb26ce235dfc8f9cf96d47bb2f760196d56cfcc94b0dc2a2a2016cd
- 发布：2026-08-05；季度：2026Q2；用途：development（执行后已暴露，不能再作为新版未见留出集）

### rent / City
值：95；单位：GBP/sqft/unknown；披露增量：1；状态：needs_review
定义：prime_office_rent；物业档次：prime；统计方法标识：BNP-UK-prime-office-v1；期间基础：quarter_end
位置：p3，页 3，规范化文本偏移 796
> Prime rents in the City increased at a greater rate of 8.6%, to £95 per sq ft.
校验说明：['UNKNOWN_RENT_TIME_BASIS', 'NO_ANNUAL_UNIT_EVIDENCE']
人工结论：待填写；审阅者：待填写；签收时间：待填写。

### vacancy / Central London
值：8.4；单位：percent；披露增量：0.1；状态：validated
定义：overall_office_vacancy；物业档次：all；统计方法标识：BNP-UK-overall-vacancy-v1；期间基础：quarter_end
位置：p3，页 3，规范化文本偏移 472
> Central London office vacancy stood at 8.4% as of Q2 2026, well below the five-year average of 10.4%.
校验说明：[]
人工结论：待填写；审阅者：待填写；签收时间：待填写。

### takeup / Central London
值：3000000；单位：sqft；披露增量：100000；状态：validated
定义：quarterly_office_takeup；物业档次：all；统计方法标识：BNP-UK-deals-over-1000sqft-v1；期间基础：quarter
位置：p3，页 3，规范化文本偏移 292
> Central London office take-up reached 3.0m sq ft in Q2 2026, a y-o-y increase of 26.0%, and bringing H1 levels to 5.5m sq ft.
校验说明：[]
人工结论：待填写；审阅者：待填写；签收时间：待填写。

## bnp-q3-2024

- 来源：https://www.realestate.bnpparibas.co.uk/insights/central-london-office-market-update-q3-2024
- 本地原件：D:\deepinsight-lite\b1\data\raw\bnp-q3-2024.html
- SHA-256：1e01b3e3dc432673a516b38b34b6bed6c4f60c33286885b10d031117de6a63e8
- 发布：2024-10-29；季度：2024Q3；用途：heldout（执行后已暴露，不能再作为新版未见留出集）

### rent / City
值：82.5；单位：GBP/sqft/unknown；披露增量：0.01；状态：needs_review
定义：prime_office_rent；物业档次：prime；统计方法标识：BNP-UK-prime-office-v1；期间基础：quarter_end
位置：html-10，页 None，规范化文本偏移 0
> Prime rents remain at record highs, with the City increasing to £82.50, an annual increase of 13.8%, and the West End staying at £160 psf, an annual growth rate of 6.7%.
校验说明：['UNKNOWN_RENT_TIME_BASIS', 'NO_ANNUAL_UNIT_EVIDENCE']
人工结论：待填写；审阅者：待填写；签收时间：待填写。

### vacancy / Central London
值：10.1；单位：percent；披露增量：0.1；状态：validated
定义：overall_office_vacancy；物业档次：all；统计方法标识：BNP-UK-overall-vacancy-v1；期间基础：quarter_end
位置：html-11，页 None，规范化文本偏移 0
> Available office supply reached 28.06m sq ft at the close of Q3 2024 which is notably above the five-year average of 27.20m sq ft. Vacancy in Q3 2024 was 10.1%, increasing the gap between the ten-year average of 9.0%.
校验说明：[]
人工结论：待填写；审阅者：待填写；签收时间：待填写。

### takeup / Central London
值：2750000；单位：sqft；披露增量：10000；状态：validated
定义：quarterly_office_takeup；物业档次：all；统计方法标识：BNP-UK-deals-over-1000sqft-v1；期间基础：quarter
位置：html-8，页 None，规范化文本偏移 0
> Take-up in Central London totalled c.2.75m sq ft in Q3 2024, an increase of 13.9% quarter-on-quarter, and remaining above the five-year quarterly average of 2.56m sq ft.
校验说明：[]
人工结论：待填写；审阅者：待填写；签收时间：待填写。

## bnp-q4-2024

- 来源：https://www.realestate.bnpparibas.co.uk/sites/default/files/2025-02/CentralLondonMarketUpdateQ42024.pdf
- 本地原件：D:\deepinsight-lite\b1\data\raw\bnp-q4-2024.pdf
- SHA-256：e0fcf257260ef88b6d5f882c8c1b1ce42eaf1b0c68cb422291ca5c020bd5ef80
- 发布：2025-02-13；季度：2024Q4；用途：heldout（执行后已暴露，不能再作为新版未见留出集）

### rent / City
值：82.5；单位：GBP/sqft/unknown；披露增量：0.01；状态：needs_review
定义：prime_office_rent；物业档次：prime；统计方法标识：BNP-UK-prime-office-v1；期间基础：quarter_end
位置：p1，页 1，规范化文本偏移 1603
> Prime rents in the City hit £82.50 per sq ft
校验说明：['UNKNOWN_RENT_TIME_BASIS', 'NO_ANNUAL_UNIT_EVIDENCE']
人工结论：待填写；审阅者：待填写；签收时间：待填写。

### vacancy / Central London
值：9.71；单位：percent；披露增量：0.01；状态：validated
定义：overall_office_vacancy；物业档次：all；统计方法标识：BNP-UK-overall-vacancy-v1；期间基础：quarter_end
位置：p1，页 1，规范化文本偏移 854
> Vacancy in Central London during Q4 2024 reached 9.71%.
校验说明：[]
人工结论：待填写；审阅者：待填写；签收时间：待填写。

### takeup / Central London
值：3050000；单位：sqft；披露增量：10000；状态：validated
定义：quarterly_office_takeup；物业档次：all；统计方法标识：BNP-UK-deals-over-1000sqft-v1；期间基础：quarter
位置：p1，页 1，规范化文本偏移 672
> Take-up for Central London offices reached 3.05m sq ft in Q4 2024
校验说明：[]
人工结论：待填写；审阅者：待填写；签收时间：待填写。

## 出版物差异与禁止推断

Q2 2026 官方叙述的 take-up 增长 26% 与披露的 2.5m→3.0m 不相等；代码只计算披露端点的 20%。空置率两个端点均为四舍五入后的 8.4%，不能复原文中所说 2bps 下降。
Q4 2024 HTML 和 PDF 端点披露精度不同，本评测绑定 PDF（9.71%、3.05m），不混用 HTML 舍入值。
City prime rent 不等同于 premium、平均成交租金或整个 Central London。£/sq ft 不能自动填入 year。