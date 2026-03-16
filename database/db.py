import sqlite3
import logging

class Database:
    def __init__(self, db_file):
        # check_same_thread=False позволяет работать с базой из разных потоков
        self.conn = sqlite3.connect(db_file, check_same_thread=False)
        self.cur = self.conn.cursor()
        self.create_tables()
        
        # КЭШ в оперативной памяти для мгновенного доступа
        self.cache = {
            "services": None,
            "portfolio_link": "https://t.me/telegram"
        }
        self.update_cache() # Загружаем данные в память при старте

    def create_tables(self):
        """Создание таблиц и индексов для ускорения поиска"""
        self.cur.execute("""CREATE TABLE IF NOT EXISTS slots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            time TEXT,
            is_booked INTEGER DEFAULT 0,
            user_id INTEGER DEFAULT NULL
        )""")
        
        self.cur.execute("""CREATE TABLE IF NOT EXISTS bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            slot_id INTEGER,
            name TEXT,
            phone TEXT,
            date_time TEXT,
            job_id TEXT
            
        )""")
        
        self.cur.execute("""CREATE TABLE IF NOT EXISTS services (
            id INTEGER PRIMARY KEY,
            main_services TEXT,
            additional_services TEXT,
            warranty TEXT,
            portfolio_link TEXT,
            photo_id TEXT  
        )""")

        # СОЗДАНИЕ ИНДЕКСОВ для моментального поиска по дате и пользователю
        self.cur.execute("CREATE INDEX IF NOT EXISTS idx_slots_date ON slots(date)")
        self.cur.execute("CREATE INDEX IF NOT EXISTS idx_bookings_user ON bookings(user_id)")

        self.cur.execute("SELECT id FROM services WHERE id = 1")
        if not self.cur.fetchone():
            self.cur.execute("""
                INSERT INTO services (id, main_services, additional_services, warranty, portfolio_link) 
                VALUES (1, 'Не заполнено', 'Не заполнено', 'Не заполнено', 'https://t.me/telegram')
            """)
        self.conn.commit()

    def update_cache(self):
        """Загрузка тяжелых текстов из БД в оперативную память"""
        try:
            self.cur.execute("SELECT main_services, additional_services, warranty, portfolio_link, photo_id FROM services WHERE id = 1")
            res = self.cur.fetchone()
            if res:
                self.cache["services"] = (res[0], res[1], res[2], res[4])
                self.cache["portfolio_link"] = res[3] if res[3] else "https://t.me/telegram"
        except Exception as e:
            logging.error(f"Ошибка обновления кэша: {e}")

    # --- МЕТОДЫ С ИСПОЛЬЗОВАНИЕМ КЭША (МГНОВЕННЫЕ) ---

    def get_services(self):
        return self.cache["services"]

    def get_portfolio_link(self):
        return self.cache["portfolio_link"]

    # --- МЕТОДЫ ОБНОВЛЕНИЯ (ОБНОВЛЯЮТ И БД И КЭШ) ---

    def update_services(self, column, text):
        query = f"UPDATE services SET {column} = ? WHERE id = 1"
        self.cur.execute(query, (text,))
        self.conn.commit()
        self.update_cache()

    def update_portfolio(self, link):
        self.cur.execute("UPDATE services SET portfolio_link = ? WHERE id = 1", (link,))
        self.conn.commit()
        self.update_cache()

    # --- ОСТАЛЬНЫЕ МЕТОДЫ (РАБОТАЮТ С ДИСКОМ) ---

    def add_slot(self, date, time):
        self.cur.execute("SELECT id FROM slots WHERE date = ? AND time = ?", (date, time))
        if not self.cur.fetchone():
            self.cur.execute("INSERT INTO slots (date, time) VALUES (?, ?)", (date, time))
            self.conn.commit()

    def get_admin_slots(self, date):
        return self.cur.execute("SELECT id, time, is_booked FROM slots WHERE date = ? ORDER BY time", (date,)).fetchall()

    def delete_slot_by_id(self, slot_id):
        self.cur.execute("DELETE FROM slots WHERE id = ?", (slot_id,))
        self.conn.commit()

    def delete_all_slots_on_date(self, date):
        self.cur.execute("DELETE FROM slots WHERE date = ?", (date,))
        self.conn.commit()

    def clear_day(self, date):
        self.cur.execute("DELETE FROM slots WHERE date = ? AND is_booked = 0", (date,))
        self.conn.commit()

    def get_slots_count_by_month(self, year_month):
        query = "SELECT date, COUNT(id) FROM slots WHERE date LIKE ? AND is_booked = 0 GROUP BY date"
        self.cur.execute(query, (f"{year_month}%",))
        return dict(self.cur.fetchall())

    def get_available_slots(self, date):
        return self.cur.execute("SELECT id, time FROM slots WHERE date = ? AND is_booked = 0 ORDER BY time", (date,)).fetchall()

    def has_booking(self, user_id):
        return self.cur.execute("SELECT id FROM bookings WHERE user_id = ?", (user_id,)).fetchone()

    def create_booking(self, user_id, slot_id, name, phone, date_time, job_id):
        self.cur.execute("UPDATE slots SET is_booked = 1, user_id = ? WHERE id = ?", (user_id, slot_id))
        self.cur.execute("INSERT INTO bookings (user_id, slot_id, name, phone, date_time, job_id) VALUES (?,?,?,?,?,?)",
                         (user_id, slot_id, name, phone, date_time, job_id))
        self.conn.commit()

    def cancel_booking(self, user_id):
        booking = self.cur.execute("SELECT slot_id, job_id FROM bookings WHERE user_id = ?", (user_id,)).fetchone()
        if booking:
            self.cur.execute("UPDATE slots SET is_booked = 0, user_id = NULL WHERE id = ?", (booking[0],))
            self.cur.execute("DELETE FROM bookings WHERE user_id = ?", (user_id,))
            self.conn.commit()
            return booking[1]
        return None

    def get_all_active_bookings(self):
        return self.cur.execute("SELECT user_id, date_time, job_id FROM bookings").fetchall()

db = Database("database.db")