import os
from dataclasses import dataclass
from zoneinfo import ZoneInfo

def load_dotenv(path: str = '.env'):
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    k, v = line.split('=', 1)
                    os.environ.setdefault(k.strip(), v.strip().strip("'\""))

load_dotenv()



"""Configuration module for NBA Fantasy Trade Eligibility System."""


# Eastern Timezone as specified
ET_TZ = ZoneInfo("America/New_York")

# Standard ESPN NBA Fantasy Slot IDs
SLOT_PG = 0
SLOT_SG = 1
SLOT_SF = 2
SLOT_PF = 3
SLOT_C = 4
SLOT_G = 5
SLOT_F = 6
SLOT_UTIL = 7
SLOT_GF = 8
SLOT_FC = 9
SLOT_BENCH_1 = 11
SLOT_BENCH = 11
SLOT_BENCH_2 = 12
SLOT_IR = 13
SLOT_BENCH_LEGACY = 14

# Support both custom and standard ESPN fantasy basketball slot IDs
BENCH_SLOTS = {SLOT_BENCH_1, SLOT_BENCH_2, SLOT_BENCH_LEGACY}
IR_SLOTS = {SLOT_IR}
RESERVE_SLOTS = BENCH_SLOTS | IR_SLOTS

# Any slot that is not bench or IR is an active starter slot
def is_active_slot(slot_id: int) -> bool:
    return slot_id not in RESERVE_SLOTS

# Injury statuses
STATUS_OUT = "OUT"
# Only "OUT" counts as injured for R1 and R2
INJURY_STATUSES_COUNTED_AS_INJURED = {STATUS_OUT}

# Timing rules as per specification
R1_WINDOW_GAME_DAYS = 14
R1_FLAG_THRESHOLD = 4
R1_CLEAR_THRESHOLD = 1
# Note: At 2 or 3 wasted days, state is preserved (hysteresis)

R2_GRACE_GAME_DAYS = 2    # Flagged from 3rd consecutive violating game day
R2_COOLDOWN_GAME_DAYS = 2 # Cleared after 2 consecutive clean game days

R3_GRACE_GAME_DAYS = 2
R3_COOLDOWN_GAME_DAYS = 2

R4_GRACE_GAME_DAYS = 2
R4_COOLDOWN_GAME_DAYS = 2

# Evaluation schedule defaults
DEFAULT_FINAL_CAPTURE_HOUR = 2  # 2:00 AM ET
DEFAULT_FINAL_CAPTURE_MINUTE = 0
DEFAULT_PRE_TIP_OFFSET_MINUTES = 20
DEFAULT_PRE_TIP_FALLBACK_TIME = "18:40" # 6:40 PM ET

@dataclass
class LeagueConfig:
    league_id: int = int(os.environ.get("ESPN_LEAGUE_ID", "0"))
    season_year: int = int(os.environ.get("ESPN_SEASON_YEAR", "2026"))
    espn_s2: str = os.environ.get("ESPN_S2", "")
    swid: str = os.environ.get("ESPN_SWID", "")
    db_path: str = os.environ.get("FANTASY_DB_PATH", "fantasy_eligibility.db")
    min_roster_size: int = int(os.environ.get("MIN_ROSTER_SIZE", "13"))
    max_ir_slots: int = 1
    pre_tip_offset_minutes: int = DEFAULT_PRE_TIP_OFFSET_MINUTES
    webhook_url: str = os.environ.get("COMMISSIONER_WEBHOOK_URL", "")

DEFAULT_CONFIG = LeagueConfig()
