# Rail 3 Access rollout (TE-09wde9.13)

This source change adds an opt-in ingress boundary. It does not provision Access applications or
authorize a deployment. Leave the Rail 3 option unset on deployments that do not use this boundary.

Before activating Rail 3:

1. Provision the web and control-plane hostname Access applications and the narrower, exact
   automation webhook application. Supply their distinct audience tags, team issuer, control
   hostname and exact webhook path via the production Terraform `rail3_access` input. Use the
   approved Cloudflare zone and web custom hostname. Do not place Access client secrets in public
   build variables.
2. Admit browser WebSockets on the control-plane hostname and confirm the browser gets the
   control-plane audience. The web Worker uses a named Cloudflare service binding internally; normal
   control-plane authorization still applies there.
3. Resolve Modal's outbound authentication before activation. The sandbox opens its own WebSocket
   and makes HTTP requests to the control plane for repository credentials, media, and PR tooling.
   Existing application credentials do not satisfy Access. Keep a distinct, scoped machine policy
   and credential delivery boundary; do not reuse the webhook credential or add an anonymous path.
   Until this path is verified, no live sandbox or docs pilot is admitted.
4. Verify that neither Worker serves a public workers.dev or preview URL. Test missing, invalid and
   wrong-audience assertions on the protected endpoints, then validate a signed-in browser session,
   service binding, and the authorized webhook. Check that the webhook audience cannot reach
   ordinary control-plane paths. Record the Cloudflare deployment/version IDs and results before
   running a docs pilot. Merge remains Mergify-only.

The live receipt must record both deployment versions, the exact fork commit, and the positive and
negative Access results before dispatch. An unauthenticated redirect alone does not prove the
browser, sandbox, or webhook can complete an authenticated request.
