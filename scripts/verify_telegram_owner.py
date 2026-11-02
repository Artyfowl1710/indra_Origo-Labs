"""Read-only by default; optional branding/test message only to a verified saved owner."""
import argparse
import json
import re
from pathlib import Path
import httpx
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--owner-username", required=True)
    parser.add_argument("--brand-bot", action="store_true")
    parser.add_argument("--send-test", action="store_true")
    args = parser.parse_args()
    env = dotenv_values(ROOT / "data/indra-auto-home/.env")
    token = env.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise SystemExit("No Telegram bot token is saved.")
    with httpx.Client(timeout=20, trust_env=False) as client:
        def call(method, **payload):
            try:
                response = client.post("https://api.telegram.org/bot" + token + "/" + method, json=payload)
                result = response.json()
                if not response.is_success or not result.get("ok"):
                    raise ValueError("Telegram request failed")
                return result.get("result")
            except (httpx.HTTPError, ValueError) as error:
                raise RuntimeError("Telegram " + method + " failed; credential-bearing URLs are withheld.") from None
        bot = call("getMe")
        owner = None
        for candidate in (env.get("TELEGRAM_ALLOWED_USERS") or "").split(",")[:32]:
            if not re.fullmatch(r"[0-9]+", candidate.strip()):
                continue
            try:
                chat = call("getChat", chat_id=int(candidate))
            except RuntimeError:
                continue
            if chat.get("type") == "private" and str(chat.get("username", "")).lower() == args.owner_username.lstrip("@").lower():
                owner = int(candidate)
                break
        report = {"bot_reachable": True, "bot_username": bot.get("username"),
                  "expected_owner_verified": owner is not None, "display_name_updated": False,
                  "test_message_delivered": False}
        if (args.brand_bot or args.send_test) and owner is None:
            raise SystemExit("The saved allowed account could not be matched to the requested username; no changes or messages sent.")
        if args.brand_bot:
            call("setMyName", name="Indra · Origo Labs")
            report["display_name_updated"] = True
        if args.send_test:
            result = call("sendMessage", chat_id=owner, text="Indra connection test: your PC messaging gateway is online. Send /status here to check it, or /help to see commands. Send /stop to cancel a task.")
            report["test_message_delivered"] = bool(result.get("message_id"))
        (ROOT / "data/test-results/telegram-owner-acceptance.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report))


if __name__ == "__main__":
    main()
