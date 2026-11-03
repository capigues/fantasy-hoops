# 🏆 NBA Fantasy League: Official Trade Eligibility & Roster Rules

Welcome to the official roster maintenance and trade eligibility guide for our fantasy basketball league. 

Our league thrives on active competition. To protect fair play, prevent tanking, and ensure every matchup is competitive, the league enforces an automated **Trade Eligibility Policy**. If a manager neglects their lineup or roster, their team is temporarily flagged as **Trade-Ineligible** until active management is restored.

---

## 🏀 Roster Layout & Lineup Rules

Every team carries up to **14 players** on their roster:

| Slot Type | Positions | Spots Available | Rules |
| :--- | :--- | :---: | :--- |
| **Active Starters** | Point Guard (PG)<br>Shooting Guard (SG)<br>Small Forward (SF)<br>Power Forward (PF)<br>Center (C)<br>Guard (G)<br>Forward (F)<br>Utility (UTIL) | **10 Starters**<br>*(1 PG, 1 SG, 1 SF, 1 PF, 1 C, 1 G, 1 F, 3 UTIL)* | Must be set daily before game tip-offs. Position slots require players with matching eligibility; UTIL slots accept any position. |
| **Bench (BE)** | Any Position | **3 Spots** | Players sitting on your bench do not earn points for your matchup. |
| **Injured Reserve (IR)** | Sidelined Players | **1 Spot** | Strictly reserved for players officially designated as **`OUT`** or **`IR`**. |

---

## 📋 The 4 Roster Rules

A team maintains full trading privileges as long as all four roster rules are followed. If any single rule enters a flagged state, **the team cannot propose or accept trades** until cleared.

```
       ┌────────────────────────────────────────────────────────┐
       │                Are You Trade Eligible?                 │
       │                                                        │
       │   Rule 1: Starting your active players with games?     │
       │   Rule 2: Putting sidelined OUT players on IR?        │
       │   Rule 3: Dropping players out for the season?         │
       │   Rule 4: Carrying a full, legal 13+ player roster?    │
       │                                                        │
       │   ✅ All 4 Followed  ──>  ELIGIBLE TO TRADE            │
       │   ❌ Any Rule Broken ──>  TRADE FREEZE (INELIGIBLE)    │
       └────────────────────────────────────────────────────────┘
```

---

### Rule 1: Set Your Lineup (No Wasted Starting Slots)

> **The Golden Rule**: Start players who have games. Do not leave starting spots empty or bench healthy players playing tonight while an inactive/off-day player sits in your starting lineup.

#### How a Wasted Slot is Checked:
Each game day, the system checks three straightforward questions:
1. **Is there an open starting spot?**
   - You started fewer than 10 players, **OR**
   - An active starter is officially ruled **`OUT`**, **OR**
   - An active starter's NBA team has **no game scheduled** that night.
2. **Do you have an active player on your bench?**
   - A player sitting on your bench has an NBA game tonight and is healthy.
3. **Does the position line up?**
   - Can the bench player legally fill that open starter spot? *(UTIL spots accept any player; position spots like PG or Forward require matching eligibility).*

If all three are **Yes**, that day is counted as a **Wasted Slot Day**.

#### What Does NOT Count as a Violation?
* **Full Active Lineup**: If all 10 of your starters have games and play, having extra bench players who also play is normal. You cannot start 11 players!
* **No Bench Replacements**: If your entire bench has the night off or is injured, starting an inactive player is not penalized because you had no alternative.
* **Position Mismatch**: If your open spot is Forward, but your only bench players playing tonight are Point Guards who cannot play Forward, you are not penalized.
* **Day-to-Day / Questionable**: Starting a game-time decision or Day-to-Day player who has a game is completely legal. Only players confirmed **`OUT`** or with **`NO GAME`** count as idle.

#### How Penalties & Clearing Work (14-Game-Day Window)
* **The Window**: Your activity is measured across a rolling window of the last **14 NBA game days**. (Days with no NBA games scheduled, like holidays or All-Star break, are skipped).
* **Trade Freeze**: If you rack up **4 or more wasted days** within the 14-day window, your team is **Trade-Ineligible**.
* **Clearing the Freeze**: To unfreeze your team, your wasted days inside the rolling 14-day window must drop down to **1 or 0**.
* **Anti-Flicker Buffer**: At 2 or 3 wasted days, an ineligible team stays ineligible. This prevents someone from fixing their lineup for one night just to force a trade through, then neglecting it again.

---

#### 📖 Example: How the 14-Day Rolling Window Works (Team No Cap)

Here is a 20-day timeline showing how team **No Cap** loses eligibility and earns it back:

##### Phase 1: Falling into Ineligibility (Days 1 to 9)
* **Day 1**: No Cap sets a full lineup. All 10 starters play. *(Window count: 0 — **ELIGIBLE**)*
* **Day 2 (1st Wasted Day)**: No Cap starts a Center whose team has the night off, while an active bench Center scores 30 points on the bench. *(Window count: 1 — **ELIGIBLE**)*
* **Day 4 (2nd Wasted Day)**: An active starter is ruled `OUT` before tip-off, but sits in an active UTIL spot while a bench player plays. *(Window count: 2 — **ELIGIBLE**)*
* **Day 6 (3rd Wasted Day)**: No Cap only starts 9 players, leaving an open Forward spot while a bench Forward plays. *(Window count: 3 — **ELIGIBLE**, 1 day away from freeze)*
* **Day 9 (4th Wasted Day)**: An active starter with no game is started over an active bench player with a game.
  - **🚨 THRESHOLD REACHED**: In the last 14 game days, No Cap now has **4 wasted days** (Days 2, 4, 6, 9).
  - **Status**: **TRADE-INELIGIBLE**. Trading privileges are frozen.

