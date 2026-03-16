# ET:Legacy Advanced Stats - JayMod Edition

## What's New in This Version

### ✅ JayMod Support
- Reads XP data from JayMod's `user.db` flat file
- Decodes base64-encoded XP skills
- Supports JayMod's GUID format (lowercase)

### ✅ Bots Included in Statistics
**ALL OMNIBOT filters have been removed!**
- Bots now appear in player leaderboards
- Bot kills, deaths, and stats are tracked
- Bot XP is displayed in rankings
- GUID mappings include bots

This means you'll see both real players AND bots like:
- [BOT]Putin
- [BOT]Cledus
- [BOT]Fullmonty
- etc.

## Files Updated

### 1. app.py
- **Changed**: Reads from JayMod's `user.db` instead of `etl.db`
- **New**: `parse_jaymod_user_db()` function to parse flat file format
- **New**: `decode_xp()` function for base64-encoded XP
- **Removed**: All OMNIBOT filters

### 2. log_parser.py
- **Changed**: Parses JayMod's `user.db` for GUID mappings
- **Changed**: Normalizes GUIDs to lowercase (JayMod format)
- **Removed**: All OMNIBOT filters
- **Updated**: GUID mapping includes bots

## Configuration

Update the paths in your files to match your JayMod installation:

### app.py CONFIG:
```python
CONFIG = {
    "stats_db":       r"D:\ET-Stats-Adv\stats.db",
    "jaymod_user_db": r"D:\ETLegacy\jaymod\user.db",  # <-- JayMod user database
    "host": "0.0.0.0",
    "port": 5001,
    "debug": False,
}
```

### log_parser.py CONFIG:
```python
CONFIG = {
    "games_log":      r"D:\ETLegacy\jaymod\games.log",
    "etconsole_log":  r"D:\ETLegacy\jaymod\etconsole.log",
    "jaymod_user_db": r"D:\ETLegacy\jaymod\user.db",      # <-- JayMod user database
    "stats_db":       r"D:\ET-Stats-Adv\stats.db",
    "offset_file":    r"D:\ET-Stats-Adv\last_offset.txt",
    "console_offset": r"D:\ET-Stats-Adv\last_console_offset.txt",
}
```

## JayMod File Formats

### user.db (Flat Text File)
```
guid = fb66d33ce37d6017bf1dfb2b2e393f11
timestamp = 1773435775
ip = 192.168.0.61
mac = 34:5a:60:05:ec:07
name = Thufke
namex = Thufke
authLevel = 0
greetingText = 
greetingAudio = 
xpSkills = UyFn9eYA6SPqH999Rsm1nf7e8xNnnzEJPgzDXnDh6vM=
```

**Key fields:**
- `guid` - Player's unique identifier (lowercase hex)
- `name` - Player name without color codes
- `namex` - Player name with color codes
- `xpSkills` - Base64-encoded XP data

### XP Skills Decoding
The `xpSkills` field is base64-encoded and contains:
- S0 = Battle Sense
- S1 = Engineering
- S2 = First Aid
- S3 = Signals
- S4 = Light Weapons
- S5 = Heavy Weapons
- S6 = Covert Ops

Example decoded: `S0\176\S1\36\S2\0\S3\71\S4\159\S5\3\S6\0`

## GUID Mapping System

The system uses **three sources** for GUID-to-name mappings:

### 1. JayMod user.db (Primary)
- Parses user.db file directly
- Gets GUID and name from the same record
- Most reliable for JayMod

### 2. etconsole.log (Real-time)
- Captures GUIDs when players connect
- Includes both real players and bots
- Updates in real-time

### 3. Automatic Normalization
- JayMod uses lowercase GUIDs
- System normalizes all GUIDs to lowercase for matching

## How It Works

### When You Run parse_logs.bat:

1. **Reads JayMod user.db**
   - Extracts all GUID-to-name mappings
   - Includes both players and bots
   - Stores in `guid_mapping` table

2. **Reads etconsole.log**
   - Extracts GUIDs from Userinfo lines
   - Updates mappings with latest names
   - Handles name changes

3. **Processes games.log**
   - Tracks kills, deaths, weapons, etc.
   - Stores match statistics
   - **Includes bot statistics**

4. **Result**
   - Complete player and bot statistics
   - XP rankings with proper names
   - Historical match data

