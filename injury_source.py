"""Injury management and Out-For-Season registry."""

import logging
import re
from typing import Any, Dict, List, Optional, Set
from db import Database

logger = logging.getLogger(__name__)

SEASON_ENDING_PATTERNS = [
    r"\bout for(?: the)? season\b",
    r"\bseason-ending\b",
    r"\bmiss(?:ing)? the rest of the season\b",
    r"\bout for year\b",
    r"\bwill miss the remainder of the season\b"
]

class InjurySource:
    def __init__(self, db: Database):
        self.db = db

    def is_player_out_for_season(self, player_id: int, player_name: str,
                                 espn_injury_notes: Optional[str] = None) -> bool:
        """
        Check if a player has an official season-ending designation.
        Uses:
        1. Commissioner-maintained registry in the database.
        2. Text analysis of official ESPN injury notes/details if available.
        """
        # 1. Check commissioner database registry first (authoritative fallback)
        registry = self.db.get_season_ending_players()
        if player_id in registry:
            return True

        # Check by lowercase name in registry
        lower_name = player_name.strip().lower()
        for p in registry.values():
            if p["player_name"].strip().lower() == lower_name:
                return True

        # 2. Check official injury notes if provided
        if espn_injury_notes:
            lower_notes = espn_injury_notes.lower()
            for pattern in SEASON_ENDING_PATTERNS:
                if re.search(pattern, lower_notes):
                    return True

        return False

    def scan_espn_injuries_feed(self, injuries_payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Scan ESPN's public injury feed and identify players with season-ending notes.
        Returns list of candidates that can be registered or alerted.
        """
        candidates = []
        injuries = injuries_payload.get("injuries", [])
        for item in injuries:
            athlete = item.get("athlete", {})
            player_id = athlete.get("id")
            player_name = athlete.get("displayName") or athlete.get("fullName")

            short_comment = item.get("shortComment", "")
            details_obj = item.get("details", {})
            detail_text = details_obj.get("detail", "")
            full_text = f"{short_comment} {detail_text}"

            for pattern in SEASON_ENDING_PATTERNS:
                if re.search(pattern, full_text, re.IGNORECASE):
                    candidates.append({
                        "player_id": int(player_id) if player_id else None,
                        "player_name": player_name,
                        "notes": full_text.strip(),
                        "source": "espn_feed"
                    })
                    break
        return candidates
