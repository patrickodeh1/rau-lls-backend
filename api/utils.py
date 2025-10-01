import json
from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials
from django.conf import settings
from datetime import datetime
from django.utils import timezone


def get_google_sheets_client():
    """Create and return Google Sheets API client."""
    try:
        # Check if GOOGLE_SHEETS_CREDENTIALS is a file path or JSON string
        creds_path_or_json = settings.GOOGLE_SHEETS_CREDENTIALS
        
        # If it's a file path (ends with .json or is a valid path)
        if creds_path_or_json.endswith('.json') or os.path.isfile(creds_path_or_json):
            creds = Credentials.from_service_account_file(
                creds_path_or_json,
                scopes=["https://www.googleapis.com/auth/spreadsheets"]
            )
        else:
            # It's a JSON string
            creds_json = json.loads(creds_path_or_json)
            creds = Credentials.from_service_account_info(
                creds_json,
                scopes=["https://www.googleapis.com/auth/spreadsheets"]
            )
        
        return build("sheets", "v4", credentials=creds)
    except Exception as e:
        raise Exception(f"Failed to initialize Google Sheets client: {str(e)}")

def verify_sheet_connection(sheet_id, tab_name):
    """Verify Google Sheet + tab exist and check for required columns."""
    try:
        client = get_google_sheets_client()
        sheet_metadata = client.spreadsheets().get(spreadsheetId=sheet_id).execute()
        sheets = [s["properties"]["title"] for s in sheet_metadata.get("sheets", [])]
        
        if tab_name not in sheets:
            return False, f"Tab '{tab_name}' not found in sheet"
        
        # Verify required columns exist
        result = client.spreadsheets().values().get(
            spreadsheetId=sheet_id,
            range=f"{tab_name}!A1:Z1"
        ).execute()
        
        headers = result.get("values", [[]])[0]
        required_columns = ["Business Name", "Phone Number", "Message", "Disposition"]
        missing = [col for col in required_columns if col not in headers]
        
        if missing:
            return False, f"Missing required columns: {', '.join(missing)}"
        
        return True, "Connection verified successfully"
    except Exception as e:
        return False, f"Connection error: {str(e)}"


def get_column_index(headers, column_name):
    """Get the index of a column by name."""
    try:
        return headers.index(column_name)
    except ValueError:
        return None


def fetch_qualified_leads(sheet_id, tab_name):
    """
    Fetch all qualified leads from Google Sheet based on PRD logic:
    - Status is NOT "Called", "NA", "NI", "DNC", "Booked"
    - If Status is "CB", CB_TIMESTAMP must be in the past
    """
    client = get_google_sheets_client()
    
    # Fetch all data
    result = client.spreadsheets().values().get(
        spreadsheetId=sheet_id,
        range=f"{tab_name}!A:Z"
    ).execute()
    
    rows = result.get("values", [])
    if not rows:
        return []
    
    headers = rows[0]
    data_rows = rows[1:]
    
    # Get column indices
    disposition_idx = get_column_index(headers, "Disposition")
    cb_date_idx = get_column_index(headers, "CB_Date")
    cb_time_idx = get_column_index(headers, "CB_Time")
    lock_status_idx = get_column_index(headers, "Lock_Status")
    
    qualified_leads = []
    current_time = timezone.now()
    
    for idx, row in enumerate(data_rows, start=2):  # Start at row 2 (after header)
        # Ensure row has enough columns
        while len(row) < len(headers):
            row.append("")
        
        disposition = row[disposition_idx] if disposition_idx is not None else ""
        lock_status = row[lock_status_idx] if lock_status_idx is not None else ""
        
        # Skip if already locked
        if lock_status and lock_status.strip():
            continue
        
        # Skip if disposition is in excluded list
        excluded_statuses = ["Called", "NA", "NI", "DNC", "Booked", "BOOK"]
        if disposition in excluded_statuses:
            continue
        
        # Handle CB (Call Back) logic
        if disposition == "CB":
            cb_date = row[cb_date_idx] if cb_date_idx is not None else ""
            cb_time = row[cb_time_idx] if cb_time_idx is not None else ""
            
            if cb_date and cb_time:
                try:
                    # Parse CB timestamp
                    cb_datetime_str = f"{cb_date} {cb_time}"
                    cb_datetime = datetime.strptime(cb_datetime_str, "%Y-%m-%d %H:%M")
                    cb_datetime = timezone.make_aware(cb_datetime)
                    
                    # Skip if CB time is in the future
                    if cb_datetime > current_time:
                        continue
                except ValueError:
                    # Invalid date format, skip
                    continue
            else:
                # No CB time set, skip
                continue
        
        # Build lead data dictionary
        lead_data = {header: row[i] if i < len(row) else "" for i, header in enumerate(headers)}
        lead_data["row_index"] = idx
        qualified_leads.append(lead_data)
    
    return qualified_leads


