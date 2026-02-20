# MX Local DNS Manager 🌐

A streamlined, interactive dashboard for managing **Local DNS Services** on Cisco Meraki MX appliances. Built with **Streamlit** and the **Meraki Python SDK**, this tool simplifies the configuration of DNS Profiles, Records, and Network Assignments through a modern, row-based user interface.

---

## 📂 Project Structure

```text
mx_local_dns_manager/
├── .streamlit/
│   └── config.toml       # Streamlit theme and server configuration
├── core/
│   ├── __init__.py
│   ├── api.py            # Singleton session management for Meraki SDK
│   └── logger.py         # Rich logging configuration (Console + File)
├── logic.py              # Backend logic, SDK calls, caching, and state management
├── web.py                # Frontend UI, inline tables, and interaction logic
├── application.log       # Runtime logs (auto-generated)
├── requirements.txt      # Python dependencies
├── LICENSE               # MIT License file
└── README.md             # Project documentation
```

---

## ✨ Key Features

*   **Unified Management Interface**:
    *   **Profiles**: Create and delete Local DNS Profiles (containers for records).
    *   **DNS Records**: Manage Hostname-to-IP mappings with automatic Profile name resolution.
    *   **Assignments**: Link Profiles to specific Networks to enable local resolution.
*   **Inline Actions**:
    *   **Row-Based Deletion**: Delete buttons (❌) located directly within data tables for quick management.
    *   **Inline Creation**: "New Entry" rows appended to the bottom of every table for seamless data entry.
*   **Data Enrichment**: Automatically resolves and displays human-readable names (e.g., "Branch Office - London") alongside IDs (e.g., "N_1234...") for Networks and Profiles.
*   **User Feedback**:
    *   Instant **Toast Notifications** for success/failure states.
    *   Automatic form clearing upon successful submission.
*   **Advanced Logging**:
    *   Color-coded console output via `Rich`.
    *   Built-in **Log Viewer** modal to inspect and download `application.log` directly from the UI.

---

## 🚀 Getting Started

### 1. Prerequisites
*   Python 3.9 or higher.
*   A Cisco Meraki API Key.
*   **MX Firmware**: Target appliances should be running firmware **MX 18.2xx** or higher (Local DNS feature requirement).

### 2. Installation
Clone the repository and install the required dependencies:

```bash
pip install streamlit pandas meraki rich
```

### 3. Environment Configuration
The application requires your Meraki API key to be set as an environment variable for security.

*   **Windows (PowerShell)**:
    ```powershell
    $env:MK_CSM_KEY = "your_api_key_here"
    ```
*   **Mac/Linux**:
    ```bash
    export MK_CSM_KEY="your_api_key_here"
    ```

### 4. Launching the App
Run the application using Streamlit:

```bash
streamlit run web.py
```

---

## ⚙️ Configuration

You can adjust system behavior by modifying constants in `logic.py` and `core/logger.py`.

### Caching Timers (`logic.py`)
Control how long data is stored in memory to reduce API calls and improve UI responsiveness.
*   **Short (300s)**: Used for volatile data.
*   **Medium (3600s)**: Used for Network lists.
*   **Long (86400s)**: Used for Organization structure.

```python
CACHE_CONFIG = {
    'short': 300,
    'medium': 3600,
    'long': 86400
}
```

### Logging (`core/logger.py`)
*   **ENABLE_FILE_LOGGING**: Set to `True` to write logs to `application.log`.
*   **Console Output**: Always enabled using `Rich` for color-coded output (Green for Success, Red for Errors, Cyan for API calls).

---

## ⚠️ API Usage

This application uses the **Meraki Python SDK** to interact with the Local DNS endpoints.

**SDK Methods Used:**
*   `appliance.getOrganizationApplianceDnsLocalProfiles`
*   `appliance.createOrganizationApplianceDnsLocalProfile`
*   `appliance.deleteOrganizationApplianceDnsLocalProfile`
*   `appliance.getOrganizationApplianceDnsLocalRecords`
*   `appliance.createOrganizationApplianceDnsLocalRecord`
*   `appliance.deleteOrganizationApplianceDnsLocalRecord`
*   `appliance.bulkOrganizationApplianceDnsLocalProfilesAssignmentsCreate`
*   `appliance.createOrganizationApplianceDnsLocalProfilesAssignmentsBulkDelete`

