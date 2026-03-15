import sqlite3
from datetime import datetime

class Database:
    
    def __init__(self, db_file):
        self.conn = sqlite3.connect(db_file)
        self.cur = self.conn.cursor()
        self.create_tables()

    def create_tables(self):
        # Слоты времени
        self.cur.execute("""CREATE TABLE IF NOT EXISTS slots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            time TEXT,
            is_booked INTEGER DEFAULT 0,
            user_id INTEGER DEFAULT NULL
        )""")
        # Записи
        self.cur.execute("""CREATE TABLE IF NOT EXISTS bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            slot_id INTEGER,
            name TEXT,
            phone TEXT,
            date_time TEXT,
            job_id TEXT
        )""")
        self.conn.commit()
    
    def get_slots_count_by_month(self, year_month):
        # Возвращает словарь {дата: количество_свободных_слотов}
        query = "SELECT date, COUNT(id) FROM slots WHERE date LIKE ? AND is_booked = 0 GROUP BY date"
        self.cur.execute(query, (f"{year_month}%",))
        return dict(self.cur.fetchall())
    
    # Методы для админа

    def get_all_slots_for_admin(self, date):
        # Показывает все слоты (и занятые, и свободные) для админа
        return self.cur.execute("SELECT id, time, is_booked FROM slots WHERE date = ?", (date,)).fetchall()
    def add_slot(self, date, time):
        self.cur.execute("INSERT INTO slots (date, time) VALUES (?, ?)", (date, time))
        self.conn.commit()

    def delete_slot(self, slot_id):
        self.cur.execute("DELETE FROM slots WHERE id = ?", (slot_id,))
        self.conn.commit()

    def get_admin_slots(self, date):
        return self.cur.execute("SELECT id, time, is_booked FROM slots WHERE date = ?", (date,)).fetchall()

    def close_day(self, date):
        self.cur.execute("DELETE FROM slots WHERE date = ?", (date,))
        self.conn.commit()

    # Методы для пользователя
    def get_available_dates(self):
        return self.cur.execute("SELECT DISTINCT date FROM slots WHERE is_booked = 0").fetchall()

    def get_available_slots(self, date):
        return self.cur.execute("SELECT id, time FROM slots WHERE date = ? AND is_booked = 0", (date,)).fetchall()

    def has_booking(self, user_id):
        return self.cur.execute("SELECT id FROM bookings WHERE user_id = ?", (user_id,)).fetchone()

    def create_booking(self, user_id, slot_id, name, phone, date_time, job_id):
        self.cur.execute("UPDATE slots SET is_booked = 1, user_id = ? WHERE id = ?", (user_id, slot_id))
        self.cur.execute("INSERT INTO bookings (user_id, slot_id, name, phone, date_time, job_id) VALUES (?,?,?,?,?,?)",
                         (user_id, slot_id, name, phone, date_time, job_id))
        self.conn.commit()

    def get_user_booking(self, user_id):
        return self.cur.execute("""
            SELECT b.id, b.slot_id, b.date_time, b.job_id, s.date, s.time 
            FROM bookings b 
            JOIN slots s ON b.slot_id = s.id 
            WHERE b.user_id = ?""", (user_id,)).fetchone()

    def cancel_booking(self, user_id):
        booking = self.get_user_booking(user_id)
        if booking:
            self.cur.execute("UPDATE slots SET is_booked = 0, user_id = NULL WHERE id = ?", (booking[1],))
            self.cur.execute("DELETE FROM bookings WHERE user_id = ?", (user_id,))
            self.conn.commit()
            return booking[3] # Вернуть job_id для удаления задачи
        return None

    def get_all_active_bookings(self):
        return self.cur.execute("SELECT user_id, date_time, job_id FROM bookings").fetchall()
    # Добавьте/обновите эти методы в класс Database
    

db = Database("database.db")