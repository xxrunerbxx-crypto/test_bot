import time
from database.db import db

def benchmark_db():
    start = time.time()
    # Имитируем 1000 запросов на получение слотов
    for i in range(1000):
        db.get_available_slots("2024-05-20")
    
    end = time.time()
    print(f"1000 запросов к базе выполнены за: {end - start:.4f} сек.")

if __name__ == "__main__":
    benchmark_db()