*Note: Ensure your `meraki` library is up to date (`pip install --upgrade meraki`) to support these endpoints.*

---

## 📝 License

This project is licensed under the **MIT License**. See the LICENSE file for details.

**Author**: SandroN  

---

## 📚 API Calls Used (with documentation)

These are the Meraki Dashboard API v1 endpoints used by this app (via the Meraki Python SDK).

| Purpose | Meraki Python SDK method | REST endpoint | Documentation |
|---|---|---|---|
| List accessible orgs | `organizations.getOrganizations` | `GET /organizations` | [Get Organizations](https://developer.cisco.com/meraki/api-v1/get-organizations/) |
| List networks in an org | `organizations.getOrganizationNetworks` | `GET /organizations/{organizationId}/networks` | [Get Organization Networks](https://developer.cisco.com/meraki/api-v1/get-organization-networks/) |
| List Local DNS profiles | `appliance.getOrganizationApplianceDnsLocalProfiles` | `GET /organizations/{organizationId}/appliance/dns/local/profiles` | [Get Organization Appliance DNS Local Profiles](https://developer.cisco.com/meraki/api-v1/get-organization-appliance-dns-local-profiles/) |
| Create Local DNS profile | `appliance.createOrganizationApplianceDnsLocalProfile` | `POST /organizations/{organizationId}/appliance/dns/local/profiles` | [Create Organization Appliance DNS Local Profile](https://developer.cisco.com/meraki/api-v1/create-organization-appliance-dns-local-profile/) |
| Delete Local DNS profile | `appliance.deleteOrganizationApplianceDnsLocalProfile` | `DELETE /organizations/{organizationId}/appliance/dns/local/profiles/{profileId}` | [Delete Organization Appliance DNS Local Profile](https://developer.cisco.com/meraki/api-v1/delete-organization-appliance-dns-local-profile/) |
| List Local DNS records | `appliance.getOrganizationApplianceDnsLocalRecords` | `GET /organizations/{organizationId}/appliance/dns/local/records` | [Get Organization Appliance DNS Local Records](https://developer.cisco.com/meraki/api-v1/get-organization-appliance-dns-local-records/) |
| Create Local DNS record | `appliance.createOrganizationApplianceDnsLocalRecord` | `POST /organizations/{organizationId}/appliance/dns/local/records` | [Create Organization Appliance DNS Local Record](https://developer.cisco.com/meraki/api-v1/create-organization-appliance-dns-local-record/) |
| Delete Local DNS record | `appliance.deleteOrganizationApplianceDnsLocalRecord` | `DELETE /organizations/{organizationId}/appliance/dns/local/records/{recordId}` | [Delete Organization Appliance DNS Local Record](https://developer.cisco.com/meraki/api-v1/delete-organization-appliance-dns-local-record/) |
| List profile assignments | `appliance.getOrganizationApplianceDnsLocalProfilesAssignments` | `GET /organizations/{organizationId}/appliance/dns/local/profiles/assignments` | [Get Organization Appliance DNS Local Profiles Assignments](https://developer.cisco.com/meraki/api-v1/get-organization-appliance-dns-local-profiles-assignments/) |
| Bulk-create assignments | `appliance.bulkOrganizationApplianceDnsLocalProfilesAssignmentsCreate` | `POST /organizations/{organizationId}/appliance/dns/local/profiles/assignments/bulkCreate` | [Bulk Organization Appliance DNS Local Profiles Assignments Create](https://developer.cisco.com/meraki/api-v1/bulk-organization-appliance-dns-local-profiles-assignments-create/) |
| Bulk-delete assignments | `appliance.createOrganizationApplianceDnsLocalProfilesAssignmentsBulkDelete` | `POST /organizations/{organizationId}/appliance/dns/local/profiles/assignments/bulkDelete` | [Create Organization Appliance DNS Local Profiles Assignments Bulk Delete](https://developer.cisco.com/meraki/api-v1/create-organization-appliance-dns-local-profiles-assignments-bulk-delete/) |