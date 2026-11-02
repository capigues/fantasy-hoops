# NBA Fantasy Trade Eligibility System

An automated tracking system for our ESPN Head-to-Head NBA Fantasy League. Its purpose is simple: **ensure fair play and keep managers actively maintaining their rosters**.

If a manager neglects their lineup or roster requirements, their team is flagged as **Trade-Ineligible** until the issues are resolved.

---

## 🏀 League Roster Structure

Each team has a total roster of up to **14 players**, broken down into:

- **10 Active Starters**:
  - Point Guard (PG) - 1 slot
  - Shooting Guard (SG) - 1 slot
  - Small Forward (SF) - 1 slot
  - Power Forward (PF) - 1 slot
  - Center (C) - 1 slot
  - Guard (G) - 1 slot
  - Forward (F) - 1 slot
  - Utility (UTIL) - 3 slots
- **3 Bench Players (BE)**
- **1 Injured Reserve Slot (IR)**

*Note: Active starters lock at tip-off. Active slots can be filled by any player eligible for that position, and UTIL slots can be filled by any position.*

---

## 📋 The 4 Roster Rules Explained in Plain English

A team must follow 4 core roster requirements. If any rule is violated beyond its grace period or threshold, the team loses trade eligibility.

```
       ┌────────────────────────────────────────────────────────┐
       │                Are You Trade Eligible?                 │
       │                                                        │
       │   R1: No repeated wasted active starter slots?         │
       │   R2: Utilizing your IR spot when players are OUT?     │
       │   R3: No season-ending injured players kept rostered?  │
       │   R4: Legal roster size (≥13 players) & ≤1 IR?         │
       │                                                        │
       │   ✅ All Clean  ──>  ELIGIBLE TO TRADE                 │
       │   ❌ Any Flag   ──>  TRADE INELIGIBLE                  │
       └────────────────────────────────────────────────────────┘
```

---

### Rule 1 (R1): Wasted Active Starter Slot
> **The Golden Rule**: Start your healthy players. Don't leave empty starter spots or bench healthy players playing that night while leaving an injured player in your lineup.

* **What counts as a violation?**
  Leaving an active starter slot empty OR starting a player designated as **OUT**, **while** you had a healthy, position-eligible bench player who played an NBA game that night.
* **What does NOT count as a violation?**
  - **No Bench Replacement**: If all your bench players also had no game that night, or were also OUT, starting an OUT player is **not** penalized. (You couldn't have played anyone else anyway!)
  - **Wrong Position**: If you start an OUT Point Guard, but your only healthy bench player is a Center who cannot play PG/G/UTIL, it is **not** a violation.
  - **Day-to-Day / Questionable**: Starting a player listed as Questionable or Day-to-Day (DTD) is completely fine. Only officially **`OUT`** players trigger this check.
  - **They Actually Played**: If a player was listed as OUT on paper but suited up and logged minutes in the box score, the system recognizes that they played. No penalty!
* **How the Penalty Works (14-Game-Day Window)**:
  - We look at a rolling window of the last **14 NBA game days**.
  - **Violated / Ineligible**: If you waste an active slot on **4 or more game days** in that 14-day window.
  - **Cleared / Eligible**: Clears back to eligible once your wasted days drop to **1 or 0**.
  - *(At 2 or 3 wasted days, your current status stays the same to avoid constant flip-flopping).*

---

### Rule 2 (R2): Unused IR Spot
> **Put your injured stars in IR**. Don't let an empty IR spot go to waste when you have players sidelined.

* **What counts as a violation?**
  Your IR slot is completely **empty**, while you have one or more players listed as **`OUT`** sitting on your active roster or bench.
* **What does NOT count as a violation?**
  - Your IR slot is already filled by an injured player.
  - The sidelined player is only Day-to-Day (DTD) or Questionable (they must be designated as `OUT` to be eligible for IR).
  - The player actually played minutes that day.
* **How the Penalty Works (2-Day Grace Period)**:
  - You get a **2-game-day grace period** to move an `OUT` player into your IR slot.
  - If you leave the IR slot empty with an `OUT` player for **3 consecutive game days**, your team is flagged **Trade-Ineligible**.
  - To clear it: Simply move an injured player into IR (or wait until your player returns to active status) for **2 consecutive game days**.

---

### Rule 3 (R3): Dead Roster Spot (Season-Ending Injuries)
> **No hoarding players out for the year**. Drop players who are officially ruled out for the remainder of the season.

* **What counts as a violation?**
  Carrying a player on your roster (even on IR) who has been officially ruled out for the rest of the NBA season (e.g., torn ACL, season-ending surgery).
* **How the Penalty Works (2-Day Grace Period)**:
  - You have **2 game days** from the official designation to drop the player.
  - On the **3rd consecutive game day**, your team becomes trade-ineligible.
  - Clears immediately after the player is dropped and verified over 2 clean game days.

---

### Rule 4 (R4): Invalid Roster Size & IR Limits
> **Maintain a legal roster**. Keep at least 13 players and never exceed 1 IR spot.

* **What counts as a violation?**
  - Carrying fewer than 13 total players (e.g., dropping players and leaving empty roster spots).
  - Having more than 1 player in the IR slot.
* **How the Penalty Works (2-Day Grace Period)**:
  - You have **2 game days** to add a player or resolve the IR overflow.
  - Flags on the **3rd consecutive game day**; clears after 2 consecutive clean game days.

---

## ⏱️ How & When It Runs

1. **Game Days Only**: Off-days (days with 0 NBA games, like Thanksgiving or All-Star break) do not count toward grace periods or trailing windows.
2. **Single Daily Evaluation**: Evaluated every morning after all games finish (2:00 AM ET).
3. **Ground-Truth Verification**: The system cross-references ESPN fantasy lineups with official NBA box-score minutes to make sure no manager is penalized due to inaccurate pre-game injury labels.
4. **Historical Baseline**: Continuous tracking began on **November 1, 2026**.

---

## 💻 Commissioner & Manager Commands

You can run these commands from the terminal to inspect the league:

```bash
# View the full league table and trade eligibility of all teams
python3 cli.py status

# Inspect the audit log of recent violations and state changes
python3 cli.py audit-log --limit 20

# Run evaluation for a specific date
python3 cli.py evaluate --date 2026-11-01

# Manage season-ending injury registry
python3 cli.py out-for-season list
python3 cli.py out-for-season add <player_id> "Player Name" --notes "Torn ACL"
```

---

## 🧪 Running Automated Tests

All 26 unit and scenario tests can be verified at any time:

```bash
python3 -m unittest discover tests
```
