# MX Local DNS Manager

A Streamlit dashboard for managing **Meraki MX Local DNS** at organization scale. Built with the **Meraki Python SDK**, it covers profile and record management, bulk MX assignment (including network-tag selection), JSON import/export, and a live overview with eligibility checks before assignment.

---

## Project Structure

```text
meraki_MX_local_DNS_managment/
├── .streamlit/
│   └── config.toml         # Streamlit theme and server configuration
├── core/
│   ├── api.py              # Singleton Meraki SDK session (MK_CSM_KEY)
│   └── logger.py           # Rich console + optional file logging
├── logic.py                # Meraki API calls, bulk ops, overview builder
├── web.py                  # Streamlit UI
├── validators.py           # Hostname, IP, and profile name validation
├── mx_requirements.py      # Local DNS assignment requirements and warnings
├── application.log         # Runtime logs (auto-generated when enabled)
├── requirements.txt
├── LICENSE
└── README.md
```

---

## Key Features

### Management Modes

| Mode | Description |
|------|-------------|
| **Overview** | Live per-MX dashboard: firmware, routed mode, template binding, profile assignment, subnet proxy-DNS status, and DNS record counts. No cached data. |
| **Profiles** | Create and delete Local DNS profiles with multi-row selection. |
| **DNS Records** | Create, filter, bulk-delete, and export records. Live API data. |
| **Network Assignments** | Bulk assign/unassign profiles to MX networks by name or **network tags**, with JSON import/export. |

### MX Overview and Eligibility

The Overview mode assesses each MX network against Meraki Local DNS requirements:

**Blocking requirements** (profile assignment is blocked if any fail):

- MX firmware **19.1+**
- **NAT/Routed** deployment mode (not passthrough)
- **Non-template** MX network
- No more than **1024** DNS records on the profile being assigned

**Warnings** (assignment allowed, but Local DNS may not work):

- **Proxy to Upstream DNS** not enabled on any subnet/VLAN (`dnsNameservers = upstream_dns`)

Selecting an MX in the overview shows:

1. Assignment requirements and warnings
2. Subnet/VLAN table (rows using Proxy to Upstream DNS are highlighted)
3. DNS records on the assigned profile

### Bulk Operations

- Assign or unassign a profile to **multiple MX networks** at once
- Filter and select networks by **network tags** (match any or all tags)
- Search networks by name
- **JSON import/export** for profile records and optional network assignments
- Confirmation dialogs for destructive actions and assignments
- Progress feedback during long-running overview scans

### Input Validation

- Hostname and IPv4/IPv6 address validation before record creation
- Profile name validation
- Per-MX record limit enforcement (1024 records)

### UI and Operations

- Branded Streamlit layout consistent with other Meraki toolkit apps
- `st.dataframe` tables with row selection
- Toast notifications for success and errors
- **Refresh** clears `st.cache_data` and reloads data
- System configuration, logs, license, and README modals in the sidebar

---

## Getting Started

### Prerequisites

- Python 3.9 or higher
- Cisco Meraki API key with access to the target organization(s)
- MX appliances on firmware **19.1+** for Local DNS
- Meraki Python SDK **1.46.0+** (see `requirements.txt`)

### Installation

```bash
git clone https://github.com/SandroNardi/meraki_MX_local_DNS_managment.git
cd meraki_MX_local_DNS_managment
pip install -r requirements.txt
```

### Environment Configuration

Set your Meraki API key as an environment variable:

**Windows (PowerShell):**

```powershell
$env:MK_CSM_KEY = "your_api_key_here"
```

**Mac/Linux:**

```bash
export MK_CSM_KEY="your_api_key_here"
```

### Launch

```bash
streamlit run web.py
```

---

## Local DNS Model

Meraki Local DNS is **organization-scoped**:

```text
Organization
 ├── Profiles (containers)
 │    └── DNS Records (hostname → IP)
 └── Assignments (Profile → MX Network)
```

Clients on an MX only use Local DNS when:

1. A profile is **assigned** to that MX network, and
2. The subnet/VLAN DHCP setting uses **Proxy to Upstream DNS**

Profiles and records are shared at org level; assignments control which MX networks use a given profile.

---

## JSON Import / Export

Export a profile (records + assigned network IDs) from **Network Assignments → JSON import / export**.

Example import file:

```json
{
  "version": 1,
  "profile": {
    "name": "Branch-DNS",
    "records": [
      { "hostname": "dc01.corp.local", "address": "10.10.1.10" },
      { "hostname": "fileserver.corp.local", "address": "10.10.1.20" }
    ]
  },
  "assignment_network_ids": []
}
```

On import you can:

- Select target MX networks individually or by **network tags**
- Optionally create the profile if it does not exist
- Review eligibility failures (blocking) and warnings before confirming

---

## Configuration

### Caching (`logic.py`)

Organization and network lists are cached to reduce API calls. Overview, DNS record inspection, and assignment validation always use **live** API data.

```python
CACHE_CONFIG = {
    "short": 300,     # 5 minutes
    "medium": 3600,   # 1 hour
    "long": 86400,    # 24 hours
}
```

Use the sidebar **Refresh** button or restart the app after changing cache TTL values.

### Logging (`core/logger.py`)

- `ENABLE_FILE_LOGGING = True` writes to `application.log`
- Console output uses Rich with color-coded levels
- View and download logs from the UI when file logging is enabled

---

## API Usage

### Local DNS Endpoints

