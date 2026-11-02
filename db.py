"""Database storage and data access layer for NBA Fantasy Trade Eligibility."""

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Dict, Generator, List, Optional

class Database:
    def __init__(self, db_path: str = "fantasy_eligibility.db"):
        self.db_path = db_path
        self.init_db()

    @contextmanager
    def get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def init_db(self):
        with self.get_connection() as conn:
            conn.executescript("""
            CREATE TABLE IF NOT EXISTS raw_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                eval_date TEXT NOT NULL,
                capture_type TEXT NOT NULL, -- 'pre_tip' or 'final'
                captured_at TEXT NOT NULL,
                payload TEXT NOT NULL,
                status TEXT NOT NULL, -- 'success', 'failed', 'partial'
                UNIQUE(eval_date, capture_type)
            );

            CREATE TABLE IF NOT EXISTS daily_facts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                eval_date TEXT NOT NULL,
                team_id INTEGER NOT NULL,
                team_name TEXT NOT NULL,
                is_game_day INTEGER NOT NULL,
                is_unknown INTEGER NOT NULL,
                r1_violation INTEGER NOT NULL,
                r1_details TEXT,
                r2_violation INTEGER NOT NULL,
                r2_details TEXT,
                r3_violation INTEGER NOT NULL,
                r3_details TEXT,
                r4_violation INTEGER NOT NULL,
                r4_details TEXT,
                created_at TEXT NOT NULL,
                UNIQUE(eval_date, team_id)
            );

            CREATE TABLE IF NOT EXISTS team_criteria_state (
                team_id INTEGER NOT NULL,
                team_name TEXT NOT NULL,
                criterion TEXT NOT NULL, -- 'R1', 'R2', 'R3', 'R4'
                is_flagged INTEGER NOT NULL DEFAULT 0,
                flagged_since TEXT,
                consecutive_violations INTEGER NOT NULL DEFAULT 0,
                consecutive_clean INTEGER NOT NULL DEFAULT 0,
                history TEXT, -- JSON array of {"date": "...", "violation": bool}
                updated_at TEXT NOT NULL,
                PRIMARY KEY (team_id, criterion)
            );

            CREATE TABLE IF NOT EXISTS state_change_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                eval_date TEXT NOT NULL,
                team_id INTEGER NOT NULL,
                team_name TEXT NOT NULL,
                criterion TEXT NOT NULL,
                old_state TEXT NOT NULL, -- 'CLEAN' or 'FLAGGED'
                new_state TEXT NOT NULL, -- 'CLEAN' or 'FLAGGED'
                reason TEXT NOT NULL,
                details TEXT
            );

            CREATE TABLE IF NOT EXISTS season_ending_players (
                player_id INTEGER PRIMARY KEY,
                player_name TEXT NOT NULL,
                date_designated TEXT NOT NULL,
                source TEXT NOT NULL DEFAULT 'commissioner',
                notes TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_snapshots_date ON raw_snapshots(eval_date);
            CREATE INDEX IF NOT EXISTS idx_facts_date ON daily_facts(eval_date);
            CREATE INDEX IF NOT EXISTS idx_change_log_team ON state_change_log(team_id);
            """)

    def save_snapshot(self, eval_date: str, capture_type: str, payload: Dict[str, Any], status: str = "success") -> int:
        captured_at = datetime.now(timezone.utc).isoformat()
        payload_str = json.dumps(payload)
        with self.get_connection() as conn:
            cursor = conn.execute("""
                INSERT INTO raw_snapshots (eval_date, capture_type, captured_at, payload, status)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(eval_date, capture_type) DO UPDATE SET
                    captured_at=excluded.captured_at,
                    payload=excluded.payload,
                    status=excluded.status
            """, (eval_date, capture_type, captured_at, payload_str, status))
            return cursor.lastrowid

    def get_snapshot(self, eval_date: str, capture_type: str) -> Optional[Dict[str, Any]]:
        with self.get_connection() as conn:
            row = conn.execute("""
                SELECT payload, status FROM raw_snapshots
                WHERE eval_date = ? AND capture_type = ?
            """, (eval_date, capture_type)).fetchone()
            if row:
                return {
                    "payload": json.loads(row["payload"]),
                    "status": row["status"]
                }
            return None

    def save_daily_fact(self, fact: Dict[str, Any]):
        now_ts = datetime.now(timezone.utc).isoformat()
        with self.get_connection() as conn:
            conn.execute("""
                INSERT INTO daily_facts (
                    eval_date, team_id, team_name, is_game_day, is_unknown,
                    r1_violation, r1_details,
                    r2_violation, r2_details,
                    r3_violation, r3_details,
                    r4_violation, r4_details,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(eval_date, team_id) DO UPDATE SET
                    team_name=excluded.team_name,
                    is_game_day=excluded.is_game_day,
                    is_unknown=excluded.is_unknown,
                    r1_violation=excluded.r1_violation,
                    r1_details=excluded.r1_details,
                    r2_violation=excluded.r2_violation,
                    r2_details=excluded.r2_details,
                    r3_violation=excluded.r3_violation,
                    r3_details=excluded.r3_details,
                    r4_violation=excluded.r4_violation,
                    r4_details=excluded.r4_details,
                    created_at=excluded.created_at
            """, (
                fact["eval_date"], fact["team_id"], fact["team_name"],
                1 if fact["is_game_day"] else 0,
                1 if fact["is_unknown"] else 0,
                1 if fact["r1_violation"] else 0, json.dumps(fact.get("r1_details", {})),
                1 if fact["r2_violation"] else 0, json.dumps(fact.get("r2_details", {})),
                1 if fact["r3_violation"] else 0, json.dumps(fact.get("r3_details", {})),
                1 if fact["r4_violation"] else 0, json.dumps(fact.get("r4_details", {})),
                now_ts
            ))

    def get_daily_facts(self, eval_date: str) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            rows = conn.execute("SELECT * FROM daily_facts WHERE eval_date = ?", (eval_date,)).fetchall()
            facts = []
            for r in rows:
                facts.append({
                    "eval_date": r["eval_date"],
                    "team_id": r["team_id"],
                    "team_name": r["team_name"],
                    "is_game_day": bool(r["is_game_day"]),
                    "is_unknown": bool(r["is_unknown"]),
                    "r1_violation": bool(r["r1_violation"]),
                    "r1_details": json.loads(r["r1_details"]) if r["r1_details"] else {},
                    "r2_violation": bool(r["r2_violation"]),
                    "r2_details": json.loads(r["r2_details"]) if r["r2_details"] else {},
                    "r3_violation": bool(r["r3_violation"]),
                    "r3_details": json.loads(r["r3_details"]) if r["r3_details"] else {},
                    "r4_violation": bool(r["r4_violation"]),
                    "r4_details": json.loads(r["r4_details"]) if r["r4_details"] else {}
                })
            return facts

    def get_team_criterion_state(self, team_id: int, criterion: str) -> Optional[Dict[str, Any]]:
        with self.get_connection() as conn:
            row = conn.execute("""
                SELECT * FROM team_criteria_state
                WHERE team_id = ? AND criterion = ?
            """, (team_id, criterion)).fetchone()
            if row:
                return {
                    "team_id": row["team_id"],
                    "team_name": row["team_name"],
                    "criterion": row["criterion"],
                    "is_flagged": bool(row["is_flagged"]),
                    "flagged_since": row["flagged_since"],
                    "consecutive_violations": row["consecutive_violations"],
                    "consecutive_clean": row["consecutive_clean"],
                    "history": json.loads(row["history"]) if row["history"] else [],
                    "updated_at": row["updated_at"]
                }
            return None

    def save_team_criterion_state(self, state: Dict[str, Any]):
        now_ts = datetime.now(timezone.utc).isoformat()
        with self.get_connection() as conn:
            conn.execute("""
                INSERT INTO team_criteria_state (
                    team_id, team_name, criterion, is_flagged, flagged_since,
                    consecutive_violations, consecutive_clean, history, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(team_id, criterion) DO UPDATE SET
                    team_name=excluded.team_name,
                    is_flagged=excluded.is_flagged,
                    flagged_since=excluded.flagged_since,
                    consecutive_violations=excluded.consecutive_violations,
                    consecutive_clean=excluded.consecutive_clean,
                    history=excluded.history,
                    updated_at=excluded.updated_at
            """, (
                state["team_id"], state["team_name"], state["criterion"],
                1 if state["is_flagged"] else 0, state["flagged_since"],
                state["consecutive_violations"], state["consecutive_clean"],
                json.dumps(state.get("history", [])),
                now_ts
            ))

    def log_state_change(self, eval_date: str, team_id: int, team_name: str, criterion: str,
                         old_state: str, new_state: str, reason: str, details: Dict[str, Any]):
        now_ts = datetime.now(timezone.utc).isoformat()
        with self.get_connection() as conn:
            conn.execute("""
                INSERT INTO state_change_log (
                    timestamp, eval_date, team_id, team_name, criterion,
                    old_state, new_state, reason, details
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                now_ts, eval_date, team_id, team_name, criterion,
                old_state, new_state, reason, json.dumps(details)
            ))

    def get_all_team_states(self) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            rows = conn.execute("""
                SELECT * FROM team_criteria_state
                ORDER BY team_name, criterion
            """).fetchall()
            results = []
            for r in rows:
                results.append({
                    "team_id": r["team_id"],
                    "team_name": r["team_name"],
                    "criterion": r["criterion"],
                    "is_flagged": bool(r["is_flagged"]),
                    "flagged_since": r["flagged_since"],
                    "consecutive_violations": r["consecutive_violations"],
                    "consecutive_clean": r["consecutive_clean"],
                    "history": json.loads(r["history"]) if r["history"] else []
                })
            return results

    def add_season_ending_player(self, player_id: int, player_name: str, date_designated: str,
                                source: str = "commissioner", notes: str = ""):
        with self.get_connection() as conn:
            conn.execute("""
                INSERT INTO season_ending_players (player_id, player_name, date_designated, source, notes)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(player_id) DO UPDATE SET
                    player_name=excluded.player_name,
                    date_designated=excluded.date_designated,
                    source=excluded.source,
                    notes=excluded.notes
            """, (player_id, player_name, date_designated, source, notes))

    def remove_season_ending_player(self, player_id: int):
        with self.get_connection() as conn:
            conn.execute("DELETE FROM season_ending_players WHERE player_id = ?", (player_id,))

    def get_season_ending_players(self) -> Dict[int, Dict[str, Any]]:
        with self.get_connection() as conn:
            rows = conn.execute("SELECT * FROM season_ending_players").fetchall()
            return {
                r["player_id"]: {
                    "player_id": r["player_id"],
                    "player_name": r["player_name"],
                    "date_designated": r["date_designated"],
                    "source": r["source"],
                    "notes": r["notes"]
                }
                for r in rows
            }

    def get_state_change_logs(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            rows = conn.execute("""
                SELECT * FROM state_change_log
                ORDER BY id DESC LIMIT ?
            """, (limit,)).fetchall()
            return [dict(r) for r in rows]
