from __future__ import annotations

import re

MIN_FIRMWARE_MAJOR = 19
MIN_FIRMWARE_MINOR = 1
MAX_LOCAL_DNS_RECORDS_PER_MX = 1024

DNS_NAMESERVER_LABELS = {
    "upstream_dns": "Proxy to Upstream DNS",
    "google_dns": "Google Public DNS",
    "opendns": "Cisco Umbrella (OpenDNS)",
}


def parse_firmware_version(firmware: str | None) -> tuple[int, int] | None:
    if not firmware:
        return None
    numbers = [int(part) for part in re.findall(r"\d+", firmware)]
    if len(numbers) >= 2:
        return numbers[0], numbers[1]
    if len(numbers) == 1:
        return numbers[0], 0
    return None


def format_firmware_version(firmware: str | None) -> str:
    parsed = parse_firmware_version(firmware)
    if not parsed:
        return firmware or "Unknown"
    return f"{parsed[0]}.{parsed[1]}"


def firmware_meets_minimum(
    firmware: str | None,
    min_major: int = MIN_FIRMWARE_MAJOR,
    min_minor: int = MIN_FIRMWARE_MINOR,
) -> bool:
    parsed = parse_firmware_version(firmware)
    if not parsed:
        return False
    return parsed >= (min_major, min_minor)


def is_proxy_upstream_dns(dns_nameservers: str | None) -> bool:
    return (dns_nameservers or "").strip().lower() == "upstream_dns"


def format_dns_nameservers(dns_nameservers: str | None) -> str:
    if not dns_nameservers:
        return "Unknown"
    key = dns_nameservers.strip().lower()
    if key in DNS_NAMESERVER_LABELS:
        return DNS_NAMESERVER_LABELS[key]
    return dns_nameservers


def build_eligibility_checks(
    *,
    firmware: str | None,
    deployment_mode: str | None,
    is_template_bound: bool,
    subnets: list[dict],
    profile_assigned: bool,
    dns_record_count: int,
) -> list[dict]:
    checks = [
        {
            "name": "MX firmware 19.1+",
            "passed": firmware_meets_minimum(firmware),
            "detail": format_firmware_version(firmware),
        },
        {
            "name": "NAT/Routed mode",
            "passed": (deployment_mode or "").lower() == "routed",
            "detail": deployment_mode or "Unknown",
        },
        {
            "name": "Non-template MX network",
            "passed": not is_template_bound,
            "detail": "Bound to config template" if is_template_bound else "Standalone network",
        },
        {
            "name": "Local DNS profile assigned",
            "passed": profile_assigned,
            "detail": "Profile linked to network" if profile_assigned else "No profile assignment",
        },
        {
            "name": "Proxy to Upstream DNS on at least one subnet",
            "passed": any(subnet.get("proxy_upstream_dns") for subnet in subnets),
            "detail": _proxy_subnet_detail(subnets),
        },
        {
            "name": f"DNS record limit (max {MAX_LOCAL_DNS_RECORDS_PER_MX} per MX)",
            "passed": dns_record_count <= MAX_LOCAL_DNS_RECORDS_PER_MX,
            "detail": f"{dns_record_count} record(s) on assigned profile",
        },
    ]
    return checks


def _proxy_subnet_detail(subnets: list[dict]) -> str:
    enabled = sum(1 for subnet in subnets if subnet.get("proxy_upstream_dns"))
    total = len(subnets)
    if total == 0:
        return "No subnets discovered"
    return f"{enabled} of {total} subnet(s) use Proxy to Upstream DNS"


def eligibility_summary(checks: list[dict]) -> str:
    if all(check["passed"] for check in checks):
        return "Ready"
    failed = [check["name"] for check in checks if not check["passed"]]
    return f"Not ready ({len(failed)} issue(s))"


def is_local_dns_functional(checks: list[dict]) -> bool:
    return all(check["passed"] for check in checks)
