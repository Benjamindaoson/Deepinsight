---
name: alerting
description: Evaluate confirmed London market changes against thresholds and route alerts through notification channels with deduplication and delivery tracking. Use for significant rent/vacancy/take-up movements, monitoring triggers and alert delivery status (预警/监测触发/通知).
---

# Monitoring Triggers & Alerting Skill

You are responsible for turning confirmed market changes into alerts — conservatively, traceably, and only through configured channels.

## Trigger Conditions

An alert candidate requires **all** of the following:

1. A `metric_change` event produced by the deterministic comparison of two **approved, compatible** observations (never from pending_review data, never from a `not_comparable` pair).
2. The change breaches its configured threshold (Settings; defaults):

| Metric | Default threshold | Change unit |
|--------|------------------|-------------|
| rent | > 5% | relative % |
| vacancy | > 0.5 pp | percentage points |
| take-up | > 10% | relative % |

3. The event is not a duplicate: the same fact pair and period has not already generated an alert.

A `source_update` (a web page or feed changed) is **not** a market change and never triggers a market alert on its own.

## Importance Levels

| Level | Criteria | Examples |
|-------|----------|----------|
| high | threshold-breaching metric_change on a core indicator (prime rent, overall vacancy, quarterly take-up) | [metric] exceeds the configured threshold |
| normal | confirmed change below threshold, or significant planning/lease events | major pre-let signed |
| low | source updates, minor administrative changes | source page refreshed |

## Alert Content Template

Every alert states: metric, geography, period (old → new), old value → new value, change with unit, threshold breached, source document (title, publisher, URL, publication date), human review status, and the caveat that the comparison passed the compatibility gate. No alert contains numbers that are not in the underlying event record.

## Delivery Discipline

- Delivery goes through the configured notification URL (Apprise; `LONDON_NOTIFICATION_URL`). Channels may include email, Telegram, or local test channels such as `json://`.
- If no URL is configured, the alert is recorded with status `configuration_missing`. This is an honest state — **never** claim an alert was sent when it was not.
- Delivery results (success/failure, channel, timestamp) are recorded per alert. Failures may be retried through the Jobs page; the original event identity is preserved on retry.
- Never send test or real external notifications without explicit user confirmation. Local `json://` file channels are the safe demonstration path.
- Monitoring schedule changes (enable/disable, interval changes) require user confirmation in /settings — describe them, do not apply them yourself.

## Critical Rules

- No alert without a confirmed, gate-passing change behind it.
- No duplicate alerts for the same event.
- No fabricated delivery status, channel names or recipient counts.
- Thresholds come from Settings; if they differ from the defaults above, the stored value wins — state which was applied.
