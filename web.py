import json
import os
import time

import pandas as pd
import streamlit as st

from core.logger import ENABLE_FILE_LOGGING, LOG_FILENAME, logger
from logic import (
    CACHE_CONFIG,
    ProjectLogic,
    filter_mx_networks,
    format_network_tags,
    get_unique_network_tags,
)
from mx_requirements import MAX_LOCAL_DNS_RECORDS_PER_MX
from validators import validate_hostname, validate_ip_address, validate_profile_name

BRANDING_CSS = """
<style>
    :root {
        --primary-accent: #144a90;
        --top-bar-bg: #07172B;
        --white: #FFFFFF;
        --gradient: linear-gradient(to right, #007bff, #6610f2, #e83e8c, #fd7e14);
    }
    [data-testid="stIconMaterial"] { color: var(--primary-accent) !important; }
    [data-testid="stBaseButton-header"] { color: var(--white) !important; }
    [data-testid="stMainMenu"] svg { fill: var(--white) !important; }
    .stAppDeployButton { display: none !important; }
    header[data-testid="stHeader"] { background-color: transparent; }
    .top-gradient-bar {
        position: fixed; top: 0; left: 0; width: 100%; height: 4px;
        background-image: var(--gradient); z-index: 100001;
    }
    .top-bar {
        position: fixed; top: 4px; left: 0; width: 100%; height: 56px;
        background-color: var(--top-bar-bg); z-index: 100000;
        display: flex; align-items: center; padding-left: 60px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.2);
    }
    .top-bar-text { color: var(--white); font-weight: 600; font-size: 1.1em; }
    .block-container { padding-top: 6rem; }
</style>
<div class="top-gradient-bar"></div>
<div class="top-bar"><div class="top-bar-text">MX LOCAL DNS MANAGER</div></div>
"""


def get_file_content(file_path, last_n_lines=None):
    try:
        if not os.path.exists(file_path):
            return f"File '{file_path}' not found."
        with open(file_path, "r", encoding="utf-8") as f:
            if last_n_lines:
                return f.readlines()[-last_n_lines:]
            return f.read()
    except Exception as exc:
        return f"Error reading file: {exc}"


def inject_branding():
    st.markdown(BRANDING_CSS, unsafe_allow_html=True)


def request_confirmation(action, message, payload):
    st.session_state["confirm_request"] = {
        "action": action,
        "message": message,
        "payload": payload,
    }


@st.dialog("Confirm Action", width="small")
def show_confirm_dialog():
    req = st.session_state.get("confirm_request", {})
    message = req.get("message", "Are you sure you want to continue?")
    st.warning(message)
    col_confirm, col_cancel = st.columns(2)
    with col_confirm:
        if st.button("Confirm", type="primary", width="stretch"):
            st.session_state["confirm_approved"] = req
            st.session_state.pop("confirm_request", None)
            st.rerun()
    with col_cancel:
        if st.button("Cancel", width="stretch"):
            st.session_state.pop("confirm_request", None)
            st.rerun()


@st.dialog("System Configuration", width="large")
def show_config_modal():
    logger.info("UI: Opening System Configuration modal.")
    st.markdown("### Environment & Logging")
    api_key_status = "Set" if os.getenv("MK_CSM_KEY") else "Missing"
    st.write(f"**API Key (MK_CSM_KEY):** {api_key_status}")
    st.write("**Log Level:** `INFO`")
    st.write(f"**File Logging:** `{'Enabled' if ENABLE_FILE_LOGGING else 'Disabled'}`")
    if ENABLE_FILE_LOGGING:
        st.write(f"**Log Filename:** `{LOG_FILENAME}`")
    st.divider()
    st.markdown("### Caching Timers (Seconds)")
    st.json(CACHE_CONFIG)
    st.caption("Overview and DNS inspection always use live API data.")


