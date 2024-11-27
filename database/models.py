import sqlite3
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime


@dataclass
class User:
    telegram_id: int
    username: Optional[str]
    first_name: Optional[str]
    last_name: Optional[str]
    balance: float = 0.0
    agreement_accepted: bool = False
    referral_balance: float = 0.0  # Добавляем поле для реферального баланса
    created_at: datetime = datetime.now()
    id: Optional[int] = None

    @property
    def display_name(self) -> str:
        if self.first_name or self.last_name:
            return f"{self.first_name or ''} {self.last_name or ''}".strip()
        return self.username or "Пользователь"

@dataclass
class Device:
    telegram_id: int  # Изменено с user_id
    device_type: str
    config_data: str
    is_active: bool = True
    created_at: datetime = datetime.now()
    expires_at: Optional[datetime] = None
    id: Optional[int] = None

@dataclass
class Transaction:
    user_id: int  # Оставляем как user_id, так как это внутреннее имя атрибута
    amount: float
    transaction_type: str
    status: str
    payment_id: Optional[str] = None
    created_at: datetime = datetime.now()
    id: Optional[int] = None


@dataclass
class Transaction:
    user_id: int
    amount: float
    transaction_type: str
    status: str
    payment_id: Optional[str] = None
    created_at: datetime = datetime.now()
    id: Optional[int] = None


@dataclass
class Plan:
    name: str
    price: float
    duration: int  # in days
    id: Optional[int] = None


DB_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    telegram_id INTEGER UNIQUE NOT NULL,
    username TEXT,
    first_name TEXT,
    last_name TEXT,
    balance REAL DEFAULT 0,
    agreement_accepted BOOLEAN DEFAULT FALSE,
    referral_balance REAL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS devices (
    id INTEGER PRIMARY KEY,
    telegram_id INTEGER,  -- Связь с пользователем
    device_type TEXT NOT NULL,
    config_data TEXT NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP,
    FOREIGN KEY (telegram_id) REFERENCES users(telegram_id)
);

CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY,
    telegram_id INTEGER,  -- Связь с пользователем
    amount REAL NOT NULL,
    transaction_type TEXT NOT NULL,
    status TEXT NOT NULL,
    payment_id TEXT, 
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (telegram_id) REFERENCES users(telegram_id)
);

CREATE TABLE IF NOT EXISTS referrals (
    id INTEGER PRIMARY KEY,
    referrer_telegram_id INTEGER NOT NULL,  -- кто пригласил
    referee_telegram_id INTEGER NOT NULL,   -- кого пригласил
    total_earnings REAL DEFAULT 0,          -- общая сумма заработка
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (referrer_telegram_id) REFERENCES users(telegram_id),
    FOREIGN KEY (referee_telegram_id) REFERENCES users(telegram_id),
    UNIQUE(referee_telegram_id)
);

CREATE INDEX IF NOT EXISTS idx_users_telegram_id ON users(telegram_id);
CREATE INDEX IF NOT EXISTS idx_devices_telegram_id ON devices(telegram_id);
CREATE INDEX IF NOT EXISTS idx_transactions_telegram_id ON transactions(telegram_id);
"""