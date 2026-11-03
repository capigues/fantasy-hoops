# NBA Fantasy Trade Eligibility System

An automated tracking system for our ESPN Head-to-Head NBA Fantasy League. Its purpose is simple: **ensure fair play and keep managers actively maintaining their rosters**.

If a manager neglects their lineup or roster requirements, their team is flagged as **Trade-Ineligible** until the issues are resolved.

---

## 🏀 League Roster Structure

Each team has a total roster of up to **14 players**, broken down into:

- **10 Active Starters**:
  - Point Guard (PG) - 1 slot (Slot 0)
  - Shooting Guard (SG) - 1 slot (Slot 1)
  - Small Forward (SF) - 1 slot (Slot 2)
  - Power Forward (PF) - 1 slot (Slot 3)
  - Center (C) - 1 slot (Slot 4)
  - Guard (G) - 1 slot (Slot 5)
  - Forward (F) - 1 slot (Slot 6)
  - Utility (UTIL) - 3 slots (Slot 11)
- **3 Bench Players (BE)** (Slot 12)
- **1 Injured Reserve Slot (IR)** (Slot 13)

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
> **The Golden Rule**: Start your active players who have games. Don't leave empty starter spots, bench players who play that night while leaving an inactive/injured starter in your lineup, or start players whose NBA teams have off-days when healthy alternatives exist.

#### The 3-Step Evaluation Process:
1. **Identify Open / Replaceable Starting Slots (Slots 1–10)**:
   - A starting slot is literally **unfilled / empty** (starting fewer than 10 players).
   - A starting slot holds a player designated **`OUT`** (and did not play).
   - A starting slot holds a starter whose NBA team has **NO GAME** scheduled that day (off-day, scored 0 pts).
2. **Filter Active Bench Candidates**:
   - Check every player in Bench Slot 12.
   - Filter to only players who **had an NBA game today** (actually suited up, played minutes, or scored fantasy points) and were **NOT OUT**.
   - If no bench players had an NBA game today (or the entire bench was injured), **no violation can occur**.
3. **Positional Alignment Check**:
   - Verify whether the active bench player is legally eligible to fill the open/idle starting slot.
   - For example:
     - An open **SF (Slot 2)** requires an SF-eligible bench player.
     - An open **Forward (Slot 6)** requires an SF or PF eligible bench player (a pure Guard cannot take a Forward slot).
     - An open **UTIL (Slot 11)** can be taken by any healthy bench player who had an NBA game.

#### What does NOT count as a violation?
- **All Active Starters Had Games**: If all 10 starters had games and played, having extra bench players who also played is expected and valid (you cannot start 11 players).
- **No Bench Replacement**: If all bench players also had off-days or were OUT, starting an idle player is not penalized.
- **Wrong Position**: If an open slot is Forward, but your only bench players playing that night are Point Guards who cannot legally play Forward, no violation occurs.
- **Day-to-Day / Questionable**: Starting a player listed as Questionable or Day-to-Day (DTD) who has a game is completely legal. Only players who are officially `OUT` or have `NO GAME` trigger this check.
- **Player Actually Played**: If a player was listed as questionable/OUT on paper but suited up and logged box score minutes, the system recognizes that they played.

#### Penalty & Rolling Window:
- Evaluated across a rolling trailing window of the last **14 NBA game days**.
- **Flagged (Ineligible)**: $\ge 4$ wasted active slot days in the window.
- **Cleared (Eligible)**: $\le 1$ wasted active slot day in the window.
- **Hysteresis Buffer**: At 2 or 3 wasted days, the team's previous state is preserved to avoid flickering.

---

#### 📖 Example: How the 14-Day Rolling Window Works (Team No Cap)

To see exactly how a team loses trade eligibility and how they earn it back, let's follow a 20-day timeline for team **No Cap**:

