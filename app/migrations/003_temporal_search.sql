-- A rebuildable projection of saved source evidence. Business records remain in 002_product.
CREATE VIRTUAL TABLE IF NOT EXISTS market_search USING fts5(
  record_type UNINDEXED, record_id UNINDEXED, locator UNINDEXED,
  source_id UNINDEXED, geography UNINDEXED, period UNINDEXED,
  metric UNINDEXED, review_status UNINDEXED, published_at UNINDEXED,
  body, tokenize='unicode61'
);
