import os
import subprocess
import re

# Change this to your desired output path
output_dir = "/Users/Cole/Cole/PROJECTS/export-mac-apple-notes/exported-notes"

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

if __name__ == '__main__':
    export_notes()
