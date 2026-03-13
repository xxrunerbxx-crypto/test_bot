import aiosqlite
from datetime import datetime, timedelta

class Database:
    def __init__(self, db_path="beauty_bot.db"):
        self.db_path = db_path

    async def create_tables(self):
        async with aiosqlite.connect(self.db_path) as db:
            # Таблица пользователей (для рассылки)
            await db.execute('CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY)')
            # Таблица слотов
            await db.execute('''CREATE TABLE IF NOT EXISTS slots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT, time TEXT, is_booked INTEGER DEFAULT 0,
                user_id INTEGER, user_name TEXT, user_phone TEXT,
                locked_until DATETIME DEFAULT NULL)''')
            # Таблица настроек (пароль, услуги, портфолио)
            await db.execute('CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)')
            await db.commit()

    # --- ПАРОЛЬ ---
    async def get_admin_password(self):
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT value FROM settings WHERE key = 'admin_password'")
            row = await cursor.fetchone()
            return row[0] if row else None

    async def set_admin_password(self, password):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('admin_password', ?)", (password,))
            await db.commit()

    # --- УСЛУГИ И ПОРТФОЛИО ---
    async def update_service_block(self, key, text):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, text))
            await db.commit()

    async def get_service_blocks(self):
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT key, value FROM settings WHERE key IN ('main_services', 'add_services', 'warranty')")
            rows = await cursor.fetchall()
            return {row[0]: row[1] for row in rows}

    async def set_portfolio(self, link):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('portfolio', ?)", (link,))
            await db.commit()

    async def get_portfolio(self):
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT value FROM settings WHERE key = 'portfolio'")
            row = await cursor.fetchone()
            return row[0] if row else None

    # --- РАБОТА СО СЛОТАМИ ---
    async def add_slot(self, date, time):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("INSERT INTO slots (date, time) VALUES (?, ?)", (date, time))
            await db.commit()

    async def delete_slot(self, slot_id):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM slots WHERE id = ?", (slot_id,))
            await db.commit()

    async def get_available_dates(self):
        async with aiosqlite.connect(self.db_path) as db:
            now = datetime.now()
            cursor = await db.execute("SELECT DISTINCT date FROM slots WHERE is_booked = 0 AND (locked_until IS NULL OR locked_until < ?)", (now,))
            rows = await cursor.fetchall()
            return [r[0] for r in rows]

    async def get_slots_by_date(self, date):
        async with aiosqlite.connect(self.db_path) as db:
            now = datetime.now()
            cursor = await db.execute("SELECT id, time FROM slots WHERE date = ? AND is_booked = 0 AND (locked_until IS NULL OR locked_until < ?)", (date, now))
            return await cursor.fetchall()

    async def lock_slot(self, slot_id):
        async with aiosqlite.connect(self.db_path) as db:
            lock_time = datetime.now() + timedelta(minutes=2)
            await db.execute("UPDATE slots SET locked_until = ? WHERE id = ?", (lock_time, slot_id))
            await db.commit()

    async def book_slot(self, slot_id, user_id, name, phone):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("UPDATE slots SET is_booked = 1, user_id = ?, user_name = ?, user_phone = ?, locked_until = NULL WHERE id = ?", (user_id, name, phone, slot_id))
            await db.commit()

    # --- ПОЛЬЗОВАТЕЛИ И РАСПИСАНИЕ ---
    async def add_user(self, user_id):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
            await db.commit()

    async def get_all_users(self):
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT user_id FROM users")
            rows = await cursor.fetchall()
            return [r[0] for r in rows]

    async def get_admin_schedule(self, date):
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM slots WHERE date = ? AND is_booked = 1", (date,))
            return await cursor.fetchall()

    async def user_has_booking(self, user_id):
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT id FROM slots WHERE user_id = ? AND is_booked = 1", (user_id,))
            return await cursor.fetchone() is not None

    async def get_user_booking(self, user_id):
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM slots WHERE user_id = ? AND is_booked = 1", (user_id,))
            return await cursor.fetchone()

    async def cancel_booking(self, user_id):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("UPDATE slots SET is_booked = 0, user_id = NULL, user_name = NULL, user_phone = NULL WHERE user_id = ?", (user_id,))
            await db.commit()

    async def cleanup_expired_locks(self):
        async with aiosqlite.connect(self.db_path) as db:
            now = datetime.now()
            await db.execute("UPDATE slots SET locked_until = NULL WHERE is_booked = 0 AND locked_until < ?", (now,))
            await db.commit()

db = Database()