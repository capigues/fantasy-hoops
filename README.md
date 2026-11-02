# NBA Fantasy Trade Eligibility System

Automated trade-eligibility tracking system for ESPN Head-to-Head (H2H) NBA Fantasy Leagues, flagging teams as **trade-ineligible** when managers neglect their rosters.

## Core Rules & Criteria

A team is flagged as **trade-ineligible** if any criterion R1–R4 is in a flagged state:

| ID | Name | Violation Condition | State Transition Rules |
|---|---|---|---|
| **R1** | Wasted active slot | Active slot is empty or holds an `OUT` player while a healthy eligible bench player with an NBA game was available | Trailing **14 game days** window. Flags at **$\ge$ 4** wasted days; clears at **$\le$ 1** wasted days; preserves state at 2 or 3 wasted days (hysteresis). |
| **R2** | Unused IR spot | The IR slot is empty while an `OUT` player sits in an active or bench slot | **Grace: 2 game days** (flags on 3rd consecutive violating game day). **Cooldown: 2 game days** (clears after 2 consecutive clean game days). |
| **R3** | Dead roster spot | A player officially out for the season is on the roster in any slot (including IR) | **Grace: 2 game days** (flags on 3rd consecutive violating game day). **Cooldown: 2 game days**. |
| **R4** | Invalid roster | Roster is below league minimum or exceeding slot limits | **Grace: 2 game days** (flags on 3rd consecutive violating game day). **Cooldown: 2 game days**. |

### Key Clarifications
- All counters run in **game days** (days with $\ge 1$ NBA game). No-game days are skipped entirely.
- Only `"OUT"` counts as injured. `"QUESTIONABLE"` and `"DAY_TO_DAY"` players never trigger violations.
- Incomplete or failed captures are recorded as `unknown`: counters pause, and unknown days never clear flags.
- Evaluation is **deterministic and replayable** from stored raw snapshots.

---

## Architecture & Project Structure

- `config.py`: League settings, slot IDs, timing parameters, and constants.
- `db.py`: SQLite persistence layer with WAL mode (`raw_snapshots`, `daily_facts`, `team_criteria_state`, `state_change_log`, `season_ending_players`).
- `espn_client.py`: API client for ESPN Fantasy Basketball v3 and public NBA Scoreboard & Injury endpoints.
- `injury_source.py`: Hybrid manager combining automated ESPN injury note analysis with a canonical commissioner registry.
- `evaluator.py`: Pure, deterministic evaluation of criteria R1 to R4 for any date $D$.
- `state_machine.py`: Manages the 14-day sliding window, grace, cooldown, hysteresis, and audit logs.
- `scheduler.py`: Timezone-aware capture orchestrator (Pre-Tip offset and 2:00 AM ET evaluation).
- `notifier.py`: Formatter for ASCII status tables, Discord/Slack webhooks, and alert logs.
- `cli.py`: Commissioner management CLI.
- `tests/`: 26 comprehensive unit and acceptance tests covering all 17 specification scenarios.

---

## Getting Started

### Configuration
Set environment variables or pass options in `.env`:
```bash
export ESPN_LEAGUE_ID=123456
export ESPN_SEASON_YEAR=2026
export ESPN_S2="your_espn_s2_cookie"
export ESPN_SWID="{your-swid-guid}"
export FANTASY_DB_PATH="fantasy_eligibility.db"
export COMMISSIONER_WEBHOOK_URL="https://discord.com/api/webhooks/..."
```

### Running CLI Commands

#### View League Status
```bash
python3 cli.py status
```

#### View Audit Trail / State Transitions
```bash
python3 cli.py audit-log --limit 20
```

#### Trigger Pre-Tip Capture
```bash
python3 cli.py pre-tip --date 2026-11-01
```

#### Run 2 AM Evaluation for Date $D$
```bash
python3 cli.py evaluate --date 2026-11-01
```

#### Deterministic Replay
```bash
python3 cli.py replay --date 2026-11-01
```

#### Manage Season-Ending Out-For-Season Registry
```bash
# Add player
python3 cli.py out-for-season add 3032977 "Player Name" --notes "Torn ACL"

# List players
python3 cli.py out-for-season list

# Remove player
python3 cli.py out-for-season remove 3032977
```

---

## Testing

Run all 26 unit and acceptance tests:
```bash
python3 -m unittest discover tests
```
