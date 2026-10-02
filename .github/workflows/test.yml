name: Minato Badminton Monitor

on:
  workflow_dispatch:

  schedule:
    - cron: "*/5 * * * *"
      timezone: "Asia/Tokyo"

permissions:
  contents: write

concurrency:
  group: minato-badminton-monitor
  cancel-in-progress: false

jobs:
  monitor:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          python -m playwright install --with-deps chromium

      - name: Run monitor
        env:
          DISCORD_WEBHOOK_URL: ${{ secrets.DISCORD_WEBHOOK_URL }}
        run: |
          python monitor.py

      - name: Show generated files
        if: always()
        run: |
          echo "===== new-slots.txt ====="
          cat new-slots.txt || true

          echo ""
          echo "===== evening-results.txt ====="
          cat evening-results.txt || true

          echo ""
          echo "===== state.json ====="
          cat state.json || true

      - name: Commit state.json
        if: success()
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "41898282+github-actions[bot]@users.noreply.github.com"

          git add state.json

          if git diff --cached --quiet; then
            echo "state.jsonに変更はありません"
          else
            git commit -m "Update monitor state"
            git push
          fi

      - name: Upload results
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: monitor-results
          path: |
            result_*.txt
            evening-results.txt
            new-slots.txt
            state.json
            error_*.png
          if-no-files-found: warn
