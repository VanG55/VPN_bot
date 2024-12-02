import sqlite3
import json
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from contextlib import contextmanager
import logging
from config.settings import DB_NAME
from .models import User, Device, Transaction, Plan, DB_SCHEMA
logger = logging.getLogger(__name__)

class DatabaseManager:
    def __init__(self, db_name: str = DB_NAME):
        self.db_name = db_name
        self._initialize_database()

    def _initialize_database(self) -> None:
        with self.get_connection() as conn:
            conn.executescript(DB_SCHEMA)

    @contextmanager
    def get_connection(self):
        conn = sqlite3.connect(self.db_name)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    def get_user(self, telegram_id: int) -> Optional[User]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM users WHERE telegram_id = ?",
                (telegram_id,)
            )
            row = cursor.fetchone()
            if row:
                return User(**dict(row))
        return None

    def update_user(self, user: User) -> None:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            existing_user = self.get_user(user.telegram_id)

            if existing_user:
                # Обновляем только информацию профиля, сохраняя баланс
                cursor.execute("""
                    UPDATE users 
                    SET username = ?, first_name = ?, last_name = ?
                    WHERE telegram_id = ?
                """, (user.username, user.first_name, user.last_name,
                      user.telegram_id))
            else:
                # Создаем нового пользователя с начальным балансом 50 рублей
                cursor.execute("""
                    INSERT INTO users (telegram_id, username, first_name, last_name, balance)
                    VALUES (?, ?, ?, ?, ?)
                """, (user.telegram_id, user.username, user.first_name,
                      user.last_name, 50.0))  # Устанавливаем начальный баланс 50 рублей

    def get_user_devices(self, telegram_id: int) -> List[Device]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM devices 
                WHERE telegram_id = ? AND is_active = 1
                ORDER BY created_at DESC
            """, (telegram_id,))

            return [Device(
                telegram_id=row['telegram_id'],
                device_type=row['device_type'],
                config_data=row['config_data'],
                is_active=row['is_active'],
                created_at=row['created_at'],
                expires_at=row['expires_at'],
                marzban_username=row['marzban_username'],
                id=row['id']
            ) for row in cursor.fetchall()]

    def add_device(self, device: Device) -> int:
        """Add new device."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO devices 
                (telegram_id, device_type, config_data, created_at, expires_at, marzban_username)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                device.telegram_id,
                device.device_type,
                device.config_data,
                device.created_at,
                device.expires_at,
                device.marzban_username
            ))
            return cursor.lastrowid

    def add_transaction(self, transaction: Transaction) -> int:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO transactions 
                (telegram_id, amount, transaction_type, status, payment_id)
                VALUES (?, ?, ?, ?, ?)
            """, (
                transaction.user_id,  # Здесь используем user_id из класса Transaction
                transaction.amount,
                transaction.transaction_type,
                transaction.status,
                transaction.payment_id
            ))
            return cursor.lastrowid

    def update_balance(self, telegram_id: int, amount: float) -> None:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE users 
                SET balance = balance + ? 
                WHERE telegram_id = ?
            """, (amount, telegram_id))

    def get_active_devices_count(self, telegram_id: int) -> int:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COUNT(*) as count 
                FROM devices 
                WHERE telegram_id = ? AND is_active = 1
            """, (telegram_id,))
            return cursor.fetchone()['count']

    def update_agreement_status(self, telegram_id: int, status: bool) -> None:
        """Update user's agreement acceptance status."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE users 
                SET agreement_accepted = ? 
                WHERE telegram_id = ?
            """, (status, telegram_id))

    def update_agreement_status(self, telegram_id: int, status: bool) -> None:
        """Update user's agreement acceptance status."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE users 
                SET agreement_accepted = ? 
                WHERE telegram_id = ?
            """, (status, telegram_id))

    def deactivate_user_devices(self, telegram_id: int) -> None:
        """Деактивация всех устройств пользователя."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE devices 
                SET is_active = 0 
                WHERE user_id = ? 
                AND is_active = 1
            """, (telegram_id,))

    def get_user_transactions(self, telegram_id: int) -> List[Dict]:
        """Get user's payment history."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    amount,
                    status,
                    payment_id,
                    strftime('%Y-%m-%d %H:%M:%S', created_at) as created_at
                FROM transactions
                WHERE telegram_id = ? 
                    AND transaction_type = 'top_up' 
                    AND status = 'completed'
                ORDER BY created_at DESC
                LIMIT 10
            """, (telegram_id,))
            return [dict(row) for row in cursor.fetchall()]

    def update_transaction_status(self, payment_id: str, status: str) -> None:
        """Update transaction status."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE transactions 
                SET status = ? 
                WHERE payment_id = ?
            """, (status, payment_id))

    def get_pending_transactions(self, telegram_id: int) -> List[Transaction]:
        """Get pending transactions for user."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM transactions 
                WHERE telegram_id = ? AND status = 'pending'
                ORDER BY created_at DESC
            """, (telegram_id,))

            rows = cursor.fetchall()
            transactions = []

            for row in rows:
                transaction = Transaction(
                    user_id=row['telegram_id'],  # Здесь оставляем user_id для класса Transaction
                    amount=row['amount'],
                    transaction_type=row['transaction_type'],
                    status=row['status'],
                    payment_id=row['payment_id'],
                    created_at=row['created_at'],
                    id=row['id']
                )
                transactions.append(transaction)

            return transactions

    def add_referral(self, referrer_telegram_id: int, referee_telegram_id: int) -> bool:
        """Add referral relationship."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()

                # Проверяем, что реферер существует
                cursor.execute("SELECT id FROM users WHERE telegram_id = ?", (referrer_telegram_id,))
                referrer = cursor.fetchone()

                # Проверяем, что реферал существует и у него еще нет реферера
                cursor.execute("SELECT id FROM users WHERE telegram_id = ?", (referee_telegram_id,))
                referee = cursor.fetchone()

                if not referrer or not referee:
                    return False

                # Проверяем, нет ли уже такой связи
                cursor.execute("""
                    SELECT id FROM referrals
                    WHERE referee_telegram_id = ?
                """, (referee_telegram_id,))

                if cursor.fetchone():
                    return False

                # Добавляем связь
                cursor.execute("""
                    INSERT INTO referrals (referrer_telegram_id, referee_telegram_id, total_earnings)
                    VALUES (?, ?, 0)
                """, (referrer_telegram_id, referee_telegram_id))

                return True

        except Exception as e:
            logger.error(f"Error adding referral: {e}")
            return False

    def process_referral_payment(self, payer_telegram_id: int, payment_amount: float) -> None:
        """Проверка и обработка реферального платежа."""
        try:
            logger.info(f"Processing referral payment for {payer_telegram_id}, amount: {payment_amount}")

            with self.get_connection() as conn:
                cursor = conn.cursor()

                # Проверяем, есть ли реферер у плательщика
                cursor.execute("""
                    SELECT * FROM referrals 
                    WHERE referee_telegram_id = ?
                """, (payer_telegram_id,))

                referral = cursor.fetchone()

                if referral:
                    referrer_id = referral['referrer_telegram_id']
                    bonus_amount = payment_amount * 0.15

                    # Добавляем бонус рефереру
                    cursor.execute("""
                        UPDATE users 
                        SET balance = balance + ? 
                        WHERE telegram_id = ?
                    """, (bonus_amount, referrer_id))

                    # Обновляем статистику в таблице referrals
                    cursor.execute("""
                        UPDATE referrals 
                        SET total_earnings = total_earnings + ?
                        WHERE referrer_telegram_id = ? AND referee_telegram_id = ?
                    """, (bonus_amount, referrer_id, payer_telegram_id))

                    # Создаем запись о бонусной транзакции
                    cursor.execute("""
                        INSERT INTO transactions (telegram_id, amount, transaction_type, status)
                        VALUES (?, ?, 'referral_bonus', 'completed')
                    """, (referrer_id, bonus_amount))

                    # Получаем имя реферала для уведомления
                    cursor.execute("SELECT username, first_name FROM users WHERE telegram_id = ?", (payer_telegram_id,))
                    referee = cursor.fetchone()
                    referee_name = referee['username'] or referee['first_name'] or f"ID{payer_telegram_id}"

                    # Отправляем уведомление
                    notification = (
                        f"💰 Получен реферальный бонус!\n\n"
                        f"От пользователя: {referee_name}\n"
                        f"Сумма пополнения: {payment_amount}₽\n"
                        f"Ваш бонус (15%): {bonus_amount}₽"
                    )

                    if hasattr(self, 'bot'):
                        self.bot.send_message(referrer_id, notification, parse_mode='Markdown')

                    logger.info(f"Referral bonus of {bonus_amount} sent to {referrer_id}")

        except Exception as e:
            logger.error(f"Error processing referral payment: {e}")

    def get_referral_stats(self, telegram_id: int) -> dict:
        """Get user's referral statistics."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                # Получаем количество рефералов
                cursor.execute("""
                    SELECT COUNT(*) as count
                    FROM referrals 
                    WHERE referrer_telegram_id = ?
                """, (telegram_id,))
                count = cursor.fetchone()['count']

                # Получаем сумму заработка
                cursor.execute("""
                    SELECT COALESCE(SUM(total_earnings), 0) as earnings
                    FROM referrals
                    WHERE referrer_telegram_id = ?
                """, (telegram_id,))
                earnings = cursor.fetchone()['earnings']

                return {
                    'referrals_count': count,
                    'total_earnings': float(earnings)
                }
        except Exception as e:
            logger.error(f"Error getting referral stats: {e}")
            return {'referrals_count': 0, 'total_earnings': 0.0}

    def process_referral_bonus(self, referee_telegram_id: int, payment_amount: float) -> None:
        """Process referral bonus when referee makes a payment."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()

                # Находим реферера
                cursor.execute("""
                    SELECT referrer_telegram_id
                    FROM referrals
                    WHERE referee_telegram_id = ?
                """, (referee_telegram_id,))

                row = cursor.fetchone()
                if row:
                    referrer_telegram_id = row['referrer_telegram_id']
                    bonus_amount = payment_amount * 0.15  # 15% от платежа

                    # Обновляем сумму заработка в таблице рефералов
                    cursor.execute("""
                        UPDATE referrals 
                        SET total_earnings = total_earnings + ?
                        WHERE referrer_telegram_id = ? AND referee_telegram_id = ?
                    """, (bonus_amount, referrer_telegram_id, referee_telegram_id))

                    # Начисляем бонус на баланс реферера
                    cursor.execute("""
                        UPDATE users 
                        SET balance = balance + ?
                        WHERE telegram_id = ?
                    """, (bonus_amount, referrer_telegram_id))

                    logger.info(f"Referral bonus {bonus_amount} added to user {referrer_telegram_id}")

        except Exception as e:
            logger.error(f"Error processing referral bonus: {e}")

    def update_referral_earnings(self, referrer_telegram_id: int, amount: float) -> None:
        """Update referral earnings when referee makes a payment."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                bonus = amount * 0.15  # 15% от платежа
                cursor.execute("""
                    UPDATE referrals 
                    SET total_earnings = total_earnings + ?
                    WHERE referrer_telegram_id = ?
                """, (bonus, referrer_telegram_id))

                # Обновляем баланс реферера
                cursor.execute("""
                    UPDATE users
                    SET balance = balance + ?,
                        referral_balance = referral_balance + ?
                    WHERE telegram_id = ?
                """, (bonus, bonus, referrer_telegram_id))
        except Exception as e:
            logger.error(f"Error updating referral earnings: {e}")

    def update_marzban_username(self, device_id: int, username: str) -> None:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE devices 
                SET marzban_username = ? 
                WHERE id = ?
            """, (username, device_id))

    def get_device_by_marzban_username(self, username: str) -> Optional[Device]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM devices 
                WHERE marzban_username = ? AND is_active = 1
            """, (username,))
            row = cursor.fetchone()
            if row:
                return Device(**dict(row))
            return None

    def get_all_active_devices(self) -> List[Device]:
        """Get all active devices."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM devices 
                WHERE is_active = 1 
                ORDER BY created_at DESC
            """)

            devices = []
            for row in cursor.fetchall():
                device = Device(
                    telegram_id=row['telegram_id'],
                    device_type=row['device_type'],
                    config_data=row['config_data'],
                    is_active=row['is_active'],
                    created_at=row['created_at'],
                    expires_at=row['expires_at'],
                    marzban_username=row['marzban_username'],
                    id=row['id']
                )
                devices.append(device)
            return devices

    def update_device_expiry(self, device_id: int, new_expiry: datetime) -> bool:
        """Update device expiry date."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE devices 
                    SET expires_at = ? 
                    WHERE id = ?
                """, (new_expiry, device_id))
                return True
        except Exception as e:
            logger.error(f"Error updating device expiry: {e}")
            return False

    def get_device_by_id(self, device_id: int) -> Optional[Device]:
        """Get device by ID."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM devices 
                WHERE id = ? AND is_active = 1
            """, (device_id,))
            row = cursor.fetchone()
            if row:
                return Device(
                    telegram_id=row['telegram_id'],
                    device_type=row['device_type'],
                    config_data=row['config_data'],
                    is_active=row['is_active'],
                    created_at=row['created_at'],
                    expires_at=row['expires_at'],
                    marzban_username=row['marzban_username'],
                    id=row['id']
                )
            return None

    def update_device_config(self, device_id: int, config_data: str) -> bool:
        """Обновление конфигурации устройства."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE devices 
                    SET config_data = ?
                    WHERE id = ?
                """, (config_data, device_id))
                return True
        except Exception as e:
            logger.error(f"Error updating device config: {e}")
            return False

    def deactivate_device(self, device_id: int) -> bool:
        """Деактивация устройства."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE devices 
                    SET is_active = 0
                    WHERE id = ?
                """, (device_id,))
                return True
        except Exception as e:
            logger.error(f"Error deactivating device: {e}")
            return False

    def get_user_active_devices_count(self, telegram_id: int) -> int:
        """Получение количества активных устройств пользователя."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT COUNT(*) as count 
                    FROM devices 
                    WHERE telegram_id = ? AND is_active = 1
                """, (telegram_id,))
                return cursor.fetchone()['count']
        except Exception as e:
            logger.error(f"Error getting active devices count: {e}")
            return 0

    def add_trial_config(self, telegram_id: int, is_referrer: bool = False) -> None:
        """
        Создает trial конфиг для пользователя.
        is_referrer - True если это реферер (2 дня), False если приглашенный (1 день)
        """
        try:
            days = 2 if is_referrer else 1
            marzban_username = f"trial_{self.device_type.lower()}_{int(datetime.now().timestamp())}"

            # Создаем конфиг в Marzban
            marzban_user = self.marzban.create_user(marzban_username, days)
            if not marzban_user:
                return None

            device = Device(
                telegram_id=telegram_id,
                device_type="Trial",
                config_data=json.dumps(marzban_user),
                marzban_username=marzban_username,
                created_at=datetime.now(),
                expires_at=datetime.now() + timedelta(days=days)
            )

            self.add_device(device)
            return device

        except Exception as e:
            logger.error(f"Error adding trial config: {e}")
            return None