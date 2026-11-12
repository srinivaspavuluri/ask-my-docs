---
title: Payments API High Latency
service: payments-api (fictional service used for testing)
---

# PaymentsApiHighLatency

## Meaning

The p95 latency of payments-api has been above 800 ms for 10 minutes. Normal
p95 latency is around 250 ms.

## Impact

Checkout feels slow. If latency keeps rising, requests start to time out and
this turns into PaymentsApiDbPoolExhausted.

## Diagnosis

- Check which endpoint is slow in the "Payments / Latency" dashboard.
- If only /v1/charge is slow, the external card provider is the likely cause:
  check its status page and the provider_latency_ms metric.
- If every endpoint is slow, check CPU throttling on the payments pods and the
  database dashboard.

## Mitigation

For a slow card provider, enable the fallback provider by setting the feature
flag `payments.fallback_provider` to true.
For CPU throttling, see the CPUThrottlingHigh runbook.
Page the payments team lead if p95 stays above 2 seconds for 15 minutes.
