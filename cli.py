"""Command Line Interface for the Commissioner and System Operators."""

import argparse
import sys
from datetime import date, datetime, timedelta
from config import DEFAULT_CONFIG, ET_TZ
from db import Database
from espn_client import EspnClient
from injury_source import InjurySource
from notifier import Notifier
from scheduler import DailyWorkflowRunner
from state_machine import StateMachine

def get_runner(db: Database) -> DailyWorkflowRunner:
    espn = EspnClient(
        league_id=DEFAULT_CONFIG.league_id,
        season_year=DEFAULT_CONFIG.season_year,
        espn_s2=DEFAULT_CONFIG.espn_s2,
        swid=DEFAULT_CONFIG.swid
    )
    injury_src = InjurySource(db)
    notifier = Notifier(webhook_url=DEFAULT_CONFIG.webhook_url)
    return DailyWorkflowRunner(db, espn, injury_src, notifier)

def cmd_status(args):
    db = Database(DEFAULT_CONFIG.db_path)
    sm = StateMachine(db)
    notifier = Notifier()
    report = sm.get_league_eligibility_report()
    if not report:
        print("No team states found in database. Run an evaluation first.")
        return
    print("\nCURRENT LEAGUE TRADE ELIGIBILITY STATUS:")
    print(notifier.format_eligibility_table(report))

def cmd_audit_log(args):
    db = Database(DEFAULT_CONFIG.db_path)
    logs = db.get_state_change_logs(limit=args.limit)
    if not logs:
        print("No state changes logged yet.")
        return
    print(f"\nRECENT STATE CHANGE LOGS (Last {len(logs)}):")
    print("-" * 80)
    for l in logs:
        print(f"[{l['timestamp']}] Date: {l['eval_date']} | Team: {l['team_name']} ({l['team_id']})")
        print(f"  Criterion: {l['criterion']} | Transition: {l['old_state']} -> {l['new_state']}")
        print(f"  Reason: {l['reason']}\n")

def cmd_pre_tip(args):
    db = Database(DEFAULT_CONFIG.db_path)
    runner = get_runner(db)
    eval_date = args.date or (datetime.now(ET_TZ).date().isoformat())
    success = runner.run_pre_tip_capture(eval_date)
    print(f"Pre-tip capture for {eval_date}: {'SUCCESS' if success else 'FAILED'}")

def cmd_evaluate(args):
    db = Database(DEFAULT_CONFIG.db_path)
    runner = get_runner(db)
    # Default evaluate date is yesterday ET
    if args.date:
        eval_date = args.date
    else:
        yesterday = (datetime.now(ET_TZ) - timedelta(days=1)).date()
        eval_date = yesterday.isoformat()

    print(f"Evaluating date: {eval_date}")
    success = runner.run_final_capture_and_evaluation(eval_date)
    print(f"Evaluation for {eval_date}: {'SUCCESS' if success else 'FAILED'}")

def cmd_replay(args):
    db = Database(DEFAULT_CONFIG.db_path)
    runner = get_runner(db)
    eval_date = args.date
    if not eval_date:
        print("Error: --date YYYY-MM-DD is required for replay.")
        sys.exit(1)
    success = runner.replay_date(eval_date)
    print(f"Replay for {eval_date}: {'SUCCESS' if success else 'FAILED'}")

def cmd_facts(args):
    db = Database(DEFAULT_CONFIG.db_path)
    facts = db.get_daily_facts(args.date)
    if not facts:
        print(f"No facts found for date {args.date}")
        return
    print(f"\nDAILY FACTS FOR {args.date}:")
    for f in facts:
        print(f"\nTeam: {f['team_name']} (ID {f['team_id']})")
        print(f"  Game Day: {f['is_game_day']} | Unknown: {f['is_unknown']}")
        print(f"  R1 Violation: {f['r1_violation']} {f['r1_details']}")
        print(f"  R2 Violation: {f['r2_violation']} {f['r2_details']}")
        print(f"  R3 Violation: {f['r3_violation']} {f['r3_details']}")
        print(f"  R4 Violation: {f['r4_violation']} {f['r4_details']}")

