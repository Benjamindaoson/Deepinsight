# ToAPIs / VOA 受控实测：调用前检查报告

结论：**BLOCKED_PRE_REQUEST**。本轮没有发送模型生成请求，未执行第一次简报或第二次追问；没有将上一轮B1测试结果当作此次VOA测试通过。

## 授权与保护线

最多2次模型请求；第二次只在第一次成功且基本格式、引用和数值校验通过后允许。输入22,000 tokens、输出3,000 tokens按两次总预算记录，费用上限人民币1元。SDK/外层/自动修复重试均须0，不允许自动模型回退。禁止Tavily、其他搜索API、完整Research流程、外部通知。模型分析必须另存，不修改原始事实、ChangeEvent、EvidenceRef或文档hash；格式通过不代表语义审核通过。

## 本次只读预检结果

| 项目 | 实际结果 |
|---|---|
| 当前目录 | D:\deepinsight-lite |
| CodeGraph | 索引可用，先行查询；没有定位到VOA领域实现 |
| 已存ToAPIs凭证 | .env中存在OPENAI_API_KEY；只核查存在性，未输出密钥，未向模型端点发请求 |
| 配置端点 | .env为https://toapis.cn/v1；不是上一轮Agno B1的另一家relay配置 |
| 候选模型 | .env的DEFAULT_MODEL=gpt-4o；尚不能认定这是本次“方案2”批准的模型 |
| 实际使用的模型/端点 | 无；没有初始化调用客户端 |
| 既存VOA证据链 | 当前业务/文档目录未定位到VOA、ChangeEvent、EvidenceBundle、EvidenceRef实现与数据；普通文本中的VOA字样不当作领域资产 |
| 调用限额/重试开关 | 授权上限已记录；因方案2执行器未定位，未声称配置已实际施加或验证 |
| 计费 | 官方公开价格只作参考，最终以账户当前报价、参数及折扣结算；未取得本账户单价、币种/积分换算和最坏费用，不能证明不超过1元 |
| Git Commit | N/A；当前根目录不是Git仓库，没有创建新仓库或虚构commit |

官方公开页面（只读直接打开，未使用搜索查询或市场检索API）：
- https://toapis.cn/en/pricing
- https://toapis.cn/en/billing-policy

官方计费政策第1节“Current account quote controls”说明最终消费以账户当前报价为准。本报告没有用OpenAI官方模型价格代替ToAPIs账户实际价格，也没有自行假设汇率、积分换算或折扣。

## 实测与费用记录

- 实际模型请求：0；应用输入/输出tokens：0/0。
- 第一份模型简报：NOT_SENT；报告内追问：NOT_SENT。
- 费用回执：N/A，未查询账户账单；不把它写成已核实的账单费用。
- 格式/引用/数值检查：NOT_RUN，没有模型结果；语义审核NOT_RUN，未清除REVIEW_REQUIRED。
- Tavily/其他搜索API/完整Research流程/外部通知：均0次。
- 已有.env、secrets/model.json、secrets/relay.json仅只读检查；hash前后相同，详见preflight.json。
- 源码、既有B0/G0证据和B1结果没有修改；只新增本次预检报告及收据。

## 阻断与恢复条件

当前缺少“方案2”对应的正确项目路径、冻结VOA输入和执行器，以及可以约束1元预算的实际账户计费依据。已请求明确目标目录；本聊此前明确禁止操作D:\deepinsight-rader，因此没有自行跨目录读取凭证或运行应用。

取得正确目标后，先完成该仓库的只读预检和账户报价/预算核算；条件仍不满足则保持停止。未经核查不发送第一次请求，不以猜测生成简报或伪造引用。
