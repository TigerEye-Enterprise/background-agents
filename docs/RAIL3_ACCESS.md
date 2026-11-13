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
3. In the admitted Modal workspace, build the credential-free sidecar with
   `uv run --frozen python deploy.py --build-rail3-access-sidecar` from `packages/modal-infra`.
   Pass its immutable image ID as `rail3_access_sidecar_image_id`. Give a dedicated Modal
   service token access to the control-plane application only, separate from the webhook application.
   Project its two Cloudflare Access fields from OpenBao into the named Modal Secret
   `rail3-control-plane-access`. Only the sidecar receives the secret. The sidecar is restricted
   to the exact control-plane hostname, forwards an allowlist of current-session routes, and keeps
   existing session authorization in place. Main sandbox egress settings are unchanged.
   Verify both HTTP and WebSocket callbacks from a real VM, and verify the agent cannot read the
   Access credential or reach the webhook through the sidecar, before the docs pilot.

4. Verify that neither Worker serves a public workers.dev or preview URL. Test missing, invalid and
   wrong-audience assertions on the protected endpoints, then validate a signed-in browser session,
   service binding, and the authorized webhook. Check that the webhook audience cannot reach
   ordinary control-plane paths. Record the Cloudflare deployment/version IDs and results before
   running a docs pilot. Merge remains Mergify-only.

The live receipt must record both deployment versions, the exact fork commit, and the positive and
negative Access results before dispatch. An unauthenticated redirect alone does not prove the
browser, sandbox, or webhook can complete an authenticated request.
