import inspect
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from scrapling.core.url_safety import (
    CloudflareChallengeNotSolved,
    ensure_safe_url,
    verify_cloudflare_solved,
)
from scrapling.engines._browsers._base import StealthySessionMixin
from scrapling.engines._browsers._stealth import AsyncStealthySession, StealthySession
from scrapling.engines.static import AsyncFetcherClient, FetcherClient
from scrapling.engines.toolbelt.convertor import ResponseFactory
from scrapling.fetchers.requests import AsyncFetcher, Fetcher
from scrapling.fetchers.stealth_chrome import StealthyFetcher


REJECTED_URLS = [
    "file:///etc/passwd",
    "ftp://ftp.example.com/resource.txt",
    "javascript:alert(1)",
    "data:text/html,<h1>Injected</h1>",
    "http://",
    "https:///no-host",
    "example.com/no-scheme",
    "",
]

ACCEPTED_URLS = [
    "http://example.com",
    "https://example.com/path?query=1",
    "HTTP://EXAMPLE.COM/UPPER",
    "HTTPS://sub.example.com:8443/test",
]


class TestUrlSafetyAllowlist:
    @pytest.mark.parametrize("bad_url", REJECTED_URLS)
    def test_ensure_safe_url_rejects_disallowed_schemes(self, bad_url: str) -> None:
        with pytest.raises(ValueError):
            ensure_safe_url(bad_url)

    @pytest.mark.parametrize("good_url", ACCEPTED_URLS)
    def test_ensure_safe_url_accepts_http_and_https(self, good_url: str) -> None:
        assert ensure_safe_url(good_url) == good_url

    @pytest.mark.parametrize("bad_url", ["file:///etc/passwd", "ftp://example.com", "javascript:alert(1)", "data:text/plain,hi"])
    @pytest.mark.parametrize("method", ["get", "post", "put", "delete"])
    def test_static_fetcher_rejects_unsafe_urls_before_network(self, bad_url: str, method: str) -> None:
        with pytest.raises(ValueError):
            getattr(Fetcher, method)(bad_url)

        client = FetcherClient()
        with pytest.raises(ValueError):
            getattr(client, method)(bad_url)

    @pytest.mark.asyncio
    @pytest.mark.parametrize("bad_url", ["file:///etc/passwd", "ftp://example.com", "javascript:alert(1)", "data:text/plain,hi"])
    @pytest.mark.parametrize("method", ["get", "post", "put", "delete"])
    async def test_async_static_fetcher_rejects_unsafe_urls_before_network(self, bad_url: str, method: str) -> None:
        with pytest.raises(ValueError):
            await getattr(AsyncFetcher, method)(bad_url)

        client = AsyncFetcherClient()
        with pytest.raises(ValueError):
            await getattr(client, method)(bad_url)

    @pytest.mark.parametrize("bad_url", ["file:///etc/passwd", "ftp://example.com", "javascript:alert(1)", "data:text/plain,hi"])
    def test_stealth_sync_rejects_unsafe_urls_without_launching_browser(self, bad_url: str) -> None:
        with pytest.raises(ValueError):
            StealthyFetcher.fetch(bad_url)

        session = StealthySession()
        with pytest.raises(ValueError):
            session.fetch(bad_url)

    @pytest.mark.asyncio
    @pytest.mark.parametrize("bad_url", ["file:///etc/passwd", "ftp://example.com", "javascript:alert(1)", "data:text/plain,hi"])
    async def test_stealth_async_rejects_unsafe_urls_without_launching_browser(self, bad_url: str) -> None:
        with pytest.raises(ValueError):
            await StealthyFetcher.async_fetch(bad_url)

        session = AsyncStealthySession()
        with pytest.raises(ValueError):
            await session.fetch(bad_url)

    def test_mcp_server_navigation_calls_ensure_safe_url(self) -> None:
        server_path = Path(__file__).resolve().parents[2] / "scrapling" / "core" / "ai" / "server.py"
        source = server_path.read_text(encoding="utf-8")
        assert "from scrapling.core.url_safety import ensure_safe_url" in source
        assert source.count("ensure_safe_url(url)") >= 4


class TestStealthHttpsErrorsConfig:
    def test_stealthy_session_mixin_source_sets_ignore_https_errors_false(self) -> None:
        source = inspect.getsource(StealthySessionMixin)
        assert '"ignore_https_errors": False' in source
        assert '"ignore_https_errors": True' not in source

    def test_stealthy_session_context_options_ignore_https_errors_is_false(self) -> None:
        sync_session = StealthySession()
        async_session = AsyncStealthySession()
        assert sync_session._context_options["ignore_https_errors"] is False
        assert async_session._context_options["ignore_https_errors"] is False


class TestCloudflareVerification:
    @pytest.mark.parametrize(
        "challenge_html",
        [
            '<html><script src="https://challenges.cloudflare.com/turnstile/v0/api.js"></script></html>',
            '<html><body><div class="cf-turnstile"></div></body></html>',
            "<html><head><title>Just a moment...</title></head><body></body></html>",
            "<html><script>window._cf_chl_opt = {};</script></html>",
            "<html><body>Verifying you are human. This may take a few seconds.</body></html>",
        ],
    )
    def test_verify_cloudflare_solved_raises_on_challenge_markers(self, challenge_html: str) -> None:
        with pytest.raises(CloudflareChallengeNotSolved):
            verify_cloudflare_solved(challenge_html, 200)

    @pytest.mark.parametrize("status", [400, 403, 429, 503])
    def test_verify_cloudflare_solved_raises_on_error_status(self, status: int) -> None:
        clean_html = "<html><head><title>Welcome</title></head><body><p>Hello world</p></body></html>"
        with pytest.raises(CloudflareChallengeNotSolved):
            verify_cloudflare_solved(clean_html, status)

    def test_verify_cloudflare_solved_passes_on_clean_200(self) -> None:
        clean_html = "<html><head><title>Welcome</title></head><body><p>Hello world</p></body></html>"
        assert verify_cloudflare_solved(clean_html, 200) is True

    def test_stealth_fetch_verifies_cloudflare_after_solving(self, monkeypatch: pytest.MonkeyPatch) -> None:
        session = StealthySession(retries=1, solve_cloudflare=True)
        session._is_alive = True

        page = MagicMock()
        first_response = MagicMock()
        first_response.status = 403
        page.goto.return_value = first_response

        page_info = MagicMock()
        page_info.page = page

        @contextmanager
        def fake_page_gen(*args, **kwargs):
            yield page_info

        monkeypatch.setattr(session, "_page_generator", fake_page_gen)
        monkeypatch.setattr(session, "_cloudflare_solver", lambda p: None)
        monkeypatch.setattr(session, "_wait_for_page_stability", lambda p, ld, ni: None)
        monkeypatch.setattr(
            ResponseFactory,
            "_get_page_content",
            staticmethod(lambda p: "<html><title>Just a moment...</title></html>"),
        )

        with pytest.raises(CloudflareChallengeNotSolved):
            session.fetch("https://example.com")
