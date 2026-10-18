# B1 G0 来源资格报告

结论：**BNP 主来源整体 BLOCKED；租金 needs_review，空置率与季度 take-up 的两期口径核查通过自动核验，仍待负责人签收。** 本报告不是投资建议，也不代表出版机构数据绝对准确。最终人工审阅者已由用户指定为项目负责人本人，状态 pending_review。

生产登记仍为 `b1/data/source-registry.json` 的 BNP 系列，没有切换为备选机构、购买数据、提交下载身份表单或降低三个指标的门槛。

## 主来源身份与检查范围

| 资料 | 官方 URL | 本地文件 | 发布日 / 期间 | SHA-256 |
|---|---|---|---|---|
| BNP Q1 2026 | https://www.realestate.bnpparibas.co.uk/sites/default/files/2026-05/Q12026CentralLondonMarketUpdate.pdf | b1/data/raw/bnp-q1-2026.pdf | 2026-05-18 / 2026Q1 | 8255a921c15294718433e5a893e6616593ab730904de4be452ba74d0c27bde7c |
| BNP Q2 2026 | https://www.realestate.bnpparibas.co.uk/sites/default/files/2026-08/Q22026CentralLondonMarketUpdate.pdf | b1/data/raw/bnp-q2-2026.pdf | 2026-08-05 / 2026Q2 | 3dd8de05ccb26ce235dfc8f9cf96d47bb2f760196d56cfcc94b0dc2a2a2016cd |

对应官方 HTML：`https://www.realestate.bnpparibas.co.uk/insights/central-london-office-market-update-q1-2026` 与 `...-q2-2026`，均已保存在 raw 目录。市场统计季度、网页发布日期、实际采集时间分别保留。PDF 内的 Research May/July 2026 是报告内研究标记，不冒充网页精确发布日期。

检查覆盖每份 PDF 的全部13页文本，包括第3页 Key Stats、正文、第4页 supply/vacancy、第6页 City rent 图表、各子市场页和末页。没有在这两份报告文本中找到 `per annum`、`per year`、`/year` 或 `p.a.`。已渲染并检查第3页文字、脚注和卡片；保存第3/13页图像供人复核。程序检索本身不能替代对图片文字的人工判读。

证据：`b1/evidence/g0/bnp-unit-audit.json`（页数、匹配结果、PDF 内链接）；`source-qualification-details.json`（完整逐页文本和备选接入结果）；`b1/evidence/source-pages/`（原件渲染）。引用与位置详见 `FACT_REVIEW.md`。

## 三类指标的资格判断

| 指标 | Q1 / Q2 原值与位置 | 已确认内容 | 判断 / 未确认内容 |
|---|---|---|---|
| City prime rent | £92.50 / £95；两份 PDF 第3页，City 第6页交叉核对 | 同一出版机构、City prime，区别于 City premium、City towers 和 West End | **BLOCKED / needs_review**：只有 per sq ft、£psf，未明确年度时间分母；不转换为 GBP/sqft/year，不计算变化 |
| Central London overall vacancy | 8.4% / 8.4%；第3页，另见第4页 overall narrative | 连续季度、同 Central London 整体市场、百分数、季度观察点；未混入 City 或 Grade A 子集 | **PASS（自动核对）/ pending_review（人工）**；由披露端点计算 0.0 pp，不声称真实底层完全不变 |
| Central London quarterly take-up | 2.5m / 3.0m sq ft；第3页 | 明示 Q1/Q2 2026；两份脚注均为 all deals over 1,000 sq ft；Q2 另列 H1 5.5m，未将 H1 当 Q2 | **PASS（自动核对）/ pending_review（人工）**；规范值2,500,000 / 3,000,000 sqft，披露增量100,000 sqft；端点差500,000 sqft，相对20% |

内部 `BNP-UK-...-v1` 是本项目口径标识，不是冒称出版机构发布过同名方法版本。来源提供的确切门槛保留在脚注；未披露的 postcode 边界、样本修订历史或完整统计手册没有被推断为已核实。

Q2 第3页正文将26%标为相对上一季度，而卡片将26%标为 y-o-y；两者与披露的 Q1 2.5m、Q2 3.0m 端点计算存在差异。第4页所称空置率约2bps下降也不能从两个8.4%舍入端点还原。保留原文差异，不修改端点来迎合叙述，也不替出版机构解释差异来源。

## BNP 官方定义补充核查

已重新从官方页面的实际下载链接读取 Europe Office Market Q1 2026 文档：`https://www.realestate.bnpparibas.com/media/com/2026-05/2026%20Q1%20Office%20Europe%20REview_1.pdf`；本地 `b1/data/raw/bnp-europe-q1-2026-official-recheck.pdf`，7页；URL、hash、采集时间和完整分段见 `b1/evidence/g0/europe-definition-recheck.json`。早期5页副本单独保留，没有用它冒充本次7页快照。

