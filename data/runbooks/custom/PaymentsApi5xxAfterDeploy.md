---
title: Payments API 5xx After Deploy
service: payments-api (fictional service used for testing)
---

# PaymentsApi5xxAfterDeploy

## Meaning

More than 2% of requests to payments-api returned HTTP 5xx (mostly 502) within
15 minutes after a new deployment.

## Impact

Customers cannot complete checkout. Every failed request is a failed payment
attempt, so this alert is treated as SEV-2.

## Diagnosis

- Check the deploy time in the "Payments / Deploys" dashboard and compare it
  with the start of the error spike.
- Check rollout status via `kubectl -n payments rollout status deployment/payments-api`.
- Check the new pods' logs via `kubectl -n payments logs deployment/payments-api --since=15m`.
- A 502 usually means the new pods failed their readiness probe on port 8443.

## Mitigation

Roll back first, investigate later:
`kubectl -n payments rollout undo deployment/payments-api`.
Then post in #payments-oncall with the deploy id and the time of the rollback.
If the error rate is still above 2% ten minutes after the rollback, escalate to
the payments team lead.
