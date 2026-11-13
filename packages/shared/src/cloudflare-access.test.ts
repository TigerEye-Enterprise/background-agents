import { exportJWK, generateKeyPair, SignJWT } from "jose";
import { afterEach, expect, it, vi } from "vitest";
import { allowsCloudflareAccess } from "./cloudflare-access";

const issuer = "https://rail3-test.cloudflareaccess.com";
const audience = "test-control-plane";
const request = (token?: string) =>
  new Request("https://control.example.com/health", {
    headers: token ? { "Cf-Access-Jwt-Assertion": token } : {},
  });

afterEach(() => vi.unstubAllGlobals());

it("accepts only an unexpired assertion signed by the configured issuer for this audience", async () => {
  const trusted = await generateKeyPair("RS256");
  const unknown = await generateKeyPair("RS256");
  const jwk = await exportJWK(trusted.publicKey);
  const fetchKeys = vi.fn(async () =>
    Response.json({ keys: [{ ...jwk, kid: "access-test", alg: "RS256" }] })
  );
  vi.stubGlobal("fetch", fetchKeys);

  const sign = (
    key = trusted.privateKey,
    iss = issuer,
    aud = audience,
    expires: string | number = "5m"
  ) =>
    new SignJWT({})
      .setProtectedHeader({ alg: "RS256", kid: "access-test" })
      .setIssuer(iss)
      .setAudience(aud)
      .setIssuedAt()
      .setExpirationTime(expires)
      .sign(key);

  const valid = await sign();
  expect(await allowsCloudflareAccess(request(valid), issuer, audience)).toBe(true);
  expect(fetchKeys.mock.calls).toHaveLength(1);
  expect(await allowsCloudflareAccess(request(), issuer, audience)).toBe(false);
  expect(await allowsCloudflareAccess(request(valid), issuer, undefined)).toBe(false);
  expect(await allowsCloudflareAccess(request(valid), "https://untrusted.test", audience)).toBe(
    false
  );
  expect(await allowsCloudflareAccess(request(valid), issuer, "test-webhook")).toBe(false);
  expect(
    await allowsCloudflareAccess(request(await sign(unknown.privateKey)), issuer, audience)
  ).toBe(false);
  expect(
    await allowsCloudflareAccess(
      request(await sign(trusted.privateKey, "https://other.cloudflareaccess.com")),
      issuer,
      audience
    )
  ).toBe(false);
  expect(
    await allowsCloudflareAccess(
      request(await sign(trusted.privateKey, issuer, audience, 1)),
      issuer,
      audience
    )
  ).toBe(false);
});

it("denies requests when the issuer key service is unavailable", async () => {
  const testIssuer = "https://rail3-outage.cloudflareaccess.com";
  const { privateKey } = await generateKeyPair("RS256");
  const token = await new SignJWT({})
    .setProtectedHeader({ alg: "RS256", kid: "outage" })
    .setIssuer(testIssuer)
    .setAudience(audience)
    .setIssuedAt()
    .setExpirationTime("5m")
    .sign(privateKey);
  vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("unavailable")));
  expect(await allowsCloudflareAccess(request(token), testIssuer, audience)).toBe(false);
});
