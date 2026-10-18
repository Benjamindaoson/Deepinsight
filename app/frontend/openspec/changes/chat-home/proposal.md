# Chat-first business frontend

Scope: app/frontend only. Reuse Agno chat components, streaming handler and Session APIs. Keep backend, budgets, review states, data and upstream unchanged.

Acceptance: / is a chat welcome screen; /overview retains the dashboard; shared collapsible navigation and searchable native sessions; persisted light-default/dark themes; quick prompts use existing native run endpoint; no model calls on mount; readable evidence, errors and explicit review labels; responsive browser checks; lint, types, production build and offline tests.

Native chat is a raw AgentOS view, not business publication approval. Label native output as requiring review and retain guarded /ask. Loading history never approves content. Validate offline first, then one bounded model submission with no automatic retry. No new dependencies or invented trends.
