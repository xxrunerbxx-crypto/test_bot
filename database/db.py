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

        self.cur.execute("CREATE INDEX IF NOT EXISTS idx_slots_owner ON slots(owner_id)")
        self.cur.execute("CREATE INDEX IF NOT EXISTS idx_slots_date ON slots(date)")
        self.cur.execute("CREATE INDEX IF NOT EXISTS idx_reviews_master ON reviews(master_id)")
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
        self.cur.execute("UPDATE slots SET is_booked = 1, user_id = ? WHERE id = ?", (user_id, slot_id))
        self.cur.execute("INSERT INTO bookings (master_id, user_id, slot_id, name, phone, date_time, job_id) VALUES (?,?,?,?,?,?,?)",
                         (master_id, user_id, slot_id, name, phone, date_time, job_id))
        self.conn.commit()

    def cancel_booking(self, user_id):
        booking = self.cur.execute("SELECT slot_id, job_id, master_id FROM bookings WHERE user_id = ?", (user_id,)).fetchone()
        if booking:
            self.cur.execute("UPDATE slots SET is_booked = 0, user_id = NULL WHERE id = ?", (booking[0],))
            self.cur.execute("DELETE FROM bookings WHERE user_id = ?", (user_id,))
            self.conn.commit()
            return booking[1], booking[2] 
        return None, None

    def get_all_active_bookings(self):
        return self.cur.execute("SELECT user_id, date_time, job_id FROM bookings").fetchall()

db = Database("database.db")