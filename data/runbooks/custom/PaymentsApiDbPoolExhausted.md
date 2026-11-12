---
title: Payments API DB Pool Exhausted
service: payments-api (fictional service used for testing)
---

# PaymentsApiDbPoolExhausted

## Meaning

All database connections in the payments-api pool are in use, and new requests
wait for a free connection. The pool size is set by the DB_POOL_MAX environment
variable, which defaults to 40.

## Impact

Requests time out after 30 seconds. Checkout becomes slow and then fails with
HTTP 504.

## Diagnosis

- Check the "Payments / Database" dashboard: active connections at 40 out of 40
  means the pool is full.
- Look for long-running queries:
  `SELECT pid, now() - query_start AS duration, query FROM pg_stat_activity WHERE state = 'active' ORDER BY duration DESC;`
- A sudden traffic increase or a slow query that holds connections are the two
  usual causes.

## Mitigation

If one query is stuck, cancel it with `SELECT pg_cancel_backend(<pid>);`.
If traffic is the cause, scale out with
`kubectl -n payments scale deployment/payments-api --replicas=6`.
Do not raise DB_POOL_MAX above 60: the database allows at most 200 connections
in total, shared by all services.
