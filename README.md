# Islanders Stat Studio

Animated 1080p graphics for New York Islanders videos: stat cards, player and team comparisons, notes slides and framed screenshots.

Open the site in Chrome or Edge on a computer (MP4 export needs one of those two browsers).

## Stats
`stats.json` is refreshed every morning by the **Update stats** GitHub Action (`.github/workflows/update-stats.yml`), which runs `scripts/nhl_pull.py`:

- NHL.com public stats API: Islanders skaters and goalies, every NHL player (for comparisons), team stats.
- MoneyPuck.com season data: xG, xGF%, Corsi, GSAx, high-danger stats. MoneyPuck's data is free for non-commercial use and must be credited; graphics that show a MoneyPuck stat add a "Data: MoneyPuck.com" credit automatically.

To refresh by hand: **Actions** tab → **Update stats** → **Run workflow**.

## Your logos, headshots and settings
They're saved in your own browser on your own computer. Use **Save setup** to back them up or move them to another computer.
