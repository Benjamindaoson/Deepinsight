# B0 架构发现产物

- 类型：architecture；8个主要节点，覆盖浏览器→Next页面→API/流→原生AgentOS→SQLite/模型API，以及浏览器状态和消息展示。
- `b0-runtime.json`：发现阶段的结构快照；其中“SQLite待实测”等文字描述当时状态，最终实测状态以 B0_TEST_REPORT 为准，不把图当运行凭据。
- `b0-runtime.html`：独立可交互HTML；源spec与artifact SHA/字节数在 `../../evidence/logs/archify-delivery.json`。
- Archify deliver：9项artifact checks通过，composition errors=0、warnings=0。
- visual-check：1440×900、1600×1000、1920×1080、2048×1320 容纳检查通过，保存大小屏浅/深色截图与contact sheet；自动receipt视觉审阅字段仍为pending。人工检查过最大浅色截图，未把其余截图描述为全部人工审阅通过。
- 来源定位：B0_UI_AUDIT、FUNCTION_CATALOG、官方Quickstart及冻结UI hooks/API/store；图是方向性架构阅读入口，不是新增产品或业务实现。