---

##### Phase 2: The "Quick Fix" Does NOT Work (Days 10 to 14)
* **Day 10**: The manager notices the trade freeze, logs in, and sets a perfect lineup.
  - *Are they eligible again?* **NO.**
  - Looking back over the last 14 game days, Days 2, 4, 6, and 9 are **still inside the window** (Count: 4).
* **Day 12**: Another clean day.
  - *Are they eligible?* **Still NO.**
  - **Why?** You cannot neglect your team for weeks, set your lineup once to make a quick trade, and walk away. Managers must show sustained active management.

---

##### Phase 3: Earning Eligibility Back (Days 15 to 20)
As new game days are played, older violations **roll off the back** of the 14-day window:

```text
Day 9:   [Day 1  ──────  Day 4 (❌) ── Day 6 (❌) ── Day 9 (❌)]  ──> 4 Violations (FROZEN)
Day 16:  [Day 3  ──────  Day 4 (❌) ── Day 6 (❌) ── Day 9 (❌)]  ──> 3 Violations (STILL FROZEN: Buffer)
Day 18:  [Day 5  ───────────── Day 6 (❌) ──────── Day 9 (❌)]  ──> 2 Violations (STILL FROZEN: Buffer)
Day 20:  [Day 7  ─────────────────────────────── Day 9 (❌)]  ──> 1 Violation  (CLEARED & ELIGIBLE!)
```

* **Day 16** (Window covers Days 3 to 16):
  - Day 2 rolls out of the window.
  - Violations remaining in window: Days 4, 6, 9 *(Count: 3)*.
  - *Status*: **STILL INELIGIBLE**. *(Must reach 1 or 0 to clear)*.
* **Day 18** (Window covers Days 5 to 18):
  - Day 4 rolls out of the window.
  - Violations remaining in window: Days 6, 9 *(Count: 2)*.
  - *Status*: **STILL INELIGIBLE**.
* **Day 20** (Window covers Days 7 to 20):
  - Day 6 rolls out of the window.
  - Violations remaining in window: Only Day 9 *(Count: 1)*.
  - **🎉 CLEARED**: The count has dropped to **$\le 1$**.
  - **Status Change**: **TRADE-ELIGIBLE**.

---

### Rule 2: Utilize the Injured Reserve (IR) Slot

> **Put your injured stars on IR**. Do not let an empty IR spot go to waste when you have sidelined players on your bench or active roster.

* **The Rule**: If you have a player designated as **`OUT`**, they should be placed in your IR slot. Leaving your single IR slot completely empty while an `OUT` player sits on your active roster or bench is a violation.
* **Grace Period**: You have **2 game days** from when a player is ruled `OUT` to move them to IR.
* **When Trades Freeze**: If left unresolved, your team is flagged **Trade-Ineligible** on the **3rd consecutive game day**.
* **How to Clear**: Move an injured player into your IR slot (or hold a clean roster once players return) for **2 consecutive game days**.

---

### Rule 3: Drop Season-Ending Injuries

> **No hoarding players out for the year**. Drop players who are officially ruled out for the remainder of the season.

* **The Rule**: Carrying a player on your roster (even on IR) who has been officially ruled out for the rest of the NBA season (e.g. season-ending surgery or ACL tear) is not permitted.
* **Grace Period**: You have **2 game days** from the official designation to drop the player.
* **When Trades Freeze**: If kept on your roster, your team becomes **Trade-Ineligible** on the **3rd consecutive game day**.
* **How to Clear**: Drop the player and maintain a clean roster for **2 consecutive game days**.

---

### Rule 4: Maintain a Complete Roster

> **Keep a legal roster size**. Carry at least 13 players and never exceed the single IR spot.

* **The Rule**: Dropping players without replacements (falling below 13 players) or holding multiple players in IR is illegal.
* **Grace Period**: You have **2 game days** to add a player or resolve an IR overflow.
* **When Trades Freeze**: Flags on the **3rd consecutive game day**; clears after **2 consecutive clean game days**.

---

## ⚡ Quick Reference Summary

| Rule | What's Checked | Penalty Threshold | How to Clear |
| :--- | :--- | :--- | :--- |
| **Rule 1: Wasted Slot** | Active players with games left on bench while starting slots are empty, OUT, or have no game. | **$\ge 4$ wasted days** in trailing 14 game days | Set clean lineups until wasted days drop to **$\le 1$** |
| **Rule 2: Unused IR** | IR slot empty while an `OUT` player sits on bench or starting lineup. | **3 consecutive game days** of violation (2-day grace) | Put injured player in IR for **2 clean game days** |
| **Rule 3: Dead Spot** | Keeping a player officially ruled out for the season on your roster. | **3 consecutive game days** of violation (2-day grace) | Drop the player for **2 clean game days** |
| **Rule 4: Illegal Roster** | Fewer than 13 players or exceeding 1 IR slot. | **3 consecutive game days** of violation (2-day grace) | Restore legal roster for **2 clean game days** |

---

## 🛡️ Commissioner Review & Trade Freezes

* **Trade Block Enforcement**: When a team is flagged as **Trade-Ineligible**, any proposed trades involving that team will be vetoed by the commissioner.
* **Notifications**: Managers receive an alert when a violation occurs or when their team enters a grace period, giving ample time to correct their lineup before trading privileges are affected.
* **Questions or Disputes**: Contact the league commissioner directly if an unusual scheduling or injury situation occurs.

---

*For developers or commissioner tools detailing system architecture, automated daily audits, and backtesting scripts, see [DESIGN.md](DESIGN.md).*
