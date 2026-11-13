import aiohttp
import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from src import rail3_sidecar

SESSION = "/sessions/session-1"
AUTH = {"Authorization": "Bearer sandbox-session-token"}


@pytest.mark.asyncio
async def test_private_sidecar_routes_only_its_session_and_keeps_access_secret_upstream(
    monkeypatch,
):
    received = []

    async def upstream(request):
        received.append((request.path, request.headers["CF-Access-Client-Secret"]))
        assert request.headers["Authorization"] == AUTH["Authorization"]
        if request.path.endswith("/ws"):
            socket = web.WebSocketResponse()
            await socket.prepare(request)
            async for msg in socket:
                await socket.send_str(msg.data)
            return socket
        return web.Response(text="ok", headers={"Set-Cookie": "CF_Authorization=do-not-forward"})

    remote = web.Application()
    remote.router.add_route("*", "/{path:.*}", upstream)
    async with TestServer(remote) as server:
        monkeypatch.setattr(
            rail3_sidecar, "_origin", lambda _: str(server.make_url("/")).rstrip("/")
        )
        proxy = rail3_sidecar.application("https://control.example", "session-1", "id", "canary")
        async with TestClient(TestServer(proxy)) as local:
            for path in (
                "/sessions/other/pr",
                "/webhooks/automation/docs",
                f"{SESSION}/archive",
                f"{SESSION}/%2E%2E/admin",
            ):
                response = await local.post(path, headers=AUTH)
                assert response.status == 403
            assert (await local.post(f"{SESSION}/pr")).status == 401
            assert received == []
            response = await local.post(
                f"{SESSION}/pr",
                headers={**AUTH, "CF-Access-Client-Secret": "caller-supplied"},
            )
            assert await response.text() == "ok"
            assert "Set-Cookie" not in response.headers
            async with local.ws_connect(f"{SESSION}/ws?type=sandbox", headers=AUTH) as ws:
                await ws.send_str("probe")
                assert await ws.receive_str() == "probe"
            assert received == [(f"{SESSION}/pr", "canary"), (f"{SESSION}/ws", "canary")]


@pytest.mark.asyncio
async def test_neither_http_nor_websocket_follows_upstream_redirect(monkeypatch):
    async def redirect(request):
        if request.path == "/other-destination":
            pytest.fail("proxy followed redirect")
        raise web.HTTPFound("/other-destination")

    remote = web.Application()
    remote.router.add_route("*", "/{path:.*}", redirect)
    async with TestServer(remote) as server:
        monkeypatch.setattr(
            rail3_sidecar, "_origin", lambda _: str(server.make_url("/")).rstrip("/")
        )
        proxy = rail3_sidecar.application("https://control.example", "session-1", "id", "canary")
        async with TestClient(TestServer(proxy)) as local:
            assert (await local.post(f"{SESSION}/pr", headers=AUTH)).status == 502
            with pytest.raises(aiohttp.WSServerHandshakeError) as refused:
                await local.ws_connect(f"{SESSION}/ws?type=sandbox", headers=AUTH)
            assert refused.value.status == 502
