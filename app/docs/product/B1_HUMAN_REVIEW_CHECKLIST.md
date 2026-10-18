# B1 核心事实人工复核清单（当前产品）

快照读取时间：`2026-10-17T23:37:23.639261+00:00`。读取当前产品 Store：`app/data/product/market.sqlite3`，使用 SQLite 只读连接。

**当前签收状态：六条事实均为 `human_review_status=pending_review`，人工批准数为 0；三组比较均为 `not_comparable`。本文件是待审材料，不是人工签收、正式金标准或 G0 放行证明。**

旧 B1 清单中的 UUID、部分自动 `validated` 和两组曾输出的端点计算属于历史记录。当前产品以这里的稳定 BNP ID、Store 状态和比较原因作为本次复核入口，不沿用旧结果作为已批准结论。

## 原件与身份

| 报告 | 当前产品原件 / 官方来源 | SHA-256 | 发布时间 / 原始采集时间 |
|---|---|---|---|
| 2026Q1 / `doc-bnp-8255a921c15294718433` | [本地原始 PDF](/D:/deepinsight-lite/app/data/product/originals/doc-bnp-8255a921c15294718433.pdf)；[BNP 官方 PDF](https://www.realestate.bnpparibas.co.uk/sites/default/files/2026-05/Q12026CentralLondonMarketUpdate.pdf) | `8255a921c15294718433e5a893e6616593ab730904de4be452ba74d0c27bde7c` | `2026-05-18` / `2026-10-17T12:32:43.296407+00:00` |
| 2026Q2 / `doc-bnp-3dd8de05ccb26ce235df` | [本地原始 PDF](/D:/deepinsight-lite/app/data/product/originals/doc-bnp-3dd8de05ccb26ce235df.pdf)；[BNP 官方 PDF](https://www.realestate.bnpparibas.co.uk/sites/default/files/2026-08/Q22026CentralLondonMarketUpdate.pdf) | `3dd8de05ccb26ce235dfc8f9cf96d47bb2f760196d56cfcc94b0dc2a2a2016cd` | `2026-08-05` / `2026-10-17T12:32:41.900043+00:00` |

页码均为 PDF 的一基页码；摘录来自实际保存的原件。报告季度、发布时间、采集时间不能相互替代。当前产品原件的哈希已在本次文档生成时重新校验。

## 六条待审事实

| 当前事实 ID | 地域 / 期间 | 原始显示与单位 | 规范化值与单位 | 原始 / 规范化披露增量 | 产品状态 / 人工状态 |
|---|---|---|---|---|---|
| `BNP-2026Q1-RENT` | City (BNP source-defined office submarket) / `2026Q1` | `92.50` GBP/sqft, time denominator not stated | null（未规范化／未知） / null（未规范化／未知） | `0.01` / `0.01` | `needs_review` / `pending_review` |
| `BNP-2026Q1-VACANCY` | Central London (BNP source-defined office market) / `2026Q1` | `8.4` percent | `8.4` / `percent` | `0.1` / `0.1` | `pending_review` / `pending_review` |
| `BNP-2026Q1-TAKEUP` | Central London (BNP source-defined office market) / `2026Q1` | `2.5` million sqft for a single quarter | `2500000` / `sqft` | `0.1` / `100000` | `pending_review` / `pending_review` |
| `BNP-2026Q2-RENT` | City (BNP source-defined office submarket) / `2026Q2` | `95` GBP/sqft, time denominator not stated | null（未规范化／未知） / null（未规范化／未知） | `1` / `1` | `needs_review` / `pending_review` |
| `BNP-2026Q2-VACANCY` | Central London (BNP source-defined office market) / `2026Q2` | `8.4` percent | `8.4` / `percent` | `0.1` / `0.1` | `pending_review` / `pending_review` |
| `BNP-2026Q2-TAKEUP` | Central London (BNP source-defined office market) / `2026Q2` | `3.0` million sqft for a single quarter | `3000000` / `sqft` | `0.1` / `100000` | `pending_review` / `pending_review` |

Take-up 的 `2.5`、`3.0` 与 million sqft 属于原始显示；`2500000`、`3000000` 与 sqft 属于规范化面积。单季度流量单独保留为 `basis=quarter`、`temporal_basis=single_quarter_flow`，不能把展开后的面积再乘一次 million。原始 G0 标注完整保留在各事实的 `original_annotation`，本次映射修复及旧值保留于产品 `revision_history`。

两条租金的币种为 `GBP`，但年度时间分母仍未知，因此规范化值和规范化单位均为空；本表没有按行业惯例补年。六条事实的系列均为 `UK Central London Office Market Update`，`method=unknown`。Vacancy 为整体市场而非仅 Grade A；租金为 City prime，而非全伦敦均租。

## 逐条原文与核对动作

### BNP-2026Q1-RENT

原件：[2026Q1 PDF](/D:/deepinsight-lite/app/data/product/originals/doc-bnp-8255a921c15294718433.pdf)，第 **3 页**；定位：`pdf:page:3:chars:876-893`。

> £92.50 per sq ft.

定义：City prime office rent; not premium, achieved average or Grade A average。档次：prime (source label)。统计基础：`quarterly_report_point_in_time`。

待确认问题：`ANNUAL_TIME_DENOMINATOR_NOT_CONFIRMED`；`UK_SERIES_PRIME_METHOD_AND_BOUNDARY_PENDING_REVIEW`。

- [ ] 核对本条数值、披露精度、对应季度与地域确实由该页支持。
- [ ] 核对指标定义、等级、统计基础和方法的已知／未知边界；不能仅因引用匹配就批准口径。
- [ ] 负责人记录本条明确结论、证据和时间；当前保持 `pending_review`。

### BNP-2026Q1-VACANCY

原件：[2026Q1 PDF](/D:/deepinsight-lite/app/data/product/originals/doc-bnp-8255a921c15294718433.pdf)，第 **3 页**；定位：`pdf:page:3:chars:474-495`。

> vacancy stood at 8.4%

定义：Overall Central London office vacancy reported by publisher; explicit UK denominator definition not found in these PDFs。档次：overall; not restricted to Grade A。统计基础：`quarterly_report_point_in_time`。

待确认问题：`UK_SERIES_VACANT_FLOORSPACE_DENOMINATOR_AND_SUBLETS_MAPPING_NOT_EXPLICIT`；`DISCLOSED_PRECISION_ONLY`。

- [ ] 核对本条数值、披露精度、对应季度与地域确实由该页支持。
- [ ] 核对指标定义、等级、统计基础和方法的已知／未知边界；不能仅因引用匹配就批准口径。
- [ ] 负责人记录本条明确结论、证据和时间；当前保持 `pending_review`。

### BNP-2026Q1-TAKEUP

原件：[2026Q1 PDF](/D:/deepinsight-lite/app/data/product/originals/doc-bnp-8255a921c15294718433.pdf)，第 **3 页**；定位：`pdf:page:3:chars:345-367`。

> 2.5m sq ft in Q1 2026

定义：Central London office take-up during Q1/Q2; all deals over 1,000 sq ft; not H1 cumulative。档次：overall; not restricted to Grade A。统计基础：`quarter`。

待确认问题：`QUARTER_EXPLICIT_DEALS_OVER_1000_SQFT`；`PUBLISHER_ROUNDED_ENDPOINT`。

- [ ] 核对本条数值、披露精度、对应季度与地域确实由该页支持。
- [ ] 核对指标定义、等级、统计基础和方法的已知／未知边界；不能仅因引用匹配就批准口径。
- [ ] 负责人记录本条明确结论、证据和时间；当前保持 `pending_review`。

### BNP-2026Q2-RENT

原件：[2026Q2 PDF](/D:/deepinsight-lite/app/data/product/originals/doc-bnp-3dd8de05ccb26ce235df.pdf)，第 **3 页**；定位：`pdf:page:3:chars:882-896`。

> £95 per sq ft.

定义：City prime office rent; not premium, achieved average or Grade A average。档次：prime (source label)。统计基础：`quarterly_report_point_in_time`。

待确认问题：`ANNUAL_TIME_DENOMINATOR_NOT_CONFIRMED`；`UK_SERIES_PRIME_METHOD_AND_BOUNDARY_PENDING_REVIEW`。

- [ ] 核对本条数值、披露精度、对应季度与地域确实由该页支持。
- [ ] 核对指标定义、等级、统计基础和方法的已知／未知边界；不能仅因引用匹配就批准口径。
- [ ] 负责人记录本条明确结论、证据和时间；当前保持 `pending_review`。

### BNP-2026Q2-VACANCY

原件：[2026Q2 PDF](/D:/deepinsight-lite/app/data/product/originals/doc-bnp-3dd8de05ccb26ce235df.pdf)，第 **3 页**；定位：`pdf:page:3:chars:504-525`。

> vacancy stood at 8.4%

定义：Overall Central London office vacancy reported by publisher; explicit UK denominator definition not found in these PDFs。档次：overall; not restricted to Grade A。统计基础：`quarterly_report_point_in_time`。

待确认问题：`UK_SERIES_VACANT_FLOORSPACE_DENOMINATOR_AND_SUBLETS_MAPPING_NOT_EXPLICIT`；`ROUNDED_ENDPOINTS_VS_REPORTED_2_BPS_CHANGE`。

- [ ] 核对本条数值、披露精度、对应季度与地域确实由该页支持。
- [ ] 核对指标定义、等级、统计基础和方法的已知／未知边界；不能仅因引用匹配就批准口径。
- [ ] 负责人记录本条明确结论、证据和时间；当前保持 `pending_review`。

### BNP-2026Q2-TAKEUP

原件：[2026Q2 PDF](/D:/deepinsight-lite/app/data/product/originals/doc-bnp-3dd8de05ccb26ce235df.pdf)，第 **3 页**；定位：`pdf:page:3:chars:335-357`。

> 3.0m sq ft in Q2 2026

定义：Central London office take-up during Q1/Q2; all deals over 1,000 sq ft; not H1 cumulative。档次：overall; not restricted to Grade A。统计基础：`quarter`。

待确认问题：`QUARTER_EXPLICIT_DEALS_OVER_1000_SQFT`；`Q2_26_PERCENT_YOY_QOQ_CONFLICT`。

- [ ] 核对本条数值、披露精度、对应季度与地域确实由该页支持。
- [ ] 核对指标定义、等级、统计基础和方法的已知／未知边界；不能仅因引用匹配就批准口径。
- [ ] 负责人记录本条明确结论、证据和时间；当前保持 `pending_review`。

## 当前三组比较及拒绝原因

| 指标 | 当前比较 ID / 输入 | 当前状态与精确 reasons | 变化结果 |
|---|---|---|---|
| rent | `58a82b64-3feb-49d6-a907-f2c4e62813b6`；`BNP-2026Q1-RENT` → `BNP-2026Q2-RENT` | `not_comparable`；`["UNKNOWN_METHOD", "NOT_VALIDATED", "MISSING_VALUE", "UNKNOWN_UNIT_BASIS", "HUMAN_REVIEW_PENDING"]` | absolute_change=`null`；relative_change_pct=`null` |
| vacancy | `0e2cbd01-ad2b-48c2-98a9-191de353cc40`；`BNP-2026Q1-VACANCY` → `BNP-2026Q2-VACANCY` | `not_comparable`；`["UNKNOWN_METHOD", "NOT_VALIDATED", "HUMAN_REVIEW_PENDING"]` | absolute_change=`null`；relative_change_pct=`null` |
| takeup | `3e54bf44-f672-4eb8-8191-8f97f00c9a82`；`BNP-2026Q1-TAKEUP` → `BNP-2026Q2-TAKEUP` | `not_comparable`；`["UNKNOWN_METHOD", "NOT_VALIDATED", "HUMAN_REVIEW_PENDING"]` | absolute_change=`null`；relative_change_pct=`null` |

`UNKNOWN_METHOD` 表示方法仍未充分确认；`NOT_VALIDATED` 与 `HUMAN_REVIEW_PENDING` 表示状态门禁未通过。租金额外的 `MISSING_VALUE` 来自年度单位未确认而保留为空的规范化输入，**不表示原文 £92.50 / £95 缺失**；`UNKNOWN_UNIT_BASIS` 表示单位基础未获确认。

## 必须分别解决的审阅问题

1. **租金年度分母与 prime 定义。** 必须找到明确适用于这套 UK Central London Office Market Update 的官方依据；欧洲报告或其他机构系列的年度单位不能移植。签收数值本身不能自动放行年度单位、方法与边界。
2. **Vacancy 方法。** 确认 vacant floorspace、stock 分母、可即时入住／未来供应、sublets、under-offer、地域与档次规则。相同 publisher 和标签不等于方法已证实一致。
3. **出版物舍入。** 两季 vacancy 均显示 8.4%，不能据此恢复出版物提到的 2 bps 变化；披露端点差和出版物底层统计变化不是同一个结论。
4. **Take-up 统计与冲突。** 保持单季度且交易门槛 >1,000 sqft；Q2 的 3.0m 不等于 H1 累计 5.5m。Q2 的 26% 叙述及同比／环比冲突继续单列，不通过改数来消除。2.5m、3.0m 为舍入端点，未经审阅不得发布为精确市场变化。
5. **留出与评测边界。** 当前单份实际模型抽取及工程测试不修复历史 AC-26 原始评测 FAIL，不把接触过的留出重新称为未见留出。

## 人工结论记录区（尚未填写）

最终审阅者：项目负责人。审阅时间：未提供。批准事实 ID：无。拒绝／要求补证事实 ID：待提供。方法／单位补证：待提供。G0 放行结论：未放行。

只有负责人明确逐项给出结论后，才可按授权更新相应事实和人工状态；本清单的生成、引用匹配、单位显示修复、工程测试数字均不构成人工批准。当前工程回归计数以 [最终测试收据](/D:/deepinsight-lite/app/data/product/evidence/python-tests-final.txt) 为准；此前 **102 passed in 6.84s** 是历史快照；该数字不是核心事实或原始评测通过率。

关联证据：[种子单位修订](/D:/deepinsight-lite/app/data/product/evidence/seed-unit-mapping-revisions.json)；[原始字段对齐](/D:/deepinsight-lite/app/data/product/evidence/raw-field-alignment.json)；[规范化修订](/D:/deepinsight-lite/app/data/product/evidence/normalization-revisions.json)；[当前结果包](/D:/deepinsight-lite/app/data/product/evidence/result-package.json)；[当前浏览器比较记录](/D:/deepinsight-lite/app/data/product/evidence/browser-comparison.txt)；[独立工程审查](/D:/deepinsight-lite/app/data/product/evidence/independent-review.md)；[历史 G0 BLOCKED 报告](/D:/deepinsight-lite/b1/g0-review/2026-10-17/G0_VALIDATION_REPORT.md)。