@st.dialog("Application Logs", width="large")
def show_log_modal():
    logger.info("UI: Opening Application Logs modal.")
    st.markdown(f"**Reading from:** `{LOG_FILENAME}`")
    lines = get_file_content(LOG_FILENAME, last_n_lines=2000)
    if isinstance(lines, list):
        full_content = "".join(lines)
        st.download_button(
            label="Download Log File",
            data=full_content,
            file_name="application_log.txt",
            mime="text/plain",
        )
        st.code(full_content, language="text")
    else:
        st.error(lines)


@st.dialog("License", width="large")
def show_license_modal():
    st.markdown("### Open Source License")
    content = get_file_content("LICENSE")
    st.code(content, language="text")


@st.dialog("ReadMe", width="large")
def show_readme_modal():
    content = get_file_content("README.md")
    st.code(content, language="text")


def render_sidebar_about():
    with st.expander("About", expanded=False):
        st.markdown("### MX Local DNS Manager")
        st.caption("Centralized management for Local DNS resolution on MX appliances.")
        st.markdown("**Author:** SandroN")
        st.markdown(
            "[GitHub Project Repository](https://github.com/SandroNardi/meraki_MX_local_DNS_managment)"
        )
        st.divider()
        if st.button("System Configuration", width="stretch"):
            show_config_modal()
        if ENABLE_FILE_LOGGING and st.button("Application Logs", width="stretch"):
            show_log_modal()
        col_license, col_readme = st.columns(2)
        with col_license:
            if st.button("License", width="stretch"):
                show_license_modal()
        with col_readme:
            if st.button("ReadMe", width="stretch"):
                show_readme_modal()


def network_tag_selector(mx_networks, key_prefix):
    all_tags = get_unique_network_tags(mx_networks)
    selected_tags = st.multiselect(
        "Filter by network tag(s)",
        options=all_tags,
        key=f"{key_prefix}_tags",
    )
    tag_match = st.radio(
        "Tag match",
        options=["Any tag", "All tags"],
        horizontal=True,
        key=f"{key_prefix}_tag_match",
    )
    name_search = st.text_input(
        "Search network name",
        key=f"{key_prefix}_name_search",
        placeholder="Optional name filter",
    )
    tag_filter_type = "withAllTags" if tag_match == "All tags" else "withAnyTags"
    filtered = filter_mx_networks(
        mx_networks,
        tag_filter=selected_tags or None,
        tag_filter_type=tag_filter_type,
        name_search=name_search,
    )
    return filtered


def network_multiselect(filtered_networks, key_prefix):
    options = {
        f"{network['name']} ({network['id']})": network["id"]
        for network in filtered_networks
    }
    selected_labels = st.multiselect(
        "Select MX network(s)",
        options=list(options.keys()),
        key=f"{key_prefix}_networks",
    )
    return [options[label] for label in selected_labels]


def execute_confirmed_action(logic, org_id, req, progress_callback=None):
    action = req.get("action")
    payload = req.get("payload", {})

    if action == "bulk_delete_profiles":
        profile_ids = payload.get("profile_ids", [])
        results = {"deleted": 0, "errors": []}
        total = len(profile_ids)
        for index, profile_id in enumerate(profile_ids, start=1):
            if progress_callback:
                progress_callback(f"Deleting profile {index}/{total}", index, total)
            res = logic.delete_profile(org_id, profile_id)
            if res and "error" in res:
                results["errors"].append({"profile_id": profile_id, "error": res["error"]})
            else:
                results["deleted"] += 1
        return results
    if action == "delete_record":
        return logic.delete_dns_record(org_id, payload["record_id"])
    if action == "bulk_delete_records":
        record_ids = payload.get("record_ids", [])
        total = len(record_ids)
        results = {"deleted": 0, "errors": []}
        for index, record_id in enumerate(record_ids, start=1):
            if progress_callback:
                progress_callback(f"Deleting record {index}/{total}", index, total)
            res = logic.delete_dns_record(org_id, record_id)
            if res and "error" in res:
                results["errors"].append({"record_id": record_id, "error": res["error"]})
            else:
                results["deleted"] += 1
        return results
    if action == "remove_assignment":
        return logic.remove_assignment(org_id, payload["assignment_id"])
    if action == "bulk_remove_assignments":
        return logic.bulk_remove_assignments(org_id, payload.get("assignment_ids", []))
    if action == "bulk_assign":
        network_ids = payload.get("network_ids", [])
        total = len(network_ids)
        if progress_callback and total > 1:
            progress_callback("Assigning profile to selected networks", 1, 1)
        return logic.bulk_assign_profile(
            org_id, network_ids, payload.get("profile_id")
        )
    if action == "import_config":
        return logic.import_profile_config(
            org_id,
            payload.get("config"),
            network_ids=payload.get("network_ids"),
            create_missing=payload.get("create_missing", True),
        )
    return {"error": f"Unknown action: {action}"}


