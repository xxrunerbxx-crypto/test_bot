import asyncio
from aiogram import Bot, Dispatcher
from handlers import admin, common # Добавь сюда свои другие роутеры
import database as db

async def main():
    await db.init_db()
    bot = Bot(token="ТВОЙ_ТОКЕН")
    dp = Dispatcher()
    dp.include_router(admin.router)
    
    print("Бот запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())