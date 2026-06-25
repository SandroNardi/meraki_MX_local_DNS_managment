from __future__ import annotations

import ipaddress
import re

HOSTNAME_RE = re.compile(
    r"^(?=.{1,253}$)(?!-)[A-Za-z0-9-]{1,63}(?<!-)"
    r"(\.(?!-)[A-Za-z0-9-]{1,63}(?<!-))*\.?$"
)
PROFILE_NAME_RE = re.compile(r"^[\w .\-]{1,128}$")


def validate_hostname(hostname: str) -> tuple[bool, str]:
    hostname = (hostname or "").strip()
    if not hostname:
        return False, "Hostname is required."
    if len(hostname) > 253:
        return False, "Hostname must be 253 characters or fewer."
    if not HOSTNAME_RE.match(hostname):
        return False, "Hostname format is invalid."
    return True, ""


def validate_ip_address(address: str) -> tuple[bool, str]:
    address = (address or "").strip()
    if not address:
        return False, "IP address is required."
    try:
        ipaddress.ip_address(address)
    except ValueError:
        return False, "IP address must be a valid IPv4 or IPv6 address."
    return True, ""


def validate_profile_name(name: str) -> tuple[bool, str]:
    name = (name or "").strip()
    if not name:
        return False, "Profile name is required."
    if not PROFILE_NAME_RE.match(name):
        return False, "Profile name may only contain letters, numbers, spaces, dots, hyphens, and underscores."
    return True, ""
