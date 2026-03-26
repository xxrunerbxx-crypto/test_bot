import sqlite3
import logging
from datetime import datetime, timedelta

class Database:
    def __init__(self, db_file):
        self.conn = sqlite3.connect(db_file, check_same_thread=False)
        self.cur = self.conn.cursor()
        self.create_tables()

    def create_tables(self):
        # Таблица слотов
        self.cur.execute("""CREATE TABLE IF NOT EXISTS slots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            owner_id INTEGER,
            date TEXT,
            time TEXT,
            is_booked INTEGER DEFAULT 0,
            user_id INTEGER DEFAULT NULL
        )""")
        
        # Таблица записей
        self.cur.execute("""CREATE TABLE IF NOT EXISTS bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            master_id INTEGER,
            user_id INTEGER,
            slot_id INTEGER,
            name TEXT,
            phone TEXT,
            date_time TEXT,
            job_id TEXT
        )""")
        
        # Таблица услуг и настроек мастера
        self.cur.execute("""CREATE TABLE IF NOT EXISTS services (
            owner_id INTEGER PRIMARY KEY,
            main_services TEXT DEFAULT 'Не заполнено',
            additional_services TEXT DEFAULT 'Не заполнено',
            warranty TEXT DEFAULT 'Не заполнено',
            portfolio_link TEXT DEFAULT 'https://t.me/telegram',
            photo_id TEXT DEFAULT NULL
        )""")

        # Таблица отзывов
        self.cur.execute("""CREATE TABLE IF NOT EXISTS reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            master_id INTEGER,
            user_id INTEGER,
            rating INTEGER,
            date TEXT
        )""")

        # НОВАЯ ТАБЛИЦА: Информация о подписке мастеров
        self.cur.execute("""CREATE TABLE IF NOT EXISTS masters_info (
            master_id INTEGER PRIMARY KEY,
            registration_date TEXT,
            subscription_until TEXT
        )""")

        # Пользователи, которые начали пользоваться ботом (/start)
        self.cur.execute("""CREATE TABLE IF NOT EXISTS tg_users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            started_at TEXT,
            last_seen TEXT
        )""")

        # Режим техработ (1 строка конфигурации)
        self.cur.execute("""CREATE TABLE IF NOT EXISTS maintenance (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            enabled INTEGER DEFAULT 0,
            message TEXT DEFAULT 'Сервис временно недоступен',
            updated_at TEXT DEFAULT (datetime('now','localtime'))
        )""")

        # Гарантируем, что строка конфигурации всегда существует
        self.cur.execute(
            "INSERT OR IGNORE INTO maintenance (id, enabled, message, updated_at) VALUES (1, 0, 'Сервис временно недоступен', datetime('now','localtime'))"
        )

        self.cur.execute("CREATE INDEX IF NOT EXISTS idx_slots_owner ON slots(owner_id)")
        self.cur.execute("CREATE INDEX IF NOT EXISTS idx_slots_date ON slots(date)")
        self.cur.execute("CREATE INDEX IF NOT EXISTS idx_reviews_master ON reviews(master_id)")
        self.cur.execute("CREATE INDEX IF NOT EXISTS idx_tg_users_last_seen ON tg_users(last_seen)")
        self.conn.commit()

    # --- ЛОГИКА ПОДПИСКИ И ДОСТУПА ---

    def register_master(self, master_id):
        """Регистрирует мастера и выдает 7 дней пробного периода"""
        self.cur.execute("SELECT master_id FROM masters_info WHERE master_id = ?", (master_id,))
        if not self.cur.fetchone():
            now = datetime.now()
            reg_date = now.strftime("%Y-%m-%d")
            # Сразу при регистрации даем +7 дней
            trial_end = (now + timedelta(days=7)).strftime("%Y-%m-%d")
            self.cur.execute("INSERT INTO masters_info (master_id, registration_date, subscription_until) VALUES (?, ?, ?)", 
                             (master_id, reg_date, trial_end))
            self.conn.commit()

    def set_subscription(self, master_id, days):
        """Продлевает подписку на N дней (используется для ручной активации и оплаты)"""
        self.register_master(master_id) # На случай, если мастера еще нет в базе подписок
        
        self.cur.execute("SELECT subscription_until FROM masters_info WHERE master_id = ?", (master_id,))
        res = self.cur.fetchone()
        
        current_until = datetime.strptime(res[0], "%Y-%m-%d")
        # Если старая подписка еще действует, прибавляем к ней. Если уже истекла — прибавляем к "сегодня"
        start_date = current_until if current_until > datetime.now() else datetime.now()
        new_until = (start_date + timedelta(days=days)).strftime("%Y-%m-%d")
        
        self.cur.execute("UPDATE masters_info SET subscription_until = ? WHERE master_id = ?", (new_until, master_id))
        self.conn.commit()
        return new_until

    def check_master_access(self, master_id):
        """Проверяет, есть ли у мастера доступ и сколько дней осталось"""
        self.register_master(master_id) # Авто-регистрация при проверке
        
        self.cur.execute("SELECT subscription_until FROM masters_info WHERE master_id = ?", (master_id,))
        res = self.cur.fetchone()
        
        until_date = datetime.strptime(res[0], "%Y-%m-%d")
        days_left = (until_date - datetime.now()).days
        
        if days_left >= 0:
            return True, str(days_left + 1) # Доступ есть
        return False, "0" # Доступ истек

    # --- ТЕХРАБОТЫ И ПОЛЬЗОВАТЕЛИ (админ-аналитика) ---

    def upsert_user_on_start(self, user_id: int, username: str | None, first_name: str | None):
        """
        Запоминаем пользователей, которые начали пользоваться ботом (/start).
        used for: админ-панель, рассылки.
        """
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Если пользователь новый — фиксируем started_at.
        self.cur.execute(
            """
            INSERT OR IGNORE INTO tg_users (user_id, username, first_name, started_at, last_seen)
            VALUES (?, ?, ?, ?, ?)
            """,
            (user_id, username, first_name, now, now),
        )

        # Обновляем актуальные данные и last_seen.
        self.cur.execute(
            """
            UPDATE tg_users
            SET username = ?, first_name = ?, last_seen = ?
            WHERE user_id = ?
            """,
            (username, first_name, now, user_id),
        )
        self.conn.commit()

    def get_all_user_ids(self) -> list[int]:
        return [row[0] for row in self.cur.execute("SELECT user_id FROM tg_users").fetchall()]

    def count_users(self) -> int:
        return self.cur.execute("SELECT COUNT(*) FROM tg_users").fetchone()[0]

    def list_users(self, limit: int = 20, offset: int = 0):
        return self.cur.execute(
            """
            SELECT user_id, username, first_name, started_at, last_seen
            FROM tg_users
            ORDER BY last_seen DESC
            LIMIT ? OFFSET ?
            """,
            (limit, offset),
        ).fetchall()

    def list_masters(self):
        return self.cur.execute(
            """
            SELECT master_id, subscription_until
            FROM masters_info
            ORDER BY master_id DESC
            """
        ).fetchall()

    def count_bookings(self) -> int:
        return self.cur.execute("SELECT COUNT(*) FROM bookings").fetchone()[0]

    def list_bookings(self, limit: int = 20, offset: int = 0):
        return self.cur.execute(
            """
            SELECT id, master_id, user_id, name, phone, date_time, job_id
            FROM bookings
            ORDER BY date_time DESC
            LIMIT ? OFFSET ?
            """,
            (limit, offset),
        ).fetchall()

    def set_maintenance(self, enabled: bool, message: str | None = None):
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if message is None:
            self.cur.execute("UPDATE maintenance SET enabled = ?, updated_at = ? WHERE id = 1", (int(enabled), now))
        else:
            self.cur.execute(
                "UPDATE maintenance SET enabled = ?, message = ?, updated_at = ? WHERE id = 1",
                (int(enabled), message, now),
            )
        self.conn.commit()

    def get_maintenance(self) -> dict:
        res = self.cur.execute("SELECT enabled, message, updated_at FROM maintenance WHERE id = 1").fetchone()
        if not res:
            return {"enabled": 0, "message": "Сервис временно недоступен", "updated_at": None}
        enabled, message, updated_at = res
        return {"enabled": enabled, "message": message, "updated_at": updated_at}

    # --- МЕТОДЫ АНАЛИТИКИ ---

    def get_master_stats(self, master_id):
        total = self.cur.execute("SELECT COUNT(*) FROM bookings WHERE master_id = ?", (master_id,)).fetchone()[0]
        active = self.cur.execute("SELECT COUNT(*) FROM slots WHERE owner_id = ? AND is_booked = 1", (master_id,)).fetchone()[0]
        avg_rating = self.cur.execute("SELECT AVG(rating) FROM reviews WHERE master_id = ?", (master_id,)).fetchone()[0]
        return {
            "total": total,
            "active": active,
            "rating": round(avg_rating, 1) if avg_rating else "Нет оценок"
        }

    # --- РАБОТА С ОТЗЫВАМИ ---

    def save_review(self, master_id, user_id, rating):
        date_now = datetime.now().strftime("%Y-%m-%d")
        self.cur.execute("INSERT INTO reviews (master_id, user_id, rating, date) VALUES (?, ?, ?, ?)",
                         (master_id, user_id, rating, date_now))
        self.conn.commit()

    # --- МЕТОДЫ ДЛЯ УСЛУГ ---
    
    def get_services(self, owner_id):
        self.cur.execute("SELECT main_services, additional_services, warranty, photo_id FROM services WHERE owner_id = ?", (owner_id,))
        return self.cur.fetchone()

    def get_portfolio_link(self, owner_id):
        self.cur.execute("SELECT portfolio_link FROM services WHERE owner_id = ?", (owner_id,))
        res = self.cur.fetchone()
        return res[0] if res else "https://t.me/telegram"

    def update_services(self, owner_id, column, text):
        self.cur.execute(f"INSERT OR IGNORE INTO services (owner_id) VALUES (?)", (owner_id,))
        self.cur.execute(f"UPDATE services SET {column} = ? WHERE owner_id = ?", (text, owner_id))
        self.conn.commit()

    def update_portfolio(self, owner_id, link):
        self.cur.execute(f"INSERT OR IGNORE INTO services (owner_id) VALUES (?)", (owner_id,))
        self.cur.execute("UPDATE services SET portfolio_link = ? WHERE owner_id = ?", (link, owner_id))
        self.conn.commit()

    # --- МЕТОДЫ ДЛЯ СЛОТОВ ---
    def add_slot(self, owner_id, date, time):
        self.cur.execute("SELECT id FROM slots WHERE owner_id = ? AND date = ? AND time = ?", (owner_id, date, time))
        if not self.cur.fetchone():
            self.cur.execute("INSERT INTO slots (owner_id, date, time) VALUES (?, ?, ?)", (owner_id, date, time))
            self.conn.commit()

    def get_admin_slots(self, owner_id, date):
        return self.cur.execute("SELECT id, time, is_booked FROM slots WHERE owner_id = ? AND date = ? ORDER BY time", (owner_id, date)).fetchall()

    def delete_all_slots_on_date(self, owner_id, date):
        self.cur.execute("DELETE FROM slots WHERE owner_id = ? AND date = ? AND is_booked = 0", (owner_id, date))
        self.conn.commit()

    def get_slots_count_by_month(self, owner_id, year_month):
        query = "SELECT date, COUNT(id) FROM slots WHERE owner_id = ? AND date LIKE ? AND is_booked = 0 GROUP BY date"
        self.cur.execute(query, (owner_id, f"{year_month}%"))
        return dict(self.cur.fetchall())

    def get_available_slots(self, owner_id, date):
        return self.cur.execute("SELECT id, time FROM slots WHERE owner_id = ? AND date = ? AND is_booked = 0 ORDER BY time", (owner_id, date)).fetchall()

    # --- БРОНИРОВАНИЕ ---
    def create_booking(self, master_id, user_id, slot_id, name, phone, date_time, job_id):
        """
        Атомарно бронирует слот.
        Бронь проходит только если слот ещё не занят.
        Возвращает id созданной записи в bookings.
        """
        # Важно: захватываем только свободный слот конкретного мастера.
        self.cur.execute(
            """
            UPDATE slots
            SET is_booked = 1, user_id = ?
            WHERE id = ? AND owner_id = ? AND is_booked = 0
            """,
            (user_id, slot_id, master_id),
        )

        if self.cur.rowcount != 1:
            raise ValueError("Slot already booked or invalid slot")

        self.cur.execute(
            "INSERT INTO bookings (master_id, user_id, slot_id, name, phone, date_time, job_id) VALUES (?,?,?,?,?,?,?)",
            (master_id, user_id, slot_id, name, phone, date_time, job_id),
        )
        booking_id = self.cur.lastrowid
        self.conn.commit()
        return booking_id

    def cancel_booking(self, user_id):
        booking = self.cur.execute(
            "SELECT id, slot_id, job_id, master_id FROM bookings WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        if booking:
            booking_id, slot_id, job_id, master_id = booking
            self.cur.execute("UPDATE slots SET is_booked = 0, user_id = NULL WHERE id = ?", (slot_id,))
            self.cur.execute("DELETE FROM bookings WHERE user_id = ?", (user_id,))
            self.conn.commit()

            # Отменяем reminder job по job_id (если он существовал)
            if job_id and job_id != "no_reminder":
                try:
                    from utils.scheduler import cancel_reminder_job

                    cancel_reminder_job(job_id)
                except Exception:
                    pass

            return job_id, master_id
        return None, None

    def get_all_active_bookings(self):
        return self.cur.execute("SELECT user_id, date_time, job_id FROM bookings").fetchall()

    def set_booking_job_id(self, booking_id: int, job_id: str):
        self.cur.execute("UPDATE bookings SET job_id = ? WHERE id = ?", (job_id, booking_id))
        self.conn.commit()

db = Database("database.db")