import json
import meraki
import streamlit as st
from core.api import session
from core.logger import logger
from mx_requirements import (
    MAX_LOCAL_DNS_RECORDS_PER_MX,
    build_eligibility_checks,
    eligibility_summary,
    format_dns_nameservers,
    format_firmware_version,
    is_local_dns_functional,
    is_proxy_upstream_dns,
)
from validators import validate_hostname, validate_ip_address, validate_profile_name

API_CALL_COUNTER = 0

CACHE_CONFIG = {
    "short": 300,
    "medium": 3600,
    "long": 86400,
}

CONFIG_VERSION = 1


def _increment_counter(endpoint):
    global API_CALL_COUNTER
    API_CALL_COUNTER += 1
    logger.info(
        f"[bold cyan][API CALL #{API_CALL_COUNTER}][/] SDK Method: [green]{endpoint}[/]"
    )


def _net_tags(network):
    tags = network.get("tags") or []
    if isinstance(tags, list):
        return {t.strip() for t in tags if isinstance(t, str) and t.strip()}
    if isinstance(tags, str) and tags.strip():
        return {t.strip() for t in tags.split() if t.strip()}
    return set()


def get_unique_network_tags(networks):
    tags = set()
    for network in networks:
        tags.update(_net_tags(network))
    return sorted(tags)


def filter_mx_networks(
    networks,
    tag_filter=None,
    tag_filter_type="withAnyTags",
    name_search="",
):
    mx_networks = [
        n
        for n in networks
        if "appliance" in (n.get("productTypes") or [])
    ]
    search = (name_search or "").strip().lower()
    if search:
        mx_networks = [
            n for n in mx_networks if search in (n.get("name") or "").lower()
        ]
    if tag_filter:
        if tag_filter_type == "withAllTags":
            mx_networks = [
                n
                for n in mx_networks
                if all(tag in _net_tags(n) for tag in tag_filter)
            ]
        else:
            mx_networks = [
                n
                for n in mx_networks
                if any(tag in _net_tags(n) for tag in tag_filter)
            ]
    return mx_networks


def format_network_tags(network):
    return ", ".join(sorted(_net_tags(network)))


