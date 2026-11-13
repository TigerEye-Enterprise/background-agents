import { allowsCloudflareAccess } from "@open-inspect/shared/cloudflare-access";
import app from "./.open-next/worker.js";
export * from "./.open-next/worker.js";

export default {
  async fetch(request, env, ctx) {
    if (!(await allowsCloudflareAccess(request, env.RAIL3_ACCESS_ISSUER, env.RAIL3_WEB_AUDIENCE))) {
      return new Response("Forbidden", { status: 403 });
    }
    // The wrapper runs before static assets too. Preserve asset routing after Access.
    if (request.method === "GET" || request.method === "HEAD") {
      const asset = await env.ASSETS.fetch(request);
      if (asset.status !== 404) return asset;
    }
    return app.fetch(request, env, ctx);
  },
};
