import os
import subprocess
import re
import requests
import time
import sys
from datetime import datetime
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
    log_file = os.getenv('LOG_FILE', 'apple_notes_export.log')
    with open(log_file, "a") as f:
        f.write(f"{timestamp}: {message}\n")

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
    print(f"Exported {len(parsed_notes)} notes to {output_dir}")

def upload_to_drive(service, file_path, folder_id):
    file_metadata = {
        'name': os.path.basename(file_path),
        'parents': [folder_id]
    }
    media = MediaFileUpload(file_path, mimetype='text/plain', resumable=True)
    try:
        file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id'
        ).execute()
        return True
    except Exception as e:
        log_status(f"Failed to upload {file_path}: {str(e)}")
        return False

def main():
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

    # Step 3: Upload to Google Drive
    if not GOOGLE_DRIVE_FOLDER_ID:
        log_status("Google Drive folder ID not configured")
        sys.exit(1)

    try:
        service = get_google_drive_service()
        successful_uploads = 0
        failed_uploads = 0

        for filename in os.listdir(output_dir):
            file_path = os.path.join(output_dir, filename)
            if os.path.isfile(file_path):
                if upload_to_drive(service, file_path, GOOGLE_DRIVE_FOLDER_ID):
                    successful_uploads += 1
                else:
                    failed_uploads += 1

        log_status(f"Upload complete. Successfully uploaded {successful_uploads} files, {failed_uploads} failed")
        
    except Exception as e:
        log_status(f"Failed to upload to Google Drive: {str(e)}")
        sys.exit(1)

if __name__ == '__main__':
    main()
