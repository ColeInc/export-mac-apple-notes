# Apple Notes Export to Google Drive

This script exports all notes from the Apple Notes app on Mac and uploads them to a Google Drive folder. It runs automatically every Sunday at midnight, with retry logic if your laptop is offline.

![silly goose](https://media3.giphy.com/media/v1.Y2lkPTc5MGI3NjExbnR1M294bmR1MWk4bGdwbHZzdXBlZmN2ODI3c21iYzR0N3o1MWM0YyZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/7wq5iawqr1IZy/giphy.gif)

---

## Quick Start (Restore from Scratch)

### 1. Create Virtual Environment

```bash
cd /Users/cole/Cole/PROJECTS/export-mac-apple-notes
python3 -m venv venv
source venv/bin/activate
pip install -r export-mac-apple-notes/requirements.txt
```

### 2. Set Up Google Drive API Credentials

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or select existing)
3. Enable the **Google Drive API** (APIs & Services > Library)
4. Create OAuth credentials (APIs & Services > Credentials > Create Credentials > OAuth client ID)
   - Application type: **Desktop app**
   - Download the JSON file
5. Add `http://localhost` to Authorized redirect URIs
6. Save the credentials JSON file to the project directory

### 3. Create .env File

Create `/Users/cole/Cole/PROJECTS/export-mac-apple-notes/export-mac-apple-notes/.env`:

```bash
# Local export directory
OUTPUT_DIR=/Users/cole/Cole/PROJECTS/export-mac-apple-notes/exported-notes

# Google Drive settings
GOOGLE_DRIVE_FOLDER_ID=your_folder_id_from_drive_url
GOOGLE_DRIVE_CREDENTIALS_PATH=/full/path/to/your/credentials.json
GOOGLE_DRIVE_TOKEN_PATH=/Users/cole/Cole/PROJECTS/export-mac-apple-notes/token.pickle

# Logging
LOG_FILE=/tmp/apple_notes_export.log
```

**To get your Google Drive folder ID:** Open the folder in Google Drive, the ID is in the URL:
`https://drive.google.com/drive/folders/THIS_IS_THE_FOLDER_ID`

### 4. Run Once to Authenticate

```bash
cd /Users/cole/Cole/PROJECTS/export-mac-apple-notes/export-mac-apple-notes
../venv/bin/python export-mac-apple-notes.py
```

A browser will open - sign in and authorize the app. This creates `token.pickle` for future runs.

### 5. Install the LaunchAgent

Copy the plist to LaunchAgents:

```bash
cp com.user.uploadapplenotestogdrive.plist ~/Library/LaunchAgents/
```

Or create `~/Library/LaunchAgents/com.user.uploadapplenotestogdrive.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.user.uploadapplenotestogdrive</string>

  <key>ProgramArguments</key>
  <array>
    <string>/Users/cole/Cole/PROJECTS/export-mac-apple-notes/venv/bin/python</string>
    <string>/Users/cole/Cole/PROJECTS/export-mac-apple-notes/export-mac-apple-notes/export-mac-apple-notes.py</string>
  </array>

  <key>WorkingDirectory</key>
  <string>/Users/cole/Cole/PROJECTS/export-mac-apple-notes/export-mac-apple-notes</string>

  <key>StartCalendarInterval</key>
  <dict>
    <key>Weekday</key>
    <integer>0</integer>
    <key>Hour</key>
    <integer>0</integer>
    <key>Minute</key>
    <integer>0</integer>
  </dict>

  <key>StartInterval</key>
  <integer>7200</integer>

  <key>StandardOutPath</key>
  <string>/tmp/uploadapplenotes.log</string>

  <key>StandardErrorPath</key>
  <string>/tmp/uploadapplenotes.err</string>

  <key>RunAtLoad</key>
  <false/>

  <key>KeepAlive</key>
  <false/>
</dict>
</plist>
```

### 6. Load the LaunchAgent

```bash
launchctl load ~/Library/LaunchAgents/com.user.uploadapplenotestogdrive.plist
```

