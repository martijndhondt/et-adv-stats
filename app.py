"""
ET:Legacy Advanced Statistics Web Server (JayMod Edition)
Browse to http://localhost:5001
"""

import sqlite3, os, re, base64
from datetime import date
from flask import Flask, render_template, jsonify, request

# ──────────────────────────────────────────────────────────────────────────────
CONFIG = {
    "stats_db":  r"D:\ET-Stats-Adv\stats.db",
    "jaymod_user_db": r"C:\Users\Administrator\Documents\ETLegacy\jaymod\user.db",  # JayMod user database
    "host": "0.0.0.0",
    "port": 5001,
    "debug": False,
}
# ──────────────────────────────────────────────────────────────────────────────

app = Flask(__name__)
RE_COLOR = re.compile(r"\^\S")
XP_SKILLS = ["Battle Sense", "Engineering", "First Aid", "Signals",
              "Light Weapons", "Heavy Weapons", "Covert Ops"]

def strip_colors(s):
    return RE_COLOR.sub("", s or "").strip()

def decode_xp(raw):
    """Decode base64 XP skills from JayMod user.db"""
    result = {s: 0 for s in XP_SKILLS}
    try:
        decoded = base64.b64decode(raw).decode("utf-8", errors="replace")
        parts = decoded.split("\\")
        for i in range(0, len(parts) - 1, 2):
            m = re.match(r"S(\d+)", parts[i])
            if m:
                idx = int(m.group(1))
                if idx < len(XP_SKILLS):
                    result[XP_SKILLS[idx]] = int(parts[i + 1] or 0)
    except Exception:
        pass
    return result

def parse_jaymod_user_db(path):
    """Parse JayMod's user.db flat file format"""
    if not os.path.exists(path):
        return {}
    
    users = {}
    current_user = {}
    
    with open(path, 'r', encoding='utf-8', errors='replace') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            
            if '=' in line:
                key, _, value = line.partition('=')
                key = key.strip()
                value = value.strip()
                
                if key == 'guid':
                    # Start of new user record
                    if current_user and 'guid' in current_user:
                        users[current_user['guid']] = current_user
                    current_user = {'guid': value}
                elif current_user:
                    current_user[key] = value
        
        # Don't forget the last user
        if current_user and 'guid' in current_user:
            users[current_user['guid']] = current_user
    
    return users

def db(path=None):
    p = path or CONFIG["stats_db"]
    if not os.path.exists(p):
        return None
    conn = sqlite3.connect(p)
    conn.row_factory = sqlite3.Row
    return conn


# ── OVERVIEW ─────────────────────────────────────────────────────────────────

@app.route("/api/overview")
def api_overview():
    day = request.args.get("day", date.today().isoformat())
    conn = db()
    if not conn:
        return jsonify({"error": "stats.db not found"}), 503

    totals = conn.execute("SELECT * FROM daily_totals WHERE day=?", (day,)).fetchone()
    totals = dict(totals) if totals else {"day": day, "total_kills": 0, "total_maps": 0,
                                           "unique_players": 0, "total_revives": 0, "total_dynaplants": 0}

    # Top killer of the day
    top = conn.execute("""
        SELECT ps.player_name, SUM(ps.kills) k
        FROM player_map_stats ps JOIN maps m ON ps.map_id=m.id
        WHERE m.day=? GROUP BY ps.player_name ORDER BY k DESC LIMIT 1
    """, (day,)).fetchone()
    totals["top_killer"] = dict(top) if top else None

    # Top weapon of the day
    tw = conn.execute("""
        SELECT wk.weapon, SUM(wk.kills) k
        FROM weapon_kills wk JOIN maps m ON wk.map_id=m.id
        WHERE m.day=? GROUP BY wk.weapon ORDER BY k DESC LIMIT 1
    """, (day,)).fetchone()
    totals["top_weapon"] = dict(tw) if tw else None

    conn.close()
    return jsonify(totals)


