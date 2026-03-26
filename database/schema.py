SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    username TEXT,
    first_name TEXT,
    role TEXT NOT NULL DEFAULT 'client' CHECK (role IN ('client', 'master', 'owner')),
    started_at TEXT NOT NULL,
    last_seen TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS masters (
    user_id INTEGER PRIMARY KEY,
    registration_date TEXT NOT NULL,
    subscription_until TEXT NOT NULL,
    main_services TEXT NOT NULL DEFAULT 'Не заполнено',
    additional_services TEXT NOT NULL DEFAULT 'Не заполнено',
    warranty TEXT NOT NULL DEFAULT 'Не заполнено',
    portfolio_link TEXT NOT NULL DEFAULT 'https://t.me/telegram',
    photo_id TEXT,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS slots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    master_id INTEGER NOT NULL,
    slot_at TEXT NOT NULL,
    booked_by INTEGER,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (master_id) REFERENCES masters(user_id) ON DELETE CASCADE,
    FOREIGN KEY (booked_by) REFERENCES users(id) ON DELETE SET NULL,
    UNIQUE (master_id, slot_at)
);

CREATE TABLE IF NOT EXISTS bookings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    slot_id INTEGER NOT NULL UNIQUE,
    master_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    client_name TEXT NOT NULL,
    client_phone TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'cancelled', 'visited')),
    reminder_job_id TEXT,
    review_job_id TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    cancelled_at TEXT,
    FOREIGN KEY (slot_id) REFERENCES slots(id) ON DELETE RESTRICT,
    FOREIGN KEY (master_id) REFERENCES masters(user_id) ON DELETE RESTRICT,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    booking_id INTEGER NOT NULL UNIQUE,
    master_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    rating INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (booking_id) REFERENCES bookings(id) ON DELETE CASCADE,
    FOREIGN KEY (master_id) REFERENCES masters(user_id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS system_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

INSERT OR IGNORE INTO system_settings (key, value) VALUES ('maintenance_enabled', '0');
INSERT OR IGNORE INTO system_settings (key, value) VALUES ('maintenance_message', 'Сервис временно недоступен');

CREATE INDEX IF NOT EXISTS idx_slots_master_slot_at ON slots(master_id, slot_at);
CREATE INDEX IF NOT EXISTS idx_slots_booked_by ON slots(booked_by);
CREATE INDEX IF NOT EXISTS idx_bookings_master_status ON bookings(master_id, status);
CREATE INDEX IF NOT EXISTS idx_bookings_user_status ON bookings(user_id, status);
CREATE INDEX IF NOT EXISTS idx_bookings_created_at ON bookings(created_at);
CREATE INDEX IF NOT EXISTS idx_reviews_master ON reviews(master_id);
CREATE INDEX IF NOT EXISTS idx_users_last_seen ON users(last_seen);
"""
