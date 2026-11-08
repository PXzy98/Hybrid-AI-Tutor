"""Where a model connection may point (task Z6, guide 4.11: SSRF protection).

Checked when a connection is saved and again before every call (the name may resolve elsewhere later):
- only http(s) URLs without credentials in them;
- never link-local addresses (169.254.0.0/16 including cloud metadata, fe80::/10) or other special ranges
  (multicast, unspecified, reserved);
- never the system's own services (`db`, `api`, `web`, `worker`, `proxy`, `caddy`, ... and their addresses);
- external connections also never private ranges (10/8, 172.16/12, 192.168/16, fc00::/7) or loopback: they
  must be public services. A trusted local connection may be private (the deployment's own vLLM/Ollama).
"""
import ipaddress
import socket
from functools import lru_cache
from urllib.parse import urlparse

SYSTEM_SERVICES = {"db", "postgres", "api", "web", "worker", "proxy", "caddy", "prometheus", "grafana"}


class UnsafeEndpoint(ValueError):
    """The URL may not be used for a model connection (the message is safe to show)."""


def _addresses(host: str) -> list[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    try:
        return [ipaddress.ip_address(host)]
    except ValueError:
        pass
    try:
        infos = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except socket.gaierror as e:
        raise UnsafeEndpoint(f"the host name {host!r} cannot be resolved") from e
    return [ipaddress.ip_address(info[4][0].split("%")[0]) for info in infos]


@lru_cache(maxsize=1)
def _system_addresses() -> frozenset:
    """Addresses of the system's own services in this deployment (best effort; unknown names are skipped)."""
    found = set()
    for name in SYSTEM_SERVICES:
        try:
            found.update(ipaddress.ip_address(i[4][0].split("%")[0])
                         for i in socket.getaddrinfo(name, None, type=socket.SOCK_STREAM))
        except (socket.gaierror, OSError, ValueError):
            continue
    return frozenset(found)


def check_endpoint_url(url: str, *, trust: str, resolve=_addresses, system=_system_addresses) -> str:
    """The normalized URL, or UnsafeEndpoint."""
    parsed = urlparse((url or "").strip())
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise UnsafeEndpoint("use an http(s) address, e.g. https://api.example.com/v1")
    if parsed.username or parsed.password:
        raise UnsafeEndpoint("do not put credentials in the address; use the API key field")
    host = parsed.hostname.lower().rstrip(".")
    if host in SYSTEM_SERVICES:
        raise UnsafeEndpoint("this address belongs to the system itself")
    if host == "metadata.google.internal":
        raise UnsafeEndpoint("link-local and special addresses (e.g. cloud metadata) are not allowed")
    own = system()
    for ip in resolve(host):
        if ip in own:
            raise UnsafeEndpoint("this address belongs to the system itself")
        if ip.is_link_local or ip.is_multicast or ip.is_unspecified or ip.is_reserved:
            raise UnsafeEndpoint("link-local and special addresses (e.g. cloud metadata) are not allowed")
        if trust != "trusted_local" and (ip.is_private or ip.is_loopback):
            raise UnsafeEndpoint("an external connection must be a public address")
    return url.strip().rstrip("/")
