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
        
        # Таблица текстов услуг (Прайс-лист)
        self.cur.execute("""CREATE TABLE IF NOT EXISTS services (
            id INTEGER PRIMARY KEY,
            main_services TEXT,
            additional_services TEXT,
            warranty TEXT
        )""")
        
        # Создаем начальную запись для услуг, если таблица пуста
        self.cur.execute("SELECT id FROM services WHERE id = 1")
        if not self.cur.fetchone():
            self.cur.execute("""
                INSERT INTO services (id, main_services, additional_services, warranty) 
                VALUES (1, 'Не заполнено', 'Не заполнено', 'Не заполнено')
            """)
            
        self.conn.commit()

    # --- МЕТОДЫ ДЛЯ УПРАВЛЕНИЯ СЛОТАМИ (АДМИН) ---
        
    def delete_slot_by_id(self, slot_id):
        """Удалить конкретный слот по ID"""
        self.cur.execute("DELETE FROM slots WHERE id = ?", (slot_id,))
        self.conn.commit()

    def delete_all_slots_on_date(self, date):
        """Удалить ВШЕ слоты на конкретную дату (и свободные, и занятые)"""
        self.cur.execute("DELETE FROM slots WHERE date = ?", (date,))
        self.conn.commit()

    def add_slot(self, date, time):
        """Добавить один временной слот"""
        # Проверка на дубликат, чтобы не добавлять одно и то же время дважды
        self.cur.execute("SELECT id FROM slots WHERE date = ? AND time = ?", (date, time))
        if not self.cur.fetchone():
            self.cur.execute("INSERT INTO slots (date, time) VALUES (?, ?)", (date, time))
            self.conn.commit()

    def get_admin_slots(self, date):
        """Получить все слоты на дату для админа (и занятые, и свободные)"""
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
        """Подсчет свободных слотов для календаря (напр. для '2024-05')"""
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
        """Проверка, есть ли у пользователя уже активная запись"""
        return self.cur.execute("SELECT id FROM bookings WHERE user_id = ?", (user_id,)).fetchone()

    # --- МЕТОДЫ БРОНИРОВАНИЯ ---

    def create_booking(self, user_id, slot_id, name, phone, date_time, job_id):
        """Создание записи и отметка слота как занятого"""
        # Помечаем слот как занятый
        self.cur.execute("UPDATE slots SET is_booked = 1, user_id = ? WHERE id = ?", (user_id, slot_id))
        # Создаем запись в таблице бронирований
        self.cur.execute(
            "INSERT INTO bookings (user_id, slot_id, name, phone, date_time, job_id) VALUES (?,?,?,?,?,?)",
            (user_id, slot_id, name, phone, date_time, job_id)
        )
        self.conn.commit()

    def cancel_booking(self, user_id):
        """Отмена записи: освобождаем слот и удаляем бронь"""
        booking = self.cur.execute(
            "SELECT slot_id, job_id FROM bookings WHERE user_id = ?", 
            (user_id,)
        ).fetchone()
        
        if booking:
            slot_id, job_id = booking
            # Делаем слот снова свободным
            self.cur.execute("UPDATE slots SET is_booked = 0, user_id = NULL WHERE id = ?", (slot_id,))
            # Удаляем запись о бронировании
            self.cur.execute("DELETE FROM bookings WHERE user_id = ?", (user_id,))
            self.conn.commit()
            return job_id  # Возвращаем ID задачи напоминания для её удаления
        return None

    # --- МЕТОДЫ ДЛЯ УСЛУГ (ПРАЙС-ЛИСТА) ---

    def update_services(self, column, text):
        """Обновление текстов услуг (основные, доп, гарантия)"""
        # Безопасная подстановка имени колонки (т.к. это внутренний метод)
        query = f"UPDATE services SET {column} = ? WHERE id = 1"
        self.cur.execute(query, (text,))
        self.conn.commit()

    def get_services(self):
        """Получение всех текстов услуг"""
        return self.cur.execute(
            "SELECT main_services, additional_services, warranty FROM services WHERE id = 1"
        ).fetchone()

    def get_all_active_bookings(self):
        """Получение всех записей для восстановления планировщика при перезапуске бота"""
        return self.cur.execute("SELECT user_id, date_time, job_id FROM bookings").fetchall()

# Создаем экземпляр базы данных
db = Database("database.db")