def build_assign_confirmation_message(network_count: int, warnings=None) -> str:
    message = f"Assign profile to {network_count} MX network(s)?"
    if not warnings:
        return message
    lines = [message, "", "Warnings (assignment allowed, Local DNS may not work):"]
    for warning in warnings:
        issue_text = "; ".join(warning["issues"])
        lines.append(f"- {warning['network_name']}: {issue_text}")
    return "\n".join(lines)


def build_import_confirmation_message(network_count: int, warnings=None) -> str:
    if network_count == 0:
        base = "Import this JSON configuration?"
    else:
        base = f"Import configuration and assign profile to {network_count} MX network(s)?"
    if not warnings:
        return base
    lines = [base, "", "Warnings (assignment allowed, Local DNS may not work):"]
    for warning in warnings:
        issue_text = "; ".join(warning["issues"])
        lines.append(f"- {warning['network_name']}: {issue_text}")
    return "\n".join(lines)


def show_assignment_blockers(failures):
    st.error("Cannot assign profile — these networks do not meet Local DNS prerequisites:")
    for failure in failures:
        issue_text = "; ".join(failure["issues"])
        st.markdown(f"- **{failure['network_name']}**: {issue_text}")


def style_subnet_dataframe(subnets_df: pd.DataFrame):
    def _highlight(row):
        if row.get("Uses Local DNS") == "Yes":
            return ["background-color: #d4edda; color: #155724"] * len(row)
        return [""] * len(row)

    return subnets_df.style.apply(_highlight, axis=1)


def render_eligibility_checks(checks, warnings=None):
    st.markdown("**Assignment requirements**")
    check_df = pd.DataFrame(
        [
            {
                "Requirement": check["name"],
                "Status": "Pass" if check["passed"] else "Fail",
                "Detail": check["detail"],
            }
            for check in checks
        ]
    )
    st.dataframe(check_df, width="stretch", hide_index=True)

    warnings = warnings or []
    if warnings:
        st.markdown("**Warnings**")
        warning_df = pd.DataFrame(
            [
                {
                    "Warning": warning["name"],
                    "Status": "OK" if warning["passed"] else "Attention",
                    "Detail": warning["detail"],
                }
                for warning in warnings
            ]
        )
        st.dataframe(warning_df, width="stretch", hide_index=True)


