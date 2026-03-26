import shutil
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
import re

from config import BACKUP_DIR, DB_PATH
from database.schema import SCHEMA_SQL


DATE_FMT = "%Y-%m-%d %H:%M"


class SlotConflictError(Exception):
    pass


class ValidationError(Exception):
    pass


@dataclass
class ActiveBooking:
    booking_id: int
    user_id: int
    master_id: int
    slot_at: str
    reminder_job_id: str | None
    review_job_id: str | None


class Repository:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON;")

    def init_schema(self) -> None:
        self.conn.executescript(SCHEMA_SQL)
        self._ensure_migrations()
        self.conn.commit()

    def _ensure_migrations(self) -> None:
        slots_cols = [r["name"] for r in self.execute("PRAGMA table_info(slots)").fetchall()]
        if "slot_end" not in slots_cols:
            self.execute("ALTER TABLE slots ADD COLUMN slot_end TEXT")
        masters_cols = [r["name"] for r in self.execute("PRAGMA table_info(masters)").fetchall()]
        if "referral_bonus_points" not in masters_cols:
            self.execute("ALTER TABLE masters ADD COLUMN referral_bonus_points INTEGER NOT NULL DEFAULT 0")
        self.execute(
            """
            CREATE TABLE IF NOT EXISTS feedback_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                user_role TEXT NOT NULL,
                feedback_type TEXT NOT NULL CHECK (feedback_type IN ('suggestion', 'bug')),
                text TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'new' CHECK (status IN ('new', 'read')),
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """
        )

    @contextmanager
    def tx(self):
        try:
            yield
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise

    def execute(self, query: str, args: tuple = ()):
        return self.conn.execute(query, args)

    def upsert_user(self, user_id: int, username: str | None, first_name: str | None, role: str = "client") -> None:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self.tx():
            self.execute(
                """
                INSERT OR IGNORE INTO users (id, username, first_name, role, started_at, last_seen)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (user_id, username, first_name, role, now, now),
            )
            self.execute(
                """
                UPDATE users
                SET username = ?, first_name = ?, last_seen = ?, role = CASE WHEN role='owner' THEN role ELSE ? END
                WHERE id = ?
                """,
                (username, first_name, now, role, user_id),
            )

    def register_master(self, master_id: int) -> None:
        self.upsert_user(master_id, None, None, "master")
        with self.tx():
            row = self.execute("SELECT user_id FROM masters WHERE user_id = ?", (master_id,)).fetchone()
            if row:
                return
            now = datetime.now()
            self.execute(
                """
                INSERT INTO masters (user_id, registration_date, subscription_until)
                VALUES (?, ?, ?)
                """,
                (
                    master_id,
                    now.strftime("%Y-%m-%d"),
                    (now + timedelta(days=7)).strftime("%Y-%m-%d"),
                ),
            )

    def is_master_registered(self, master_id: int) -> bool:
        row = self.execute("SELECT 1 FROM masters WHERE user_id = ?", (master_id,)).fetchone()
        return bool(row)

    def set_subscription(self, master_id: int, days: int) -> str:
        self.register_master(master_id)
        row = self.execute("SELECT subscription_until FROM masters WHERE user_id = ?", (master_id,)).fetchone()
        current_until = datetime.strptime(row["subscription_until"], "%Y-%m-%d").date()
        today = datetime.now().date()
        start = current_until if current_until > today else today
        new_until = (start + timedelta(days=days)).strftime("%Y-%m-%d")
        with self.tx():
            self.execute("UPDATE masters SET subscription_until = ? WHERE user_id = ?", (new_until, master_id))
        return new_until

    def check_master_access(self, master_id: int) -> tuple[bool, str]:
        self.register_master(master_id)
        row = self.execute("SELECT subscription_until FROM masters WHERE user_id = ?", (master_id,)).fetchone()
        until_date = datetime.strptime(row["subscription_until"], "%Y-%m-%d").date()
        days_left = (until_date - datetime.now().date()).days
        return (days_left >= 0, str(max(0, days_left + 1)))

    def normalize_portfolio_link(self, raw: str) -> str:
        value = (raw or "").strip()
        if not value:
            raise ValidationError("Portfolio link is empty")
        if value.startswith("@"):
            return f"https://t.me/{value[1:]}"
        if re.match(r"^t\.me\/[A-Za-z0-9_]{4,}$", value):
            return f"https://{value}"
        if value.startswith("http://") or value.startswith("https://"):
            return value
        raise ValidationError("Portfolio link must be URL or @username")

    def get_maintenance(self) -> dict:
        enabled = self.execute("SELECT value FROM system_settings WHERE key='maintenance_enabled'").fetchone()["value"]
        message = self.execute("SELECT value FROM system_settings WHERE key='maintenance_message'").fetchone()["value"]
        return {"enabled": enabled == "1", "message": message}

    def set_maintenance(self, enabled: bool, message: str | None = None) -> None:
        with self.tx():
            self.execute(
                "UPDATE system_settings SET value = ?, updated_at = datetime('now') WHERE key='maintenance_enabled'",
                ("1" if enabled else "0",),
            )
            if message is not None:
                self.execute(
                    "UPDATE system_settings SET value = ?, updated_at = datetime('now') WHERE key='maintenance_message'",
                    (message,),
                )

    def update_master_profile(self, master_id: int, field: str, value: str) -> None:
        allowed = {"main_services", "additional_services", "warranty", "portfolio_link", "photo_id"}
        if field not in allowed:
            raise ValidationError("Unsupported profile field")
        self.register_master(master_id)
        with self.tx():
            self.execute(f"UPDATE masters SET {field} = ? WHERE user_id = ?", (value, master_id))

    def get_master_profile(self, master_id: int):
        return self.execute(
            """
            SELECT main_services, additional_services, warranty, portfolio_link, photo_id
            FROM masters WHERE user_id = ?
            """,
            (master_id,),
        ).fetchone()

    def add_slot(self, master_id: int, slot_at: str) -> None:
        self.register_master(master_id)
        slot_at = slot_at.strip()
        slot_start = slot_at
        slot_end = None
        if " " in slot_at and "-" in slot_at:
            date_part, time_part = slot_at.split(" ", 1)
            if "-" in time_part:
                start_part, end_part = [x.strip() for x in time_part.split("-", 1)]
                slot_start = f"{date_part} {start_part}"
                slot_end = f"{date_part} {end_part}"
        with self.tx():
            self.execute(
                "INSERT OR IGNORE INTO slots (master_id, slot_at, slot_end) VALUES (?, ?, ?)",
                (master_id, slot_start, slot_end),
            )

    def clear_free_slots_for_date(self, master_id: int, date: str) -> None:
        with self.tx():
            self.execute(
                "DELETE FROM slots WHERE master_id = ? AND date(slot_at) = ? AND booked_by IS NULL",
                (master_id, date),
            )

    def delete_free_slot_by_id(self, master_id: int, slot_id: int) -> bool:
        with self.tx():
            cur = self.execute(
                "DELETE FROM slots WHERE id = ? AND master_id = ? AND booked_by IS NULL",
                (slot_id, master_id),
            )
            return cur.rowcount > 0

    def get_available_slots(self, master_id: int, date: str):
        return self.execute(
            """
            SELECT id,
                   CASE WHEN slot_end IS NOT NULL
                        THEN strftime('%H:%M', slot_at) || '-' || strftime('%H:%M', slot_end)
                        ELSE strftime('%H:%M', slot_at)
                   END as time,
                   slot_at
            FROM slots
            WHERE master_id=? AND date(slot_at)=? AND booked_by IS NULL
            ORDER BY slot_at
            """,
            (master_id, date),
        ).fetchall()

    def get_admin_slots(self, master_id: int, date: str):
        return self.execute(
            """
            SELECT id,
                   CASE WHEN slot_end IS NOT NULL
                        THEN strftime('%H:%M', slot_at) || '-' || strftime('%H:%M', slot_end)
                        ELSE strftime('%H:%M', slot_at)
                   END as time,
                   CASE WHEN booked_by IS NULL THEN 0 ELSE 1 END as booked
            FROM slots
            WHERE master_id=? AND date(slot_at)=?
            ORDER BY slot_at
            """,
            (master_id, date),
        ).fetchall()

    def get_slots_count_by_month(self, master_id: int, year_month: str) -> dict:
        rows = self.execute(
            """
            SELECT date(slot_at) as slot_date, COUNT(*) as cnt
            FROM slots
            WHERE master_id = ? AND slot_at LIKE ? AND booked_by IS NULL
            GROUP BY date(slot_at)
            """,
            (master_id, f"{year_month}%"),
        ).fetchall()
        return {row["slot_date"]: row["cnt"] for row in rows}

    def create_booking_atomic(
        self,
        master_id: int,
        user_id: int,
        slot_id: int,
        client_name: str,
        client_phone: str,
    ) -> int:
        self.upsert_user(user_id, None, None, "client")
        with self.tx():
            active_count = self.execute(
                "SELECT COUNT(*) as c FROM bookings WHERE user_id = ? AND status = 'active'",
                (user_id,),
            ).fetchone()["c"]
            if active_count >= 2:
                raise ValidationError("User already has maximum active bookings")
            row = self.execute(
                "SELECT master_id, booked_by FROM slots WHERE id = ?",
                (slot_id,),
            ).fetchone()
            if not row or row["master_id"] != master_id:
                raise ValidationError("Slot not found")
            if row["booked_by"] is not None:
                raise SlotConflictError("Slot already booked")
            self.execute("UPDATE slots SET booked_by = ? WHERE id = ?", (user_id, slot_id))
            cur = self.execute(
                """
                INSERT INTO bookings (slot_id, master_id, user_id, client_name, client_phone, status)
                VALUES (?, ?, ?, ?, ?, 'active')
                """,
                (slot_id, master_id, user_id, client_name, client_phone),
            )
            return cur.lastrowid

    def get_user_active_booking(self, user_id: int):
        return self.execute(
            """
            SELECT b.id, b.master_id, b.slot_id, s.slot_at, b.reminder_job_id, b.review_job_id
            FROM bookings b
            JOIN slots s ON s.id = b.slot_id
            WHERE b.user_id = ? AND b.status = 'active'
            ORDER BY b.id DESC LIMIT 1
            """,
            (user_id,),
        ).fetchone()

    def cancel_booking(self, user_id: int):
        row = self.get_user_active_booking(user_id)
        if not row:
            return None
        with self.tx():
            self.execute("UPDATE slots SET booked_by = NULL WHERE id = ?", (row["slot_id"],))
            self.execute(
                "UPDATE bookings SET status='cancelled', cancelled_at=datetime('now') WHERE id = ?",
                (row["id"],),
            )
        return row

    def cancel_booking_by_id(self, user_id: int, booking_id: int):
        row = self.execute(
            """
            SELECT b.id, b.master_id, b.slot_id, b.reminder_job_id, b.review_job_id
            FROM bookings b
            WHERE b.id = ? AND b.user_id = ? AND b.status = 'active'
            """,
            (booking_id, user_id),
        ).fetchone()
        if not row:
            return None
        with self.tx():
            self.execute("UPDATE slots SET booked_by = NULL WHERE id = ?", (row["slot_id"],))
            self.execute("UPDATE bookings SET status='cancelled', cancelled_at=datetime('now') WHERE id = ?", (row["id"],))
        return row

    def list_user_active_bookings(self, user_id: int):
        return self.execute(
            """
            SELECT b.id, b.master_id,
                   CASE WHEN s.slot_end IS NOT NULL
                        THEN s.slot_at || ' - ' || strftime('%H:%M', s.slot_end)
                        ELSE s.slot_at
                   END AS slot_at
            FROM bookings b
            JOIN slots s ON s.id = b.slot_id
            WHERE b.user_id = ? AND b.status = 'active'
            ORDER BY s.slot_at
            """,
            (user_id,),
        ).fetchall()

    def get_slot_by_id(self, slot_id: int):
        return self.execute(
            """
            SELECT id, master_id, slot_at,
                   CASE WHEN slot_end IS NOT NULL
                        THEN strftime('%H:%M', slot_at) || '-' || strftime('%H:%M', slot_end)
                        ELSE strftime('%H:%M', slot_at)
                   END as label
            FROM slots
            WHERE id = ?
            """,
            (slot_id,),
        ).fetchone()

    def set_booking_jobs(self, booking_id: int, reminder_job_id: str | None, review_job_id: str | None):
        with self.tx():
            self.execute(
                "UPDATE bookings SET reminder_job_id = ?, review_job_id = ? WHERE id = ?",
                (reminder_job_id, review_job_id, booking_id),
            )

    def get_active_bookings_for_restore(self) -> list[ActiveBooking]:
        rows = self.execute(
            """
            SELECT b.id, b.user_id, b.master_id, s.slot_at, b.reminder_job_id, b.review_job_id
            FROM bookings b
            JOIN slots s ON s.id = b.slot_id
            WHERE b.status='active'
            """
        ).fetchall()
        return [
            ActiveBooking(
                booking_id=r["id"],
                user_id=r["user_id"],
                master_id=r["master_id"],
                slot_at=r["slot_at"],
                reminder_job_id=r["reminder_job_id"],
                review_job_id=r["review_job_id"],
            )
            for r in rows
        ]

    def save_review(self, booking_id: int, master_id: int, user_id: int, rating: int):
        with self.tx():
            self.execute(
                "INSERT OR REPLACE INTO reviews (booking_id, master_id, user_id, rating) VALUES (?, ?, ?, ?)",
                (booking_id, master_id, user_id, rating),
            )

    def get_master_stats(self, master_id: int) -> dict:
        total = self.execute("SELECT COUNT(*) as c FROM bookings WHERE master_id = ?", (master_id,)).fetchone()["c"]
        active = self.execute(
            "SELECT COUNT(*) as c FROM bookings WHERE master_id = ? AND status='active'",
            (master_id,),
        ).fetchone()["c"]
        avg = self.execute("SELECT AVG(rating) as r FROM reviews WHERE master_id = ?", (master_id,)).fetchone()["r"]
        return {"total": total, "active": active, "rating": round(avg, 1) if avg else "Нет оценок"}

    def list_users(self, limit: int = 20, offset: int = 0):
        return self.execute(
            "SELECT id, username, first_name, started_at, last_seen FROM users ORDER BY last_seen DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()

    def list_masters(self):
        return self.execute(
            "SELECT user_id, subscription_until FROM masters ORDER BY user_id DESC"
        ).fetchall()

    def list_bookings(self, limit: int = 20, offset: int = 0):
        return self.execute(
            """
            SELECT id, master_id, user_id, client_name, client_phone, status, created_at
            FROM bookings ORDER BY id DESC LIMIT ? OFFSET ?
            """,
            (limit, offset),
        ).fetchall()

    def get_all_user_ids(self) -> list[int]:
        return [row["id"] for row in self.execute("SELECT id FROM users").fetchall()]

    def count_users(self) -> int:
        return self.execute("SELECT COUNT(*) as c FROM users").fetchone()["c"]

    def count_bookings(self) -> int:
        return self.execute("SELECT COUNT(*) as c FROM bookings").fetchone()["c"]

    def list_all_users(self):
        return self.execute(
            "SELECT id, username, first_name, role, started_at, last_seen FROM users ORDER BY id"
        ).fetchall()

    def list_all_masters(self):
        return self.execute(
            "SELECT user_id, registration_date, subscription_until FROM masters ORDER BY user_id"
        ).fetchall()

    def list_all_bookings(self):
        return self.execute(
            """
            SELECT id, master_id, user_id, client_name, client_phone, status, created_at, cancelled_at
            FROM bookings ORDER BY id
            """
        ).fetchall()

    def list_master_clients(self, master_id: int, limit: int = 50):
        return self.execute(
            """
            SELECT b.user_id, MAX(s.slot_at) as last_visit, COUNT(*) as visits,
                   COALESCE(u.first_name, u.username, CAST(u.id AS TEXT)) as display
            FROM bookings b
            JOIN slots s ON s.id = b.slot_id
            LEFT JOIN users u ON u.id = b.user_id
            WHERE b.master_id = ?
            GROUP BY b.user_id
            ORDER BY last_visit DESC
            LIMIT ?
            """,
            (master_id, limit),
        ).fetchall()

    def get_client_card(self, master_id: int, user_id: int):
        stats = self.execute(
            """
            SELECT COUNT(*) as visits,
                   SUM(CASE WHEN status='active' THEN 1 ELSE 0 END) as active_bookings
            FROM bookings
            WHERE master_id = ? AND user_id = ?
            """,
            (master_id, user_id),
        ).fetchone()
        profile = self.execute(
            "SELECT id, username, first_name FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
        note_row = self.execute(
            "SELECT note, updated_at FROM client_notes WHERE master_id = ? AND user_id = ?",
            (master_id, user_id),
        ).fetchone()
        return {
            "profile": profile,
            "visits": stats["visits"] if stats else 0,
            "active_bookings": stats["active_bookings"] if stats else 0,
            "note": note_row["note"] if note_row else "",
            "note_updated_at": note_row["updated_at"] if note_row else None,
        }

    def set_client_note(self, master_id: int, user_id: int, note: str):
        with self.tx():
            self.execute(
                """
                INSERT INTO client_notes(master_id, user_id, note, updated_at)
                VALUES (?, ?, ?, datetime('now'))
                ON CONFLICT(master_id, user_id) DO UPDATE SET
                  note=excluded.note,
                  updated_at=datetime('now')
                """,
                (master_id, user_id, note),
            )

    def apply_referral_bonus(self, referrer_master_id: int, referred_master_id: int, bonus_points: int = 100) -> bool:
        if referrer_master_id == referred_master_id:
            return False
        self.register_master(referrer_master_id)
        self.register_master(referred_master_id)
        exists = self.execute(
            "SELECT id FROM referrals WHERE referred_master_id = ?",
            (referred_master_id,),
        ).fetchone()
        if exists:
            return False
        with self.tx():
            self.execute(
                """
                INSERT INTO referrals(referrer_master_id, referred_master_id, bonus_days)
                VALUES (?, ?, ?)
                """,
                (referrer_master_id, referred_master_id, 0),
            )
            self.execute(
                "UPDATE masters SET referral_bonus_points = referral_bonus_points + ? WHERE user_id = ?",
                (bonus_points, referrer_master_id),
            )
        return True

    def get_referral_stats(self, master_id: int) -> dict:
        row = self.execute(
            "SELECT COUNT(*) AS cnt FROM referrals WHERE referrer_master_id = ?",
            (master_id,),
        ).fetchone()
        points_row = self.execute(
            "SELECT referral_bonus_points FROM masters WHERE user_id = ?",
            (master_id,),
        ).fetchone()
        return {"count": row["cnt"], "bonus_points": (points_row["referral_bonus_points"] if points_row else 0)}

    def get_master_profile_stats(self, master_id: int) -> dict:
        main = self.get_master_stats(master_id)
        ref = self.get_referral_stats(master_id)
        return {
            "total_clients": main["total"],
            "active_bookings": main["active"],
            "rating": main["rating"],
            "referrals": ref["count"],
            "referral_bonus_points": ref["bonus_points"],
        }

    def create_feedback(self, user_id: int, user_role: str, feedback_type: str, text: str):
        with self.tx():
            self.execute(
                """
                INSERT INTO feedback_messages(user_id, user_role, feedback_type, text, status)
                VALUES (?, ?, ?, ?, 'new')
                """,
                (user_id, user_role, feedback_type, text.strip()),
            )

    def list_feedback(
        self,
        limit: int = 50,
        offset: int = 0,
        feedback_type: str = "all",
        only_new: bool = False,
    ):
        where = []
        args: list = []
        if feedback_type in ("bug", "suggestion"):
            where.append("feedback_type = ?")
            args.append(feedback_type)
        if only_new:
            where.append("status = 'new'")
        where_sql = ("WHERE " + " AND ".join(where)) if where else ""
        args.extend([limit, offset])
        return self.execute(
            f"""
            SELECT id, user_id, user_role, feedback_type, text, status, created_at
            FROM feedback_messages
            {where_sql}
            ORDER BY id DESC
            LIMIT ? OFFSET ?
            """,
            tuple(args),
        ).fetchall()

    def count_feedback(self, feedback_type: str = "all", only_new: bool = False) -> int:
        where = []
        args: list = []
        if feedback_type in ("bug", "suggestion"):
            where.append("feedback_type = ?")
            args.append(feedback_type)
        if only_new:
            where.append("status = 'new'")
        where_sql = ("WHERE " + " AND ".join(where)) if where else ""
        return self.execute(
            f"SELECT COUNT(*) AS c FROM feedback_messages {where_sql}",
            tuple(args),
        ).fetchone()["c"]

    def mark_feedback_read(self, feedback_id: int) -> None:
        with self.tx():
            self.execute(
                "UPDATE feedback_messages SET status = 'read' WHERE id = ?",
                (feedback_id,),
            )

    def add_master_bonus_points(self, master_id: int, points: int) -> int:
        self.register_master(master_id)
        with self.tx():
            self.execute(
                "UPDATE masters SET referral_bonus_points = referral_bonus_points + ? WHERE user_id = ?",
                (points, master_id),
            )
        row = self.execute("SELECT referral_bonus_points FROM masters WHERE user_id = ?", (master_id,)).fetchone()
        return row["referral_bonus_points"]

    def spend_master_bonus_points(self, master_id: int, points: int) -> bool:
        self.register_master(master_id)
        with self.tx():
            row = self.execute("SELECT referral_bonus_points FROM masters WHERE user_id = ?", (master_id,)).fetchone()
            current = row["referral_bonus_points"] if row else 0
            if current < points:
                return False
            self.execute(
                "UPDATE masters SET referral_bonus_points = referral_bonus_points - ? WHERE user_id = ?",
                (points, master_id),
            )
        return True


def prepare_fresh_database(db_path: Path) -> None:
    db_exists = db_path.exists()
    if db_exists:
        conn = sqlite3.connect(str(db_path))
        has_v1 = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='system_settings'"
        ).fetchone()
        conn.close()
        if not has_v1:
            BACKUP_DIR.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = BACKUP_DIR / f"database_pre_v1_{stamp}.db"
            shutil.copy2(db_path, backup_file)
            db_path.unlink()


prepare_fresh_database(DB_PATH)
db = Repository(DB_PATH)
db.init_schema()
