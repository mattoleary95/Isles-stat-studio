#!/usr/bin/env python3
"""Pull New York Islanders stats from the NHL's public stats API and print one JSON
object for Islanders Stat Studio: {"updated", "season", "F", "D", "G"} where F/D/G are
CSV tabs (header row, one row per player, then a League AVG row).
Usage: python3 nhl_pull.py [TEAM] > stats.json   (TEAM defaults to NYI)"""
import csv, io, json, sys, urllib.request, urllib.parse
from datetime import datetime, timezone

TEAM = (sys.argv[1] if len(sys.argv) > 1 else "NYI").upper()
UA = {"User-Agent": "Mozilla/5.0 (stat-studio)"}

def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
        return json.load(r)

def rest(kind, report, season):
    exp = urllib.parse.quote(f"seasonId={season} and gameTypeId=2")
    try:
        return get(f"https://api.nhle.com/stats/rest/en/{kind}/{report}?limit=-1&cayenneExp={exp}").get("data", [])
    except Exception as e:
        print(f"warning: {kind}/{report} unavailable: {e}", file=sys.stderr)
        return []

def nm(p):
    return f'{(p.get("firstName") or {}).get("default","")} {(p.get("lastName") or {}).get("default","")}'.strip()

def num(v):
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) else None

def r1(v): return None if v is None else round(v, 1)
def r2(v): return None if v is None else round(v, 2)
def pct(v): return None if v is None else round(v * 100, 1)          # 0.1428 -> 14.3
def svp(v): return None if v is None else f"{v:.3f}".lstrip("0")      # 0.9123 -> .912
def toi(sec):
    if sec is None: return None
    sec = int(round(sec)); return f"{sec // 60}:{sec % 60:02d}"
def fmt(v):
    if v is None: return ""
    if isinstance(v, float) and v.is_integer(): return str(int(v))
    return str(v)

SK = ["Name", "Pos", "GP", "G", "A", "PTS", "+/-", "PIM", "PPG", "PPP", "SHG", "GWG", "SOG", "SH%", "TOI/GP", "FO%", "Hits", "Blocks", "Takeaways", "Giveaways"]
GO = ["Name", "GP", "GS", "W", "L", "OTL", "SV PCT", "GAA", "SO", "Saves", "SA", "GA"]

def skater_row(name, pos, s, rt):
    return {"Name": name, "Pos": pos,
            "GP": num(s.get("gamesPlayed")), "G": num(s.get("goals")), "A": num(s.get("assists")), "PTS": num(s.get("points")),
            "+/-": num(s.get("plusMinus")), "PIM": num(s.get("penaltyMinutes")),
            "PPG": num(s.get("powerPlayGoals", s.get("ppGoals"))), "PPP": num(rt.get("ppPoints")),
            "SHG": num(s.get("shorthandedGoals", s.get("shGoals"))), "GWG": num(s.get("gameWinningGoals")),
            "SOG": num(s.get("shots")), "SH%": pct(num(s.get("shootingPctg", s.get("shootingPct")))),
            "TOI/GP": toi(num(s.get("avgTimeOnIcePerGame", s.get("timeOnIcePerGame")))),
            "FO%": pct(num(s.get("faceoffWinPctg", s.get("faceoffWinPct")))) if (num(s.get("faceoffWinPctg", s.get("faceoffWinPct"))) or 0) > 0 else None,
            "Hits": num(rt.get("hits")), "Blocks": num(rt.get("blockedShots")),
            "Takeaways": num(rt.get("takeaways")), "Giveaways": num(rt.get("giveaways"))}

def goalie_row(name, g):
    return {"Name": name, "GP": num(g.get("gamesPlayed")), "GS": num(g.get("gamesStarted")), "W": num(g.get("wins")),
            "L": num(g.get("losses")), "OTL": num(g.get("overtimeLosses", g.get("otLosses"))),
            "SV PCT": svp(num(g.get("savePercentage", g.get("savePct")))), "GAA": r2(num(g.get("goalsAgainstAverage"))),
            "SO": num(g.get("shutouts")), "Saves": num(g.get("saves")), "SA": num(g.get("shotsAgainst")), "GA": num(g.get("goalsAgainst"))}

def regulars(rows):
    gp = [r.get("gamesPlayed") or 0 for r in rows]
    if not gp or max(gp) == 0: return []
    cut = max(1, 0.5 * max(gp))
    return [r for r in rows if (r.get("gamesPlayed") or 0) >= cut]

