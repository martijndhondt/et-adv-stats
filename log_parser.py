"""
ET:Legacy Advanced Statistics Log Parser (JayMod Edition)
Captures: kills, deaths, weapons, teams, classes, kill streaks,
          revives, health packs, ammo packs, dynamite plants, friendly fire.
          
INCLUDES BOTS IN ALL STATISTICS

Run on a schedule (Windows Task Scheduler, every 5 minutes).
"""

import sqlite3, re, os, sys, logging
from datetime import date, datetime

# ──────────────────────────────────────────────────────────────────────────────
CONFIG = {
    "games_log":      r"C:\Users\Administrator\Documents\ETLegacy\jaymod\games.log",
    "etconsole_log":  r"C:\Users\Administrator\Documents\ETLegacy\jaymod\etconsole.log",
    "jaymod_user_db": r"C:\Users\Administrator\Documents\ETLegacy\jaymod\user.db",
    "stats_db":       r"D:\ET-Stats-Adv\stats.db",
    "offset_file":    r"D:\ET-Stats-Adv\last_offset.txt",
    "console_offset": r"D:\ET-Stats-Adv\last_console_offset.txt",
}
# ──────────────────────────────────────────────────────────────────────────────

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s  %(levelname)s  %(message)s",
                    handlers=[logging.StreamHandler(sys.stdout)])
log = logging.getLogger(__name__)

RE_COLOR  = re.compile(r"\^\S")
RE_LINE   = re.compile(r"^\d+:\d{2} (\w+):(.*)")
RE_KILL   = re.compile(r"\s*(\d+)\s+(\d+)\s+(\d+):\s+(.+?)\s+killed\s+(.+?)\s+by\s+(\S+)\s*$")
RE_MAP    = re.compile(r"\\mapname\\([^\\]+)")

TEAM_MAP  = {"1": "Allies", "2": "Axis", "3": "Spectator"}
CLASS_MAP = {"0": "Soldier", "1": "Medic", "2": "Engineer", "3": "FieldOps", "4": "CovertOps"}

def strip_colors(s):
    return RE_COLOR.sub("", s or "").strip()

def parse_uci(rest):
    client_id, _, kv = rest.strip().partition(" ")
    parts = kv.split("\\")
    fields = {"client_id": client_id}
    for i in range(0, len(parts) - 1, 2):
        fields[parts[i]] = parts[i + 1]
    return fields

def game_seconds(line):
    m = re.match(r"^(\d+):(\d{2}) ", line)
    return int(m.group(1)) * 60 + int(m.group(2)) if m else 0

