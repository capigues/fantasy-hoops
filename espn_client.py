"""Client for interacting with ESPN Fantasy API and public NBA endpoints."""

import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)
ET_TZ = ZoneInfo("America/New_York")

class EspnClient:
    def __init__(self, league_id: int = 0, season_year: int = 2026,
                 espn_s2: str = "", swid: str = "", timeout: int = 15):
        self.league_id = league_id
        self.season_year = season_year
        self.espn_s2 = espn_s2
        self.swid = swid
        self.timeout = timeout

    def _build_request(self, url: str, headers: Optional[Dict[str, str]] = None) -> urllib.request.Request:
        req_headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko)",
            "Accept": "application/json"
        }
        if self.espn_s2 and self.swid:
            req_headers["Cookie"] = f"espn_s2={self.espn_s2}; SWID={self.swid}"
        if headers:
            req_headers.update(headers)
        return urllib.request.Request(url, headers=req_headers)

    def _get_json(self, url: str) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
        try:
            req = self._build_request(url)
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                if response.status == 200:
                    data = json.loads(response.read().decode("utf-8"))
                    return True, data, None
                return False, None, f"HTTP Status {response.status}"
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                return False, None, f"Authentication error (HTTP {e.code}): Check espn_s2 and SWID cookies"
            return False, None, f"HTTP Error {e.code}: {e.reason}"
        except urllib.error.URLError as e:
            return False, None, f"Network error: {e.reason}"
        except Exception as e:
            return False, None, f"Unexpected error fetching {url}: {str(e)}"

    def fetch_rosters(self, scoring_period_id: int) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
        url = (
            f"https://lm-api-reads.fantasy.espn.com/apis/v3/games/fba/seasons/{self.season_year}"
            f"/segments/0/leagues/{self.league_id}?view=mRoster&view=mTeam&scoringPeriodId={scoring_period_id}"
        )
        return self._get_json(url)

    def fetch_league_settings(self) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
        url = (
            f"https://lm-api-reads.fantasy.espn.com/apis/v3/games/fba/seasons/{self.season_year}"
            f"/segments/0/leagues/{self.league_id}?view=mSettings"
        )
        return self._get_json(url)

    def fetch_nba_scoreboard(self, date_str: str) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
        """Fetch scoreboard for date formatted as YYYY-MM-DD or YYYYMMDD."""
        formatted_date = date_str.replace("-", "")
        url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates={formatted_date}"
        return self._get_json(url)

    def fetch_nba_injuries(self) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
        url = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/injuries"
        return self._get_json(url)

    def parse_scoreboard_info(self, scoreboard_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract game day status, first tip-off time, and teams playing on this date."""
        events = scoreboard_data.get("events", [])
        is_game_day = len(events) > 0
        teams_playing: Set[str] = set()
        earliest_tip_utc: Optional[datetime] = None

        for event in events:
            date_str = event.get("date")
            if date_str:
                try:
                    tip_time = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                    if earliest_tip_utc is None or tip_time < earliest_tip_utc:
                        earliest_tip_utc = tip_time
                except Exception as e:
                    logger.warning("Could not parse tip date %s: %s", date_str, e)

            for comp in event.get("competitions", []):
                for competitor in comp.get("competitors", []):
                    team = competitor.get("team", {})
                    abbrev = team.get("abbreviation")
                    if abbrev:
                        teams_playing.add(abbrev.upper())
                    name = team.get("displayName")
                    if name:
                        teams_playing.add(name.upper())
                    tid = team.get("id") or competitor.get("id")
                    if tid is not None:
                        teams_playing.add(str(tid))
                        try:
                            teams_playing.add(int(tid))
                        except (ValueError, TypeError):
                            pass

        earliest_tip_et = earliest_tip_utc.astimezone(ET_TZ) if earliest_tip_utc else None

        return {
            "is_game_day": is_game_day,
            "game_count": len(events),
            "earliest_tip_utc": earliest_tip_utc.isoformat() if earliest_tip_utc else None,
            "earliest_tip_et": earliest_tip_et.isoformat() if earliest_tip_et else None,
            "teams_playing": list(teams_playing)
        }
