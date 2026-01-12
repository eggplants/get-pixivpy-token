from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

import gppt.gppt as gppt_module
from gppt.gppt import GetPixivToken


@dataclass
class DummyPage:
    handlers: dict[str, Any] = field(default_factory=dict)

    def on(self, event: str, handler: Any) -> None:
        self.handlers[event] = handler


@dataclass
class DummyContext:
    options: dict[str, Any]
    page: DummyPage = field(default_factory=DummyPage)

    async def new_page(self) -> DummyPage:
        return self.page


@dataclass
class DummyBrowser:
    created_contexts: list[DummyContext] = field(default_factory=list)
    closed: bool = False

    async def new_context(self, **options: Any) -> DummyContext:
        ctx = DummyContext(options=options)
        self.created_contexts.append(ctx)
        return ctx

    async def close(self) -> None:
        self.closed = True


@dataclass
class DummyChromium:
    last_launch: dict[str, Any] | None = None
    browser: DummyBrowser = field(default_factory=DummyBrowser)

    async def launch(self, *, headless: bool, args: list[str]) -> DummyBrowser:
        self.last_launch = {"headless": headless, "args": args}
        return self.browser


@dataclass
class DummyPlaywright:
    chromium: DummyChromium = field(default_factory=DummyChromium)


def test_setup_browser_calls_install_and_creates_page(monkeypatch: Any) -> None:
    install_calls: list[dict[str, Any]] = []

    def fake_install(browsers: list[Any], *, with_deps: bool) -> None:
        install_calls.append({"browsers": browsers, "with_deps": with_deps})

    def fake_get_browser_options(*, headless: bool | None) -> dict[str, Any]:
        return {
            "headless": True if headless is None else bool(headless),
            "args": ["--unit-test-arg"],
            "proxy": {"server": "http://proxy.invalid:3128"},
        }

    monkeypatch.setattr(gppt_module, "install", fake_install)
    monkeypatch.setattr(gppt_module, "_get_browser_options", fake_get_browser_options)

    token = GetPixivToken(headless=True)
    p = DummyPlaywright()

    asyncio.run(token._GetPixivToken__setup_browser(p))

    assert len(install_calls) == 1
    assert install_calls[0]["browsers"] == [p.chromium]
    assert install_calls[0]["with_deps"] is True

    assert token.browser is p.chromium.browser
    assert token.context is not None
    assert getattr(token.context, "options", {}) == {"proxy": {"server": "http://proxy.invalid:3128"}}
    assert token.page is not None
    assert isinstance(token.page, DummyPage)
    assert "request" in token.page.handlers
