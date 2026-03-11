import csv
import uuid
import os
import random

def short_id():
    return uuid.uuid4().hex[:8]

path = input("Path to message_index.csv: ").strip().strip("'\"")

if not os.path.isfile(path):
    print(f"File not found: {path}")
    exit(1)

rows = []
with open(path, "r", newline="", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    fieldnames = reader.fieldnames

    # Validate CSV structure
    required_columns = {"message-content", "timestamp", "message-id"}
    if fieldnames is None:
        print("Error: CSV file is empty or has no header.")
        exit(1)
    missing = required_columns - set(fieldnames)
    if missing:
        print(f"Error: Missing required column(s): {', '.join(missing)}")
        exit(1)

    for i, row in enumerate(reader, start=2):
        # Check for empty required fields (except message-id, which will be assigned)
        if not row.get("message-content", "").strip():
            print(f"Error: Row {i} has empty 'message-content'.")
            exit(1)
        if not row.get("timestamp", "").strip():
            print(f"Error: Row {i} has empty 'timestamp'.")
            exit(1)
        if not row["timestamp"].strip().isdigit():
            print(f"Error: Row {i} has invalid 'timestamp': \"{row['timestamp']}\" (must be numeric).")
            exit(1)
        rows.append(row)

if len(rows) == 0:
    print("Error: CSV file has no data rows.")
    exit(1)

print(f"CSV valid! {len(rows)} row(s) found.\n")

# Shuffle rows randomly (keeping each row's fields intact)
random.shuffle(rows)

# Assign unique IDs, retry if duplicates found
while True:
    for row in rows:
        row["message-id"] = short_id()

    ids = [row["message-id"] for row in rows]
    if len(ids) == len(set(ids)):
        print("\nAll IDs are unique!")
        break
    print("\nDuplicate IDs found, retrying...")

with open(path, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)

print(f"\nDone! {len(rows)} message(s) processed.")