def render_overview(logic, org_id, progress_callback=None):
    st.subheader("MX Local DNS Overview")
    st.caption(
        "Live data — eligibility checks, subnet DNS proxy settings, and DNS records per MX."
    )

    with st.spinner("Loading live MX, subnet, and DNS state..."):
        overview = logic.build_mx_overview(org_id, progress_callback=progress_callback)

    summary = overview["summary"]
    metric_cols = st.columns(6)
    metric_cols[0].metric("MX Networks", summary["total_mx"])
    metric_cols[1].metric("Profile Assigned", summary["configured_mx"])
    metric_cols[2].metric("Ready for Assignment", summary["eligible_mx"])
    metric_cols[3].metric("Subnets Using Local DNS", summary["total_proxy_subnets"])
    metric_cols[4].metric("Profiles", summary["total_profiles"])
    metric_cols[5].metric("Total DNS Records", summary["total_records"])

    with st.expander("Local DNS prerequisites", expanded=False):
        st.markdown(
            """
            Local DNS requires the following **before** a profile can be assigned:

            - MX firmware **19.1+**
            - **NAT/Routed** deployment mode (not passthrough)
            - **Non-template** MX network
            - No more than **1024** DNS records on the profile being assigned

            **Proxy to Upstream DNS** on a subnet is recommended but not required.
            Without it, a profile can still be assigned but Local DNS will not take effect.
            """
        )

    mx_networks = logic.fetch_mx_networks_live(org_id)
    filtered_networks = network_tag_selector(mx_networks, "overview")
    allowed_ids = {network["id"] for network in filtered_networks}

    rows = [row for row in overview["rows"] if row["network_id"] in allowed_ids]
    if not rows:
        st.info("No MX networks match the current filters.")
        return

    overview_df = pd.DataFrame(
        [
            {
                "Network": row["network_name"],
                "Tags": row["tags"],
                "Firmware": row["firmware_display"],
                "Mode": row["deployment_mode"],
                "Template Bound": "Yes" if row["is_template_bound"] else "No",
                "Profile": row["profile_name"] or "—",
                "DNS Records": row["dns_record_count"],
                "Subnets (Proxy/Total)": (
                    f"{row['proxy_subnet_count']}/{row['total_subnet_count']}"
                ),
                "Eligibility": row["eligibility"],
                "Network ID": row["network_id"],
            }
            for row in rows
        ]
    )

    table_event = st.dataframe(
        overview_df,
        width="stretch",
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row",
        key="overview_table",
    )

    selected_rows = table_event.selection.rows if table_event.selection else []
    if selected_rows:
        selected_row = rows[selected_rows[0]]
        st.markdown(f"#### {selected_row['network_name']}")

        render_eligibility_checks(selected_row["checks"], selected_row.get("warnings"))
        if not selected_row["eligible_for_assignment"]:
            st.warning(
                "This MX network does not meet all assignment requirements. "
                "A Local DNS profile cannot be assigned until the failed checks are resolved."
            )
        elif not selected_row.get("local_dns_effective", True):
            st.warning(
                "A profile can be assigned, but Local DNS will not work until "
                "**Proxy to Upstream DNS** is enabled on at least one subnet."
            )
        if not selected_row["record_limit_ok"]:
            st.error(
                f"Assigned profile exceeds the per-MX limit of "
                f"{MAX_LOCAL_DNS_RECORDS_PER_MX} DNS records."
            )

        st.markdown("##### Subnets / VLANs")
        st.caption(
            "Highlighted rows have **Proxy to Upstream DNS** enabled and will use Local DNS."
        )
        subnets = selected_row.get("subnets") or []
        if subnets:
            subnets_df = pd.DataFrame(
                [
                    {
                        "Subnet / VLAN": subnet["name"],
                        "CIDR": subnet["subnet"],
                        "DHCP DNS Setting": subnet["dns_label"],
                        "Uses Local DNS": (
                            "Yes" if subnet["proxy_upstream_dns"] else "No"
                        ),
                        "DHCP Handling": subnet["dhcp_handling"],
                    }
                    for subnet in subnets
                ]
            )
            st.dataframe(
                style_subnet_dataframe(subnets_df),
                width="stretch",
                hide_index=True,
            )
        else:
            st.info("No subnets or VLANs were returned for this network.")

        st.markdown("##### DNS records on assigned profile")
        if selected_row["profile_name"]:
            st.caption(
                f"Profile: {selected_row['profile_name']} ({selected_row['profile_id']})"
            )
        records = selected_row.get("records") or []
        if records:
            records_df = pd.DataFrame(
                [
                    {
                        "Hostname": record["hostname"],
                        "Address": record["address"],
                        "Record ID": record["recordId"],
                    }
                    for record in records
                ]
            )
            st.dataframe(records_df, width="stretch", hide_index=True)
        elif selected_row["status"] == "Configured":
            st.info("This profile has no DNS records yet.")
        else:
            st.warning("This MX network does not have a Local DNS profile assigned.")


