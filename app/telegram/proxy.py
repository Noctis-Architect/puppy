from __future__ import annotations

from typing import Any

from telethon.network import ConnectionTcpMTProxyRandomizedIntermediate

from app.config import ProxyConfig

FALLBACK_PROXIES: list[tuple[Any, ...]] = [
    ("socks5", "127.0.0.1", 10808),
    ("socks5", "127.0.0.1", 1080),
    ("socks5", "127.0.0.1", 9050),
    ("http", "127.0.0.1", 8080),
]


def proxy_label(proxy: tuple[Any, ...] | None) -> str:
    if proxy is None:
        return "direct"
    return f"{proxy[0]} {proxy[1]}:{proxy[2]}"


def proxy_to_tuple(proxy: ProxyConfig) -> tuple[Any, ...]:
    if proxy.type == "mtproxy":
        if not proxy.secret:
            raise ValueError("MTProxy secret is required.")
        return ("mtproxy", proxy.host, proxy.port, proxy.secret)
    if proxy.username and proxy.password:
        return (proxy.type, proxy.host, proxy.port, True, proxy.username, proxy.password)
    return (proxy.type, proxy.host, proxy.port)


def client_kwargs_for_proxy(proxy: tuple[Any, ...] | None) -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "connection_retries": 3,
        "retry_delay": 2,
        "timeout": 30,
    }
    if proxy and proxy[0] == "mtproxy":
        kwargs["connection"] = ConnectionTcpMTProxyRandomizedIntermediate
        kwargs["proxy"] = proxy
    elif proxy:
        kwargs["proxy"] = proxy
    return kwargs
