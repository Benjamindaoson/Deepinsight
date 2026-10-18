# London Office Market product technical test report

## News discovery and notifications, 2026-10-18

Baseline 192 PASS; final 208 PASS (34.93s). Offline Tavily/source fixtures plus real localhost Apprise accepted one POST; duplicate suppressed. Live GPE acquisition, native monitoring/report Runs, browser job/report display and restart persistence PASS. New dedicated Tavily key and external recipient missing: real search and external delivery BLOCKED, not PASS. Real LLM requests 0. No data approval or model-budget changes. Evidence: `app/data/product/evidence/news-discovery-notifications-20261018/ACCEPTANCE_REPORT.md`.

## 最新真实验收 — 2026-10-18 12:15（修复后）

一次真实网页 Native Agent 提交，2次模型请求、1次工具检索；模型claude-sonnet-4-6，经api.jingziai.club/v1。实际回执输入2394/输出1356 Token，原生流21.540秒，含发布投影21.646秒，费用N/A。Run d075bf6b-9e43-4c01-b944-9f4babc66764 COMPLETED。

技术执行PASS；AI语义分析未通过（伦敦塔误写塔桥、部分逐项引用缺失）；安全回退PASS（非空、1条机构披露变化+8条待审披露、9条证据校验全通过、0批准）。无预算或账本错误，无第二次提交。业务源码未修改，资料/审核状态/历史会话保持一致。其他业务不作本轮新验收结论。

预检另运行23项离线预算/账本测试通过，不混同真实请求。两个展示限制保留：规划事件null/default状态差异被省略；机构变化通用数值栏未映射reported字段，正确数值仍在引用原文中。完整记录：`app/data/product/evidence/post-fallback-live-20261018/AI_QA_ACCEPTANCE_REPORT.md`。

## 最新补充 — 离线安全回答回退

- 后端全量 **192 passed in 37.87s**；原176项继续通过，新增16项回退测试。包含真实已存草稿/JLL原文离线回放和明确标识的合成异常样例。
- 前端25测试、TypeScript、生产构建、Lint通过（既有img警告）。原生流及会话恢复接入只读发布结果。
- 真实浏览器只读打开既有 Run，非空安全回答、来源、待审状态与刷新恢复通过。没有新网页提交或模型调用。
- 指定旧草稿保留11条待审披露，3条省略，0批准；数据库、原件、原生Run、历史证据及模型账本前后校验一致。
- 真实模型：本轮NOT RUN，历史FAIL不变。人工审核与正式趋势比较门槛不变，整体PARTIAL。
- 证据：`app/data/product/evidence/safe-answer-fallback-20261018/REPAIR_ACCEPTANCE_REPORT.md`；构建manifest `bfbfd31e01cb87d6c0b9715afe26396cf77e87495821c7ffbbfa6bd68691cb1f`。

## 最新补充 — 2026-10-18 provider receipts

- 离线/本地完整回归：176 passed in 31.48s。新增原始用量保存、超限终止、SDK MockTransport与真实Windows文件共享冲突回归。
- 真实模型：一次网页提交、2请求、1工具；第二次流中账本原子替换WinError5，Run ERROR、最终分析FAIL；第二次及累计实际用量未知，费用N/A。没有第二次提交。
- 缺陷已离线修复，后端已重启；修复后未重新调用模型，不能宣布完整链路通过。
- 真实浏览器：失败提示、历史恢复和重启后ERROR状态已检查，不把草稿当完成结果。
- 问答当时前端：集成20测试及构建/类型通过，99文件身份一致。随后并行UX会话继续修改前端；此身份不代表其尚未发布的新源码。
- 原33个事实存储记录整体哈希和原件哈希不变；正式人审与G0门槛不变。
- 证据：`app/data/product/evidence/provider-receipts-20261018/AI_QA_ACCEPTANCE_REPORT.md`。下面保留历史结果。

---

Recorded 2026-10-18T00:05:24.322506+00:00. These are local engineering and execution results, not human approval of market facts.

## Fresh verification

- Python: **106 passed in 11.90s**, `app/data/product/evidence/python-tests-final.txt`.
- Python compileall and strict OpenSpec validation executed; their command results are recorded in the delivery transcript/verification receipts.
- Frontend production build, lint/type checks and 3/3 SSE tests passed. See `app/frontend/FRONTEND_VERIFICATION.md` and the 91-file `FRONTEND_BUILD_IDENTITY.json`. Latest build used the approved Linux mirror with identical authoritative source; upstream lock unchanged.
- Seven business pages and native `/chat` were exercised in the real browser. Evidence includes filters, quote/hash drawer, comparison refusal, reports/read/download, missing-channel feedback, settings save, jobs, real Chinese Agent answer and native session refresh recovery.
- Real source acquisition saved HTML/PDF/CSV/JSON, including the actual BNP PDF link followed from its saved page. Employment LF24 is explicitly May–July 2026 rolling average, not June-only or Q2.
- Independent review found and corrected budget lifetime/isolation, duplicate paid work, workflow skip-to-success, raw/normalized scale, conditional child retry and provenance defects. See `independent-review.md`; initial failed receipts remain preserved.