def render_profiles(logic, org_id):
    st.subheader("Local DNS Profiles")
    profiles = logic.list_profiles(org_id)

    if profiles:
        profile_df = pd.DataFrame(
            [{"Profile ID": profile["profileId"], "Name": profile["name"]} for profile in profiles]
        )
        selection = st.dataframe(
            profile_df,
            width="stretch",
            hide_index=True,
            on_select="rerun",
            selection_mode="multi-row",
            key="profiles_table",
        )
        selected_rows = selection.selection.rows if selection.selection else []
        if selected_rows:
            selected_profiles = [profiles[index] for index in selected_rows]
            if st.button("Delete selected profile(s)", type="secondary"):
                labels = ", ".join(profile["name"] for profile in selected_profiles)
                request_confirmation(
                    "bulk_delete_profiles",
                    (
                        f"Delete {len(selected_profiles)} profile(s): {labels}? "
                        "Remove related DNS records and network assignments first."
                    ),
                    {
                        "profile_ids": [
                            profile["profileId"] for profile in selected_profiles
                        ]
                    },
                )
    else:
        st.info("No profiles found. Create one below.")

    st.divider()
    new_profile_name = st.text_input(
        "New profile name",
        key="new_prof_name",
        placeholder="Enter profile name",
    )
    if st.button("Create profile", type="primary"):
        valid, message = validate_profile_name(new_profile_name)
        if not valid:
            st.toast(message, icon="⚠️")
        else:
            result = logic.create_profile(org_id, new_profile_name)
            if result and "error" not in result:
                st.toast(f"Profile '{new_profile_name.strip()}' created.", icon="✅")
                st.session_state.pop("new_prof_name", None)
                time.sleep(0.5)
                st.rerun()
            else:
                st.toast(f"Error: {result.get('error', 'Unknown')}", icon="⚠️")