@app.route("/api/available_days")
def api_available_days():
    conn = db()
    if not conn:
        return jsonify([])
    rows = conn.execute("SELECT DISTINCT day FROM maps ORDER BY day DESC LIMIT 60").fetchall()
    conn.close()
    return jsonify([r["day"] for r in rows])


# ── MAPS ─────────────────────────────────────────────────────────────────────

@app.route("/api/maps")
def api_maps():
    day = request.args.get("day", date.today().isoformat())
    conn = db()
    if not conn:
        return jsonify([])
    maps = conn.execute("SELECT * FROM maps WHERE day=? ORDER BY id DESC", (day,)).fetchall()
    result = []
    for m in maps:
        players = conn.execute("""
            SELECT player_name, team, class, kills, deaths, team_kills,
                   kill_streak, revives, health_packs, ammo_packs, dynamite_plants, time_played_s
            FROM player_map_stats WHERE map_id=? ORDER BY kills DESC
        """, (m["id"],)).fetchall()
        weapons = conn.execute("""
            SELECT weapon, SUM(kills) k FROM weapon_kills
            WHERE map_id=? GROUP BY weapon ORDER BY k DESC
        """, (m["id"],)).fetchall()
        result.append({
            "id": m["id"], "map_name": m["map_name"],
            "started_at": m["started_at"], "ended_at": m["ended_at"],
            "duration_s": m["duration_s"],
            "players": [dict(p) for p in players],
            "weapons": [dict(w) for w in weapons],
            "total_kills": sum(p["kills"] for p in players),
        })
    conn.close()
    return jsonify(result)


# ── PLAYERS ──────────────────────────────────────────────────────────────────

@app.route("/api/players")
def api_players():
    """All-time player leaderboard."""
    conn = db()
    if not conn:
        return jsonify([])
    rows = conn.execute("""
        SELECT player_name,
               SUM(kills)           total_kills,
               SUM(deaths)          total_deaths,
               SUM(team_kills)      total_tk,
               MAX(kill_streak)     best_streak,
               SUM(revives)         total_revives,
               SUM(health_packs)    total_hp,
               SUM(ammo_packs)      total_ap,
               SUM(dynamite_plants) total_dynaplants,
               SUM(time_played_s)   total_time,
               COUNT(DISTINCT map_id) maps_played
        FROM player_map_stats
        GROUP BY player_name
        ORDER BY total_kills DESC
    """).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route("/api/player/<name>")
def api_player(name):
    """Full profile for one player."""
    conn = db()
    if not conn:
        return jsonify({"error": "db not found"}), 503

    # Overall stats
    stats = conn.execute("""
        SELECT SUM(kills) k, SUM(deaths) d, SUM(team_kills) tk,
               MAX(kill_streak) best_streak, SUM(revives) rev,
               SUM(health_packs) hp, SUM(ammo_packs) ap,
               SUM(dynamite_plants) dyna, SUM(time_played_s) time,
               COUNT(DISTINCT map_id) maps
        FROM player_map_stats WHERE player_name=?
    """, (name,)).fetchone()

    # Per-map history
    history = conn.execute("""
        SELECT m.day, m.map_name, ps.team, ps.class, ps.kills, ps.deaths,
               ps.kill_streak, ps.revives, ps.time_played_s
        FROM player_map_stats ps JOIN maps m ON ps.map_id=m.id
        WHERE ps.player_name=? ORDER BY m.id DESC LIMIT 30
    """, (name,)).fetchall()

    # Weapon breakdown (all time)
    weapons = conn.execute("""
        SELECT weapon, SUM(kills) k FROM weapon_kills
        WHERE player_name=? GROUP BY weapon ORDER BY k DESC
    """, (name,)).fetchall()

    # Favourite class
    fav_class = conn.execute("""
        SELECT class, COUNT(*) c FROM player_map_stats
        WHERE player_name=? AND class != '' GROUP BY class ORDER BY c DESC LIMIT 1
    """, (name,)).fetchone()

    # Favourite team
    fav_team = conn.execute("""
        SELECT team, COUNT(*) c FROM player_map_stats
        WHERE player_name=? AND team != '' GROUP BY team ORDER BY c DESC LIMIT 1
    """, (name,)).fetchone()

    # XP from JayMod user.db
    xp_data = {}
    users = parse_jaymod_user_db(CONFIG["jaymod_user_db"])
    
    # Try to find GUID for this player name
    guid_row = conn.execute("SELECT guid FROM guid_mapping WHERE player_name=?", (name,)).fetchone()
    if guid_row:
        guid = guid_row["guid"]
        user = users.get(guid)
        if user and 'xpSkills' in user:
            xp_data = decode_xp(user['xpSkills'])

    conn.close()
    return jsonify({
        "name": name,
        "stats": dict(stats) if stats else {},
        "history": [dict(h) for h in history],
        "weapons": [dict(w) for w in weapons],
        "fav_class": fav_class["class"] if fav_class else "—",
        "fav_team": fav_team["team"] if fav_team else "—",
        "xp": xp_data,
    })


