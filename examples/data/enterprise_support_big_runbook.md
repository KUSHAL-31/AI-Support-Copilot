# Enterprise Support Operations Runbook

## Overview

This runbook describes operational behavior for enterprise card payments, API key rotation,
refund retries, incident response, webhook delivery, account lockouts, rate limits, and customer
escalations. It is intentionally larger than the basic sample document so local ingestion creates
multiple chunks and exercises retrieval, reranking, context assembly, citations, and confidence
scoring.

## Enterprise Card Payment Failures

Enterprise card payments can fail for several reasons. The most common cause is a processor risk
decision that rejects the authorization before the issuing bank approves the transaction. These
failures usually include a processor response code, a risk policy identifier, and a gateway trace id.
Support engineers should first inspect the payment attempt record, then compare the gateway response
with the processor event log. If the processor rejected the authorization because of velocity,
merchant category, or billing country mismatch, the customer should be advised to retry with a
different card or contact their card issuer.

Gateway timeout failures are different from processor rejections. A timeout means the gateway did not
receive a final answer before the request deadline. The payment workflow marks these attempts as
unknown until the reconciliation job receives a final processor event. Support should not manually
retry unknown payments until reconciliation completes, because duplicate captures can occur when the
original authorization later succeeds.

## Refund Retry Workflow

Refunds use a retry workflow with three stages. The first retry happens after fifteen minutes for
transient gateway errors. The second retry happens after four hours if the processor reports a
temporary settlement delay. The third retry happens the next business day and is routed through the
bulk refund queue. Permanent errors, such as closed card accounts or processor refusal codes, should
not be retried automatically.

When a refund remains pending after all retries, support should open an escalation with the payments
operations team. The escalation must include the customer id, payment id, refund id, processor trace
id, amount, currency, and the last gateway response. If the refund is time-sensitive, mark the ticket
as priority two and notify the on-call payments engineer.

## API Key Rotation

API keys are rotated from the admin console. Create a new key, deploy it to the service secret store,
verify that production traffic is using the new credential, and then revoke the old key. The old key
must remain active for at least one deployment cycle unless there is a confirmed compromise. Emergency
rotation can skip the overlap window, but the incident commander must approve the change.

The recommended rotation sequence is: create key, update secrets, restart dependent services, verify
authentication success rate, revoke old key, and record the change in the security audit log. If a
customer reports authentication failures immediately after rotation, check whether their integration
still sends the previous key in the `Authorization` header.

## Webhook Delivery

Webhook delivery uses exponential backoff. The platform attempts delivery immediately after the event
is committed, then retries after one minute, five minutes, thirty minutes, two hours, and twelve
hours. A webhook endpoint is marked degraded when more than fifty percent of deliveries fail during a
ten-minute window. Degraded endpoints continue receiving retries but are excluded from high-priority
incident alerts unless the customer has a premium support plan.

Support engineers should inspect the webhook delivery log before escalating. Common customer-side
issues include expired TLS certificates, DNS changes, firewall allowlist problems, and endpoints that
return HTML error pages instead of JSON acknowledgements.

## Rate Limits

Enterprise tenants have rate limits based on contract tier. Standard enterprise tenants receive six
hundred requests per minute per API key. Premium enterprise tenants receive two thousand requests per
minute per API key. Burst limits are calculated separately and protect the platform from sudden
traffic spikes. A customer hitting rate limits should receive the response header `x-ratelimit-reset`,
which indicates when the current window resets.

If a customer claims that rate limits are incorrect, support should compare the API key id, tenant id,
source region, and route-level limit. Some routes have stricter limits because they trigger expensive
ledger or reporting queries.

## Incident Response

For payment incidents, the first responder must determine whether the issue affects a single tenant,
a region, a processor, or the entire platform. The incident channel should include the on-call backend
engineer, payments operations, support lead, and incident commander. Customer communication should
avoid speculation and should include the impact window, affected workflows, mitigation status, and
next update time.

After mitigation, the incident commander owns the post-incident review. The review should document
root cause, detection gap, customer impact, timeline, what worked, what failed, and prevention items.
Any prevention item tied to alerting, retries, or data integrity must have a directly assigned owner
and a target completion date.

## Account Lockouts

Accounts are locked after repeated failed login attempts, suspicious IP changes, or security policy
violations. A support engineer can unlock an account only after verifying the requester identity using
the tenant's configured support verification method. For premium tenants, identity verification may
require approval from a tenant administrator.

Unlock events are written to the security audit log. The audit event must include the support agent
id, customer requester id, tenant id, unlock reason, and verification method. If the lockout was
caused by suspected credential stuffing, the customer should rotate API keys and enforce multi-factor
authentication for administrators.

## Escalation Policy

Priority one escalations include full payment outage, data integrity risk, security compromise,
customer production outage, or any incident affecting multiple enterprise tenants. Priority two
escalations include degraded payment success rate, delayed refunds, elevated webhook failures, or a
single premium tenant production impact. Priority three issues include configuration questions,
dashboard confusion, and non-urgent integration errors.

Every escalation must include a concise problem statement, customer impact, timestamps, relevant ids,
logs or traces, attempted mitigations, and the exact customer-facing question. Poorly formed
escalations slow down engineering response and create duplicate investigation work.
