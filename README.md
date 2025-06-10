this python script exports all notes from the apple notes app on mac to a specified directory on your computer. it then checks if you're connected to internet. if so, uploads exported notes to specified google drive folder.

![silly goose](https://media3.giphy.com/media/v1.Y2lkPTc5MGI3NjExbnR1M294bmR1MWk4bGdwbHZzdXBlZmN2ODI3c21iYzR0N3o1MWM0YyZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/7wq5iawqr1IZy/giphy.gif)


### launchd plist explanation

on the 1st of every month at 9:00 am, macos runs a python script using launchd. the script checks if the laptop is connected to the internet.

- if the laptop is online, the script runs the main task and exits successfully.
- if the laptop is offline or the task fails, the script exits with an error code.

because of the `StartInterval` setting, launchd will retry the script every hour until it runs successfully. once the script succeeds, it won't run again until the next month.

**key components:**

- `Label`: a unique identifier for the job.
- `ProgramArguments`: the command to run, including the full path to python3 and the script.
- `StartCalendarInterval`: schedules the script to run at 9:00 am on the 1st of each month.
- `StartInterval`: runs the script every 3600 seconds (1 hour), useful for retrying if it fails.
- `RunAtLoad`: ensures the script runs when the plist is first loaded or after reboot.
- `StandardOutPath` / `StandardErrorPath`: log output and errors to files in /tmp for debugging.
- `KeepAlive`: set to false, so the job doesn't automatically restart unless scheduled.

the script itself checks if the internet is available. if it is, it completes the task and exits with code 0. if not, it logs the failure and exits with code 1, allowing launchd to retry on the next interval.

.plist example:
```
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" 
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.user.uploadapplenotestogdrive</string>

  <key>ProgramArguments</key>
  <array>
    <string>/Users/Cole/Cole/PROJECTS/export-mac-apple-notes/venv/bin/python</string>
    <string>/Users/Cole/Cole/PROJECTS/export-mac-apple-notes/export-mac-apple-notes/export-mac-apple-notes.py</string>
  </array>

  <key>StartCalendarInterval</key>
  <dict>
    <key>Day</key>
    <integer>1</integer>
    <key>Hour</key>
    <integer>9</integer>
    <key>Minute</key>
    <integer>0</integer>
  </dict>

  <key>StartInterval</key>
  <integer>3600</integer>

  <key>StandardOutPath</key>
  <string>/tmp/uploadapplenotes.log</string>

  <key>StandardErrorPath</key>
  <string>/tmp/uploadapplenotes.err</string>

  <key>RunAtLoad</key>
  <true/>

  <key>KeepAlive</key>
  <false/>
</dict>
</plist>
```

## Upon changes to python script triggered by .plist

Any time you make changes to the python script, you'll need to reload the launch agent for those changes to kick into effect.

unload it:
launchctl unload ~/Library/LaunchAgents/com.user.uploadapplenotestogdrive.plist
reload it:
launchctl load ~/Library/LaunchAgents/com.user.uploadapplenotestogdrive.plist 
if at any time you want to manually kick the job off to see how it runs:
launchctl start com.user.uploadapplenotestogdrive   


### environment variables setup

create a `.env` file in the root directory with the following variables:

```
# directory where notes will be exported to
OUTPUT_DIR=/path/to/your/exported/notes/directory

# google drive api credentials
GOOGLE_DRIVE_FOLDER_ID=your_google_drive_folder_id
GOOGLE_DRIVE_TOKEN_PATH=/path/to/token.pickle
GOOGLE_DRIVE_CREDENTIALS_PATH=/path/to/credentials.json
```

to set up:
1. create a `.env` file in the root directory
2. copy the template above
3. replace the placeholder values with your actual paths and credentials
4. ensure the `.env` file is in your `.gitignore` to keep sensitive information secure


