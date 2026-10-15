name: Update stats

on:
  schedule:
    # 10:10 UTC = 6:10 AM Eastern (5:10 AM in winter). GitHub may start scheduled runs a little late.
    - cron: "10 10 * * *"
  workflow_dispatch: {}
  push:
    branches: [main]

permissions:
  contents: write
  pages: write
  id-token: write

concurrency:
  group: update-stats
  cancel-in-progress: false

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: Pull NHL.com + MoneyPuck stats
        id: pull
        continue-on-error: true
        run: python3 scripts/nhl_pull.py NYI > stats.new.json
      - name: Check the result
        id: check
        continue-on-error: true
        run: |
          python3 - <<'PY'
          import json, sys
          d = json.load(open("stats.new.json"))
          if not d.get("players"):
              sys.exit("No players in the pull; keeping the previous stats.json")
          print(d["source"], "|", d["players"], "Isles players |", d.get("league_players"), "league players |",
                d.get("teams"), "teams |", len(d.get("games", [])), "games |", d["updated"])
          PY
          mv stats.new.json stats.json
      - name: Save stats.json to the repository
        if: steps.check.outcome == 'success' && github.event_name != 'push'
        run: |
          git config user.name "stats-bot"
          git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
          git add stats.json
          if git diff --cached --quiet; then echo "No changes"; exit 0; fi
          git commit -m "Update stats $(date -u +%Y-%m-%d)"
          git push
      - name: Report a failed pull
        if: steps.pull.outcome != 'success' || steps.check.outcome != 'success'
        run: echo "::warning::The stats pull failed today, so the site keeps the previous stats. Open this run's 'Pull NHL.com + MoneyPuck stats' step to see why."
      - uses: actions/configure-pages@v5
      - uses: actions/upload-pages-artifact@v3
        with:
          path: "."

  deploy:
    needs: build
    runs-on: ubuntu-latest
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    steps:
      - id: deployment
        uses: actions/deploy-pages@v4