## Observed execution

Real extraction v2: 8 exact quotes from the original BNP Q1 report; two provider requests, 12,661 input/1,572 output tokens, 139.453s. Candidate facts remain needs_review where fields are unknown. Workflow Run `3e09d973-4511-4762-a241-e5385a2e4e10`; native extraction Run `2c7b503a-120a-4959-9053-d547be3df898`.

Async saved-evidence answer: two provider requests, 9,062 input/964 output tokens, first content6.673s, completion17.401s. Native Run `920cc028-85fb-4d86-9883-e5ddc352199a`. Browser Chinese answer and native reload use Run `7db1cd08-8be3-4700-b750-39ec97c1020a`.

Same-document extraction returned cached=true and zero new model requests in0.396s. Optional AI reports ran through native report workflow and separate analysis jobs. First analysis completed in59.8s, cached repeat in0.217s; its semantic problems are explicitly preserved. V2 concise analysis completed in approximately29.35s. It remains REVIEW_REQUIRED, with disclosed defects about combined pre-let/under-offer transaction area and an implied supply trend across unconfirmed publisher methods. No model response was made into approved source facts.

Total actual provider requests in this delivery: **16**. One original streaming run has incomplete final usage; no zero substitution. Provider fee receipt unavailable: **N/A**. A provider output-cap/accounting anomaly remains disclosed in `provider-usage-review.json`. Post-response total-budget rejection is tested; it cannot undo provider billing.

## Performance and reliability

30 cached HTTP query samples: P95 **212.36ms**. 30 uncached direct SQLite/service reads: P95 **1.58ms** (not HTTP). 30 deterministic comparison/refusal requests: P95 **90.24ms**. Three real PDF parse samples: median **167.58ms**. The final sample arrays are retained in `performance.json`; model failures and network failures are retained in their original receipts. Dashboard browser commit timing is in `browser-performance-final.json`; local targets do not establish production SLA.

The original all-source batch had7 successes/4 failures and retained successes. Native Scheduler triggered real report generation while the browser was irrelevant; temporary minute schedule is disabled, and four product definitions remain. Generic scheduler history does not provide native report Run ID automatically; the corresponding report job stores the actual native Run ID.

Actual process restart preserved facts/reports/native sessions. A real BBC refresh was interrupted, recovered as interrupted, explicitly retried and reported its genuine network failure. A separate real subprocess was terminated between SQLite INSERT and COMMIT: uncommitted row absent and all existing facts unchanged. Loopback Apprise HTTP delivery plus successful-send dedup passed; no external recipient is configured or claimed.

Protected baseline:304 hashes checked unchanged, official UI tracked source unchanged at pinned commit. Credential-body scan writes counts and matches only, never the key. JSON exports and consistent SQLite backups are local evidence.

## Explicit unpassed gates

G0 annual-unit/method qualification, human fact approval, original four-report90% evaluation and three approved real market changes remain unpassed. Historical AC matrix is separately dated in `LEGACY_AC_STATUS.md` (24 PASS/5 BLOCKED/1 FAIL). These engineering tests do not rewrite it. AI semantics remain review-required. External notification delivery and public deployment are not verified.

## 2026-10-18 bounded Native Agent final-answer acceptance

Latest evidence: [AI_QA_ACCEPTANCE_REPORT](../../data/product/evidence/ai-qa-final-acceptance/AI_QA_ACCEPTANCE_REPORT.md). This is a separate, explicitly authorized single attempt; earlier runs above are historical.

- **Offline engineering:** 145 Python tests passed, 4 frontend SSE tests passed, changed-file lint/type checks and frozen production build passed. Fixed responses in these tests are labelled Mock and are not real model acceptance.
- **Real provider:** one browser submission, two `claude-sonnet-4-6` requests through the unchanged relay; input 7,061 / output 1,879 Token, 36.836 seconds. Each output stayed at or below max_tokens 1,800. One compact retrieval returned eight facts and one event. No retries, fallback, third request or second submission. Cost N/A means unknown, not free.
- **Real browser:** received the publication-withheld result, not a complete approved analysis. Browser first content receipt 36.855 seconds, completion 36.930 seconds. Screenshot and DOM retained.
- **Acceptance FAIL:** the raw answer states insufficient verified evidence, but ends mid-sentence at exactly 1,800 output tokens on its second response. Finish reason was not retained. Existing publication rules also flagged date/newline/URL text as source counts and condition/negation text as trend assertions. `under offer` translation remains inaccurate. No rules were loosened after this outcome.
- **Human review:** facts/documents/events hashes unchanged; all pending states remain. No G0 approval, comparison qualification or historical evaluation gate was upgraded. Provider/run completion is not semantic approval.

Work stopped after saving this real failure. The report describes follow-up improvements without implementing them or making another paid call.