---

## How the Schedule Works

| Trigger | When |
|---------|------|
| **Primary** | Every Sunday at 12:00 AM (midnight) |
| **Retry** | Every 2 hours if the primary run failed |

### Behavior

1. **Sunday midnight**: Script attempts to run
2. **If successful**: Records timestamp to `.last_successful_run`, skips all runs until next Sunday
3. **If failed** (laptop closed/no internet): Exits with error, launchd retries in 2 hours
4. **Retry continues** every 2 hours until one succeeds
5. **Once successful**: All 2-hour triggers skip until next Sunday

### What Happens If Your Computer Is Off?

- **Off at midnight Sunday**: Missed, but 2-hour retry catches it when you open your laptop
- **Off for the whole week**: First wake triggers the 2-hour interval, notes sync
- **Success is remembered**: Only syncs once per week even with multiple wakes

---

## Useful Commands

```bash
# Check if the job is loaded
launchctl list | grep uploadapplenotestogdrive

# Manually trigger a run
launchctl start com.user.uploadapplenotestogdrive

# View logs
cat /tmp/apple_notes_export.log
tail -f /tmp/apple_notes_export.log  # live follow

# View errors
cat /tmp/uploadapplenotes.err

# Unload the job (stop scheduling)
launchctl unload ~/Library/LaunchAgents/com.user.uploadapplenotestogdrive.plist

# Reload after changes
launchctl unload ~/Library/LaunchAgents/com.user.uploadapplenotestogdrive.plist
launchctl load ~/Library/LaunchAgents/com.user.uploadapplenotestogdrive.plist

# Force a fresh run this week (delete success tracker)
rm /Users/cole/Cole/PROJECTS/export-mac-apple-notes/export-mac-apple-notes/.last_successful_run
launchctl start com.user.uploadapplenotestogdrive
```

---

## File Locations

| File | Path |
|------|------|
| Script | `/Users/cole/Cole/PROJECTS/export-mac-apple-notes/export-mac-apple-notes/export-mac-apple-notes.py` |
| Environment | `/Users/cole/Cole/PROJECTS/export-mac-apple-notes/export-mac-apple-notes/.env` |
| LaunchAgent | `~/Library/LaunchAgents/com.user.uploadapplenotestogdrive.plist` |
| Exported notes | `/Users/cole/Cole/PROJECTS/export-mac-apple-notes/exported-notes/` |
| Google token | `/Users/cole/Cole/PROJECTS/export-mac-apple-notes/token.pickle` |
| Success tracker | `/Users/cole/Cole/PROJECTS/export-mac-apple-notes/export-mac-apple-notes/.last_successful_run` |
| Log file | `/tmp/apple_notes_export.log` |
| Error log | `/tmp/uploadapplenotes.err` |

---

## How It Works

1. **Export**: Uses AppleScript to extract all notes from Apple Notes app
2. **Save locally**: Writes each note as a `.txt` file to the output directory
3. **Check internet**: Pings Google to verify connectivity
4. **Upload to Drive**: For each file:
   - Checks if file already exists in the Drive folder
   - Updates existing file OR creates new file
   - Does NOT create duplicates
5. **Track success**: Records timestamp so it skips until next Sunday

---

## Troubleshooting

### "Access blocked: redirect_uri_mismatch"
Add `http://localhost` to Authorized redirect URIs in Google Cloud Console credentials.

### Script not running
```bash
# Check if loaded
launchctl list | grep uploadapplenotestogdrive

# Check for errors
cat /tmp/uploadapplenotes.err
```

### Token expired
Delete `token.pickle` and run the script manually to re-authenticate:
```bash
rm /Users/cole/Cole/PROJECTS/export-mac-apple-notes/token.pickle
../venv/bin/python export-mac-apple-notes.py
```

### Force immediate sync
```bash
rm /Users/cole/Cole/PROJECTS/export-mac-apple-notes/export-mac-apple-notes/.last_successful_run
launchctl start com.user.uploadapplenotestogdrive
```