# ── WEAPONS ──────────────────────────────────────────────────────────────────

@app.route("/api/weapons")
def api_weapons():
    """All-time weapon leaderboard."""
    day = request.args.get("day", None)
    conn = db()
    if not conn:
        return jsonify([])
    if day:
        rows = conn.execute("""
            SELECT wk.weapon, SUM(wk.kills) k, COUNT(DISTINCT wk.player_name) players
            FROM weapon_kills wk JOIN maps m ON wk.map_id=m.id
            WHERE m.day=? GROUP BY wk.weapon ORDER BY k DESC
        """, (day,)).fetchall()
    else:
        rows = conn.execute("""
            SELECT weapon, SUM(kills) k, COUNT(DISTINCT player_name) players
            FROM weapon_kills GROUP BY weapon ORDER BY k DESC
        """).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route("/api/weapon/<weapon>")
def api_weapon_detail(weapon):
    """Top players with a specific weapon."""
    conn = db()
    if not conn:
        return jsonify([])
    rows = conn.execute("""
        SELECT player_name, SUM(kills) k FROM weapon_kills
        WHERE weapon=? GROUP BY player_name ORDER BY k DESC LIMIT 20
    """, (weapon,)).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


# ── XP / JAYMOD ──────────────────────────────────────────────────────────────

@app.route("/api/xp")
def api_xp():
    users = parse_jaymod_user_db(CONFIG["jaymod_user_db"])
    if not users:
        return jsonify({"error": "user.db not found or empty"}), 503
    
    # Get GUID to name mappings from our stats DB
    conn = db()
    guid_map = {}
    if conn:
        mappings = conn.execute("SELECT guid, player_name FROM guid_mapping").fetchall()
        for m in mappings:
            guid_map[m["guid"]] = m["player_name"]
        conn.close()
    
    result = []
    for guid, user in users.items():
        if 'xpSkills' not in user:
            continue
        
        skills = decode_xp(user['xpSkills'])
        total_xp = sum(skills.values())
        
        # Get player name - prefer from mapping, fallback to user.db name field
        display_name = guid_map.get(guid, user.get('name', user.get('namex', guid[:16] + "...")))
        
        result.append({
            "guid": guid,
            "name": display_name,
            "skills": skills,
            "total_xp": total_xp,
        })
    
    result.sort(key=lambda x: x["total_xp"], reverse=True)
    return jsonify(result)


# ── PAGES ─────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/maps")
def page_maps():
    return render_template("index.html")

@app.route("/players")
def page_players():
    return render_template("index.html")

@app.route("/weapons")
def page_weapons():
    return render_template("index.html")

@app.route("/player/<name>")
def page_player(name):
    return render_template("index.html")


if __name__ == "__main__":
    app.run(host=CONFIG["host"], port=CONFIG["port"], debug=CONFIG["debug"])