def lock_lead(sheet_id, tab_name, row_index, agent_id):
    """Lock a lead by setting Lock_Status column."""
    client = get_google_sheets_client()
    
    # Get headers to find Lock_Status column
    result = client.spreadsheets().values().get(
        spreadsheetId=sheet_id,
        range=f"{tab_name}!A1:Z1"
    ).execute()
    
    headers = result.get("values", [[]])[0]
    lock_status_idx = get_column_index(headers, "Lock_Status")
    
    if lock_status_idx is None:
        raise Exception("Lock_Status column not found in sheet")
    
    # Convert to A1 notation
    column_letter = chr(65 + lock_status_idx)  # A=65
    cell_range = f"{tab_name}!{column_letter}{row_index}"
    
    # Set lock
    lock_value = f"In Progress by Agent {agent_id}"
    client.spreadsheets().values().update(
        spreadsheetId=sheet_id,
        range=cell_range,
        valueInputOption="RAW",
        body={"values": [[lock_value]]}
    ).execute()


def unlock_lead(sheet_id, tab_name, row_index):
    """Unlock a lead by clearing Lock_Status column."""
    client = get_google_sheets_client()
    
    # Get headers
    result = client.spreadsheets().values().get(
        spreadsheetId=sheet_id,
        range=f"{tab_name}!A1:Z1"
    ).execute()
    
    headers = result.get("values", [[]])[0]
    lock_status_idx = get_column_index(headers, "Lock_Status")
    
    if lock_status_idx is None:
        return
    
    column_letter = chr(65 + lock_status_idx)
    cell_range = f"{tab_name}!{column_letter}{row_index}"
    
    client.spreadsheets().values().update(
        spreadsheetId=sheet_id,
        range=cell_range,
        valueInputOption="RAW",
        body={"values": [[""]]}
    ).execute()


def update_lead_disposition(sheet_id, tab_name, row_index, disposition, agent_id, extra_data=None):
    """
    Write lead disposition back to Google Sheet.
    Updates: Disposition, Agent_ID, Timestamp, Lock_Status, and any extra fields.
    """
    client = get_google_sheets_client()
    
    # Get headers
    result = client.spreadsheets().values().get(
        spreadsheetId=sheet_id,
        range=f"{tab_name}!A1:Z1"
    ).execute()
    
    headers = result.get("values", [[]])[0]
    
    # Prepare updates
    updates = []
    timestamp = timezone.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Update Disposition
    disp_idx = get_column_index(headers, "Disposition")
    if disp_idx is not None:
        col_letter = chr(65 + disp_idx)
        updates.append({
            "range": f"{tab_name}!{col_letter}{row_index}",
            "values": [[disposition]]
        })
    
    # Update Agent_ID
    agent_idx = get_column_index(headers, "Agent_ID")
    if agent_idx is not None:
        col_letter = chr(65 + agent_idx)
        updates.append({
            "range": f"{tab_name}!{col_letter}{row_index}",
            "values": [[str(agent_id)]]
        })
    
    # Update Timestamp
    ts_idx = get_column_index(headers, "Timestamp")
    if ts_idx is not None:
        col_letter = chr(65 + ts_idx)
        updates.append({
            "range": f"{tab_name}!{col_letter}{row_index}",
            "values": [[timestamp]]
        })
    
    # Clear Lock_Status
    lock_idx = get_column_index(headers, "Lock_Status")
    if lock_idx is not None:
        col_letter = chr(65 + lock_idx)
        updates.append({
            "range": f"{tab_name}!{col_letter}{row_index}",
            "values": [[""]]
        })
    
    # Handle extra data (CB dates/times, appointment info)
    if extra_data:
        for key, value in extra_data.items():
            idx = get_column_index(headers, key)
            if idx is not None:
                col_letter = chr(65 + idx)
                updates.append({
                    "range": f"{tab_name}!{col_letter}{row_index}",
                    "values": [[str(value)]]
                })
    
    # Batch update
    if updates:
        client.spreadsheets().values().batchUpdate(
            spreadsheetId=sheet_id,
            body={"data": updates, "valueInputOption": "RAW"}
        ).execute()