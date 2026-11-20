"""Startup warnings for a deployment that looks unsafe (security review M3, M4); they only log."""
import ipaddress
from urllib.parse import urlparse

from app.core.config import Settings


def _is_local_host(host: str) -> bool:
    """Loopback, a private address, or a name only the host's own network resolves (a Compose service)."""
    try:  # an address literal first: a public IPv6 address has no dot either
        address = ipaddress.ip_address(host.strip("[]"))
    except ValueError:
        return host == "localhost" or "." not in host or host.endswith((".local", ".internal"))
    return address.is_loopback or address.is_private or address.is_link_local


def deployment_warnings(settings: Settings) -> list[str]:
    warnings = []
    site = (settings.site_address or "").strip()
    if site and not site.startswith((":", "http://", "localhost")) and not settings.auth.cookie_secure:
        warnings.append(f"SITE_ADDRESS {site} serves HTTPS but AUTH__COOKIE_SECURE is not true: the session "
                        "cookie would also travel over plain HTTP (docs/OPERATIONS.md)")
    url = urlparse(settings.vllm_base_url or "")
    if url.hostname and not _is_local_host(url.hostname):
        if url.scheme != "https":
            warnings.append("VLLM_BASE_URL is not on this network and not https: original student text "
                            "would cross the internet unencrypted (docs/DEMO_VLLM.md)")
        if settings.vllm_key is None:
            warnings.append("VLLM_BASE_URL is not on this network and VLLM_KEY is empty: the server must "
                            "run with --api-key (docs/DEMO_VLLM.md)")
    return warnings