| Purpose | SDK method |
|---------|------------|
| List profiles | `appliance.getOrganizationApplianceDnsLocalProfiles` |
| Create profile | `appliance.createOrganizationApplianceDnsLocalProfile` |
| Delete profile | `appliance.deleteOrganizationApplianceDnsLocalProfile` |
| List records | `appliance.getOrganizationApplianceDnsLocalRecords` |
| Create record | `appliance.createOrganizationApplianceDnsLocalRecord` |
| Delete record | `appliance.deleteOrganizationApplianceDnsLocalRecord` |
| List assignments | `appliance.getOrganizationApplianceDnsLocalProfilesAssignments` |
| Bulk-create assignments | `appliance.bulkOrganizationApplianceDnsLocalProfilesAssignmentsCreate` |
| Bulk-delete assignments | `appliance.createOrganizationApplianceDnsLocalProfilesAssignmentsBulkDelete` |

### Eligibility / Overview Endpoints

| Purpose | SDK method |
|---------|------------|
| List MX networks | `organizations.getOrganizationNetworks` |
| List MX devices (firmware) | `organizations.getOrganizationDevices` |
| Appliance settings (routed mode) | `appliance.getNetworkApplianceSettings` |
| VLAN settings | `appliance.getNetworkApplianceVlansSettings` |
| VLAN list (proxy DNS per subnet) | `appliance.getNetworkApplianceVlans` |
| Single-LAN config | `appliance.getNetworkApplianceSingleLan` |
| VLAN 1 (single-LAN DNS fallback) | `appliance.getNetworkApplianceVlan` |

Ensure the Meraki SDK is current:

```bash
pip install --upgrade meraki
```

---

## API Reference (Meraki Dashboard API v1)

| Purpose | SDK method | Documentation |
|---------|------------|---------------|
| List organizations | `organizations.getOrganizations` | [Get Organizations](https://developer.cisco.com/meraki/api-v1/get-organizations/) |
| List networks | `organizations.getOrganizationNetworks` | [Get Organization Networks](https://developer.cisco.com/meraki/api-v1/get-organization-networks/) |
| List devices | `organizations.getOrganizationDevices` | [Get Organization Devices](https://developer.cisco.com/meraki/api-v1/get-organization-devices/) |
| Appliance settings | `appliance.getNetworkApplianceSettings` | [Get Network Appliance Settings](https://developer.cisco.com/meraki/api-v1/get-network-appliance-settings/) |
| VLAN settings | `appliance.getNetworkApplianceVlansSettings` | [Get Network Appliance VLANs Settings](https://developer.cisco.com/meraki/api-v1/get-network-appliance-vlans-settings/) |
| List VLANs | `appliance.getNetworkApplianceVlans` | [Get Network Appliance VLANs](https://developer.cisco.com/meraki/api-v1/get-network-appliance-vlans/) |
| List Local DNS profiles | `appliance.getOrganizationApplianceDnsLocalProfiles` | [Get Organization Appliance DNS Local Profiles](https://developer.cisco.com/meraki/api-v1/get-organization-appliance-dns-local-profiles/) |
| Create Local DNS profile | `appliance.createOrganizationApplianceDnsLocalProfile` | [Create Organization Appliance DNS Local Profile](https://developer.cisco.com/meraki/api-v1/create-organization-appliance-dns-local-profile/) |
| Delete Local DNS profile | `appliance.deleteOrganizationApplianceDnsLocalProfile` | [Delete Organization Appliance DNS Local Profile](https://developer.cisco.com/meraki/api-v1/delete-organization-appliance-dns-local-profile/) |
| List Local DNS records | `appliance.getOrganizationApplianceDnsLocalRecords` | [Get Organization Appliance DNS Local Records](https://developer.cisco.com/meraki/api-v1/get-organization-appliance-dns-local-records/) |
| Create Local DNS record | `appliance.createOrganizationApplianceDnsLocalRecord` | [Create Organization Appliance DNS Local Record](https://developer.cisco.com/meraki/api-v1/create-organization-appliance-dns-local-record/) |
| Delete Local DNS record | `appliance.deleteOrganizationApplianceDnsLocalRecord` | [Delete Organization Appliance DNS Local Record](https://developer.cisco.com/meraki/api-v1/delete-organization-appliance-dns-local-record/) |
| List assignments | `appliance.getOrganizationApplianceDnsLocalProfilesAssignments` | [Get Organization Appliance DNS Local Profiles Assignments](https://developer.cisco.com/meraki/api-v1/get-organization-appliance-dns-local-profiles-assignments/) |
| Bulk-create assignments | `appliance.bulkOrganizationApplianceDnsLocalProfilesAssignmentsCreate` | [Bulk Create Assignments](https://developer.cisco.com/meraki/api-v1/bulk-organization-appliance-dns-local-profiles-assignments-create/) |
| Bulk-delete assignments | `appliance.createOrganizationApplianceDnsLocalProfilesAssignmentsBulkDelete` | [Bulk Delete Assignments](https://developer.cisco.com/meraki/api-v1/create-organization-appliance-dns-local-profiles-assignments-bulk-delete/) |

---

## Meraki Documentation

- [Local DNS Service on MX](https://documentation.meraki.com/SASE_and_SD-WAN/MX/Operate_and_Maintain/How-Tos/Local_DNS_Service_on_MX)
- [Configuring DNS Nameservers for DHCP](https://documentation.meraki.com/SASE_and_SD-WAN/MX/Design_and_Configure/Configuration_Guides/DHCP/Configuring_DNS_Nameservers_for_DHCP)

---

## License

MIT License — see [LICENSE](LICENSE).

**Author:** SandroN
