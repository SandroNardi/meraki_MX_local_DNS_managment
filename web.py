import streamlit as st
import pandas as pd
import time
import os
import html
from core.logger import logger, ENABLE_FILE_LOGGING, LOG_FILENAME
from logic import ProjectLogic, CACHE_CONFIG

# --- UTILITY FUNCTIONS ---

def get_file_content(file_path, last_n_lines=None):
    """Safely reads local files for UI modals."""
    try:
        if not os.path.exists(file_path):
            return f"File '{file_path}' not found."
        with open(file_path, "r", encoding="utf-8") as f:
            if last_n_lines:
                return f.readlines()[-last_n_lines:]
            return f.read()
    except Exception as e:
        return f"Error reading file: {e}"

# --- MODAL DIALOGS ---

@st.dialog("System Configuration", width="large")
def show_config_modal():
    """Display system configuration including API key status, logging settings, and cache configuration."""
    logger.info("UI: Opening System Configuration modal.")
    st.markdown("### 🛠️ Environment & Logging")
    api_key_status = "✅ Set" if os.getenv("MK_CSM_KEY") else "❌ Missing"
    st.write(f"**API Key (MK_CSM_KEY):** {api_key_status}")
    st.write(f"**Log Level:** `INFO` (Rich Markup Enabled)")
    st.write(f"**File Logging:** `{'Enabled' if ENABLE_FILE_LOGGING else 'Disabled'}`")
    if ENABLE_FILE_LOGGING:
        st.write(f"**Log Filename:** `{LOG_FILENAME}`")
    
    st.divider()
    st.markdown("### ⏱️ Caching Timers (Seconds)")
    st.json(CACHE_CONFIG)

@st.dialog("Application Logs", width="large")
def show_log_modal():
    """Display application logs in a terminal-style interface with syntax highlighting."""
    logger.info("UI: Opening Application Logs modal.")
    st.markdown(f"**Reading from:** `{LOG_FILENAME}`")
    lines = get_file_content(LOG_FILENAME, last_n_lines=2000)
    
    if isinstance(lines, list):
        full_content = "".join(lines)
        st.download_button(
            label="📥 Download Log File",
            data=full_content,
            file_name="application_log.txt",
            mime="text/plain",
        )
        
        # Terminal-style log renderer with color-coded log levels
        log_html = ["""
        <style>
            .terminal-window {
                background-color: #0e1117; color: #c9d1d9; font-family: 'Courier New', Courier, monospace;
                font-size: 12px; padding: 15px; border-radius: 8px; border: 1px solid #30363d;
                height: 500px; overflow-y: auto; white-space: pre-wrap; line-height: 1.4;
            }
            .log-line { margin-bottom: 2px; }
            .log-info { color: #3fb950; }
            .log-warn { color: #d29922; }
            .log-error { color: #f85149; }
            .log-meta { color: #8b949e; }
        </style>
        <div class="terminal-window">
        """]

        for line in lines:
            safe_line = html.escape(line.strip())
            css_class = "log-line"
            if "INFO" in safe_line: css_class += " log-info"
            elif "WARNING" in safe_line: css_class += " log-warn"
            elif "ERROR" in safe_line: css_class += " log-error"
            
            parts = safe_line.split(" - ", 1)
            if len(parts) > 1:
                log_html.append(f'<div class="{css_class}"><span class="log-meta">{parts[0]} - </span>{parts[1]}</div>')
            else:
                log_html.append(f'<div class="{css_class}">{safe_line}</div>')

        log_html.append("</div>")
        st.markdown("".join(log_html), unsafe_allow_html=True)
    else:
        st.error(lines)

@st.dialog("License", width="large")
def show_license_modal():
    """Display the application license file."""
    st.markdown("### Open Source License")
    content = get_file_content("LICENSE")
    st.code(content, language="text")

@st.dialog("ReadMe", width="large")
def show_readme_modal():
    """Display the README.md file content."""
    content = get_file_content("README.md")
    st.markdown(content)

# --- MAIN APPLICATION ---