def avg_row(rows, cols, rounding):
    out = {"Name": "League AVG"}
    for c in cols:
        if c in ("Name", "Pos"): continue
        vals = []
        for r in rows:
            v = r.get(c)
            if isinstance(v, str):
                try:
                    if ":" in v: a, b = v.split(":"); v = int(a) * 60 + int(b)
                    else: v = float(v)
                except ValueError: v = None
            if isinstance(v, (int, float)): vals.append(v)
        if not vals: out[c] = None; continue
        m = sum(vals) / len(vals)
        if c == "TOI/GP": out[c] = toi(m)
        elif "PCT" in c: out[c] = f"{m:.3f}".lstrip("0")
        else: out[c] = rounding.get(c, r1)(m)
    return out

def to_csv(cols, rows):
    buf = io.StringIO(); w = csv.writer(buf, lineterminator="\n"); w.writerow(cols)
    for r in rows: w.writerow([fmt(r.get(c)) for c in cols])
    return buf.getvalue().rstrip("\n")

club = get(f"https://api-web.nhle.com/v1/club-stats/{TEAM}/now")
season = str(club.get("season") or "")
sk_sum = rest("skater", "summary", season) if season else []
sk_rt = {r.get("playerId"): r for r in rest("skater", "realtime", season)} if season else {}
for r in sk_sum:  # summary has ppPoints / faceoffs-related fields; fold into the realtime lookup
    sk_rt.setdefault(r.get("playerId"), {}).update({k: r[k] for k in ("ppPoints",) if k in r})
go_sum = rest("goalie", "summary", season) if season else []

F, D = [], []
for s in club.get("skaters", []):
    pos = s.get("positionCode", "")
    row = skater_row(nm(s), {"L": "LW", "R": "RW"}.get(pos, pos), s, sk_rt.get(s.get("playerId"), {}))
    (D if pos == "D" else F).append(row)
G = [goalie_row(nm(g), g) for g in club.get("goalies", [])]
key = lambda r: (-(r.get("PTS") or 0), -(r.get("GP") or 0), r["Name"])
F.sort(key=key); D.sort(key=key); G.sort(key=lambda r: (-(r.get("GP") or 0), r["Name"]))

# league averages from every NHL regular at the position (half the max games played or more)
lf, ld = [], []
for s in sk_sum:
    rt = sk_rt.get(s.get("playerId"), {})
    s2 = dict(s); s2["avgTimeOnIcePerGame"] = s.get("timeOnIcePerGame"); s2["faceoffWinPctg"] = s.get("faceoffWinPct")
    (ld if s.get("positionCode") == "D" else lf).append(dict(skater_row("", "", s2, rt), gamesPlayed=s.get("gamesPlayed")))
lg = [dict(goalie_row("", g), gamesPlayed=g.get("gamesPlayed")) for g in go_sum]
counts = {c: r1 for c in SK}; counts.update({"GAA": r2})
if lf: F.append(avg_row(regulars(lf), SK, counts))
if ld: D.append(avg_row(regulars(ld), SK, counts))
if lg: G.append(avg_row(regulars(lg), GO, counts))

# every NHL player, for the comparison slides (team = most recent club when a player was traded)
def team_of(r): return (r.get("teamAbbrevs") or "").split(",")[-1].strip()
LSK = ["Name", "Team"] + SK[1:]
LGO = ["Name", "Team"] + GO[1:]
LF, LD, LG = [], [], []
for s in sk_sum:
    rt = sk_rt.get(s.get("playerId"), {})
    s2 = dict(s); s2["avgTimeOnIcePerGame"] = s.get("timeOnIcePerGame"); s2["faceoffWinPctg"] = s.get("faceoffWinPct")
    pos = s.get("positionCode", "")
    row = skater_row(s.get("skaterFullName", ""), {"L": "LW", "R": "RW"}.get(pos, pos), s2, rt); row["Team"] = team_of(s)
    (LD if pos == "D" else LF).append(row)
for g in go_sum:
    row = goalie_row(g.get("goalieFullName", ""), g); row["Team"] = team_of(g); LG.append(row)
lkey = lambda r: (r["Team"], -(r.get("PTS") or r.get("GP") or 0), r["Name"])
LF.sort(key=lkey); LD.sort(key=lkey); LG.sort(key=lkey)

