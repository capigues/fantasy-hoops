# NBA Fantasy Trade Eligibility System: Technical Architecture & Design

This document details the technical design, system architecture, data models, and API integration for the automated trade eligibility system. For the player-facing league rules, see [README.md](README.md).

---

## 1. System Overview

The trade eligibility system monitors an ESPN Head-to-Head NBA Fantasy League, tracking manager activity through roster state transitions. A team is flagged as **Trade-Ineligible** if any of the 4 defined criteria (R1–R4) enter a violated state.

```
       ┌────────────────────────────────────────────────────────┐
       │                Data Discovery Layer                    │
       │   - ESPN Fantasy API (Scoreboard, Rosters, Settings)   │
       │   - Official NBA Box Scores & Pre-Tip Injury Lists    │
       └──────────────────────────┬─────────────────────────────┘
                                  │ Uniform Data Contract
                                  ▼
       ┌────────────────────────────────────────────────────────┐
       │               Deterministic Evaluator                  │
       │   - R1: Wasted Active Slots (10 Starters)              │
       │   - R2: Unused IR Slot Detection                       │
       │   - R3: Out-for-Season Roster Checks                   │
       │   - R4: Roster Minimums & IR Slot Compliance           │
       └──────────────────────────┬─────────────────────────────┘
                                  │ Daily Facts
                                  ▼
       ┌────────────────────────────────────────────────────────┐
       │               State Machine & Storage                  │
       │   - 14-Game-Day Trailing Rolling Window (R1)           │
       │   - Grace Period (2 Days) & Cooldown (2 Days) (R2–R4)  │
       │   - SQLite Persistence / In-Memory Dry Run             │
       └──────────────────────────┬─────────────────────────────┘
                                  │ State Transitions
                                  ▼
       ┌────────────────────────────────────────────────────────┐
       │             Enforcement & Notifications                │
       │   - CLI Status & Audit Log Reports                     │
       │   - Webhook & League Commissioner Alerts               │
       └────────────────────────────────────────────────────────┘
```

---

## 2. Roster Specifications & Slot Mapping

The league operates with a 14-player roster:

| Slot ID | Name | Count | Position Eligibility |
| :---: | :---: | :---: | :--- |
| `0` | Point Guard (PG) | 1 | Guard, PG |
| `1` | Shooting Guard (SG) | 1 | Guard, SG |
| `2` | Small Forward (SF) | 1 | Forward, SF |
| `3` | Power Forward (PF) | 1 | Forward, PF |
| `4` | Center (C) | 1 | Center |
| `5` | Guard (G) | 1 | PG, SG, G |
| `6` | Forward (F) | 1 | SF, PF, F |
| `11` | Utility (UTIL) | 3 | Any active NBA player |
| `12` | Bench (BE) | 3 | Any player |
| `13` | Injured Reserve (IR) | 1 | Official `OUT` or `IR` status |

- **Total Active Starting Slots**: 10 (Slots 0, 1, 2, 3, 4, 5, 6, 11, 11, 11).
- **Bench Slots**: 3 (Slot 12).
- **IR Slots**: 1 (Slot 13).
- **Minimum Roster Size**: 13 players.

---

## 3. Evaluation Criteria Engine (`evaluator.py`)

### Rule 1 (R1): Wasted Active Slot
Evaluates whether a starting spot went unutilized while a healthy bench player with a scheduled NBA game was available.

1. **Step 1: Open / Replaceable Starting Slot Detection**:
   - Starter count $< 10$ (unfilled / empty starting slot).
   - Starter designated `OUT` (with 0 minutes/points recorded).
   - Starter whose NBA team had **no game scheduled** on date $D$ (off-day, 0 points recorded).
2. **Step 2: Active Bench Identification**:
   - Players in Slot 12 who had a scheduled NBA game on date $D$.
   - Must have physically played minutes or scored fantasy points, and must not hold an official `OUT` status.
3. **Step 3: Positional Compatibility Matching**:
   - Verifies if the active bench player has the required slot ID in their `eligibleSlots` array (Slot 11 UTIL matches all positions).

### Rule 2 (R2): Unused IR Spot
- Evaluates if the IR slot (Slot 13) is empty (`len(ir_entries) == 0`) while one or more players with `OUT` status occupy active (Slots 0–11) or bench (Slot 12) slots.

### Rule 3 (R3): Dead Roster Spot (Season-Ending Injury)
- Cross-references rostered player IDs against the commissioner-managed registry of season-ending injuries (`out_for_season` table).
- Applies if the player occupies any slot, including active, bench, or IR.

### Rule 4 (R4): Invalid Roster Structure
- Triggers if total roster size $< 13$ players, or if IR slot count $> 1$.

---

## 4. State Machine Architecture (`state_machine.py`)

All evaluations operate in **NBA game days** (days where $\ge 1$ NBA game is scheduled). Non-game days (e.g., Thanksgiving, Election Day, All-Star break) pause all counters.

### R1 State Engine (14-Game-Day Trailing Window)
- **Window Size**: Last 14 consecutive NBA game days.
- **Flag Condition**: $\ge 4$ violated game days within the window → `FLAGGED` (`TRADE-INELIGIBLE`).
- **Clear Condition**: $\le 1$ violated game days within the window → `CLEAN` (`ELIGIBLE`).
- **Hysteresis Buffer**: At 2 or 3 violations, the existing state is preserved to prevent daily flip-flopping.

### R2, R3, R4 State Engine (Grace & Cooldown)
- **Grace Period**: 2 consecutive game days. Flag triggers on the 3rd consecutive violating game day.
- **Cooldown Period**: 2 consecutive game days. Flag clears only after 2 consecutive clean game days.

---

## 5. ESPN API Integration (`espn_client.py`)

The system interfaces with ESPN Fantasy v3 endpoints using league authentication cookies:

- `league_id`: ESPN league identifier.
- `season_year`: Target championship season year (e.g., `2027` for 2026–27 season).
- `espn_s2`: ESPN session token cookie.
- `swid`: Software Identification GUID cookie.

### Endpoints
- **Roster & Schedule View**:
  `GET https://lm-api-reads.fantasy.espn.com/apis/v3/games/fba/seasons/{season}/segments/0/leagues/{league_id}?view=mRoster&view=mTeam&view=mMatchupScore&scoringPeriodId={sp}`
- **NBA Daily Scoreboard**:
  `GET https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates={YYYYMMDD}`
- **NBA Game Summary & Box Scores**:
  `GET https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event={event_id}`

---

## 6. Historical Backtesting Framework (`backtester.py`)

The backtester provides deterministic historical replay across any date range:

- **Uniform Data Contract**: Normalizes historical locked lineups (`rosterForCurrentScoringPeriod`), box-score minutes, and official injury reports into the identical data structure used by live daily runs.
- **In-Memory Mode**: Supports `--dry-run` flag via in-memory SQLite (`:memory:`) to audit scenarios without mutating the production database.

---

## 7. CLI & Operations (`cli.py`)

```bash
# View league eligibility table
python3 cli.py status

# Inspect state transitions and violation history
python3 cli.py audit-log --limit 25

# Trigger daily evaluation for a given date
python3 cli.py evaluate --date 2026-11-01

# Season-ending injury registry management
python3 cli.py out-for-season list
python3 cli.py out-for-season add 3102531 "Kristaps Porzingis" --notes "Foot surgery recovery"
python3 cli.py out-for-season remove 3102531
```

---

## 8. Test Suite

Unit, scenario, and state machine tests are located in `tests/`:

```bash
# Execute test suite
python3 -m unittest discover tests
```
