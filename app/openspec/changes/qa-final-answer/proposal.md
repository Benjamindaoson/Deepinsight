# Bounded Native Agent final-answer repair

Keep Agno 2.9.0 and existing provider. Replace byte-as-token estimation only on product question runs with a calibrated conservative estimate of the actual provider payload. Keep 3 requests, 60,000 input, 8,000 output, max_tokens 1800 and zero retries. Record decisions and real usage separately; compact only wire copies of evidence before rejecting an oversized request. Third request disallows tools; ignore no provider overrun.

Select compact, topic-relevant saved evidence with original status, definition, date, period, location and URL. No source acquisition or fact approval. Retain existing publication guard. A useful answer may explicitly conclude insufficient verified evidence, while labelling candidates and hypotheses.

Map budget, timeout, provider, tool and missing-answer errors to clear SSE results with completed stages. Offline mocks must precede a single authorized real browser submission. Stop after that attempt regardless of outcome; store evidence under app/data/product/evidence/ai-qa-final-acceptance.
