import csv
import uuid
import os

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
    for row in reader:
        rows.append(row)

# Assign unique IDs, retry if duplicates found
while True:
    for row in rows:
        row["message-id"] = short_id()
        print(f"UUID assigned: {row['message-id']} -> \"{row['message-content'][:40]}...\"")

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
