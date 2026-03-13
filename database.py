import aiosqlite
from datetime import datetime, timedelta

class Database:
    def __init__(self, db_path="beauty_bot.db"):
        self.db_path = db_path

    # ========================================================================
    # БЛОК 1: ИНИЦИАЛИЗАЦИЯ (СОЗДАНИЕ ТАБЛИЦ)
    # ========================================================================
    async def create_tables(self):
        """Создает таблицы в базе данных при первом запуске"""
        async with aiosqlite.connect(self.db_path) as db:
            # ТАБЛИЦА ПОЛЬЗОВАТЕЛЕЙ (Добавили, чтобы рассылка работала)
            await db.execute('''CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY
            )''')

            # Таблица слотов (записей на время)
            await db.execute('''CREATE TABLE IF NOT EXISTS slots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT,                      -- Дата (напр. 15.01)
                time TEXT,                      -- Время (напр. 10:00)
                is_booked INTEGER DEFAULT 0,    -- 1 если занято, 0 если свободно
                user_id INTEGER DEFAULT NULL,   -- Телеграм ID клиента
                user_name TEXT DEFAULT NULL,    -- Имя клиента
                user_phone TEXT DEFAULT NULL,   -- Телефон клиента
                locked_until DATETIME DEFAULT NULL -- Время, до которого слот забронирован (2 мин)
            )''')
            
            # Таблица настроек (здесь храним Услуги, Портфолио, Пароль)
            await db.execute('''CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,           -- Название настройки (напр. 'main_services')
                value TEXT                      -- Текст или ссылка
            )''')
            
            await db.commit()

    # ========================================================================
    # БЛОК 2: ФУНКЦИИ ДЛЯ МАСТЕРА (АДМИН-ПАНЕЛЬ)
    # ========================================================================
    
    # Первичная настройка и проверка пароля 

    async def get_admin_password(self):
        """Проверяет, установлен ли пароль в базе"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT value FROM settings WHERE key = 'admin_password'")
            row = await cursor.fetchone()
            return row[0] if row else None

    async def set_admin_password(self, password):
        """Сохраняет пароль при первом запуске"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('admin_password', ?)", (password,))
            await db.commit()
    
    # Функции управления слотами и услугами
    
    async def add_slot(self, date, time):
        """Добавляет новое рабочее окно в базу"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("INSERT INTO slots (date, time) VALUES (?, ?)", (date, time))
            await db.commit()

    async def delete_slot(self, slot_id):
        """Удаляет конкретный слот из базы"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM slots WHERE id = ?", (slot_id,))
            await db.commit()

    async def get_admin_schedule(self, date):
        """Возвращает список всех КЛИЕНТОВ, записанных на выбранную дату"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row 
            cursor = await db.execute(
                "SELECT * FROM slots WHERE date = ? AND is_booked = 1", (date,)
            )
            return await cursor.fetchall()

    async def update_service_block(self, key, text):
        """Сохраняет блоки текста: Основные услуги, Доп. услуги или Гарантию"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, text))
            await db.commit()

    async def set_portfolio(self, link):
        """Сохраняет ссылку на портфолио"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('portfolio', ?)", (link,))
            await db.commit()

    # Функции для рассылки

    async def add_user(self, user_id):
        """Сохраняет пользователя в базу (для рассылки)"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
            await db.commit()

    async def get_all_users(self):
        """Получает ID всех пользователей для рассылки"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT user_id FROM users")
            rows = await cursor.fetchall()
            return [r[0] for r in rows]

    # ========================================================================
    # БЛОК 3: ФУНКЦИИ ДЛЯ КЛИЕНТА (ЗАПИСЬ И ПРОСМОТР)
    # ========================================================================

    async def get_service_blocks(self):
        """Загружает все блоки услуг для пользователя"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT key, value FROM settings WHERE key IN ('main_services', 'add_services', 'warranty')"
            )
            rows = await cursor.fetchall()
            return {row[0]: row[1] for row in rows}

    async def get_portfolio(self):
        """Получает ссылку на портфолио"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT value FROM settings WHERE key = 'portfolio'")
            row = await cursor.fetchone()
            return row[0] if row else None

    async def get_available_dates(self):
        """Ищет даты, где есть свободное время"""
        async with aiosqlite.connect(self.db_path) as db:
            now = datetime.now()
            cursor = await db.execute("""
                SELECT DISTINCT date FROM slots 
                WHERE is_booked = 0 
                AND (locked_until IS NULL OR locked_until < ?)
            """, (now,))
            rows = await cursor.fetchall()
            return [r[0] for r in rows]

    async def get_slots_by_date(self, date):
        """Получает список свободного времени на дату"""
        async with aiosqlite.connect(self.db_path) as db:
            now = datetime.now()
            cursor = await db.execute("""
                SELECT id, time FROM slots 
                WHERE date = ? AND is_booked = 0 
                AND (locked_until IS NULL OR locked_until < ?)
            """, (date, now))
            return await cursor.fetchall()

    async def lock_slot(self, slot_id):
        """Бронирует слот на 2 минуты"""
        async with aiosqlite.connect(self.db_path) as db:
            lock_time = datetime.now() + timedelta(minutes=2)
            await db.execute("UPDATE slots SET locked_until = ? WHERE id = ?", (lock_time, slot_id))
            await db.commit()

    async def book_slot(self, slot_id, user_id, name, phone):
        """Финальное бронирование клиента"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                UPDATE slots 
                SET is_booked = 1, user_id = ?, user_name = ?, user_phone = ?, locked_until = NULL 
                WHERE id = ?
            """, (user_id, name, phone, slot_id))
            await db.commit()

    async def user_has_booking(self, user_id):
        """Проверяет наличие активной записи"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT id FROM slots WHERE user_id = ? AND is_booked = 1", (user_id,))
            res = await cursor.fetchone()
            return res is not None

    async def get_user_booking(self, user_id):
        """Данные о записи для кнопки 'Моя запись'"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM slots WHERE user_id = ? AND is_booked = 1", (user_id,))
            return await cursor.fetchone()

    async def cancel_booking(self, user_id):
        """Отмена записи"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                UPDATE slots 
                SET is_booked = 0, user_id = NULL, user_name = NULL, user_phone = NULL 
                WHERE user_id = ?
            """, (user_id,))
            await db.commit()

    # ========================================================================
    # БЛОК 4: ТЕХНИЧЕСКИЕ ФУНКЦИИ (ОЧИСТКА)
    # ========================================================================

    async def cleanup_expired_locks(self):
        """Сбрасывает просроченную бронь (2 мин)"""
        async with aiosqlite.connect(self.db_path) as db:
            now = datetime.now()
            await db.execute("UPDATE slots SET locked_until = NULL WHERE is_booked = 0 AND locked_until < ?", (now,))
            await db.commit()

# Создание объекта базы
db = Database()