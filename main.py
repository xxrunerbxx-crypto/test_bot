import asyncio
from aiogram import Bot, Dispatcher
from handlers import admin # Оставляем только админа, пока не создашь остальные файлы
import database as db

async def main():
    # 1. Инициализация базы данных
    await db.init_db()
    
    # 2. Твой токен
    bot = Bot(token="1193808132")
    dp = Dispatcher()
    
    # 3. Подключаем только те файлы, которые у тебя точно есть и работают
    dp.include_router(admin.router)
    
    # Очищаем очередь старых сообщений, чтобы бот не спамил при старте
    await bot.delete_webhook(drop_pending_updates=True)
    
    print("🚀 Бот запущен и готов к работе!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Бот выключен")