##### Phase 1: Falling into Ineligibility (Days 1 to 9)
* **Day 1**: No Cap sets a full lineup. All 10 starters play. *(Window count: 0 — **ELIGIBLE**)*
* **Day 2 (1st Wasted Day)**: No Cap starts a Center whose team has the night off, while an active bench Center scores 30 points on the bench. *(Window count: 1 — **ELIGIBLE**)*
* **Day 4 (2nd Wasted Day)**: An active starter is ruled `OUT` before tip-off, but sits in an active UTIL spot while a bench player plays. *(Window count: 2 — **ELIGIBLE**)*
* **Day 6 (3rd Wasted Day)**: No Cap only starts 9 players, leaving an open Forward spot while a bench Forward plays. *(Window count: 3 — **ELIGIBLE**, but 1 day away from a flag)*
* **Day 9 (4th Wasted Day)**: Another active starter with no game is started over an active bench player with a game. 
  - **🚨 THRESHOLD REACHED**: In the last 14 game days, No Cap now has **4 wasted days** (Days 2, 4, 6, 9).
  - **Status Change**: **TRADE-INELIGIBLE**. The team can no longer propose or accept trades.

---

##### Phase 2: The "Quick Fix" Does NOT Work (Days 10 to 14)
* **Day 10**: The manager notices the trade freeze, logs in, and sets a perfect lineup.
  - *Are they eligible again?* **NO.**
  - Looking back over the last 14 game days, Days 2, 4, 6, and 9 are **still inside the window** (Count: 4).
* **Day 12**: Another clean day.
  - *Are they eligible?* **Still NO.**
  - **Why?** The rule stops managers from neglecting their roster for weeks, fixing it for 5 minutes just to squeeze a trade through, and immediately abandoning it again. Managers must demonstrate sustained active management.

---

##### Phase 3: Earning Eligibility Back (Days 15 to 20)
As new game days are played, older days **roll off the back** of the 14-day window:

```text
Day 9:   [Day 1  ──────  Day 4 (❌) ── Day 6 (❌) ── Day 9 (❌)]  ──> 4 Violations (FLAGGED)
Day 16:  [Day 3  ──────  Day 4 (❌) ── Day 6 (❌) ── Day 9 (❌)]  ──> 3 Violations (STILL FLAGGED: Buffer)
Day 18:  [Day 5  ───────────── Day 6 (❌) ──────── Day 9 (❌)]  ──> 2 Violations (STILL FLAGGED: Buffer)
Day 20:  [Day 7  ─────────────────────────────── Day 9 (❌)]  ──> 1 Violation  (CLEARED & ELIGIBLE!)
```

* **Day 16** (Window looks at Days 3 to 16):
  - Day 2 rolls out of the window.
  - Violations remaining in window: Days 4, 6, 9 *(Count: 3)*.
  - *Status*: **STILL INELIGIBLE** *(The 2–3 day buffer means an ineligible team stays ineligible until reaching 1 or 0)*.
* **Day 18** (Window looks at Days 5 to 18):
  - Day 4 rolls out of the window.
  - Violations remaining in window: Days 6, 9 *(Count: 2)*.
  - *Status*: **STILL INELIGIBLE**.
* **Day 20** (Window looks at Days 7 to 20):
  - Day 6 rolls out of the window.
  - Violations remaining in window: Only Day 9 *(Count: 1)*.
  - **🎉 CLEARED**: The count has dropped to **$\le 1$**.
  - **Status Change**: **TRADE-ELIGIBLE**.

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
  - To clear it: Simply move an injured player into IR (or wait until your player returns to active status) for **2 consecutive clean game days**.

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
3. **Ground-Truth Verification**: The system cross-references ESPN fantasy lineups with official NBA box-score minutes and injury reports to ensure zero false positives.
4. **Uniform Data Contract**: Backtesting and live daily runs share identical data structures, guaranteeing that historical validation and live daily evaluation use the exact same evaluation logic.

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

# Run historical backtesting across a date range
python3 investigation.py

# Manage season-ending injury registry
python3 cli.py out-for-season list
python3 cli.py out-for-season add <player_id> "Player Name" --notes "Torn ACL"
```

---

## 🧪 Running Automated Tests

All 29 unit, state machine, and scenario tests can be verified at any time:

```bash
python3 -m unittest discover tests
```
