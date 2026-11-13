import { createRemoteJWKSet, jwtVerify } from "jose";

const keysByIssuer = new Map<string, ReturnType<typeof createRemoteJWKSet>>();

/** Verify the Access assertion at a public Worker entry point. Fail closed on config or key errors. */
export async function allowsCloudflareAccess(
  request: Request,
  issuer: string | undefined,
  audience: string | undefined
): Promise<boolean> {
  const token = request.headers.get("Cf-Access-Jwt-Assertion");
  if (
    !token ||
    !issuer ||
    !audience ||
    !/^https:\/\/[a-z0-9-]+\.cloudflareaccess\.com$/.test(issuer)
  ) {
    return false;
  }

  try {
    let keys = keysByIssuer.get(issuer);
    if (!keys) {
      keys = createRemoteJWKSet(new URL("/cdn-cgi/access/certs", issuer));
      keysByIssuer.set(issuer, keys);
    }
    await jwtVerify(token, keys, {
      issuer,
      audience,
      algorithms: ["RS256"],
      requiredClaims: ["exp", "iat"],
    });
    return true;
  } catch {
    return false;
  }
}
