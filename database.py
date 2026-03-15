import aiosqlite

async def init_db():
    async with aiosqlite.connect("bot_database.db") as db:
        await db.execute('''CREATE TABLE IF NOT EXISTS slots 
            (id INTEGER PRIMARY KEY, date TEXT, time TEXT, is_booked INTEGER DEFAULT 0)''')
        await db.execute('''CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY)''')
        await db.commit()

async def add_slot(date, time):
    async with aiosqlite.connect("bot_database.db") as db:
        await db.execute("INSERT INTO slots (date, time) VALUES (?, ?)", (date, time))
        await db.commit()

async def get_unique_dates():
    async with aiosqlite.connect("bot_database.db") as db:
        async with db.execute("SELECT DISTINCT date FROM slots ORDER BY date") as cursor:
            return [row[0] for row in await cursor.fetchall()]

async def get_slots_by_date(date):
    async with aiosqlite.connect("bot_database.db") as db:
        async with db.execute("SELECT id, time, is_booked FROM slots WHERE date = ?", (date,)) as cursor:
            return await cursor.fetchall()

async def delete_slot(slot_id):
    async with aiosqlite.connect("bot_database.db") as db:
        await db.execute("DELETE FROM slots WHERE id = ?", (slot_id,))
        await db.commit()