# ---------------- team stats (NHL.com) + MoneyPuck advanced stats ----------------
NICK = {"ANA":"Ducks","BOS":"Bruins","BUF":"Sabres","CGY":"Flames","CAR":"Hurricanes","CHI":"Blackhawks","COL":"Avalanche","CBJ":"Blue Jackets","DAL":"Stars","DET":"Red Wings","EDM":"Oilers","FLA":"Panthers","LAK":"Kings","MIN":"Wild","MTL":"Canadiens","NSH":"Predators","NJD":"Devils","NYI":"Islanders","NYR":"Rangers","OTT":"Senators","PHI":"Flyers","PIT":"Penguins","SJS":"Sharks","SEA":"Kraken","STL":"Blues","TBL":"Lightning","TOR":"Maple Leafs","UTA":"Mammoth","VAN":"Canucks","VGK":"Golden Knights","WSH":"Capitals","WPG":"Jets"}
MP_TEAM = {"T.B": "TBL", "N.J": "NJD", "L.A": "LAK", "S.J": "SJS", "UTA": "UTA", "ARI": "UTA"}
def abbr_from_name(full):
    for ab, nick in NICK.items():
        if (full or "").endswith(nick): return ab
    return ""

def mp_csv(kind):
    import os
    if os.environ.get("MP_DIR"):  # local copies, for testing
        with open(os.path.join(os.environ["MP_DIR"], kind + ".csv"), encoding="utf-8-sig") as fh: return list(csv.DictReader(fh))
    yr = season[:4]
    url = f"https://moneypuck.com/moneypuck/playerData/seasonSummary/{yr}/regular/{kind}.csv"
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=60) as r:
            return list(csv.DictReader(io.StringIO(r.read().decode("utf-8-sig"))))
    except Exception as e:
        print(f"warning: MoneyPuck {kind} unavailable: {e}", file=sys.stderr)
        return []

def f(row, k):
    try: return float(row.get(k, ""))
    except (TypeError, ValueError): return None
def sub(a, b): return None if a is None or b is None else a - b
def div(a, b): return None if a is None or not b else a / b

mp_sk = mp_csv("skaters") if season else []
mp_go = mp_csv("goalies") if season else []
mp_tm = mp_csv("teams") if season else []
MP = bool(mp_sk or mp_go or mp_tm)

def by_sit(rows, key):
    out = {}
    for r in rows: out.setdefault(r.get(key), {})[r.get("situation")] = r
    return out

MP_SK_COLS = ["xG", "GAx", "xG/60", "xGF%", "5v5 xGF%", "CF%", "HD Shots", "GS/GP"]
MP_GO_COLS = ["GSAx", "GSAx/60", "xGA", "HDSV PCT", "HD Saves"]
sk_mp = {}
for pid, sits in by_sit(mp_sk, "playerId").items():
    a, e = sits.get("all", {}), sits.get("5on5", {})
    xg, gl, ice = f(a, "I_F_xGoals"), f(a, "I_F_goals"), f(a, "icetime")
    sk_mp[pid] = {"xG": r1(xg), "GAx": r1(sub(gl, xg)), "xG/60": r2(div(xg, (ice or 0) / 3600)),
                  "xGF%": pct(f(a, "onIce_xGoalsPercentage")), "5v5 xGF%": pct(f(e, "onIce_xGoalsPercentage")),
                  "CF%": pct(f(a, "onIce_corsiPercentage")), "HD Shots": f(a, "I_F_highDangerShots"),
                  "GS/GP": r2(div(f(a, "gameScore"), f(a, "games_played")))}
go_mp = {}
for pid, sits in by_sit(mp_go, "playerId").items():
    a = sits.get("all", {})
    xga, ga, ice = f(a, "xGoals"), f(a, "goals"), f(a, "icetime")
    hds, hdg = f(a, "highDangerShots"), f(a, "highDangerGoals")
    go_mp[pid] = {"GSAx": r1(sub(xga, ga)), "GSAx/60": r2(div(sub(xga, ga), (ice or 0) / 3600)), "xGA": r1(xga),
                  "HDSV PCT": svp(1 - hdg / hds) if hds and hdg is not None else None, "HD Saves": sub(hds, hdg)}

def add_mp(rows, src, cols, idkey="_pid"):
    for r in rows:
        m = src.get(str(r.get(idkey)), {})
        for c in cols: r[c] = m.get(c)

# attach playerIds so MoneyPuck rows can join (MoneyPuck uses NHL player ids)
def tag_ids(rows, src_list, name_fn):
    ids = {name_fn(p): p.get("playerId") for p in src_list}
    for r in rows: r["_pid"] = ids.get(r["Name"])