def run_web():
    """Main application entry point. Initializes the Streamlit UI and handles all user interactions."""
    st.set_page_config(page_title="MX Local DNS Manager", layout="wide", initial_sidebar_state="expanded")
    logger.info("[bold green]Initialising MX Local DNS Manager Web UI[/]")
    
    # Inject custom CSS for branding and styling
    st.markdown(f"""
    <style>
        :root {{
            --primary-accent: #144a90;
            --top-bar-bg: #07172B;
            --white: #FFFFFF;
            --st-light-grey: rgba(49, 51, 63, 0.6);
            --gradient: linear-gradient(to right, #007bff, #6610f2, #e83e8c, #fd7e14);
        }}
        [data-testid="stIconMaterial"] {{ color: var(--primary-accent) !important; }}
        [data-testid="stBaseButton-header"] {{ color: var(--white) !important; }}                
        [data-testid="stMainMenu"] svg {{ fill: var(--white) !important; }}
        .stAppDeployButton {{ display: none !important; }}
        header[data-testid="stHeader"] {{ background-color: transparent; }}
        .top-gradient-bar {{ position: fixed; top: 0; left: 0; width: 100%; height: 4px; background-image: var(--gradient); z-index: 100001; }}
        .top-bar {{ position: fixed; top: 4px; left: 0; width: 100%; height: 56px; background-color: var(--top-bar-bg); z-index: 100000; display: flex; align-items: center; padding-left: 60px; box-shadow: 0 2px 4px rgba(0,0,0,0.2); }}
        .top-bar-text {{ color: var(--white); font-weight: 600; font-size: 1.1em; }}
        .block-container {{ padding-top: 6rem; }}
        
        /* Table header styling */
        .table-header {{ font-weight: bold; border-bottom: 2px solid var(--primary-accent); padding-bottom: 5px; margin-bottom: 10px; }}
        
        /* Compact input field styling for table cells */
        div[data-testid="stColumn"] > div > div > div > div > input {{
            min-height: 0px; padding: 0.25rem 0.5rem;
        }}
    </style>
    <div class="top-gradient-bar"></div>
    <div class="top-bar"><div class="top-bar-text">MX LOCAL DNS MANAGER</div></div>
    """, unsafe_allow_html=True)

    try:
        logic = ProjectLogic()
        orgs = logic.get_organizations()
        org_map = {o['name']: o['id'] for o in orgs}

        with st.sidebar:
            st.header("1. Scope")
            selected_org_name = st.selectbox("Organization", list(org_map.keys()))
            org_id = org_map[selected_org_name]
            
            st.header("2. Mode")
            mode = st.radio("Management Mode", ["Profiles", "DNS Records", "Network Assignments"])

            st.divider()
            if mode == "Profiles":
                st.info("Manage Local DNS Profiles. Profiles act as containers for DNS records.")
            elif mode == "DNS Records":
                st.info("Manage Hostname-to-IP mappings associated with specific Profiles.")
            elif mode == "Network Assignments":
                st.info("Link Profiles to specific Networks to enable local resolution.")

            refresh_btn = st.button("Refresh", type="primary", width='stretch')

            # About section with system configuration and documentation links
            st.divider()
            with st.expander("ℹ️ About", expanded=False):
                st.markdown("### MX Local DNS Manager")
                st.caption("Centralized management for Local DNS resolution on MX appliances.")
                st.markdown("**Author:** SandroN")
                st.markdown("[GitHub Project Repository](https://github.com/SandroNardi/meraki_MX_local_DNS_managment)")
                
                st.divider()
                if st.button("⚙️ System Configuration", width='stretch'):
                    show_config_modal()

                if ENABLE_FILE_LOGGING:
                    if st.button("📄 Application Logs", width='stretch'):
                        show_log_modal()

                c1, c2 = st.columns(2)
                with c1:
                    if st.button("📜 License", width='stretch'):
                        show_license_modal()
                with c2:
                    if st.button("📖 ReadMe", width='stretch'):
                        show_readme_modal()

        # Progress bar for long-running operations
        progress_bar = st.progress(0)
        status_text = st.empty()

        def update_progress(message, current, total):
            """Update the progress bar and status text."""
            val = min(current / total, 1.0)
            progress_bar.progress(val)
            status_text.text(f"Processing: {message}")

        if refresh_btn:
            logger.info(f"UI: Manual refresh triggered for [cyan]{mode}[/]")

        # Main content area - render based on selected mode
        if mode == "Profiles":
            st.subheader("Local DNS Profiles")
            profiles = logic.list_profiles(org_id)
            
            # Table header
            cols = st.columns([2, 4, 1])
            cols[0].markdown("<div class='table-header'>Profile ID</div>", unsafe_allow_html=True)
            cols[1].markdown("<div class='table-header'>Name</div>", unsafe_allow_html=True)
            cols[2].markdown("<div class='table-header'>Actions</div>", unsafe_allow_html=True)

            # Display existing profiles
            if profiles:
                for p in profiles:
                    r_cols = st.columns([2, 4, 1])
                    r_cols[0].text(p['profileId'])
                    r_cols[1].text(p['name'])
                    if r_cols[2].button("❌", key=f"del_prof_{p['profileId']}", help="Delete Profile", width='stretch'):
                        res = logic.delete_profile(org_id, p['profileId'])
                        if not res or "error" not in res:
                            st.toast("✅ Profile deleted successfully!", icon="🗑️")
                            time.sleep(1); st.rerun()
                        else:
                            st.toast(f"❌ Error: {res['error']}", icon="⚠️")
            else:
                st.info("No profiles found. Use the row below to create one.")

            # Inline creation row for new profiles
            st.markdown("---")
            i_cols = st.columns([2, 4, 1])
            i_cols[0].markdown("*(New)*")
            new_prof_name = i_cols[1].text_input("New Profile Name", label_visibility="collapsed", placeholder="Enter Profile Name", key="new_prof_name")
            
            if i_cols[2].button("➕", key="add_prof_btn", help="Create New Profile", width='stretch'):
                if new_prof_name:
                    res = logic.create_profile(org_id, new_prof_name)
                    if res and "error" not in res:
                        st.toast(f"✅ Profile '{new_prof_name}' created!", icon="🚀")
                        if "new_prof_name" in st.session_state: del st.session_state["new_prof_name"]
                        time.sleep(1); st.rerun()
                    else:
                        st.toast(f"❌ Error: {res.get('error', 'Unknown')}", icon="⚠️")
                else:
                    st.toast("⚠️ Please enter a profile name.", icon="⚠️")


        elif mode == "DNS Records":
            st.subheader("DNS Records")
            records = logic.list_dns_records(org_id)
            profiles = logic.list_profiles(org_id) 
            
            # Create lookup map for Profile ID -> Name
            prof_lookup = {p['profileId']: p['name'] for p in profiles}

            # Table header
            cols = st.columns([2, 3, 2, 3, 1])
            cols[0].markdown("<div class='table-header'>Record ID</div>", unsafe_allow_html=True)
            cols[1].markdown("<div class='table-header'>Hostname</div>", unsafe_allow_html=True)
            cols[2].markdown("<div class='table-header'>Address</div>", unsafe_allow_html=True)
            cols[3].markdown("<div class='table-header'>Profile (ID)</div>", unsafe_allow_html=True)
            cols[4].markdown("<div class='table-header'>Actions</div>", unsafe_allow_html=True)

            # Display existing DNS records
            if records:
                for r in records:
                    r_cols = st.columns([2, 3, 2, 3, 1])
                    r_cols[0].text(r['recordId'])
                    r_cols[1].text(r['hostname'])
                    r_cols[2].text(r['address'])
                    
                    # Resolve profile name from ID
                    pid = r.get('profile', {}).get('id', 'N/A')
                    pname = prof_lookup.get(pid, "Unknown")
                    r_cols[3].text(f"{pname} ({pid})")

                    if r_cols[4].button("❌", key=f"del_rec_{r['recordId']}", help="Delete Record", width='stretch'):
                        res = logic.delete_dns_record(org_id, r['recordId'])
                        if not res or "error" not in res:
                            st.toast("✅ DNS Record removed!", icon="🗑️")
                            time.sleep(1); st.rerun()
                        else:
                            st.toast(f"❌ Error: {res['error']}", icon="⚠️")
            else:
                st.info("No DNS records found. Use the row below to create one.")

            # Inline creation row for new DNS records
            st.markdown("---")
            if profiles:
                # Map dropdown display format "Name (ID)" to profile ID
                p_map = {f"{p['name']} ({p['profileId']})": p['profileId'] for p in profiles}
                
                i_cols = st.columns([2, 3, 2, 3, 1])
                i_cols[0].markdown("*(New)*")
                new_host = i_cols[1].text_input("Host", label_visibility="collapsed", placeholder="Hostname", key="new_host")
                new_addr = i_cols[2].text_input("IP", label_visibility="collapsed", placeholder="IP Address", key="new_addr")
                new_prof_select = i_cols[3].selectbox("Profile", options=list(p_map.keys()), label_visibility="collapsed", key="new_prof_select")
                
                if i_cols[4].button("➕", key="add_rec_btn", help="Add DNS Record", width='stretch'):
                    if new_host and new_addr and new_prof_select:
                        res = logic.create_dns_record(org_id, p_map[new_prof_select], new_host, new_addr)
                        if res and "error" not in res:
                            st.toast("✅ DNS Record created!", icon="🌐")
                            if "new_host" in st.session_state: del st.session_state["new_host"]
                            if "new_addr" in st.session_state: del st.session_state["new_addr"]
                            time.sleep(1); st.rerun()
                        else:
                            st.toast(f"❌ Error: {res.get('error', 'Unknown')}", icon="⚠️")
                    else:
                        st.toast("⚠️ Please fill in all fields.", icon="⚠️")
            else:
                st.warning("⚠️ You must create a Profile before adding DNS records.")


        elif mode == "Network Assignments":
            st.subheader("Network Assignments")
            update_progress("Enriching Data...", 1, 3)
            assigns = logic.list_assignments(org_id)
            nets = logic.get_networks(org_id)
            profs = logic.list_profiles(org_id)
            
            # Create lookup maps for network and profile names
            net_lookup = {n['id']: n['name'] for n in nets}
            prof_lookup = {p['profileId']: p['name'] for p in profs}
            
            update_progress("Complete", 3, 3)
            time.sleep(0.3); status_text.empty(); progress_bar.empty()

            # Table header
            cols = st.columns([2, 3, 3, 1])
            cols[0].markdown("<div class='table-header'>Assignment ID</div>", unsafe_allow_html=True)
            cols[1].markdown("<div class='table-header'>Network (ID)</div>", unsafe_allow_html=True)
            cols[2].markdown("<div class='table-header'>Profile (ID)</div>", unsafe_allow_html=True)
            cols[3].markdown("<div class='table-header'>Actions</div>", unsafe_allow_html=True)

            # Display existing assignments
            if assigns:
                for a in assigns:
                    n_id = a.get('network', {}).get('id')
                    p_id = a.get('profile', {}).get('id')
                    
                    # Resolve network and profile names from IDs
                    n_name = net_lookup.get(n_id, "Unknown")
                    p_name = prof_lookup.get(p_id, "Unknown")
                    
                    n_display = f"{n_name} ({n_id})"
                    p_display = f"{p_name} ({p_id})"

                    r_cols = st.columns([2, 3, 3, 1])
                    r_cols[0].text(a['assignmentId'])
                    r_cols[1].text(n_display)
                    r_cols[2].text(p_display)
                    
                    if r_cols[3].button("❌", key=f"del_assign_{a['assignmentId']}", help="Remove Assignment", width='stretch'):
                        res = logic.remove_assignment(org_id, a['assignmentId'])
                        if not res or "error" not in res:
                            st.toast("✅ Assignment removed!", icon="🔗")
                            time.sleep(1); st.rerun()
                        else:
                            st.toast(f"❌ Error: {res['error']}", icon="⚠️")
            else:
                st.info("No network assignments found. Use the row below to create one.")

            # Inline creation row for new assignments
            st.markdown("---")
            if nets and profs:
                # Map dropdown display format "Name (ID)" to IDs
                n_map_rev = {f"{n['name']} ({n['id']})": n['id'] for n in nets}
                p_map_rev = {f"{p['name']} ({p['profileId']})": p['profileId'] for p in profs}

                i_cols = st.columns([2, 3, 3, 1])
                i_cols[0].markdown("*(New)*")
                sel_net_name = i_cols[1].selectbox("Net", options=list(n_map_rev.keys()), label_visibility="collapsed", key="new_assign_net")
                sel_prof_name = i_cols[2].selectbox("Prof", options=list(p_map_rev.keys()), label_visibility="collapsed", key="new_assign_prof")
                
                if i_cols[3].button("➕", key="add_assign_btn", help="Create Assignment", width='stretch'):
                    res = logic.assign_profile(org_id, n_map_rev[sel_net_name], p_map_rev[sel_prof_name])
                    if res and "error" not in res:
                        st.toast("✅ Network assigned to profile!", icon="🔗")
                        if "new_assign_net" in st.session_state: del st.session_state["new_assign_net"]
                        if "new_assign_prof" in st.session_state: del st.session_state["new_assign_prof"]
                        time.sleep(1); st.rerun()
                    else:
                        st.toast(f"❌ Error: {res.get('error', 'Unknown')}", icon="⚠️")
            else:
                st.warning("⚠️ You need both Networks and Profiles to create an assignment.")

    except Exception as e:
        logger.error(f"[bold red]Critical App Error: {e}[/]", exc_info=True)
        st.error(f"Application Error: {e}")

if __name__ == "__main__":
    run_web()