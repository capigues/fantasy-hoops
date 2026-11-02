"""Notification and reporting module for Commissioner alerts."""

import json
import logging
import urllib.request
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

class Notifier:
    def __init__(self, webhook_url: str = ""):
        self.webhook_url = webhook_url

    def format_eligibility_table(self, report: List[Dict[str, Any]]) -> str:
        """Render a formatted text table of all teams."""
        header = f"{'Team Name':<28} | {'Eligibility':<18} | {'Active Flags':<14} | {'Flagged Since':<14}"
        separator = "-" * len(header)
        rows = [separator, header, separator]

        for team in report:
            status = "TRADE-INELIGIBLE" if team["is_flagged"] else "ELIGIBLE"
            flags = ", ".join(team["active_flags"]) if team["active_flags"] else "None"
            since = team["earliest_flag_date"] or "N/A"
            rows.append(f"{team['team_name']:<28} | {status:<18} | {flags:<14} | {since:<14}")

        rows.append(separator)
        return "\n".join(rows)

    def send_state_change_notifications(self, changes: List[Dict[str, Any]]):
        """Notify commissioner of any state transitions."""
        if not changes:
            return

        for ch in changes:
            team_name = ch["team_name"]
            crit = ch["criterion"]
            old_s = ch["old_state"]
            new_s = ch["new_state"]
            reason = ch["reason"]

            if new_s == "FLAGGED":
                msg = f"🚨 TRADE ELIGIBILITY ALERT: '{team_name}' is now TRADE-INELIGIBLE!\nReason: {crit} - {reason}"
            else:
                msg = f"✅ TRADE ELIGIBILITY RESTORED: '{team_name}' is now ELIGIBLE.\nReason: {crit} - {reason}"

            print("\n" + "=" * 60)
            print(msg)
            print("=" * 60 + "\n")

            if self.webhook_url:
                self._dispatch_webhook(msg)

    def _dispatch_webhook(self, message: str):
        try:
            payload = json.dumps({"text": message, "content": message}).encode("utf-8")
            req = urllib.request.Request(
                self.webhook_url,
                data=payload,
                headers={"Content-Type": "application/json"}
            )
            urllib.request.urlopen(req, timeout=5)
        except Exception as e:
            logger.error("Failed to post webhook notification: %s", e)
