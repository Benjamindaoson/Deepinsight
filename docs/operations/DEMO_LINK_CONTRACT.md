# Reviewer demo link contract

The final assessment email names two public URLs. Treat them as stable product
interfaces during future Lite and Mini changes:

| Product | Railway project | Existing service | Public URL | Current access method |
| --- | --- | --- | --- | --- |
| Mini | `deepinsight-mini` | `deepinsight-mini-web` | https://deepinsight-mini-web-production.up.railway.app/ | Application sign-in with the existing access code |
| Lite | `deepinsight-lite` | `lite-frontend` | https://lite-frontend-production.up.railway.app/ | HTTP Basic, username `reviewer`, existing Railway password |

The access values are intentionally absent from Git, this document, and test
receipts. The Lite frontend is connected to a separate private `lite-backend`
service. Both projects are currently deployed by direct upload, with GitHub
auto-deploy disabled. A GitHub push alone does not update either live demo.

## Release rule

Keep the existing Railway projects, services, environments, and generated
domains. Deploy a new version **to those services** and use Railway's normal
deployment rollback if a release fails. Do not create replacement services,
remove the domains, rotate the access values, change the `reviewer` username,
or change the Mini sign-in flow as a side effect of visual or feature work.
Preserve the existing backend volume and evidence database. If access policy
must change, update the assessment recipient's instructions before doing so.

Run the read-only check both before and after each deployment:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\check-demo-contract.ps1
```

It verifies exact domain-to-service mapping, successful latest deployments,
unchanged access *methods*, actual login using values fetched privately from
Railway, and Lite's frontend-to-backend market API path. It also compares
salted credential digests with the protected local baseline at
`secrets/demo-access-baseline.json`; a missing baseline fails closed. It never
calls a model, sends a notification, or prints credentials. For an audit
receipt, pass `-ReceiptPath` pointing to an ignored local evidence directory.

The local baseline was established from the Railway access values that worked
when this contract was introduced. Keep that file private and available to
future release checks; a new workstation needs its protected copy. The digest
comparison detects a later Railway value change, but this check does not
independently verify what a recipient copied from the email. If a recipient
reports a mismatch, verify the email and live access privately before
redeploying. A successful homepage response also does not establish AI answer
quality, data freshness, or a production SLA.
