# Reuse market monitoring for bounded news discovery

Add an opt-in Tavily URL discovery adapter to the existing news refresh Workflow. Preserve four Scheduler identities, business schema, event review gates and Apprise delivery path. Dedicated new server key only; never inherit generic TAVILY_API_KEY. No additional LLM calls.

Original acquisition must validate registered enabled publisher, HTTPS host, redirect and public destination; search snippets never become evidence. Save discovery receipts in existing jobs and originals in existing documents/artifacts. Reuse receipts during the six-hour window, including failures, to prevent scheduler retries charging repeatedly. Explicit original retries remain possible.

Notification configuration validation must not send. Catch configuration failures in the existing send path, preserve sent dedup and ambiguous-delivery guard. Actual external sends require configured destination and explicit authorization.