- 第3页图例明确 `€/sqm/year`，说明该欧洲图表使用年度单位。
- 第5页 glossary 定义 prime rent、vacancy rate、take-up，并说明欧元汇率采用季度平均值。
- 同页 prime rent 定义为调查时点最佳地点、最高规格的典型单元租金；实际交易支持 headline，排除不代表市场的一次性交易，必要时采用专家假设。
- 这不是对 UK Q1/Q2 2026 City `£psf` 单位的明示引用或系列映射。没有用欧洲图表、历史文章、某栋物业的年度报价、收益率或 annual rental growth 替 UK 系列补时间分母。
- 该文件另有客户端用途/复制许可限制；没有将其作为可商用、可外部分发的授权依据。

英国官网公开检索也检查了带 `per annum` / `psf pa` 的官方结果。检索命中的单体物业费用声明和 annual growth/return 叙述，均未被当成主系列单位证明。结论限定为“本轮已检查的资料仍不能确认”，不声称所有官方资料永远不存在该定义。

## 备选来源核查

| 来源及实际资料 | 指标覆盖与具体位置 | 差异和资格结果 |
|---|---|---|
| Savills Q1/Q2 2026；官方 PDF：`https://pdf.euro.savills.co.uk/uk/office-reports/central-london-q1-2026-report.pdf` 与 `...q2-2026-report.pdf`；本地两份均已取回，10页/份 | 第2页 summary；第3页季度 leasing；第6页 Central London vacancy 7.4% / 7.2%；第8页 City average prime rent 130.80 / 116.73 psf | **BLOCKED / 待复核**：第8页明确 average prime rents derived from achieved rents rather than ERVs，与 BNP headline prime 定义不同；仍未找到租金时间分母。Q2 summary 的4.7m是H1，不可当Q2；正文才是Q2 2.4m。Q1网页和月报还存在不同统计表现，未混入生产 |
| Carter Jonas Q1/Q2 2026；Q2官方入口 `https://www.carterjonas.co.uk/insights/the-london-office-market-q2-2026`；原始下载 URL、hash、时间见 source-qualification-details.json；两份 PDF 各11页 | 第7页 table3明确 `£ per sq ft per annum`、space over5,000sqft、GradeA/B和分区；第8页为综合 occupancy costs，需分离rent分项 | **年度单位 PASS；整体组合 BLOCKED**：是典型 advertised rent 和多个区间/物业细分类别，不能直接替换 BNP City prime；本轮全文未找到可独立确认的 Central London 整体数值空置率与同定义季度 take-up 连续两期组合。定性 low vacancy、单栋成交或出租面积清单不足以补齐 |
| CBRE Q2 2026；官方入口 `https://www.cbre.com/insights/figures/central-london-office-figures-q2-2026` | 摘要给19.4m sqft supply，官方新闻给2.7m sqft quarterly take-up；不能把供给面积当vacancy rate | **BLOCKED / 需访问决策**：官方 Download PDF 指向 `https://cloud.cbrecommunications.com/hq-figure-page-form-submission`，要求邮箱、姓名、公司、职位和隐私选择；未提交身份信息，未绕过。完整报告中租金年度单位/空置率/两期一致性未完成资格确认 |

备选 HTML 直接 fetch 的部分请求发生 ConnectError/HTTPStatusError/内容类型拒绝，均记录为失败；不能据此声称机构资料不存在。Savills 和 Carter PDF 已真实下载。CBRE 表单由 web 工具只读检查，凭据保存为 `b1/evidence/g0/cbre-download-gate-web.json`，不是伪造的本地 fetch 成功记录。

公开替代报告已继续查找并保留证据，目前没有一组通过全部三指标资格门禁的替代来源。未将任何备选数值入生产事实库，也没有跨机构拼接比较。

## 访问边界与下一项决策

BNP 官网条款：`https://www.realestate.bnpparibas.co.uk/terms-of-use`；原始 HTML 与结构化采集凭据已保存为 `b1/data/raw/bnp-terms-of-use.html`、`b1/evidence/g0/source-terms.json`。本交付限定本地、不公开的技术验证，没有声明商业使用许可或再分发授权。

可以继续而无需改变范围的事项：人工签收已有12个指标机会，复核两个已计算比较，使用只读 Agent/UI，重放确定性测试和已有响应，检查保存快照。

租金放行需要可定位、适用于该 UK 系列的官方时间单位依据。获得依据后应做显式 profile/定义版本变更与新 attempt，保留旧结果。若选择其他机构，应先完成该机构两期完整资格审查，再由负责人明确批准切换。若需要提交身份信息、付费权限、购买数据或改变范围，另行决定；本次未执行这些动作。
