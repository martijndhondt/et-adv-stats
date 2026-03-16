"""
Diagnostic script to test GUID mapping from etconsole.log
"""
import sqlite3
import re
import os

# ──────────────────────────────────────────────────────────────────────────────
# UPDATE THESE PATHS TO MATCH YOUR SYSTEM
CONFIG = {
    "etconsole_log": r"C:\Users\Administrator\Documents\ETLegacy\legacy\etconsole.log",
    "stats_db":      r"D:\ET-Stats-Adv\stats.db",
}
# ──────────────────────────────────────────────────────────────────────────────

RE_COLOR = re.compile(r"\^\S")

def strip_colors(s):
    return RE_COLOR.sub("", s or "").strip()

print("="*80)
print("GUID Mapping Diagnostic Tool")
print("="*80)

# Check if etconsole.log exists
print(f"\n1. Checking etconsole.log path...")
if not os.path.exists(CONFIG["etconsole_log"]):
    print(f"   ❌ ERROR: etconsole.log not found at: {CONFIG['etconsole_log']}")
    print(f"   Please update the path in this script.")
    input("\nPress Enter to exit...")
    exit(1)
else:
    size = os.path.getsize(CONFIG["etconsole_log"])
    print(f"   ✓ Found etconsole.log ({size:,} bytes)")

# Read and parse etconsole.log
print(f"\n2. Parsing etconsole.log for GUID mappings...")
with open(CONFIG["etconsole_log"], "r", encoding="utf-8", errors="replace") as f:
    lines = f.readlines()

print(f"   Total lines in file: {len(lines):,}")

# Find Userinfo lines
userinfo_lines = [line for line in lines if "Userinfo:" in line]
print(f"   Found {len(userinfo_lines):,} Userinfo lines")

# Parse GUIDs
guid_mappings = []
for line in userinfo_lines:
    name_match = re.search(r'\\name\\([^\\]+)', line)
    guid_match = re.search(r'\\cl_guid\\([A-F0-9]+)', line)
    
    if name_match and guid_match:
        name = strip_colors(name_match.group(1))
        guid = guid_match.group(1)
        
        if name and guid and not guid.startswith("OMNIBOT"):
            guid_mappings.append((guid, name))

print(f"   Found {len(guid_mappings)} non-bot GUID mappings")

if guid_mappings:
    print(f"\n3. Sample GUID mappings found:")
    for guid, name in guid_mappings[:10]:
        print(f"      {guid[:16]}... -> {name}")
else:
    print(f"\n   ⚠ No real player GUIDs found in etconsole.log")
    print(f"   This is normal if only bots have connected to your server.")
    print(f"   Once real players join, their GUIDs will be captured.")

# Check stats.db
print(f"\n4. Checking stats.db...")
if not os.path.exists(CONFIG["stats_db"]):
    print(f"   ❌ ERROR: stats.db not found at: {CONFIG['stats_db']}")
    print(f"   Please run parse_logs.bat first to create the database.")
    input("\nPress Enter to exit...")
    exit(1)
else:
    print(f"   ✓ Found stats.db")

# Check if guid_mapping table exists
conn = sqlite3.connect(CONFIG["stats_db"])
cursor = conn.cursor()

cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='guid_mapping';")
table_exists = cursor.fetchone()

if not table_exists:
    print(f"   ⚠ guid_mapping table does not exist yet")
    print(f"   Run parse_logs.bat to create it")
else:
    print(f"   ✓ guid_mapping table exists")
    
    # Check current mappings
    cursor.execute("SELECT COUNT(*) FROM guid_mapping")
    count = cursor.fetchone()[0]
    print(f"   Current entries in guid_mapping: {count}")
    
    if count > 0:
        cursor.execute("SELECT guid, player_name, last_seen, times_seen FROM guid_mapping LIMIT 10")
        rows = cursor.fetchall()
        print(f"\n5. Current GUID mappings in database:")
        for guid, name, last_seen, times_seen in rows:
            print(f"      {guid[:16]}... -> {name} (seen {times_seen}x, last: {last_seen})")
    else:
        print(f"\n   ⚠ No entries in guid_mapping table yet")
        print(f"   This means parse_logs.bat hasn't been run, or etconsole_log path is wrong in log_parser.py")

conn.close()

print("\n" + "="*80)
print("NEXT STEPS:")
print("="*80)
if not guid_mappings:
    print("1. No real players have connected yet (only bots)")
    print("2. Once real players join, run parse_logs.bat")
    print("3. Their GUIDs will be automatically mapped")
elif not table_exists:
    print("1. Run parse_logs.bat to create the guid_mapping table")
    print("2. The script will process etconsole.log and populate mappings")
elif count == 0:
    print("1. Make sure 'etconsole_log' path in log_parser.py matches this diagnostic:")
    print(f"   etconsole_log: r\"{CONFIG['etconsole_log']}\"")
    print("2. Run parse_logs.bat")
    print("3. Check for any errors in the output")
else:
    print("✓ Everything looks good! GUID mappings are working.")
    print(f"✓ {count} players mapped so far")

print("\nPress Enter to exit...")
input()