def render_dns_records(logic, org_id):
    st.subheader("DNS Records")
    st.caption("Live data — no cache.")

    profiles = logic.list_profiles(org_id)
    profile_lookup = {profile["profileId"]: profile["name"] for profile in profiles}

    filter_cols = st.columns([2, 2, 2])
    with filter_cols[0]:
        hostname_filter = st.text_input(
            "Filter hostname",
            key="dns_hostname_filter",
            placeholder="Contains...",
        )
    with filter_cols[1]:
        profile_filter = st.multiselect(
            "Filter profile",
            options=[profile["name"] for profile in profiles],
            key="dns_profile_filter",
        )
    with filter_cols[2]:
        address_filter = st.text_input(
            "Filter address",
            key="dns_address_filter",
            placeholder="Contains...",
        )

    records = logic.list_dns_records(org_id)
    filtered_records = []
    for record in records:
        profile_id = (record.get("profile") or {}).get("id")
        profile_name = profile_lookup.get(profile_id, "Unknown")
        if profile_filter and profile_name not in profile_filter:
            continue
        if hostname_filter and hostname_filter.lower() not in record.get("hostname", "").lower():
            continue
        if address_filter and address_filter.lower() not in record.get("address", "").lower():
            continue
        filtered_records.append(record)

    if filtered_records:
        records_df = pd.DataFrame(
            [
                {
                    "Record ID": record["recordId"],
                    "Hostname": record["hostname"],
                    "Address": record["address"],
                    "Profile": profile_lookup.get(
                        (record.get("profile") or {}).get("id"), "Unknown"
                    ),
                }
                for record in filtered_records
            ]
        )
        selection = st.dataframe(
            records_df,
            width="stretch",
            hide_index=True,
            on_select="rerun",
            selection_mode="multi-row",
            key="dns_records_table",
        )
        action_cols = st.columns([1, 1])
        selected_rows = selection.selection.rows if selection.selection else []
        if selected_rows:
            selected_records = [filtered_records[index] for index in selected_rows]
            with action_cols[0]:
                if st.button("Delete selected record(s)", type="secondary"):
                    labels = ", ".join(record["hostname"] for record in selected_records)
                    request_confirmation(
                        "bulk_delete_records",
                        f"Delete {len(selected_records)} DNS record(s): {labels}?",
                        {"record_ids": [record["recordId"] for record in selected_records]},
                    )
            with action_cols[1]:
                export_payload = {
                    "version": 1,
                    "records": [
                        {
                            "record_id": record["recordId"],
                            "hostname": record["hostname"],
                            "address": record["address"],
                            "profile_id": (record.get("profile") or {}).get("id"),
                        }
                        for record in selected_records
                    ],
                }
                st.download_button(
                    "Export selected as JSON",
                    data=json.dumps(export_payload, indent=2),
                    file_name="dns_records_export.json",
                    mime="application/json",
                    width="stretch",
                )
    else:
        st.info("No DNS records match the current filters.")

    st.divider()
    st.markdown("#### Add DNS record")
    if not profiles:
        st.warning("Create a profile before adding DNS records.")
        return

    profile_options = {
        f"{profile['name']} ({profile['profileId']})": profile["profileId"]
        for profile in profiles
    }
    create_cols = st.columns([2, 2, 2, 1])
    new_host = create_cols[0].text_input("Hostname", key="new_host", placeholder="hostname.local")
    new_addr = create_cols[1].text_input("IP address", key="new_addr", placeholder="10.0.0.1")
    selected_profile = create_cols[2].selectbox(
        "Profile",
        options=list(profile_options.keys()),
        key="new_prof_select",
    )
    if create_cols[3].button("Add", type="primary", width="stretch"):
        host_ok, host_msg = validate_hostname(new_host)
        ip_ok, ip_msg = validate_ip_address(new_addr)
        if not host_ok:
            st.toast(host_msg, icon="⚠️")
        elif not ip_ok:
            st.toast(ip_msg, icon="⚠️")
        else:
            result = logic.create_dns_record(
                org_id,
                profile_options[selected_profile],
                new_host,
                new_addr,
            )
            if result and "error" not in result:
                st.toast("DNS record created.", icon="✅")
                for key in ("new_host", "new_addr"):
                    st.session_state.pop(key, None)
                time.sleep(0.5)
                st.rerun()
            else:
                st.toast(f"Error: {result.get('error', 'Unknown')}", icon="⚠️")


