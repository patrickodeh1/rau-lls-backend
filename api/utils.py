import gspread
from google.oauth2.service_account import Credentials
import os
from django.conf import settings
from datetime import datetime

def get_google_sheets_client():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = Credentials.from_service_account_file(
        os.getenv('GOOGLE_SHEETS_CREDENTIALS'),
        scopes=scopes
    )
    return gspread.authorize(creds)

def get_qualified_lead(sheet_id, tab_name, agent_id):
    client = get_google_sheets_client()
    try:
        sheet = client.open_by_key(sheet_id).worksheet(tab_name)
        data = sheet.get_all_records()
        for index, row in enumerate(data, start=2):
            disposition = row.get('Disposition', '')
            if disposition not in ['Called', 'NA', 'NI', 'DNC', 'Booked']:
                if disposition == 'CB':
                    cb_date = row.get('CB_Date', '')
                    if cb_date and cb_date < datetime.now().strftime('%Y-%m-%d'):
                        sheet.update_cell(index, sheet.find('Lock_Status').col, f'In Progress by Agent {agent_id}')
                        row['row_index'] = index
                        row['agent_script'] = "Hello, this is your script..."
                        row['history'] = row.get('Notes/History', '')
                        return row
                else:
                    sheet.update_cell(index, sheet.find('Lock_Status').col, f'In Progress by Agent {agent_id}')
                    row['row_index'] = index
                    row['agent_script'] = "Hello, this is your script..."
                    row['history'] = row.get('Notes/History', '')
                    return row
        return None
    except Exception as e:
        raise Exception(f"Failed to fetch lead: {str(e)}")

def update_lead_disposition(sheet_id, tab_name, row_index, disposition, agent_id, extra_data=None):
    client = get_google_sheets_client()
    try:
        sheet = client.open_by_key(sheet_id).worksheet(tab_name)
        headers = sheet.row_values(1)
        row_data = sheet.row_values(row_index)
        row_dict = dict(zip(headers, row_data))

        row_dict['Disposition'] = disposition
        row_dict['Agent_ID'] = str(agent_id)
        row_dict['Timestamp'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        row_dict['Lock_Status'] = ''  # Release lock

        if extra_data:
            row_dict.update(extra_data)

        # Update the row
        sheet.update(f'A{row_index}:{chr(65 + len(headers) - 1)}{row_index}', [list(row_dict.values())])
    except Exception as e:
        raise Exception(f"Failed to update lead: {str(e)}")

def verify_sheet_connection(sheet_id, tab_name):
    try:
        client = get_google_sheets_client()
        sheet = client.open_by_key(sheet_id).worksheet(tab_name)
        headers = sheet.row_values(1)
        required_columns = [
            'Business Name', 'Phone Number', 'Message', 'Notes/History',
            'Disposition', 'CB_Date', 'CB_Time', 'Appointment_Date',
            'Appointment_Time', 'Appointment_Notes', 'Agent_ID', 'Timestamp', 'Lock_Status'
        ]
        missing_columns = [col for col in required_columns if col not in headers]
        if missing_columns:
            return False, f"Missing columns: {', '.join(missing_columns)}"
        return True, "Connected successfully!"
    except Exception as e:
        return False, f"Connection failed: {str(e)}"