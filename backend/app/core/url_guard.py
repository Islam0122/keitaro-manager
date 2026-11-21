"""SSRF protection for the user-supplied Keitaro API URL.

The backend sends the Keitaro API key to this URL, and the "test connection" endpoint reports errors back to the
caller, so a malicious URL could be used to reach internal services or cloud metadata endpoints. Rules:

* scheme must be ``https`` (``http`` only when ``KEITARO_ALLOW_HTTP=true``);
* no user-info (``user:pass@host``), no query string or fragment;
* the host must not be a known internal name (``localhost``, ``metadata.google.internal`` ...);
* every address the host resolves to must be globally routable — loopback, private (RFC1918, ULA), link-local
  (incl. ``169.254.169.254``), CGNAT, multicast, reserved and unspecified ranges are rejected.

``KEITARO_ALLOW_PRIVATE_HOSTS=true`` (local development only) permits loopback/private addresses, but link-local and
cloud-metadata addresses stay blocked in every mode.

The check runs when settings are saved and again every time a client is built, which narrows (but cannot fully close)
the DNS-rebinding window; redirects are never followed by the client.
"""
from __future__ import annotations

import asyncio
import ipaddress
import socket
from collections.abc import Awaitable, Callable
from urllib.parse import urlsplit

Resolver = Callable[[str, int], Awaitable[list[str]]]

# Cloud metadata services: blocked ALWAYS, even with KEITARO_ALLOW_PRIVATE_HOSTS=true.
METADATA_HOSTNAMES = {
    "metadata",
    "metadata.google.internal",
    "metadata.goog",
    "instance-data",
    "instance-data.ec2.internal",
    "metadata.azure.com",
}
BLOCKED_HOSTNAMES = {"localhost", "localhost.localdomain", "ip6-localhost", "ip6-loopback", *METADATA_HOSTNAMES}
BLOCKED_SUFFIXES = (".localhost", ".local", ".internal", ".intranet", ".lan", ".home.arpa")
# 169.254.0.0/16 and fe80::/10 hold the AWS/GCP/Azure/OpenStack metadata endpoints (169.254.169.254, fd00:ec2::254 ...)
ALWAYS_BLOCKED_NETWORKS = [
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("fe80::/10"),
    ipaddress.ip_network("fd00:ec2::254/128"),
    ipaddress.ip_network("100.100.100.200/32"),  # Alibaba Cloud metadata
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("::/128"),
]


class UnsafeURLError(ValueError):
    """The URL is not allowed as a Keitaro endpoint."""


async def system_resolver(host: str, port: int) -> list[str]:
    loop = asyncio.get_running_loop()
    infos = await loop.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    return sorted({str(info[4][0]) for info in infos})


IPAddress = ipaddress.IPv4Address | ipaddress.IPv6Address


def _unmap(ip: IPAddress) -> IPAddress:
    if isinstance(ip, ipaddress.IPv6Address):
        mapped = ip.ipv4_mapped or ip.sixtofour
        if mapped is not None:
            return mapped
    return ip


def _always_blocked(ip: IPAddress) -> bool:
    ip = _unmap(ip)
    return ip.is_multicast or any(ip in net for net in ALWAYS_BLOCKED_NETWORKS if ip.version == net.version)


def _is_public(ip: IPAddress) -> bool:
    if isinstance(ip, ipaddress.IPv6Address):
        mapped = ip.ipv4_mapped or ip.sixtofour
        if mapped is not None:
            return _is_public(mapped)
    return ip.is_global and not (ip.is_multicast or ip.is_reserved or ip.is_loopback or ip.is_link_local)


class URLGuard:
    def __init__(
        self, *, allow_http: bool = False, allow_private: bool = False, resolver: Resolver = system_resolver
    ) -> None:
        self.allow_http = allow_http
        self.allow_private = allow_private
        self.resolver = resolver

    def check_syntax(self, url: str) -> tuple[str, int]:
        try:
            parts = urlsplit(url.strip())
            port = parts.port
        except ValueError as exc:
            raise UnsafeURLError("Некорректный URL") from exc
        allowed = {"https", "http"} if self.allow_http else {"https"}
        if parts.scheme not in allowed:
            raise UnsafeURLError(
                "Разрешены только https-адреса" if not self.allow_http else "URL должен начинаться с http:// или https://"
            )
        if parts.username or parts.password:
            raise UnsafeURLError("URL не должен содержать логин и пароль")
        if parts.query or parts.fragment:
            raise UnsafeURLError("URL не должен содержать параметры запроса или фрагмент")
        host = (parts.hostname or "").rstrip(".").lower()
        if not host:
            raise UnsafeURLError("В URL не указан хост")
        if host in METADATA_HOSTNAMES:
            raise UnsafeURLError("Адрес указывает на служебный metadata-сервис")
        if not self.allow_private and (host in BLOCKED_HOSTNAMES or host.endswith(BLOCKED_SUFFIXES)):
            raise UnsafeURLError("Адрес указывает на внутренний хост")
        return host, port or (443 if parts.scheme == "https" else 80)

    async def validate(self, url: str) -> str:
        """Return the normalised URL or raise :class:`UnsafeURLError`."""
        host, port = self.check_syntax(url)
        try:
            addresses = [ipaddress.ip_address(host)]
        except ValueError:
            try:
                resolved = await self.resolver(host, port)
            except (OSError, UnicodeError) as exc:
                raise UnsafeURLError(f"Не удалось разрешить имя хоста {host}") from exc
            if not resolved:
                raise UnsafeURLError(f"Не удалось разрешить имя хоста {host}") from None
            addresses = [ipaddress.ip_address(a.split("%")[0]) for a in resolved]
        if any(_always_blocked(ip) for ip in addresses):
            raise UnsafeURLError("Адрес указывает на служебную сеть (link-local / metadata)")
        if not self.allow_private and not all(_is_public(ip) for ip in addresses):
            raise UnsafeURLError("Адрес указывает на локальную, частную или служебную сеть")
        return url.strip().rstrip("/")
