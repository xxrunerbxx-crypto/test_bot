import sqlite3

class Database:
    def __init__(self, db_file):
        # Соединение с базой данных
        self.conn = sqlite3.connect(db_file)
        self.cur = self.conn.cursor()
        self.create_tables()

    def create_tables(self):
        """Создание всех необходимых таблиц при запуске"""
        
        # Таблица временных слотов
        self.cur.execute("""CREATE TABLE IF NOT EXISTS slots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            time TEXT,
            is_booked INTEGER DEFAULT 0,
            user_id INTEGER DEFAULT NULL
        )""")
        
        # Таблица записей клиентов
        self.cur.execute("""CREATE TABLE IF NOT EXISTS bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            slot_id INTEGER,
            name TEXT,
            phone TEXT,
            date_time TEXT,
            job_id TEXT
        )""")
        
        # Таблица текстов услуг и портфолио
        self.cur.execute("""CREATE TABLE IF NOT EXISTS services (
            id INTEGER PRIMARY KEY,
            main_services TEXT,
            additional_services TEXT,
            warranty TEXT,
            portfolio_link TEXT
        )""")
        
        # Проверка: если таблица услуг уже была создана без колонки portfolio_link, добавляем её
        try:
            self.cur.execute("ALTER TABLE services ADD COLUMN portfolio_link TEXT")
        except sqlite3.OperationalError:
            # Если колонка уже есть, sqlite выдаст ошибку, просто игнорируем её
            pass

        # Создаем начальную запись для услуг, если таблица пуста
        self.cur.execute("SELECT id FROM services WHERE id = 1")
        if not self.cur.fetchone():
            self.cur.execute("""
                INSERT INTO services (id, main_services, additional_services, warranty, portfolio_link) 
                VALUES (1, 'Не заполнено', 'Не заполнено', 'Не заполнено', 'https://t.me/telegram')
            """)
        # Добавь это в конец метода create_tables
        self.cur.execute("CREATE INDEX IF NOT EXISTS idx_slots_date ON slots(date)")
        self.cur.execute("CREATE INDEX IF NOT EXISTS idx_bookings_user ON bookings(user_id)")
        self.conn.commit()   
        self.conn.commit()

    # --- МЕТОДЫ ДЛЯ УПРАВЛЕНИЯ СЛОТАМИ (АДМИН) ---
        
    def delete_slot_by_id(self, slot_id):
        """Удалить конкретный слот по ID"""
        self.cur.execute("DELETE FROM slots WHERE id = ?", (slot_id,))
        self.conn.commit()

    def delete_all_slots_on_date(self, date):
        """Удалить ВСЕ слоты на конкретную дату"""
        self.cur.execute("DELETE FROM slots WHERE date = ?", (date,))
        self.conn.commit()

    def add_slot(self, date, time):
        """Добавить один временной слот"""
        self.cur.execute("SELECT id FROM slots WHERE date = ? AND time = ?", (date, time))
        if not self.cur.fetchone():
            self.cur.execute("INSERT INTO slots (date, time) VALUES (?, ?)", (date, time))
            self.conn.commit()

    def get_admin_slots(self, date):
        """Получить все слоты на дату для админа"""
        return self.cur.execute(
            "SELECT id, time, is_booked FROM slots WHERE date = ? ORDER BY time", 
            (date,)
        ).fetchall()

    def clear_day(self, date):
        """Удалить все СВОБОДНЫЕ слоты на выбранную дату"""
        self.cur.execute("DELETE FROM slots WHERE date = ? AND is_booked = 0", (date,))
        self.conn.commit()

    # --- МЕТОДЫ ДЛЯ ПОЛЬЗОВАТЕЛЯ ---

    def get_slots_count_by_month(self, year_month):
        """Подсчет свободных слотов для календаря"""
        query = "SELECT date, COUNT(id) FROM slots WHERE date LIKE ? AND is_booked = 0 GROUP BY date"
        self.cur.execute(query, (f"{year_month}%",))
        return dict(self.cur.fetchall())

    def get_available_slots(self, date):
        """Получить только свободные слоты на дату"""
        return self.cur.execute(
            "SELECT id, time FROM slots WHERE date = ? AND is_booked = 0 ORDER BY time", 
            (date,)
        ).fetchall()

    def has_booking(self, user_id):
        """Проверка активной записи"""
        return self.cur.execute("SELECT id FROM bookings WHERE user_id = ?", (user_id,)).fetchone()

    # --- МЕТОДЫ БРОНИРОВАНИЯ ---

    def create_booking(self, user_id, slot_id, name, phone, date_time, job_id):
        self.cur.execute("UPDATE slots SET is_booked = 1, user_id = ? WHERE id = ?", (user_id, slot_id))
        self.cur.execute(
            "INSERT INTO bookings (user_id, slot_id, name, phone, date_time, job_id) VALUES (?,?,?,?,?,?)",
            (user_id, slot_id, name, phone, date_time, job_id)
        )
        self.conn.commit()

    def cancel_booking(self, user_id):
        booking = self.cur.execute(
            "SELECT slot_id, job_id FROM bookings WHERE user_id = ?", 
            (user_id,)
        ).fetchone()
        
        if booking:
            slot_id, job_id = booking
            self.cur.execute("UPDATE slots SET is_booked = 0, user_id = NULL WHERE id = ?", (slot_id,))
            self.cur.execute("DELETE FROM bookings WHERE user_id = ?", (user_id,))
            self.conn.commit()
            return job_id
        return None

    # --- МЕТОДЫ ДЛЯ УСЛУГ И ПОРТФОЛИО ---

    def update_services(self, column, text):
        """Обновление текстов услуг"""
        query = f"UPDATE services SET {column} = ? WHERE id = 1"
        self.cur.execute(query, (text,))
        self.conn.commit()

    def get_services(self):
        """Получение всех текстов услуг"""
        return self.cur.execute(
            "SELECT main_services, additional_services, warranty FROM services WHERE id = 1"
        ).fetchone()

    def update_portfolio(self, link):
        """Обновление ссылки на портфолио"""
        self.cur.execute("UPDATE services SET portfolio_link = ? WHERE id = 1", (link,))
        self.conn.commit()

    def get_portfolio_link(self):
        """Получение ссылки на портфолио"""
        res = self.cur.execute("SELECT portfolio_link FROM services WHERE id = 1").fetchone()
        if res and res[0]:
            return res[0]
        return "https://t.me/telegram" # Ссылка по умолчанию

    def get_all_active_bookings(self):
        return self.cur.execute("SELECT user_id, date_time, job_id FROM bookings").fetchall()

# Создаем экземпляр базы данных
db = Database("database.db")