import streamlit as st
import pandas as pd
import meraki
from core.api import session
from core.logger import logger

# Global counter for tracking API calls made through the SDK
API_CALL_COUNTER = 0

def _increment_counter(endpoint):
    """Increments the global API call counter and logs the SDK method being called."""
    global API_CALL_COUNTER
    API_CALL_COUNTER += 1
    logger.info(f"[bold cyan][API CALL #{API_CALL_COUNTER}][/] SDK Method: [green]{endpoint}[/]")

# Cache TTL configuration in seconds
CACHE_CONFIG = {
    'short': 300,    # 5 minutes
    'medium': 3600,  # 1 hour
    'long': 86400    # 24 hours
}

class ProjectLogic:
    """Business logic layer for managing Meraki MX Local DNS profiles, records, and assignments."""
    
    def __init__(self):
        """Initialize the ProjectLogic instance with a Meraki Dashboard SDK session."""
        self.dashboard = session.get_dashboard()
        logger.info("[bold green]ProjectLogic initialized with Meraki SDK.[/]")

    @st.cache_data(ttl=CACHE_CONFIG['long'])
    def get_organizations(_self):
        """Retrieve all organizations accessible to the API key."""
        _increment_counter("organizations.getOrganizations")
        return _self.dashboard.organizations.getOrganizations()

    @st.cache_data(ttl=CACHE_CONFIG['medium'])
    def get_networks(_self, organization_id):
        """Retrieve all networks for a given organization."""
        _increment_counter("organizations.getOrganizationNetworks")
        return _self.dashboard.organizations.getOrganizationNetworks(organization_id)

    def list_profiles(self, org_id):
        """List all Local DNS profiles for an organization."""
        _increment_counter("appliance.getOrganizationApplianceDnsLocalProfiles")
        try:
            response = self.dashboard.appliance.getOrganizationApplianceDnsLocalProfiles(org_id)
            return response.get("items", [])
        except meraki.APIError as e:
            logger.error(f"[bold red]SDK Error (list_profiles): {e}[/]")
            return []

    def create_profile(self, org_id, name):
        """Create a new Local DNS profile."""
        _increment_counter("appliance.createOrganizationApplianceDnsLocalProfile")
        try:
            return self.dashboard.appliance.createOrganizationApplianceDnsLocalProfile(org_id, name)
        except meraki.APIError as e:
            logger.error(f"[bold red]SDK Error (create_profile): {e}[/]")
            return {"error": str(e)}

    def list_dns_records(self, org_id):
        """List all DNS records for an organization."""
        _increment_counter("appliance.getOrganizationApplianceDnsLocalRecords")
        try:
            response = self.dashboard.appliance.getOrganizationApplianceDnsLocalRecords(org_id)
            return response.get("items", [])
        except meraki.APIError as e:
            logger.error(f"[bold red]SDK Error (list_dns_records): {e}[/]")
            return []

    def create_dns_record(self, org_id, profile_id, hostname, address):
        """Create a new DNS record (hostname to IP mapping) within a profile."""
        _increment_counter("appliance.createOrganizationApplianceDnsLocalRecord")
        try:
            profile = {'id': profile_id}
            return self.dashboard.appliance.createOrganizationApplianceDnsLocalRecord(
                org_id, hostname, address, profile
            )
        except meraki.APIError as e:
            logger.error(f"[bold red]SDK Error (create_dns_record): {e}[/]")
            return {"error": str(e)}

    def list_assignments(self, org_id):
        """List all profile-to-network assignments for an organization."""
        _increment_counter("appliance.getOrganizationApplianceDnsLocalProfilesAssignments")
        try:
            response = self.dashboard.appliance.getOrganizationApplianceDnsLocalProfilesAssignments(org_id)
            return response.get("items", [])
        except meraki.APIError as e:
            logger.error(f"[bold red]SDK Error (list_assignments): {e}[/]")
            return []

    def assign_profile(self, org_id, network_id, profile_id):
        """Assign a Local DNS profile to a network."""
        _increment_counter("appliance.bulkOrganizationApplianceDnsLocalProfilesAssignmentsCreate")
        try:
            items = [{'network': {'id': network_id}, 'profile': {'id': profile_id}}]
            return self.dashboard.appliance.bulkOrganizationApplianceDnsLocalProfilesAssignmentsCreate(org_id, items)
        except meraki.APIError as e:
            logger.error(f"[bold red]SDK Error (assign_profile): {e}[/]")
            return {"error": str(e)}

    def delete_profile(self, org_id, profile_id):
        """Delete a Local DNS profile."""
        _increment_counter("appliance.deleteOrganizationApplianceDnsLocalProfile")
        try:
            res = self.dashboard.appliance.deleteOrganizationApplianceDnsLocalProfile(org_id, profile_id)
            return res if res is not None else {}
        except meraki.APIError as e:
            logger.error(f"[bold red]SDK Error (delete_profile): {e}[/]")
            return {"error": str(e)}

    def delete_dns_record(self, org_id, record_id):
        """Delete a DNS record."""
        _increment_counter("appliance.deleteOrganizationApplianceDnsLocalRecord")
        try:
            res = self.dashboard.appliance.deleteOrganizationApplianceDnsLocalRecord(org_id, record_id)
            return res if res is not None else {}
        except meraki.APIError as e:
            logger.error(f"[bold red]SDK Error (delete_dns_record): {e}[/]")
            return {"error": str(e)}

    def remove_assignment(self, org_id, assignment_id):
        """Remove a profile-to-network assignment."""
        _increment_counter("appliance.createOrganizationApplianceDnsLocalProfilesAssignmentsBulkDelete")
        try:
            items = [{'assignmentId': assignment_id}]
            res = self.dashboard.appliance.createOrganizationApplianceDnsLocalProfilesAssignmentsBulkDelete(org_id, items)
            return res if res is not None else {}
        except meraki.APIError as e:
            logger.error(f"[bold red]SDK Error (remove_assignment): {e}[/]")
            return {"error": str(e)}