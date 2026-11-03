import json
from datetime import date
from backtester import BacktestRunner
from notifier import Notifier

runner = BacktestRunner(dry_run=True)
res = runner.run_backtest(
    start_date=date(2026, 10, 20),
    end_date=date(2026, 11, 1),
    verbose=False
)

print("\n" + "=" * 90)
print("📊 CURRENT R1 (WASTED ACTIVE SLOT) COUNTS & STATUS (TRAILING 14 GAME DAYS)")
print("=" * 90)

all_states = runner.db.get_all_team_states()
r1_states = [s for s in all_states if s["criterion"] == "R1"]

print(f"{'Team Name':<22} | {'R1 Count':<8} | {'Status':<10} | {'Dates Violated'}")
print("-" * 90)

for s in sorted(r1_states, key=lambda x: (-len([h for h in x.get("history", [])[-14:] if h.get("violation")]), x["team_name"])):
    hist = s.get("history", [])
    window = hist[-14:]
    viol_dates = [h["date"] for h in window if h.get("violation")]
    count = len(viol_dates)
    status = "FLAGGED" if s.get("is_flagged") else "CLEAN"
    dates_str = ", ".join(viol_dates) if viol_dates else "None (0 wasted days)"
    print(f"{s['team_name']:<22} | {count:<8} | {status:<10} | {dates_str}")

print("\n" + "=" * 90)
print("🔍 DETAILS FOR EVERY R1 WASTED ACTIVE SLOT DAY:")
print("=" * 90)

for v in res["violations"]:
    if v.get("r1_violation"):
        print(f"\n🏀 Date: {v['eval_date']} | Team: {v['team_name']} (ID {v['team_id']})")
        details = v.get("r1_details", {})
        for ws in details.get("wasted_slots", []):
            print(f"   • Slot {ws.get('slot_id')} ({ws.get('current_player')}): {ws.get('reason')}")
            replacements = ws.get("eligible_bench_replacements", [])
            print(f"     Eligible bench replacements: {', '.join(replacements)}")
        bench_healthy = details.get("available_healthy_bench", [])
        if bench_healthy:
            print(f"     All available healthy bench with games: {', '.join(bench_healthy)}")
