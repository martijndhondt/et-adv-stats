"""
Test GUID Parser - Verbose Version
Run this to see exactly what's happening when parsing etconsole.log
"""
import sqlite3
import re
import os
from datetime import datetime

# ──────────────────────────────────────────────────────────────────────────────
# UPDATE THESE PATHS TO MATCH YOUR log_parser.py CONFIG
CONFIG = {
    "etconsole_log":  r"C:\Users\Administrator\Documents\ETLegacy\legacy\etconsole.log",
    "stats_db":       r"D:\ET-Stats-Adv\stats.db",
    "console_offset": r"D:\ET-Stats-Adv\last_console_offset.txt",
}
# ──────────────────────────────────────────────────────────────────────────────

RE_COLOR = re.compile(r"\^\S")

def strip_colors(s):
    return RE_COLOR.sub("", s or "").strip()

def get_offset(path):
    try:
        return int(open(path).read().strip())
    except Exception:
        return 0

def save_offset(path, offset):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    open(path, "w").write(str(offset))

print("="*80)
print("GUID Parser Test - Verbose Mode")
print("="*80)

# Check etconsole.log
print(f"\n1. Checking etconsole.log...")
console_log = CONFIG["etconsole_log"]
print(f"   Path: {console_log}")

if not os.path.exists(console_log):
    print(f"   ❌ ERROR: File not found!")
    input("\nPress Enter to exit...")
    exit(1)

size = os.path.getsize(console_log)
print(f"   ✓ File found ({size:,} bytes)")

# Check offset
offset_file = CONFIG["console_offset"]
print(f"\n2. Checking offset file...")
print(f"   Path: {offset_file}")

offset = get_offset(offset_file)
print(f"   Current offset: {offset:,} bytes")

if size < offset:
    print(f"   Log rotated - resetting offset to 0")
    offset = 0

if size == offset:
    print(f"   ⚠ No new data to process (file size = offset)")
    print(f"   This means all data has already been processed.")
    print(f"   To reprocess, delete: {offset_file}")
    reprocess = input("\n   Delete offset and reprocess? (y/n): ")
    if reprocess.lower() == 'y':
        if os.path.exists(offset_file):
            os.remove(offset_file)
        offset = 0
        print(f"   ✓ Offset reset to 0")
    else:
        print(f"   Exiting...")
        input("\nPress Enter to exit...")
        exit(0)

# Read new data
print(f"\n3. Reading etconsole.log from byte {offset:,} to {size:,}...")
with open(console_log, "rb") as f:
    f.seek(offset)
    new_data = f.read()

lines = new_data.decode("utf-8", errors="replace").splitlines()
print(f"   Read {len(lines):,} new lines")

# Parse Userinfo lines
print(f"\n4. Parsing Userinfo lines...")
userinfo_lines = [line for line in lines if "Userinfo:" in line]
print(f"   Found {len(userinfo_lines):,} Userinfo lines")

if len(userinfo_lines) > 0:
    print(f"\n   Sample Userinfo line:")
    print(f"   {userinfo_lines[0][:200]}...")

# Extract GUIDs
guid_mappings = []
for i, line in enumerate(userinfo_lines):
    name_match = re.search(r'\\name\\([^\\]+)', line)
    guid_match = re.search(r'\\cl_guid\\([A-F0-9]+)', line)
    
    if name_match and guid_match:
        name = strip_colors(name_match.group(1))
        guid = guid_match.group(1)
        
        if name and guid:
            is_bot = guid.startswith("OMNIBOT")
            guid_mappings.append((guid, name, is_bot))
            if i < 5:  # Show first 5
                print(f"   Line {i+1}: {guid[:16]}... -> {name} {'(BOT)' if is_bot else ''}")

non_bot_mappings = [(g, n) for g, n, b in guid_mappings if not b]
print(f"\n   Total GUIDs found: {len(guid_mappings)}")
print(f"   Non-bot GUIDs: {len(non_bot_mappings)}")
print(f"   Bot GUIDs (skipped): {len(guid_mappings) - len(non_bot_mappings)}")

if len(non_bot_mappings) == 0:
    print(f"\n   ⚠ No real player GUIDs to process")
    print(f"   This is normal if only bots have connected.")
else:
    print(f"\n5. Inserting into database...")
    print(f"   Database: {CONFIG['stats_db']}")
    
    if not os.path.exists(CONFIG["stats_db"]):
        print(f"   ❌ ERROR: stats.db not found!")
        input("\nPress Enter to exit...")
        exit(1)
    
    conn = sqlite3.connect(CONFIG["stats_db"])
    cursor = conn.cursor()
    
    # Check table
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='guid_mapping';")
    if not cursor.fetchone():
        print(f"   Creating guid_mapping table...")
        cursor.execute("""
            CREATE TABLE guid_mapping (
                guid         TEXT PRIMARY KEY,
                player_name  TEXT NOT NULL,
                last_seen    TEXT,
                times_seen   INTEGER DEFAULT 1
            )
        """)
        conn.commit()
    
    inserted = 0
    updated = 0
    now = datetime.now().isoformat()
    
    for guid, name in non_bot_mappings:
        existing = cursor.execute("SELECT * FROM guid_mapping WHERE guid=?", (guid,)).fetchone()
        
        if existing:
            cursor.execute("""UPDATE guid_mapping 
                             SET last_seen=?, times_seen=times_seen+1 
                             WHERE guid=?""", (now, guid))
            updated += 1
            print(f"   Updated: {guid[:16]}... -> {name}")
        else:
            cursor.execute("""INSERT INTO guid_mapping (guid, player_name, last_seen, times_seen)
                             VALUES (?, ?, ?, 1)""", (guid, name, now))
            inserted += 1
            print(f"   Inserted: {guid[:16]}... -> {name}")
    
    conn.commit()
    print(f"\n   ✓ Inserted: {inserted}")
    print(f"   ✓ Updated: {updated}")
    
    # Verify
    cursor.execute("SELECT COUNT(*) FROM guid_mapping")
    total = cursor.fetchone()[0]
    print(f"   ✓ Total entries in database: {total}")
    
    conn.close()

# Save offset
print(f"\n6. Saving offset...")
save_offset(offset_file, size)
print(f"   ✓ Offset saved: {size:,} bytes")

print("\n" + "="*80)
print("COMPLETE!")
print("="*80)
if len(non_bot_mappings) > 0:
    print(f"✓ Successfully processed {len(non_bot_mappings)} GUID mappings")
else:
    print("No real player GUIDs found (only bots have connected)")
    print("Once real players join, run this script again or run parse_logs.bat")

input("\nPress Enter to exit...")