class ProjectLogic:
    """Business logic layer for managing Meraki MX Local DNS profiles, records, and assignments."""

    def __init__(self):
        self.dashboard = session.get_dashboard()
        logger.info("[bold green]ProjectLogic initialized with Meraki SDK.[/]")

    @st.cache_data(ttl=CACHE_CONFIG["long"])
    def get_organizations(_self):
        _increment_counter("organizations.getOrganizations")
        return _self.dashboard.organizations.getOrganizations()

    @st.cache_data(ttl=CACHE_CONFIG["medium"])
    def get_networks(_self, organization_id):
        _increment_counter("organizations.getOrganizationNetworks")
        return _self.dashboard.organizations.getOrganizationNetworks(
            organizationId=organization_id,
            total_pages="all",
        )

    def fetch_mx_networks_live(self, org_id):
        """Fresh MX/appliance network list — never cached."""
        _increment_counter("organizations.getOrganizationNetworks (live)")
        try:
            networks = self.dashboard.organizations.getOrganizationNetworks(
                organizationId=org_id,
                productTypes=["appliance"],
                total_pages="all",
            )
            return networks
        except meraki.APIError as e:
            logger.error(f"[bold red]SDK Error (fetch_mx_networks_live): {e}[/]")
            return []

    def fetch_live_dns_state(self, org_id):
        """Fetch profiles, records, and assignments in one live snapshot."""
        profiles = self.list_profiles(org_id)
        records = self.list_dns_records(org_id)
        assignments = self.list_assignments(org_id)
        return profiles, records, assignments

    def fetch_organization_appliances_live(self, org_id):
        """Fresh appliance device list keyed by network — never cached."""
        _increment_counter("organizations.getOrganizationDevices (live)")
        try:
            devices = self.dashboard.organizations.getOrganizationDevices(
                organizationId=org_id,
                productTypes=["appliance"],
                total_pages="all",
            )
            by_network = {}
            for device in devices:
                network_id = device.get("networkId")
                if network_id:
                    by_network.setdefault(network_id, []).append(device)
            return by_network
        except meraki.APIError as e:
            logger.error(f"[bold red]SDK Error (fetch_organization_appliances_live): {e}[/]")
            return {}

    def fetch_network_appliance_settings_live(self, network_id):
        _increment_counter("appliance.getNetworkApplianceSettings (live)")
        try:
            return self.dashboard.appliance.getNetworkApplianceSettings(network_id)
        except meraki.APIError as e:
            logger.warning(f"Could not fetch appliance settings for {network_id}: {e}")
            return {}

    def fetch_network_subnets_live(self, network_id):
        """Return subnet/VLAN rows with Proxy to Upstream DNS status."""
        _increment_counter("appliance.getNetworkApplianceVlansSettings (live)")
        subnets = []
        vlans_enabled = True
        try:
            vlan_settings = self.dashboard.appliance.getNetworkApplianceVlansSettings(
                network_id
            )
            vlans_enabled = vlan_settings.get("vlansEnabled", True)
        except meraki.APIError:
            vlans_enabled = True

        if vlans_enabled:
            _increment_counter("appliance.getNetworkApplianceVlans (live)")
            try:
                vlans = self.dashboard.appliance.getNetworkApplianceVlans(network_id)
                for vlan in vlans:
                    dns_nameservers = vlan.get("dnsNameservers")
                    subnets.append(
                        {
                            "subnet_key": str(vlan.get("id", "")),
                            "name": vlan.get("name") or f"VLAN {vlan.get('id')}",
                            "subnet": vlan.get("subnet") or "",
                            "dns_nameservers": dns_nameservers,
                            "dns_label": format_dns_nameservers(dns_nameservers),
                            "proxy_upstream_dns": is_proxy_upstream_dns(dns_nameservers),
                            "dhcp_handling": vlan.get("dhcpHandling") or "",
                        }
                    )
            except meraki.APIError as e:
                logger.warning(f"Could not fetch VLANs for {network_id}: {e}")
        else:
            _increment_counter("appliance.getNetworkApplianceSingleLan (live)")
            single_lan = {}
            try:
                single_lan = self.dashboard.appliance.getNetworkApplianceSingleLan(
                    network_id
                )
            except meraki.APIError:
                single_lan = {}

            dns_nameservers = None
            proxy_upstream_dns = False
            vlan_name = "Single LAN"
            vlan_subnet = single_lan.get("subnet", "")
            vlan_id = "1"

            _increment_counter("appliance.getNetworkApplianceVlan (live)")
            try:
                vlan = self.dashboard.appliance.getNetworkApplianceVlan(network_id, "1")
                dns_nameservers = vlan.get("dnsNameservers")
                proxy_upstream_dns = is_proxy_upstream_dns(dns_nameservers)
                vlan_name = vlan.get("name") or vlan_name
                vlan_subnet = vlan.get("subnet") or vlan_subnet
                vlan_id = str(vlan.get("id", "1"))
            except meraki.APIError:
                pass

            subnets.append(
                {
                    "subnet_key": vlan_id,
                    "name": vlan_name,
                    "subnet": vlan_subnet,
                    "dns_nameservers": dns_nameservers,
                    "dns_label": format_dns_nameservers(dns_nameservers),
                    "proxy_upstream_dns": proxy_upstream_dns,
                    "dhcp_handling": "Run a DHCP server",
                }
            )

        return subnets

    def assess_mx_network(
        self,
        network,
        appliances,
        profile_id,
        profile_name,
        profile_records,
        assignment_id,
    ):
        network_id = network.get("id")
        primary_appliance = appliances[0] if appliances else {}
        firmware = primary_appliance.get("firmware")
        settings = self.fetch_network_appliance_settings_live(network_id)
        subnets = self.fetch_network_subnets_live(network_id)
        is_template_bound = bool(network.get("isBoundToConfigTemplate"))
        deployment_mode = settings.get("deploymentMode")
        dns_record_count = len(profile_records)
        profile_assigned = profile_id is not None

        checks = build_eligibility_checks(
            firmware=firmware,
            deployment_mode=deployment_mode,
            is_template_bound=is_template_bound,
            subnets=subnets,
            profile_assigned=profile_assigned,
            dns_record_count=dns_record_count,
        )
        proxy_subnet_count = sum(
            1 for subnet in subnets if subnet.get("proxy_upstream_dns")
        )

        return {
            "network_id": network_id,
            "network_name": network.get("name", "Unknown"),
            "tags": format_network_tags(network),
            "firmware": firmware or "",
            "firmware_display": format_firmware_version(firmware),
            "deployment_mode": deployment_mode or "Unknown",
            "is_template_bound": is_template_bound,
            "status": "Configured" if profile_assigned else "Not configured",
            "profile_id": profile_id or "",
            "profile_name": profile_name or "",
            "dns_record_count": dns_record_count,
            "assignment_id": assignment_id or "",
            "records": profile_records,
            "subnets": subnets,
            "proxy_subnet_count": proxy_subnet_count,
            "total_subnet_count": len(subnets),
            "checks": checks,
            "eligibility": eligibility_summary(checks),
            "local_dns_functional": is_local_dns_functional(checks),
            "record_limit_ok": dns_record_count <= MAX_LOCAL_DNS_RECORDS_PER_MX,
        }

    def build_mx_overview(self, org_id, progress_callback=None):
        """
        Build a per-MX overview with eligibility checks and subnet-level DNS proxy data.
        Always uses live API data.
        """
        mx_networks = self.fetch_mx_networks_live(org_id)
        appliances_by_network = self.fetch_organization_appliances_live(org_id)
        profiles, records, assignments = self.fetch_live_dns_state(org_id)

        profile_lookup = {p["profileId"]: p for p in profiles}
        records_by_profile = {}
        for record in records:
            profile_id = (record.get("profile") or {}).get("id")
            if profile_id:
                records_by_profile.setdefault(profile_id, []).append(record)

        assignment_by_network = {}
        for assignment in assignments:
            network_id = (assignment.get("network") or {}).get("id")
            if network_id:
                assignment_by_network[network_id] = assignment

        rows = []
        configured = 0
        functional = 0
        total_proxy_subnets = 0
        total = len(mx_networks)

        for index, network in enumerate(mx_networks, start=1):
            if progress_callback:
                progress_callback(
                    f"Assessing {network.get('name', 'network')} ({index}/{total})",
                    index,
                    total,
                )

            network_id = network.get("id")
            assignment = assignment_by_network.get(network_id)
            profile_id = (assignment.get("profile") or {}).get("id") if assignment else None
            profile = profile_lookup.get(profile_id) if profile_id else None
            profile_records = records_by_profile.get(profile_id, []) if profile_id else []

            row = self.assess_mx_network(
                network,
                appliances_by_network.get(network_id, []),
                profile_id,
                profile.get("name", "") if profile else "",
                profile_records,
                assignment.get("assignmentId", "") if assignment else "",
            )
            rows.append(row)

            if profile_id:
                configured += 1
            if row["local_dns_functional"]:
                functional += 1
            total_proxy_subnets += row["proxy_subnet_count"]

        return {
            "rows": rows,
            "summary": {
                "total_mx": total,
                "configured_mx": configured,
                "unconfigured_mx": total - configured,
                "functional_mx": functional,
                "total_profiles": len(profiles),
                "total_records": len(records),
                "total_proxy_subnets": total_proxy_subnets,
            },
        }

    def validate_networks_for_local_dns(self, org_id, network_ids):
        """Return per-network eligibility warnings before assignment/import."""
        if not network_ids:
            return []

        mx_networks = self.fetch_mx_networks_live(org_id)
        network_lookup = {network["id"]: network for network in mx_networks}
        appliances_by_network = self.fetch_organization_appliances_live(org_id)
        warnings = []

        for network_id in network_ids:
            network = network_lookup.get(network_id)
            if not network:
                warnings.append(
                    {
                        "network_id": network_id,
                        "network_name": network_id,
                        "issues": ["Network is not an MX/appliance network in this org."],
                    }
                )
                continue

            row = self.assess_mx_network(
                network,
                appliances_by_network.get(network_id, []),
                None,
                "",
                [],
                "",
            )
            issues = [
                f"{check['name']}: {check['detail']}"
                for check in row["checks"]
                if not check["passed"]
                and check["name"] != "Local DNS profile assigned"
            ]
            if issues:
                warnings.append(
                    {
                        "network_id": network_id,
                        "network_name": row["network_name"],
                        "issues": issues,
                    }
                )
        return warnings

    def list_profiles(self, org_id):
        _increment_counter("appliance.getOrganizationApplianceDnsLocalProfiles")
        try:
            response = self.dashboard.appliance.getOrganizationApplianceDnsLocalProfiles(
                org_id
            )
            return response.get("items", [])
        except meraki.APIError as e:
            logger.error(f"[bold red]SDK Error (list_profiles): {e}[/]")
            return []

    def create_profile(self, org_id, name):
        valid, message = validate_profile_name(name)
        if not valid:
            return {"error": message}

        _increment_counter("appliance.createOrganizationApplianceDnsLocalProfile")
        try:
            return self.dashboard.appliance.createOrganizationApplianceDnsLocalProfile(
                org_id, name.strip()
            )
        except meraki.APIError as e:
            logger.error(f"[bold red]SDK Error (create_profile): {e}[/]")
            return {"error": str(e)}

    def list_dns_records(self, org_id, profile_ids=None):
        _increment_counter("appliance.getOrganizationApplianceDnsLocalRecords")
        try:
            kwargs = {}
            if profile_ids:
                kwargs["profileIds"] = profile_ids
            response = self.dashboard.appliance.getOrganizationApplianceDnsLocalRecords(
                org_id, **kwargs
            )
            return response.get("items", [])
        except meraki.APIError as e:
            logger.error(f"[bold red]SDK Error (list_dns_records): {e}[/]")
            return []

    def create_dns_record(self, org_id, profile_id, hostname, address):
        valid_host, host_msg = validate_hostname(hostname)
        if not valid_host:
            return {"error": host_msg}
        valid_ip, ip_msg = validate_ip_address(address)
        if not valid_ip:
            return {"error": ip_msg}

        _increment_counter("appliance.createOrganizationApplianceDnsLocalRecord")
        try:
            existing = self.list_dns_records(org_id, profile_ids=[profile_id])
            if len(existing) >= MAX_LOCAL_DNS_RECORDS_PER_MX:
                return {
                    "error": (
                        f"Profile already has the maximum of "
                        f"{MAX_LOCAL_DNS_RECORDS_PER_MX} local DNS records per MX."
                    )
                }
            profile = {"id": profile_id}
            return self.dashboard.appliance.createOrganizationApplianceDnsLocalRecord(
                org_id, hostname.strip(), address.strip(), profile
            )
        except meraki.APIError as e:
            logger.error(f"[bold red]SDK Error (create_dns_record): {e}[/]")
            return {"error": str(e)}

    def update_dns_record(self, org_id, record_id, profile_id, hostname, address):
        valid_host, host_msg = validate_hostname(hostname)
        if not valid_host:
            return {"error": host_msg}
        valid_ip, ip_msg = validate_ip_address(address)
        if not valid_ip:
            return {"error": ip_msg}

        _increment_counter("appliance.updateOrganizationApplianceDnsLocalRecord")
        try:
            profile = {"id": profile_id}
            return self.dashboard.appliance.updateOrganizationApplianceDnsLocalRecord(
                org_id,
                record_id,
                hostname.strip(),
                address.strip(),
                profile,
            )
        except meraki.APIError as e:
            logger.error(f"[bold red]SDK Error (update_dns_record): {e}[/]")
            return {"error": str(e)}

    def list_assignments(self, org_id):
        _increment_counter("appliance.getOrganizationApplianceDnsLocalProfilesAssignments")
        try:
            response = (
                self.dashboard.appliance.getOrganizationApplianceDnsLocalProfilesAssignments(
                    org_id
                )
            )
            return response.get("items", [])
        except meraki.APIError as e:
            logger.error(f"[bold red]SDK Error (list_assignments): {e}[/]")
            return []

    def bulk_assign_profile(self, org_id, network_ids, profile_id):
        if not network_ids:
            return {"error": "Select at least one MX network."}
        if not profile_id:
            return {"error": "Select a profile."}

        _increment_counter("appliance.bulkOrganizationApplianceDnsLocalProfilesAssignmentsCreate")
        try:
            items = [
                {"network": {"id": network_id}, "profile": {"id": profile_id}}
                for network_id in network_ids
            ]
            return self.dashboard.appliance.bulkOrganizationApplianceDnsLocalProfilesAssignmentsCreate(
                org_id, items
            )
        except meraki.APIError as e:
            logger.error(f"[bold red]SDK Error (bulk_assign_profile): {e}[/]")
            return {"error": str(e)}

    def assign_profile(self, org_id, network_id, profile_id):
        return self.bulk_assign_profile(org_id, [network_id], profile_id)

    def bulk_remove_assignments(self, org_id, assignment_ids):
        if not assignment_ids:
            return {"error": "Select at least one assignment."}

        _increment_counter(
            "appliance.createOrganizationApplianceDnsLocalProfilesAssignmentsBulkDelete"
        )
        try:
            items = [{"assignmentId": assignment_id} for assignment_id in assignment_ids]
            res = self.dashboard.appliance.createOrganizationApplianceDnsLocalProfilesAssignmentsBulkDelete(
                org_id, items
            )
            return res if res is not None else {}
        except meraki.APIError as e:
            logger.error(f"[bold red]SDK Error (bulk_remove_assignments): {e}[/]")
            return {"error": str(e)}

    def remove_assignment(self, org_id, assignment_id):
        return self.bulk_remove_assignments(org_id, [assignment_id])

    def delete_profile(self, org_id, profile_id):
        _increment_counter("appliance.deleteOrganizationApplianceDnsLocalProfile")
        try:
            res = self.dashboard.appliance.deleteOrganizationApplianceDnsLocalProfile(
                org_id, profile_id
            )
            return res if res is not None else {}
        except meraki.APIError as e:
            logger.error(f"[bold red]SDK Error (delete_profile): {e}[/]")
            return {"error": str(e)}

    def delete_dns_record(self, org_id, record_id):
        _increment_counter("appliance.deleteOrganizationApplianceDnsLocalRecord")
        try:
            res = self.dashboard.appliance.deleteOrganizationApplianceDnsLocalRecord(
                org_id, record_id
            )
            return res if res is not None else {}
        except meraki.APIError as e:
            logger.error(f"[bold red]SDK Error (delete_dns_record): {e}[/]")
            return {"error": str(e)}

    def bulk_delete_dns_records(self, org_id, record_ids):
        results = {"deleted": 0, "errors": []}
        for record_id in record_ids:
            res = self.delete_dns_record(org_id, record_id)
            if res and "error" in res:
                results["errors"].append({"record_id": record_id, "error": res["error"]})
            else:
                results["deleted"] += 1
        return results

    def export_profile_config(self, org_id, profile_id):
        profiles, records, assignments = self.fetch_live_dns_state(org_id)
        profile = next((p for p in profiles if p["profileId"] == profile_id), None)
        if not profile:
            return {"error": "Profile not found."}

        profile_records = [
            {"hostname": r["hostname"], "address": r["address"]}
            for r in records
            if (r.get("profile") or {}).get("id") == profile_id
        ]
        assigned_network_ids = [
            (a.get("network") or {}).get("id")
            for a in assignments
            if (a.get("profile") or {}).get("id") == profile_id
            and (a.get("network") or {}).get("id")
        ]

        return {
            "version": CONFIG_VERSION,
            "profile": {
                "name": profile["name"],
                "profile_id": profile_id,
                "records": profile_records,
            },
            "assignment_network_ids": assigned_network_ids,
        }

    def import_profile_config(self, org_id, config, network_ids=None, create_missing=True):
        if not isinstance(config, dict):
            return {"error": "Configuration must be a JSON object."}

        profile_data = config.get("profile") or {}
        profile_name = (profile_data.get("name") or "").strip()
        profile_id = profile_data.get("profile_id")
        records_data = profile_data.get("records") or []
        target_network_ids = network_ids or config.get("assignment_network_ids") or []

        profiles = self.list_profiles(org_id)
        if profile_id:
            profile = next((p for p in profiles if p["profileId"] == profile_id), None)
            if not profile and profile_name:
                profile = next((p for p in profiles if p["name"] == profile_name), None)
        else:
            profile = next((p for p in profiles if p["name"] == profile_name), None) if profile_name else None

        if not profile:
            if not create_missing:
                return {"error": "Profile not found and create_missing is disabled."}
            valid, message = validate_profile_name(profile_name)
            if not valid:
                return {"error": message}
            created = self.create_profile(org_id, profile_name)
            if created and "error" in created:
                return created
            profile_id = created.get("profileId")
            if not profile_id:
                profiles = self.list_profiles(org_id)
                profile = next((p for p in profiles if p["name"] == profile_name), None)
                profile_id = profile["profileId"] if profile else None
        else:
            profile_id = profile["profileId"]

        if not profile_id:
            return {"error": "Unable to resolve profile for import."}

        existing_records = self.list_dns_records(org_id, profile_ids=[profile_id])
        existing_keys = {
            (r.get("hostname", "").lower(), r.get("address", "")) for r in existing_records
        }
        new_record_count = 0
        for item in records_data:
            hostname = (item.get("hostname") or "").strip().lower()
            address = (item.get("address") or "").strip()
            if (hostname, address) not in existing_keys:
                new_record_count += 1
        if len(existing_records) + new_record_count > MAX_LOCAL_DNS_RECORDS_PER_MX:
            return {
                "error": (
                    f"Import would exceed the per-MX limit of "
                    f"{MAX_LOCAL_DNS_RECORDS_PER_MX} local DNS records."
                )
            }

        created_records = 0
        skipped_records = 0
        record_errors = []
        for item in records_data:
            hostname = (item.get("hostname") or "").strip()
            address = (item.get("address") or "").strip()
            key = (hostname.lower(), address)
            if key in existing_keys:
                skipped_records += 1
                continue
            res = self.create_dns_record(org_id, profile_id, hostname, address)
            if res and "error" in res:
                record_errors.append({"hostname": hostname, "error": res["error"]})
            else:
                created_records += 1
                existing_keys.add(key)

        assignment_result = {}
        assignment_error = None
        if target_network_ids:
            assignment_result = self.bulk_assign_profile(
                org_id, list(dict.fromkeys(target_network_ids)), profile_id
            )
            if isinstance(assignment_result, dict) and assignment_result.get("error"):
                assignment_error = assignment_result["error"]

        result = {
            "profile_id": profile_id,
            "created_records": created_records,
            "skipped_records": skipped_records,
            "record_errors": record_errors,
            "assignment_result": assignment_result,
        }
        if assignment_error:
            result["assignment_error"] = assignment_error
        return result

    @staticmethod
    def parse_config_json(raw_text):
        try:
            return json.loads(raw_text), None
        except json.JSONDecodeError as exc:
            return None, f"Invalid JSON: {exc}"
