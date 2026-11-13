from ipaddress import ip_address, ip_network
from urllib.parse import urlsplit


_LAN_NETWORKS = tuple(ip_network(value) for value in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "127.0.0.0/8", "::1/128", "fc00::/7"))


def local_browser_origin(origin: str | None, host: str | None, scheme: str) -> bool:
    """Permit only same-origin requests to a literal LAN address or localhost."""
    if not origin or not host or scheme not in {"http", "https"} or origin != f"{scheme}://{host}":
        return False
    try:
        parsed = urlsplit(origin)
        if parsed.username is not None or parsed.password is not None or parsed.hostname is None:
            return False
        if parsed.hostname == "localhost":
            return True
        address = ip_address(parsed.hostname)
        return any(address in network for network in _LAN_NETWORKS)
    except ValueError:
        return False