def render_assignments(logic, org_id, progress_callback):
    st.subheader("Network Assignments")
    st.caption("Assign Local DNS profiles to MX networks individually, by tag, or via JSON import.")

    assigns = logic.list_assignments(org_id)
    mx_networks = logic.fetch_mx_networks_live(org_id)
    profiles = logic.list_profiles(org_id)

    net_lookup = {network["id"]: network for network in mx_networks}
    prof_lookup = {profile["profileId"]: profile["name"] for profile in profiles}

    if assigns:
        assignment_df = pd.DataFrame(
            [
                {
                    "Assignment ID": assignment["assignmentId"],
                    "Network": net_lookup.get(
                        (assignment.get("network") or {}).get("id"), {}
                    ).get("name", "Unknown"),
                    "Network ID": (assignment.get("network") or {}).get("id", ""),
                    "Tags": format_network_tags(
                        net_lookup.get((assignment.get("network") or {}).get("id"), {})
                    ),
                    "Profile": prof_lookup.get(
                        (assignment.get("profile") or {}).get("id"), "Unknown"
                    ),
                    "Profile ID": (assignment.get("profile") or {}).get("id", ""),
                }
                for assignment in assigns
            ]
        )
        selection = st.dataframe(
            assignment_df,
            width="stretch",
            hide_index=True,
            on_select="rerun",
            selection_mode="multi-row",
            key="assignments_table",
        )
        selected_rows = selection.selection.rows if selection.selection else []
        if selected_rows and st.button("Unassign selected network(s)", type="secondary"):
            selected_assignments = [assigns[index] for index in selected_rows]
            labels = ", ".join(
                net_lookup.get((item.get("network") or {}).get("id"), {}).get("name", "Unknown")
                for item in selected_assignments
            )
            request_confirmation(
                "bulk_remove_assignments",
                f"Remove Local DNS assignment from: {labels}?",
                {
                    "assignment_ids": [
                        item["assignmentId"] for item in selected_assignments
                    ]
                },
            )
    else:
        st.info("No network assignments found.")

    st.divider()
    st.markdown("#### Assign profile to MX networks")
    if not profiles:
        st.warning("Create a profile before assigning networks.")
        return
    if not mx_networks:
        st.warning("No MX networks found in this organization.")
        return

    filtered_networks = network_tag_selector(mx_networks, "assign")
    selected_network_ids = network_multiselect(filtered_networks, "assign")
    profile_options = {
        f"{profile['name']} ({profile['profileId']})": profile["profileId"]
        for profile in profiles
    }
    selected_profile = st.selectbox(
        "Profile to assign",
        options=list(profile_options.keys()),
        key="bulk_assign_profile",
    )

    if st.button("Assign profile to selected network(s)", type="primary"):
        if not selected_network_ids:
            st.toast("Select at least one MX network.", icon="⚠️")
        else:
            profile_id = profile_options[selected_profile]
            validation = logic.validate_networks_for_local_dns(
                org_id, selected_network_ids, profile_id=profile_id
            )
            if validation["failures"]:
                show_assignment_blockers(validation["failures"])
            else:
                request_confirmation(
                    "bulk_assign",
                    build_assign_confirmation_message(
                        len(selected_network_ids), validation["warnings"]
                    ),
                    {
                        "network_ids": selected_network_ids,
                        "profile_id": profile_id,
                    },
                )

    st.divider()
    st.markdown("#### JSON import / export")
    export_cols = st.columns(2)
    with export_cols[0]:
        export_profile_key = st.selectbox(
            "Profile to export",
            options=list(profile_options.keys()),
            key="export_profile_select",
        )
        if st.button("Build export preview", width="stretch"):
            export_data = logic.export_profile_config(
                org_id, profile_options[export_profile_key]
            )
            if export_data and "error" in export_data:
                st.error(export_data["error"])
            else:
                st.session_state["export_preview"] = export_data
        if st.session_state.get("export_preview"):
            st.download_button(
                "Download profile JSON",
                data=json.dumps(st.session_state["export_preview"], indent=2),
                file_name="mx_local_dns_profile.json",
                mime="application/json",
                width="stretch",
            )
            st.json(st.session_state["export_preview"])

    with export_cols[1]:
        uploaded = st.file_uploader(
            "Import profile JSON",
            type=["json"],
            key="import_json_file",
        )
        import_networks = network_multiselect(
            filter_mx_networks(mx_networks),
            "import",
        )
        create_missing = st.checkbox(
            "Create profile if missing",
            value=True,
            key="import_create_missing",
        )
        if uploaded is not None:
            raw_text = uploaded.getvalue().decode("utf-8")
            config, parse_error = ProjectLogic.parse_config_json(raw_text)
            if parse_error:
                st.error(parse_error)
            else:
                st.json(config)
                if st.button("Import configuration", type="primary"):
                    profile_data = config.get("profile") or {}
                    profile_id = profile_data.get("profile_id")
                    record_count = len(profile_data.get("records") or [])
                    failures = []
                    assignment_warnings = []
                    if import_networks:
                        validation = logic.validate_networks_for_local_dns(
                            org_id,
                            import_networks,
                            profile_id=profile_id,
                            profile_record_count=record_count if not profile_id else None,
                        )
                        failures = validation["failures"]
                        assignment_warnings = validation["warnings"]
                    if failures:
                        show_assignment_blockers(failures)
                    else:
                        request_confirmation(
                            "import_config",
                            build_import_confirmation_message(
                                len(import_networks), assignment_warnings
                            ),
                            {
                                "config": config,
                                "network_ids": import_networks,
                                "create_missing": create_missing,
                            },
                        )


