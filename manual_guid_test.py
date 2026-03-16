"""
Manual GUID Mapping Test
This script manually adds a test GUID mapping to verify the database works.
"""
import sqlite3
import os
from datetime import datetime

# ──────────────────────────────────────────────────────────────────────────────
# UPDATE THIS PATH
STATS_DB = r"D:\ET-Stats-Adv\stats.db"
# ──────────────────────────────────────────────────────────────────────────────

print("="*80)
print("Manual GUID Mapping Test")
print("="*80)

if not os.path.exists(STATS_DB):
    print(f"❌ ERROR: stats.db not found at: {STATS_DB}")
    input("Press Enter to exit...")
    exit(1)

conn = sqlite3.connect(STATS_DB)
cursor = conn.cursor()

# Check if table exists
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='guid_mapping';")
table_exists = cursor.fetchone()

if not table_exists:
    print("Creating guid_mapping table...")
    cursor.execute("""
        CREATE TABLE guid_mapping (
            guid         TEXT PRIMARY KEY,
            player_name  TEXT NOT NULL,
            last_seen    TEXT,
            times_seen   INTEGER DEFAULT 1
        )
    """)
    conn.commit()
    print("✓ Table created")
else:
    print("✓ guid_mapping table exists")

# Insert test mapping
test_guid = "TEST1234567890ABCDEF1234567890AB"
test_name = "TestPlayer"
now = datetime.now().isoformat()

print(f"\nInserting test mapping:")
print(f"  GUID: {test_guid}")
print(f"  Name: {test_name}")

cursor.execute("""
    INSERT OR REPLACE INTO guid_mapping (guid, player_name, last_seen, times_seen)
    VALUES (?, ?, ?, 1)
""", (test_guid, test_name, now))
conn.commit()

# Verify
cursor.execute("SELECT * FROM guid_mapping WHERE guid=?", (test_guid,))
row = cursor.fetchone()

if row:
    print("\n✓ Success! Test mapping inserted:")
    print(f"  GUID: {row[0]}")
    print(f"  Name: {row[1]}")
    print(f"  Last Seen: {row[2]}")
    print(f"  Times Seen: {row[3]}")
else:
    print("\n❌ ERROR: Failed to insert test mapping")

# Show all mappings
cursor.execute("SELECT COUNT(*) FROM guid_mapping")
count = cursor.fetchone()[0]
print(f"\nTotal entries in guid_mapping: {count}")

if count > 0:
    cursor.execute("SELECT guid, player_name FROM guid_mapping LIMIT 10")
    print("\nAll mappings:")
    for guid, name in cursor.fetchall():
        print(f"  {guid[:16]}... -> {name}")

conn.close()

print("\n" + "="*80)
print("Database is working correctly!")
print("If you can't see entries after running parse_logs.bat,")
print("check the paths in log_parser.py CONFIG section.")
print("="*80)
input("\nPress Enter to exit...")