## What You'll See

### Player/Bot Leaderboards
```
#  Player              Kills  Deaths  K/D    Streak  Time
1  [BOT]Putin           423    198    2.14    21    145m
2  Thufke               387    215    1.80    15    132m
3  [BOT]Fullmonty       356    203    1.75    22    128m
4  [BOT]Cledus          298    187    1.59    15    117m
```

### XP Rankings
```
#  Player              Total XP  Battle  Eng  First  Signals  Light  Heavy  Covert
1  Thufke                 445     176    36    0      71      159     3      0
2  [BOT]Putin             387     145    42    18     56      126     0      0
3  [BOT]Cledus            324     121    28    15     48      112     0      0
```

## Restart Required

After updating the files:

1. **Stop your web server** (Ctrl+C if running)

2. **Update CONFIG paths** in both `app.py` and `log_parser.py`

3. **Run the log parser once:**
   ```
   parse_logs.bat
   ```

4. **Verify mappings:**
   - Check the console output for "Extracted X GUID mappings from user.db"
   - Should see mappings for both players and bots

5. **Start the web server:**
   ```
   start_server.bat
   ```

6. **Clear browser cache** (Ctrl+F5)

## Differences from ET:Legacy/Nitmod

| Feature | ET:Legacy | Nitmod | JayMod |
|---------|-----------|--------|--------|
| **Database Type** | SQLite (etl.db) | SQLite (nitmod.sqlite) | Flat text files |
| **XP Storage** | Columns (skill0-6) | Base64 encoded | Base64 encoded |
| **GUID Format** | Mixed case | Mixed case | Lowercase |
| **Player DB** | prestige_users table | users table | user.db file |
| **Bots in Stats** | ❌ Filtered out | ❌ Filtered out | ✅ **Included!** |

## Troubleshooting

### Issue: "user.db not found or empty"

**Solution:**
1. Check the path in `app.py` CONFIG
2. Verify JayMod is writing to user.db
3. Make sure at least one player has connected

### Issue: No XP data showing

**Solution:**
1. Players must have played at least one match
2. JayMod writes to user.db when players disconnect
3. Check that `jaymod_user_db` path is correct in both files

### Issue: Bots not showing up

**Solution:**
1. Verify OMNIBOT filters were removed (check log_parser.py)
2. Run `parse_logs.bat` to reprocess logs
3. Check that bots are connecting (look in games.log)

### Issue: GUID mappings not working

**Solution:**
1. JayMod uses **lowercase** GUIDs
2. System auto-normalizes to lowercase
3. Check guid_mapping table: `SELECT * FROM guid_mapping LIMIT 10;`
4. Run `parse_logs.bat` to rebuild mappings

## Testing

To verify everything works:

1. **Check user.db exists and has data:**
   ```
   notepad D:\ETLegacy\jaymod\user.db
   ```
   Should see guid/name/xpSkills entries

2. **Run parse_logs.bat and watch output:**
   ```
   INFO  Extracted 15 GUID mappings from user.db
   INFO  Extracted 12 GUID mappings from etconsole.log (including bots)
   ```

3. **Check stats.db for mappings:**
   ```sql
   SELECT * FROM guid_mapping;
   ```
   Should see both player and bot GUIDs

4. **View XP rankings:**
   - Go to http://localhost:5001
   - Click "XP Ranks" tab
   - Should see players and bots with XP data

## Bot Names

Typical bot names you'll see:
- [BOT]Putin
- [BOT]Fullmonty
- [BOT]Cledus
- [BOT]Chimichanga
- [BOT]Kaolin
- [BOT]Michael
- [BOT]WhittlinMan
- [BOT]Mungri
- And more...

All these bots will now appear in your statistics!

## Benefits

### Why Include Bots?

1. **Server Activity**: Shows true server activity, not just human players
2. **Practice Tracking**: Track your performance against bots
3. **Complete Picture**: See the full competitive landscape
4. **Testing**: Easier to test the system with bot data

### Performance

- Bots don't slow down the system
- Same database structure, more data
- Filtering by player type can be added later if needed

## Future Enhancements

If you want to filter bots later, you could:
1. Add a `is_bot` column to `player_map_stats`
2. Filter in SQL queries: `WHERE is_bot = 0`
3. Add a toggle in the web interface

For now, all players (human and bot) are treated equally!
