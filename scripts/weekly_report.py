"""Weekly StepStone health summary. Independent from the review queue."""
import json
import os
from pathlib import Path

import requests


def build_report(health):
    return "\n".join([
        "📊 Arash Job Radar — weekly StepStone validation",
        "Mode: DRY RUN (no test advertisements sent)",
        "Candidates found: " + str(health["candidates"]),
        "Descriptions successfully extracted: " + str(health["details_extracted"]),
        "Advertisements scored: " + str(health["scored"]),
        "Potential matches: " + str(health["potential_matches_not_sent"]),
        "Accuracy: not yet certified; real-advertisement review is ongoing.",
        "Indeed: inactive pending a permitted, reliable connection.",
    ])


def main():
    if os.getenv("MARKET_DRY_RUN") != "1":
        raise SystemExit("Weekly market summary requires MARKET_DRY_RUN=1")
    health = json.loads(Path("market_health.json").read_text(encoding="utf-8"))
    if not health.get("healthy"):
        raise SystemExit("Weekly source validation did not pass")
    token, chat = os.getenv("BOT_TOKEN"), os.getenv("CHAT_ID")
    if not token or not chat:
        raise SystemExit("Weekly source summary requires Telegram credentials")
    response = requests.post(
        "https://api.telegram.org/bot" + token + "/sendMessage",
        data={"chat_id": chat, "text": build_report(health), "disable_web_page_preview": True},
        timeout=20,
    )
    response.raise_for_status()
    print("Weekly StepStone dry-run summary delivered")


if __name__ == "__main__":
    main()