def init_db(path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS maps (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            day         TEXT NOT NULL,
            map_name    TEXT NOT NULL,
            started_at  TEXT,
            ended_at    TEXT,
            duration_s  INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS player_map_stats (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            map_id          INTEGER NOT NULL REFERENCES maps(id),
            player_name     TEXT NOT NULL,
            team            TEXT DEFAULT '',
            class           TEXT DEFAULT '',
            kills           INTEGER DEFAULT 0,
            deaths          INTEGER DEFAULT 0,
            team_kills      INTEGER DEFAULT 0,
            kill_streak     INTEGER DEFAULT 0,
            revives         INTEGER DEFAULT 0,
            health_packs    INTEGER DEFAULT 0,
            ammo_packs      INTEGER DEFAULT 0,
            dynamite_plants INTEGER DEFAULT 0,
            time_played_s   INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS weapon_kills (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            map_id      INTEGER NOT NULL REFERENCES maps(id),
            player_name TEXT NOT NULL,
            weapon      TEXT NOT NULL,
            kills       INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS daily_totals (
            day              TEXT PRIMARY KEY,
            total_kills      INTEGER DEFAULT 0,
            total_maps       INTEGER DEFAULT 0,
            unique_players   INTEGER DEFAULT 0,
            total_revives    INTEGER DEFAULT 0,
            total_dynaplants INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS guid_mapping (
            guid         TEXT PRIMARY KEY,
            player_name  TEXT NOT NULL,
            last_seen    TEXT,
            times_seen   INTEGER DEFAULT 1
        );
    """)
    conn.commit()
    return conn

def get_offset(path):
    try:
        return int(open(path).read().strip())
    except Exception:
        return 0

def save_offset(path, offset):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    open(path, "w").write(str(offset))

def empty_player():
    return {
        "team": "", "class": "",
        "kills": 0, "deaths": 0, "team_kills": 0,
        "kill_streak": 0, "current_streak": 0,
        "revives": 0, "health_packs": 0, "ammo_packs": 0,
        "dynamite_plants": 0,
        "joined_at": 0, "time_played_s": 0,
        "weapons": {},
    }

def update_guid_mapping(conn, guid, player_name):
    """Update GUID to player name mapping. NOW INCLUDES BOTS."""
    if not guid or not player_name:
        return
    
    # Normalize GUID to lowercase (JayMod uses lowercase)
    guid = guid.lower()
    
    c = conn.cursor()
    existing = c.execute("SELECT * FROM guid_mapping WHERE guid=?", (guid,)).fetchone()
    
    if existing:
        # Update times_seen and last_seen
        c.execute("""UPDATE guid_mapping 
                     SET last_seen=?, times_seen=times_seen+1 
                     WHERE guid=?""",
                  (datetime.now().isoformat(timespec="seconds"), guid))
    else:
        # Insert new mapping
        c.execute("""INSERT INTO guid_mapping (guid, player_name, last_seen, times_seen)
                     VALUES (?, ?, ?, 1)""",
                  (guid, player_name, datetime.now().isoformat(timespec="seconds")))
    conn.commit()

def parse_jaymod_user_db(cfg, conn):
    """Parse JayMod's user.db file for GUID mappings."""
    user_db = cfg.get("jaymod_user_db")
    if not user_db or not os.path.exists(user_db):
        log.info("JayMod user.db not found, skipping user.db GUID extraction")
        return
    
    guid_count = 0
    current_guid = None
    current_name = None
    
    with open(user_db, 'r', encoding='utf-8', errors='replace') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            
            if '=' in line:
                key, _, value = line.partition('=')
                key = key.strip()
                value = value.strip()
                
                if key == 'guid':
                    # Save previous entry if exists
                    if current_guid and current_name:
                        update_guid_mapping(conn, current_guid, current_name)
                        guid_count += 1
                    current_guid = value
                    current_name = None
                elif key == 'name' and current_guid:
                    current_name = strip_colors(value)
        
        # Don't forget the last entry
        if current_guid and current_name:
            update_guid_mapping(conn, current_guid, current_name)
            guid_count += 1
    
    if guid_count > 0:
        log.info("Extracted %d GUID mappings from user.db", guid_count)

def parse_etconsole_for_guids(cfg, conn):
    """Parse etconsole.log to extract GUID-to-name mappings. NOW INCLUDES BOTS."""
    console_log = cfg.get("etconsole_log")
    if not console_log or not os.path.exists(console_log):
        log.info("etconsole.log not found, skipping GUID extraction from console")
        return
    
    offset_file = cfg.get("console_offset", cfg["offset_file"].replace("last_offset", "last_console_offset"))
    offset = get_offset(offset_file)
    
    try:
        size = os.path.getsize(console_log)
    except FileNotFoundError:
        return
    
    if size < offset:
        log.info("etconsole.log rotated — resetting offset.")
        offset = 0
    if size == offset:
        return
    
    with open(console_log, "rb") as f:
        f.seek(offset)
        new_data = f.read()
    
    lines = new_data.decode("utf-8", errors="replace").splitlines()
    
    # Parse Userinfo lines for GUID mappings (INCLUDING BOTS)
    guid_count = 0
    for line in lines:
        if "Userinfo:" not in line:
            continue
        
        # Extract name and cl_guid
        name_match = re.search(r'\\name\\([^\\]+)', line)
        guid_match = re.search(r'\\cl_guid\\([A-F0-9]+)', line, re.IGNORECASE)
        
        if name_match and guid_match:
            name = strip_colors(name_match.group(1))
            guid = guid_match.group(1)
            
            if name and guid:
                update_guid_mapping(conn, guid, name)
                guid_count += 1
                if not guid.lower().startswith("omnibot"):
                    log.info("GUID mapping from etconsole: %s -> %s", guid[:16], name)
    
    save_offset(offset_file, size)
    if guid_count > 0:
        log.info("Extracted %d GUID mappings from etconsole.log (including bots)", guid_count)

def flush_game(conn, game, in_progress=False):
    """
    Save or update a game session.
    If game["saved_map_id"] is set, UPDATE that existing row in-place
    (preserving its id and started_at for stable ordering).
    Otherwise INSERT a new row.
    """
    if not game.get("map") or not game["players"]:
        return None
    if game.get("warmup"):
        log.info("Skipping warmup for map=%s", game["map"])
        return None

    day      = game.get("day", date.today().isoformat())
    duration = game.get("duration_s", 0)
    now      = datetime.now().isoformat(timespec="seconds")
    c        = conn.cursor()

    existing_id = game.get("saved_map_id")

    if existing_id:
        # Update the map row in-place — keeps original id and started_at
        c.execute("""UPDATE maps SET ended_at=?, duration_s=? WHERE id=?""",
                  (now if not in_progress else None, duration, existing_id))
        # Wipe old player/weapon rows for this map, re-insert fresh
        saved = c.execute(
            "SELECT SUM(kills) k, SUM(revives) r, SUM(dynamite_plants) d FROM player_map_stats WHERE map_id=?",
            (existing_id,)
        ).fetchone()
        c.execute("DELETE FROM weapon_kills WHERE map_id=?",      (existing_id,))
        c.execute("DELETE FROM player_map_stats WHERE map_id=?",  (existing_id,))
        # Adjust daily totals to remove the old counts (we'll re-add below)
        c.execute("""UPDATE daily_totals SET
            total_kills      = MAX(0, total_kills - ?),
            total_revives    = MAX(0, total_revives - ?),
            total_dynaplants = MAX(0, total_dynaplants - ?)
            WHERE day=?""",
            (saved["k"] or 0, saved["r"] or 0, saved["d"] or 0, day))
        map_id = existing_id
        log.info("Updating existing session map_id=%d map=%s", map_id, game["map"])
    else:
        # New session
        started_at = game.get("started_at", now)
        c.execute("INSERT INTO maps (day, map_name, started_at, ended_at, duration_s) VALUES (?,?,?,?,?)",
                  (day, game["map"], started_at, now if not in_progress else None, duration))
        map_id = c.lastrowid
        log.info("Inserting new session map_id=%d map=%s", map_id, game["map"])

    total_kills = total_revives = total_dynaplants = 0
    for name, s in game["players"].items():
        c.execute("""INSERT INTO player_map_stats
            (map_id, player_name, team, class, kills, deaths, team_kills,
             kill_streak, revives, health_packs, ammo_packs, dynamite_plants, time_played_s)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (map_id, name, s["team"], s["class"],
             s["kills"], s["deaths"], s["team_kills"],
             s["kill_streak"], s["revives"], s["health_packs"],
             s["ammo_packs"], s["dynamite_plants"], s["time_played_s"]))
        for weapon, wkills in s["weapons"].items():
            c.execute("INSERT INTO weapon_kills (map_id, player_name, weapon, kills) VALUES (?,?,?,?)",
                      (map_id, name, weapon, wkills))
        total_kills      += s["kills"]
        total_revives    += s["revives"]
        total_dynaplants += s["dynamite_plants"]

    c.execute("""
        INSERT INTO daily_totals (day, total_kills, total_maps, unique_players, total_revives, total_dynaplants)
        VALUES (?,?,1,?,?,?)
        ON CONFLICT(day) DO UPDATE SET
            total_kills      = total_kills + excluded.total_kills,
            total_maps       = total_maps + (CASE WHEN ? THEN 0 ELSE 1 END),
            total_revives    = total_revives + excluded.total_revives,
            total_dynaplants = total_dynaplants + excluded.total_dynaplants,
            unique_players   = (
                SELECT COUNT(DISTINCT ps.player_name)
                FROM player_map_stats ps JOIN maps m ON ps.map_id=m.id
                WHERE m.day=excluded.day
            )
    """, (day, total_kills, len(game["players"]), total_revives, total_dynaplants,
          1 if existing_id else 0))

    conn.commit()
    log.info("Saved [%s] map=%s players=%d kills=%d map_id=%d",
             "update" if existing_id else ("in-progress" if in_progress else "complete"),
             game["map"], len(game["players"]), total_kills, map_id)
    return map_id

def find_session_start(all_lines, before_idx):
    last_init = None
    for i, line in enumerate(all_lines[:before_idx + 1]):
        if " InitGame:" in line:
            last_init = i
        elif " ShutdownGame:" in line:
            last_init = None
    return last_init

def parse_log(cfg):
    conn = init_db(cfg["stats_db"])
    
    # Parse GUID mappings from JayMod user.db
    parse_jaymod_user_db(cfg, conn)
    
    # Parse etconsole.log for GUID mappings (including bots)
    parse_etconsole_for_guids(cfg, conn)
    
    offset = get_offset(cfg["offset_file"])

    try:
        size = os.path.getsize(cfg["games_log"])
    except FileNotFoundError:
        log.warning("games.log not found: %s", cfg["games_log"])
        conn.close()
        return

    log.info("File size=%d  offset=%d", size, offset)
    if size < offset:
        log.info("Log rotated — resetting offset.")
        offset = 0
    if size == offset:
        log.info("No new data.")
        conn.close()
        return

    with open(cfg["games_log"], "rb") as f:
        all_bytes = f.read()
    all_lines = all_bytes.decode("utf-8", errors="replace").splitlines()

    # Find line index for our saved byte offset
    byte_pos = 0
    new_from_line = len(all_lines)
    for i, line in enumerate(all_lines):
        if byte_pos >= offset:
            new_from_line = i
            break
        byte_pos += len((line + "\n").encode("utf-8"))

    session_start = find_session_start(all_lines, new_from_line)
    parse_from = session_start if (session_start is not None and session_start < new_from_line) else new_from_line
    log.info("Parsing from line %d (session started line %s)", parse_from, session_start)

    # Find existing in-progress DB row to update rather than re-insert
    saved_map_id = None
    if session_start is not None and session_start < new_from_line:
        mn = RE_MAP.search(all_lines[session_start])
        if mn:
            row = conn.execute(
                "SELECT id FROM maps WHERE day=? AND map_name=? ORDER BY id DESC LIMIT 1",
                (date.today().isoformat(), mn.group(1))
            ).fetchone()
            if row:
                saved_map_id = row["id"]
                log.info("Will update existing session map_id=%d", saved_map_id)

    clients = {}
    game = None

    for i, raw in enumerate(all_lines[parse_from:], start=parse_from):
        line = raw.rstrip()
        gs = game_seconds(line)

        if game is not None:
            if "Start of warmup." in line:
                game["warmup"] = True
                continue
            if "Start of round." in line:
                game["warmup"] = False
                continue

        m = RE_LINE.match(line)
        if not m:
            continue
        event, rest = m.group(1), m.group(2)

        # ── InitGame ─────────────────────────────────────────────────────────
        if event == "InitGame":
            if game and game["players"]:
                flush_game(conn, game)
            mn = RE_MAP.search(rest)
            is_warmup = bool(re.search(r"\\humans\\0\\", rest))
            clients = {}
            now = datetime.now()
            game = {
                "map":          mn.group(1) if mn else "unknown",
                "players":      {},
                "day":          now.strftime("%Y-%m-%d"),
                "started_at":   now.isoformat(timespec="seconds"),
                "ended_at":     None,
                "warmup":       is_warmup,
                "saved_map_id": saved_map_id if i == parse_from else None,
                "start_gs":     gs,
                "duration_s":   0,
            }
            saved_map_id = None

        # ── ShutdownGame ──────────────────────────────────────────────────────
        elif event == "ShutdownGame":
            if game:
                game["ended_at"]  = datetime.now().isoformat(timespec="seconds")
                game["duration_s"]= gs - game.get("start_gs", 0)
                for name, s in game["players"].items():
                    if s["joined_at"] > 0:
                        s["time_played_s"] += gs - s["joined_at"]
                        s["joined_at"] = 0
                flush_game(conn, game, in_progress=False)
                game = None
                clients = {}

        # ── ClientUserinfoChanged ─────────────────────────────────────────────
        elif event == "ClientUserinfoChanged" and game is not None:
            fields = parse_uci(rest)
            cid  = fields.get("client_id", "")
            name = strip_colors(fields.get("n", ""))
            team = TEAM_MAP.get(fields.get("t", ""), "")
            cls  = CLASS_MAP.get(fields.get("c", ""), "")
            if not name:
                continue
            old_name = clients.get(cid)
            if old_name and old_name != name and old_name in game["players"]:
                game["players"][name] = game["players"].pop(old_name)
            clients[cid] = name
            if name not in game["players"]:
                game["players"][name] = empty_player()
                game["players"][name]["joined_at"] = gs
            p = game["players"][name]
            if team and team != "Spectator":
                p["team"] = team
            if cls:
                p["class"] = cls

        # ── ClientDisconnect ──────────────────────────────────────────────────
        elif event == "ClientDisconnect" and game is not None:
            cid = rest.strip()
            name = clients.get(cid)
            if name and name in game["players"]:
                p = game["players"][name]
                if p["joined_at"] > 0:
                    p["time_played_s"] += gs - p["joined_at"]
                    p["joined_at"] = 0

        # ── Kill ──────────────────────────────────────────────────────────────
        elif event == "Kill" and game is not None:
            mk = RE_KILL.search(rest)
            if not mk:
                continue
            killer_id = mk.group(1)
            victim_id = mk.group(2)
            killer    = strip_colors(mk.group(4))
            victim    = strip_colors(mk.group(5))
            weapon    = mk.group(6)

            for name, cid in [(killer, killer_id), (victim, victim_id)]:
                if name and name != "<world>" and name not in game["players"]:
                    game["players"][name] = empty_player()
                    game["players"][name]["joined_at"] = gs
                    clients[cid] = name

            killer_team = game["players"].get(killer, {}).get("team", "")
            victim_team  = game["players"].get(victim,  {}).get("team", "")
            friendly = killer_team and victim_team and killer_team == victim_team

            if killer and killer != "<world>":
                p = game["players"][killer]
                if friendly:
                    p["team_kills"] += 1
                    p["current_streak"] = 0
                else:
                    p["kills"] += 1
                    p["weapons"][weapon] = p["weapons"].get(weapon, 0) + 1
                    p["current_streak"] += 1
                    if p["current_streak"] > p["kill_streak"]:
                        p["kill_streak"] = p["current_streak"]

            if victim and victim in game["players"]:
                game["players"][victim]["deaths"] += 1
                game["players"][victim]["current_streak"] = 0

        # ── Medic_Revive ──────────────────────────────────────────────────────
        elif event == "Medic_Revive" and game is not None:
            cid = rest.strip().split()[0]
            name = clients.get(cid)
            if name and name in game["players"]:
                game["players"][name]["revives"] += 1

        # ── Health_Pack ───────────────────────────────────────────────────────
        elif event == "Health_Pack" and game is not None:
            cid = rest.strip().split()[0]
            name = clients.get(cid)
            if name and name in game["players"]:
                game["players"][name]["health_packs"] += 1

        # ── Ammo_Pack ─────────────────────────────────────────────────────────
        elif event == "Ammo_Pack" and game is not None:
            cid = rest.strip().split()[0]
            name = clients.get(cid)
            if name and name in game["players"]:
                game["players"][name]["ammo_packs"] += 1

        # ── Dynamite_Plant ────────────────────────────────────────────────────
        elif event == "Dynamite_Plant" and game is not None:
            cid = rest.strip()
            name = clients.get(cid)
            if name and name in game["players"]:
                game["players"][name]["dynamite_plants"] += 1

    # Flush in-progress game at end of file
    if game and game["players"] and not game.get("warmup"):
        flush_game(conn, game, in_progress=True)

    save_offset(cfg["offset_file"], size)
    log.info("Done. Offset=%d", size)
    conn.close()

if __name__ == "__main__":
    parse_log(CONFIG)