def run_web():
    st.set_page_config(
        page_title="MX Local DNS Manager",
        page_icon=":material/dns:",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    inject_branding()
    logger.info("[bold green]Initialising MX Local DNS Manager Web UI[/]")

    if st.session_state.get("confirm_request"):
        show_confirm_dialog()

    try:
        logic = ProjectLogic()
        orgs = logic.get_organizations()
        if not orgs:
            st.error("No organizations available for this API key.")
            return

        org_map = {org["name"]: org["id"] for org in orgs}

        with st.sidebar:
            st.header("1. Scope")
            selected_org_name = st.selectbox("Organization", list(org_map.keys()))
            org_id = org_map[selected_org_name]

            st.header("2. Mode")
            mode = st.radio(
                "Management Mode",
                [
                    "Overview",
                    "Profiles",
                    "DNS Records",
                    "Network Assignments",
                ],
            )

            st.divider()
            mode_help = {
                "Overview": "Live dashboard with Local DNS eligibility, subnet proxy settings, and DNS records.",
                "Profiles": "Create and delete Local DNS profiles.",
                "DNS Records": "Manage hostname-to-IP mappings.",
                "Network Assignments": "Assign profiles to MX networks, including tag-based bulk actions.",
            }
            st.info(mode_help[mode])

            if st.button("Refresh", type="primary", width="stretch"):
                st.cache_data.clear()
                logger.info(f"UI: Manual refresh triggered for {mode}")
                st.rerun()

            st.divider()
            render_sidebar_about()

        progress_bar = st.progress(0)
        status_text = st.empty()

        def update_progress(message, current, total):
            progress_bar.progress(min(current / total, 1.0))
            status_text.text(f"Processing: {message}")

        approved = st.session_state.pop("confirm_approved", None)
        if approved:
            with st.spinner("Applying confirmed action..."):
                result = execute_confirmed_action(
                    logic,
                    org_id,
                    approved,
                    progress_callback=update_progress,
                )
            progress_bar.empty()
            status_text.empty()

            action = approved.get("action")
            if isinstance(result, dict) and result.get("error"):
                st.toast(f"Error: {result['error']}", icon="⚠️")
            elif action in ("bulk_delete_records", "bulk_delete_profiles"):
                deleted = result.get("deleted", 0)
                errors = result.get("errors", [])
                st.toast(f"Deleted {deleted} item(s).", icon="✅")
                if errors:
                    st.warning(f"{len(errors)} item(s) could not be deleted.")
            elif action == "import_config":
                st.toast(
                    f"Import complete. Created {result.get('created_records', 0)} record(s), "
                    f"skipped {result.get('skipped_records', 0)} duplicate(s).",
                    icon="✅",
                )
                if result.get("record_errors"):
                    st.warning(result["record_errors"])
                if result.get("assignment_error"):
                    st.warning(f"Assignment error: {result['assignment_error']}")
            else:
                st.toast("Action completed successfully.", icon="✅")
            time.sleep(0.5)
            st.rerun()

        if mode == "Overview":
            render_overview(logic, org_id, progress_callback=update_progress)
        elif mode == "Profiles":
            render_profiles(logic, org_id)
        elif mode == "DNS Records":
            render_dns_records(logic, org_id)
        elif mode == "Network Assignments":
            render_assignments(logic, org_id, update_progress)

        progress_bar.empty()
        status_text.empty()

    except Exception as exc:
        logger.error(f"[bold red]Critical App Error: {exc}[/]", exc_info=True)
        st.error(f"Application Error: {exc}")


if __name__ == "__main__":
    run_web()
