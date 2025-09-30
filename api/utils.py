from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials
from django.conf import settings

from .models import Appointment


def get_google_sheets_client():
    """Create and return Google Sheets API client."""
    creds = Credentials.from_service_account_file(
        settings.GOOGLE_SHEETS_CREDENTIALS_FILE,
        scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    return build("sheets", "v4", credentials=creds)


def verify_sheet_connection(sheet_id, tab_name):
    """Verify Google Sheet + tab exist."""
    try:
        client = get_google_sheets_client()
        sheet_metadata = client.spreadsheets().get(spreadsheetId=sheet_id).execute()
        sheets = [s["properties"]["title"] for s in sheet_metadata["sheets"]]
        if tab_name not in sheets:
            return False, f"Tab '{tab_name}' not found in sheet"
        return True, "Connection verified"
    except Exception as e:
        return False, str(e)


def update_lead_disposition(sheet_id, tab_name, row_index, disposition, agent_id, extra_data):
    """Write lead disposition back to Google Sheet."""
    client = get_google_sheets_client()
    sheet_range = f"{tab_name}!A{row_index}:Z{row_index}"
    values = [[disposition, str(agent_id), str(extra_data)]]
    client.spreadsheets().values().update(
        spreadsheetId=sheet_id,
        range=sheet_range,
        valueInputOption="RAW",
        body={"values": values}
    ).execute()


# -------------------------
# Appointment helpers
# -------------------------
def add_appointment_to_sheet(sheet_id, tab_name, appointment: Appointment):
    """Append a new appointment row in Google Sheet."""
    client = get_google_sheets_client()
    values = [[
        str(appointment.id),
        appointment.owner.name,
        appointment.lead.data if appointment.lead else "",
        str(appointment.date),
        str(appointment.time),
        appointment.notes or "",
        appointment.status,
        str(appointment.created_at),
    ]]
    client.spreadsheets().values().append(
        spreadsheetId=sheet_id,
        range=tab_name,
        valueInputOption="RAW",
        insertDataOption="INSERT_ROWS",
        body={"values": values}
    ).execute()


def update_appointment_in_sheet(sheet_id, tab_name, appointment: Appointment):
    """
    Update an appointment row.
    NOTE: This assumes row mapping is tracked separately — you may need
    to store the row index in the Appointment model for precise updates.
    """
    client = get_google_sheets_client()
    # For now: find row by appointment ID (requires reading the sheet)
    sheet_data = client.spreadsheets().values().get(
        spreadsheetId=sheet_id,
        range=tab_name
    ).execute()

    rows = sheet_data.get("values", [])
    row_index = None
    for i, row in enumerate(rows, start=1):
        if row and row[0] == str(appointment.id):
            row_index = i
            break

    if not row_index:
        raise Exception("Appointment not found in sheet")

    sheet_range = f"{tab_name}!A{row_index}:H{row_index}"
    values = [[
        str(appointment.id),
        appointment.owner.name,
        appointment.lead.data if appointment.lead else "",
        str(appointment.date),
        str(appointment.time),
        appointment.notes or "",
        appointment.status,
        str(appointment.updated_at),
    ]]
    client.spreadsheets().values().update(
        spreadsheetId=sheet_id,
        range=sheet_range,
        valueInputOption="RAW",
        body={"values": values}
    ).execute()