tag_ids(F + D, club.get("skaters", []), nm); tag_ids(G, club.get("goalies", []), nm)
tag_ids(LF + LD, sk_sum, lambda p: p.get("skaterFullName", "")); tag_ids(LG, go_sum, lambda p: p.get("goalieFullName", ""))
if MP:
    for rows in (F, D, LF, LD): add_mp(rows, sk_mp, MP_SK_COLS)
    for rows in (G, LG): add_mp(rows, go_mp, MP_GO_COLS)
    SK += MP_SK_COLS; GO += MP_GO_COLS; LSK += MP_SK_COLS; LGO += MP_GO_COLS
    # league-average rows: recompute so the new columns are filled in
    def regular_rows(lst): return regulars([dict(r, gamesPlayed=r.get("GP")) for r in lst])
    for tab, lst, cols in ((F, LF, SK), (D, LD, SK), (G, LG, GO)):
        if tab and tab[-1]["Name"] == "League AVG": tab[-1] = avg_row(regular_rows(lst), [c for c in cols if c not in ("Team",)], counts)

# teams: NHL.com standings-style numbers + MoneyPuck team analytics
TM = ["Name", "Team", "GP", "W", "L", "OTL", "PTS", "PT PCT", "GF/GP", "GA/GP", "PP%", "PK%", "SF/GP", "SA/GP", "FO%"]
TM_MP = ["xGF%", "5v5 xGF%", "CF%", "5v5 CF%", "xGF", "xGA", "HDCF", "HDCA"]
try:
    nhl_tm = get("https://api.nhle.com/stats/rest/en/team/summary?cayenneExp=" + urllib.parse.quote(f"seasonId={season} and gameTypeId=2")).get("data", []) if season else []
except Exception as e:
    print(f"warning: team summary unavailable: {e}", file=sys.stderr); nhl_tm = []
tm_mp = {}
for ab, sits in by_sit(mp_tm, "team").items():
    a, e = sits.get("all", {}), sits.get("5on5", {})
    tm_mp[MP_TEAM.get(ab, ab)] = {"xGF%": pct(f(a, "xGoalsPercentage")), "5v5 xGF%": pct(f(e, "xGoalsPercentage")),
        "CF%": pct(f(a, "corsiPercentage")), "5v5 CF%": pct(f(e, "corsiPercentage")), "xGF": r1(f(a, "xGoalsFor")), "xGA": r1(f(a, "xGoalsAgainst")),
        "HDCF": f(a, "highDangerShotsFor"), "HDCA": f(a, "highDangerShotsAgainst")}
T = []
for t in nhl_tm:
    ab = abbr_from_name(t.get("teamFullName"))
    row = {"Name": t.get("teamFullName"), "Team": ab, "GP": num(t.get("gamesPlayed")), "W": num(t.get("wins")), "L": num(t.get("losses")),
           "OTL": num(t.get("otLosses")), "PTS": num(t.get("points")), "PT PCT": svp(num(t.get("pointPct"))),
           "GF/GP": r2(num(t.get("goalsForPerGame"))), "GA/GP": r2(num(t.get("goalsAgainstPerGame"))),
           "PP%": pct(num(t.get("powerPlayPct"))), "PK%": pct(num(t.get("penaltyKillPct"))),
           "SF/GP": r1(num(t.get("shotsForPerGame"))), "SA/GP": r1(num(t.get("shotsAgainstPerGame"))), "FO%": pct(num(t.get("faceoffWinPct")))}
    row.update(tm_mp.get(ab, {})); T.append(row)
T.sort(key=lambda r: (r["Team"] != TEAM, -(r.get("PTS") or 0), r["Name"] or ""))
TMC = TM + (TM_MP if MP else [])
if T:
    avg = avg_row(T, [c for c in TMC if c != "Team"], counts)
    T.append(avg)

out = {"updated": datetime.now(timezone.utc).isoformat(timespec="seconds"), "season": season, "team": TEAM,
       "source": "NHL.com stats API" + (" + MoneyPuck.com" if MP else ""), "F": to_csv(SK, F), "D": to_csv(SK, D), "G": to_csv(GO, G),
       "players": sum(1 for r in F + D + G if r["Name"] != "League AVG"),
       "LF": to_csv(LSK, LF), "LD": to_csv(LSK, LD), "LG": to_csv(LGO, LG), "league_players": len(LF) + len(LD) + len(LG),
       "T": to_csv(TMC, T), "teams": sum(1 for r in T if r["Name"] != "League AVG"), "moneypuck": MP,
       "mp_cols": (MP_SK_COLS + MP_GO_COLS + TM_MP) if MP else []}
print(json.dumps(out))
