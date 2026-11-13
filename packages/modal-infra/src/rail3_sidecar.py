"""Private Modal Sidecar: authorize requests to a single sandbox session at Cloudflare Access."""

import asyncio
import os
import re
from collections.abc import AsyncIterator
from urllib.parse import urlsplit

import aiohttp
from aiohttp import web

PORT = 8788
METHODS = {
    "GET": re.compile(
        r"(?:attachments/[a-zA-Z0-9_-]+|commit-signing|tunnel-urls|sandbox-skills|sandbox-memory(?:/[a-zA-Z0-9_-]+)?|children(?:/[a-zA-Z0-9_-]+)?)"
    ),
    "PUT": re.compile(r"diff"),
    "POST": re.compile(
        r"(?:sandbox-error|scm-credentials|commit-signing|pr|media|diff/failure|sandbox-memory(?:/search)?|openai-token-refresh|xai-token-refresh|mcp-context/close|provider-auth/[a-zA-Z0-9_-]+/(?:access-token|runtime-credential)|children(?:/[a-zA-Z0-9_-]+/(?:prompt|cancel))?)"
    ),
}
REQUEST_HEADERS = ("Authorization", "Content-Type", "X-Sandbox-ID")
RESPONSE_HEADERS = ("Content-Type", "Content-Disposition")


def _origin(value: str) -> str:
    url = urlsplit(value)
    if (
        url.scheme != "https"
        or not url.hostname
        or url.netloc != url.hostname
        or url.path not in {"", "/"}
        or url.query
        or url.fragment
        or url.hostname.endswith(".workers.dev")
    ):
        raise ValueError("Rail 3 sidecar needs the approved HTTPS control-plane origin")
    return f"https://{url.hostname}"


async def _pipe(
    source: web.WebSocketResponse | aiohttp.ClientWebSocketResponse,
    target: web.WebSocketResponse | aiohttp.ClientWebSocketResponse,
) -> None:
    async for message in source:
        if message.type == aiohttp.WSMsgType.TEXT:
            await target.send_str(message.data)
        elif message.type == aiohttp.WSMsgType.BINARY:
            await target.send_bytes(message.data)
        else:
            break


def application(
    origin: str, session_id: str, access_id: str, access_secret: str
) -> web.Application:
    origin = _origin(origin)
    if not re.fullmatch(r"[a-zA-Z0-9_-]+", session_id) or not access_id or not access_secret:
        raise ValueError("Rail 3 sidecar configuration is incomplete")
    prefix = f"/sessions/{session_id}/"
    active = asyncio.Semaphore(8)
    app = web.Application(client_max_size=32 * 1024 * 1024)

    async def upstream_client(app: web.Application) -> AsyncIterator[None]:
        async def deny_redirect(*_args: object) -> None:
            raise web.HTTPBadGateway()

        trace = aiohttp.TraceConfig()
        trace.on_request_redirect.append(deny_redirect)
        async with aiohttp.ClientSession(
            trace_configs=[trace],
            cookie_jar=aiohttp.DummyCookieJar(),
            timeout=aiohttp.ClientTimeout(total=120),
        ) as client:
            app[CLIENT] = client
            yield

    async def bounded(request: web.Request) -> web.StreamResponse:
        if active.locked():
            raise web.HTTPServiceUnavailable()
        async with active:
            return await handle(request)

    async def handle(request: web.Request) -> web.StreamResponse:
        if not request.raw_path.partition("?")[0].startswith(prefix):
            raise web.HTTPForbidden()
        suffix = request.raw_path.partition("?")[0][len(prefix) :]
        upgrade = request.headers.get("Upgrade", "").lower() == "websocket"
        if upgrade:
            if request.method != "GET" or suffix != "ws" or request.query_string != "type=sandbox":
                raise web.HTTPForbidden()
        elif request.method not in METHODS or not METHODS[request.method].fullmatch(suffix):
            raise web.HTTPForbidden()
        if not request.headers.get("Authorization", "").startswith("Bearer "):
            raise web.HTTPUnauthorized()
        headers = {key: request.headers[key] for key in REQUEST_HEADERS if key in request.headers}
        headers["CF-Access-Client-Id"] = access_id
        headers["CF-Access-Client-Secret"] = access_secret
        target = origin + request.raw_path
        client = request.app[CLIENT]
        if upgrade:
            # Prevent a redirect before sending either credential to another host.
            try:
                remote = await client.ws_connect(target, headers=headers)
            except aiohttp.WSServerHandshakeError as error:
                return web.Response(
                    status=error.status if error.status in {401, 403, 404, 410} else 502
                )
            except (aiohttp.ClientError, TimeoutError):
                raise web.HTTPBadGateway() from None
            async with remote:
                local = web.WebSocketResponse()
                await local.prepare(request)
                tasks = [
                    asyncio.create_task(_pipe(local, remote)),
                    asyncio.create_task(_pipe(remote, local)),
                ]
                try:
                    await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
                finally:
                    for task in tasks:
                        task.cancel()
                    await asyncio.gather(*tasks, return_exceptions=True)
                    await local.close()
                return local
        async with client.request(
            request.method,
            target,
            headers=headers,
            data=await request.read(),
            allow_redirects=False,
        ) as response:
            if 300 <= response.status < 400:
                raise web.HTTPBadGateway()
            relayed = web.StreamResponse(
                status=response.status,
                headers={
                    key: response.headers[key]
                    for key in RESPONSE_HEADERS
                    if key in response.headers
                },
            )
            await relayed.prepare(request)
            async for chunk in response.content.iter_chunked(64 * 1024):
                await relayed.write(chunk)
            await relayed.write_eof()
            return relayed

    app.cleanup_ctx.append(upstream_client)
    app.router.add_route("*", "/{path:.*}", bounded)
    return app


CLIENT = web.AppKey("upstream", aiohttp.ClientSession)


if __name__ == "__main__":
    web.run_app(
        application(
            os.environ["RAIL3_CONTROL_ORIGIN"],
            os.environ["RAIL3_SESSION_ID"],
            os.environ["CF_ACCESS_CLIENT_ID"],
            os.environ["CF_ACCESS_CLIENT_SECRET"],
        ),
        port=PORT,
        access_log=None,
    )