def cmd_out_for_season(args):
    db = Database(DEFAULT_CONFIG.db_path)
    sub = args.subcommand
    if sub == "add":
        db.add_season_ending_player(
            player_id=args.player_id,
            player_name=args.name,
            date_designated=args.date or datetime.now(ET_TZ).date().isoformat(),
            notes=args.notes or ""
        )
        print(f"Added {args.name} (ID: {args.player_id}) to season-ending registry.")
    elif sub == "remove":
        db.remove_season_ending_player(args.player_id)
        print(f"Removed player ID {args.player_id} from season-ending registry.")
    elif sub == "list":
        players = db.get_season_ending_players()
        if not players:
            print("No season-ending players registered.")
            return
        print(f"\nSEASON-ENDING REGISTRY ({len(players)} players):")
        print(f"{'ID':<10} | {'Player Name':<28} | {'Designated':<12} | {'Notes'}")
        print("-" * 70)
        for pid, p in players.items():
            print(f"{pid:<10} | {p['player_name']:<28} | {p['date_designated']:<12} | {p['notes']}")

def main():
    parser = argparse.ArgumentParser(description="NBA Fantasy Trade Eligibility System CLI")
    subparsers = parser.add_subparsers(dest="cmd", help="Subcommand to execute")

    # status
    p_status = subparsers.add_parser("status", help="View current trade eligibility status")
    p_status.set_defaults(func=cmd_status)

    # audit-log
    p_log = subparsers.add_parser("audit-log", help="View recent state change logs")
    p_log.add_argument("--limit", type=int, default=20, help="Number of log entries to show")
    p_log.set_defaults(func=cmd_audit_log)

    # pre-tip
    p_pre = subparsers.add_parser("pre-tip", help="Trigger pre-tip capture")
    p_pre.add_argument("--date", help="Evaluation date (YYYY-MM-DD)")
    p_pre.set_defaults(func=cmd_pre_tip)

    # evaluate
    p_eval = subparsers.add_parser("evaluate", help="Trigger 2 AM capture and evaluation")
    p_eval.add_argument("--date", help="Evaluation date D (default: yesterday ET)")
    p_eval.set_defaults(func=cmd_evaluate)

    # replay
    p_rep = subparsers.add_parser("replay", help="Replay evaluation for date D from stored snapshots")
    p_rep.add_argument("--date", required=True, help="Evaluation date (YYYY-MM-DD)")
    p_rep.set_defaults(func=cmd_replay)

    # facts
    p_facts = subparsers.add_parser("facts", help="Inspect daily facts for date D")
    p_facts.add_argument("--date", required=True, help="Evaluation date (YYYY-MM-DD)")
    p_facts.set_defaults(func=cmd_facts)

    # out-for-season
    p_ofs = subparsers.add_parser("out-for-season", help="Manage season-ending player registry")
    ofs_sub = p_ofs.add_subparsers(dest="subcommand", required=True)
    
    ofs_add = ofs_sub.add_parser("add", help="Add a season-ending player")
    ofs_add.add_argument("player_id", type=int, help="Player ID")
    ofs_add.add_argument("name", help="Player Full Name")
    ofs_add.add_argument("--date", help="Date designated (default: today)")
    ofs_add.add_argument("--notes", help="Injury details / notes")
    
    ofs_rm = ofs_sub.add_parser("remove", help="Remove a season-ending player")
    ofs_rm.add_argument("player_id", type=int, help="Player ID")

    ofs_ls = ofs_sub.add_parser("list", help="List registered season-ending players")
    p_ofs.set_defaults(func=cmd_out_for_season)

    args = parser.parse_args()
    if not args.cmd:
        parser.print_help()
        sys.exit(0)

    args.func(args)

if __name__ == "__main__":
    main()
