import os
import subprocess
import re
import requests
import time
import sys
from datetime import datetime, timedelta
from dotenv import load_dotenv
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import pickle

# Load environment variables
load_dotenv()

# Get output directory from environment variable
output_dir = os.getenv('OUTPUT_DIR', os.path.join(os.path.dirname(__file__), "exported-notes"))

# Google Drive API settings
SCOPES = ['https://www.googleapis.com/auth/drive.file']
GOOGLE_DRIVE_FOLDER_ID = os.getenv('GOOGLE_DRIVE_FOLDER_ID')

def get_google_drive_service():
    creds = None
    token_path = os.getenv('GOOGLE_DRIVE_TOKEN_PATH', 'token.pickle')
    credentials_path = os.getenv('GOOGLE_DRIVE_CREDENTIALS_PATH')

    if os.path.exists(token_path):
        with open(token_path, 'rb') as token:
            creds = pickle.load(token)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(token_path, 'wb') as token:
            pickle.dump(creds, token)

    return build('drive', 'v3', credentials=creds)

def is_connected():
    try:
        requests.get("https://www.google.com", timeout=5)
        return True
    except requests.RequestException:
        return False

def log_status(message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # log_file = os.getenv('LOG_FILE', 'apple_notes_export.log')
    log_file = os.getenv('LOG_FILE', '/tmp/apple_notes_export.log')

    with open(log_file, "a") as f:
        f.write(f"{timestamp}: {message}\n")

# Weekly success tracking
SUCCESS_TRACKER_FILE = os.path.join(os.path.dirname(__file__), '.last_successful_run')

def get_week_start():
    """Get the start of the current week (Sunday at midnight)."""
    today = datetime.now()
    days_since_sunday = today.weekday() + 1  # Monday=0, so Sunday=6+1=7, but we want Sunday=0
    if today.weekday() == 6:  # If today is Sunday
        days_since_sunday = 0
    else:
        days_since_sunday = today.weekday() + 1
    week_start = today - timedelta(days=days_since_sunday)
    return week_start.replace(hour=0, minute=0, second=0, microsecond=0)

def already_ran_this_week():
    """Check if we already had a successful run this week."""
    if not os.path.exists(SUCCESS_TRACKER_FILE):
        return False

    try:
        with open(SUCCESS_TRACKER_FILE, 'r') as f:
            last_run_str = f.read().strip()
            last_run = datetime.fromisoformat(last_run_str)
            week_start = get_week_start()
            return last_run >= week_start
    except (ValueError, IOError):
        return False

def record_successful_run():
    """Record that we had a successful run."""
    with open(SUCCESS_TRACKER_FILE, 'w') as f:
        f.write(datetime.now().isoformat())

def get_all_notes():
    script = '''
    set output to ""
    tell application "Notes"
        repeat with aNote in every note
            set noteName to the name of aNote
            set noteBody to the body of aNote
            set output to output & "---NOTE START---\n"
            set output to output & "Title: " & noteName & "\n"
            set output to output & "Body:\n" & noteBody & "\n"
            set output to output & "---NOTE END---\n"
        end repeat
    end tell
    return output
    '''

    result = subprocess.run(['osascript', '-e', script], stdout=subprocess.PIPE, text=True)
    return result.stdout

def sanitize_filename(name):
    return re.sub(r'[^\w\-_ ]', '_', name).strip()[:100]  # Limit filename length

def parse_notes(notes_output):
    notes = []
    raw_notes = notes_output.split("---NOTE START---\n")
    for raw in raw_notes:
        if raw.strip() == "":
            continue
        title_match = re.search(r'Title: (.*?)\n', raw)
        body_match = re.search(r'Body:\n(.*?)\n---NOTE END---', raw, re.DOTALL)
        title = title_match.group(1).strip() if title_match else "Untitled"
        body = body_match.group(1).strip() if body_match else ""
        notes.append((sanitize_filename(title), body))
    return notes

def export_notes():
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    all_notes = get_all_notes()
    parsed_notes = parse_notes(all_notes)

    for title, body in parsed_notes:
        file_path = os.path.join(output_dir, f"{title}.txt")
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(body)
    print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}: Exported {len(parsed_notes)} notes to {output_dir}")

def find_existing_file(service, filename, folder_id):
    """Find an existing file with the same name in the specified folder."""
    try:
        query = f"name='{filename}' and '{folder_id}' in parents and trashed=false"
        results = service.files().list(
            q=query,
            spaces='drive',
            fields='files(id, name)'
        ).execute()
        files = results.get('files', [])
        return files[0]['id'] if files else None
    except Exception as e:
        log_status(f"Error searching for existing file {filename}: {str(e)}")
        return None

def upload_to_drive(service, file_path, folder_id):
    filename = os.path.basename(file_path)
    
    # Check if file already exists
    existing_file_id = find_existing_file(service, filename, folder_id)
    
    media = MediaFileUpload(file_path, mimetype='text/plain', resumable=True)
    
    try:
        if existing_file_id:
            # Update existing file
            file = service.files().update(
                fileId=existing_file_id,
                media_body=media,
                fields='id'
            ).execute()
            log_status(f"Updated existing file: {filename}")
        else:
            # Create new file
            file_metadata = {
                'name': filename,
                'parents': [folder_id]
            }
            file = service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id'
            ).execute()
            log_status(f"Created new file: {filename}")
        
        return True
    except Exception as e:
        log_status(f"Failed to upload {file_path}: {str(e)}")
        return False

def main():
    # Step 0: Check if we already ran successfully this week
    if already_ran_this_week():
        log_status("Already ran successfully this week - skipping until next Sunday")
        sys.exit(0)

    # Step 1: Export notes to local directory
    try:
        export_notes()
        log_status("Successfully exported notes to local directory")
    except Exception as e:
        log_status(f"Failed to export notes: {str(e)}")
        sys.exit(1)

    # Step 2: Check internet connectivity
    if not is_connected():
        log_status("No internet connection available")
        sys.exit(1)
    log_status("Internet connectivity check successful")

    # Step 3: Upload to Google Drive
    if not GOOGLE_DRIVE_FOLDER_ID:
        log_status("Google Drive folder ID not configured")
        sys.exit(1)

    try:
        service = get_google_drive_service()
        log_status("Successfully authenticated with Google Drive")
        successful_uploads = 0
        failed_uploads = 0

        total_files = len([f for f in os.listdir(output_dir) if os.path.isfile(os.path.join(output_dir, f))])
        log_status(f"Starting upload of {total_files} files to Google Drive")

        for filename in os.listdir(output_dir):
            file_path = os.path.join(output_dir, filename)
            if os.path.isfile(file_path):
                log_status(f"Attempting to upload {filename}")
                if upload_to_drive(service, file_path, GOOGLE_DRIVE_FOLDER_ID):
                    successful_uploads += 1
                    log_status(f"Successfully uploaded {filename}")
                else:
                    failed_uploads += 1
                    log_status(f"Failed to upload {filename}")

        log_status(f"Upload complete. Successfully uploaded {successful_uploads} files, {failed_uploads} failed")

        # Record successful run so we don't run again until next week
        if failed_uploads == 0:
            record_successful_run()
            log_status("Recorded successful weekly run - will skip until next Sunday")

    except Exception as e:
        log_status(f"Failed to upload to Google Drive: {str(e)}")
        sys.exit(1)

if __name__ == '__main__':
    main()
