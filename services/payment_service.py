import logging
from typing import Optional, Dict, Any
from yookassa import Payment, Configuration
from yookassa.domain.models.currency import Currency
from yookassa.domain.common.confirmation_type import ConfirmationType
from database.models import Transaction
from database.db_manager import DatabaseManager
from database.models import User
from config.settings import (
    YOOKASSA_ACCOUNT_ID,
    YOOKASSA_SECRET_KEY,
    MIN_TOP_UP,
    MAX_TOP_UP,
    BOT_USERNAME
)

logger = logging.getLogger('payment_service')


class PaymentService:
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        # Инициализация ЮKassa
        Configuration.account_id = YOOKASSA_ACCOUNT_ID
        Configuration.secret_key = YOOKASSA_SECRET_KEY
        self.min_amount = 10.0  # Минимальная сумма
        self.max_amount = 10000.0  # Максимальная сумма


    def create_payment_link(self, telegram_id: int, amount: float, email: str) -> Optional[Dict[str, Any]]:
        """Create payment in YooKassa and return payment link."""
        try:
            logger.info(f"Starting payment creation for user {telegram_id}, amount {amount}, email {email}")

            amount = float(amount)
            if not self._validate_payment_amount(amount):
                logger.error(f"Invalid payment amount: {amount}")
                return None

            # Форматируем сумму до двух знаков после запятой
            formatted_amount = "{:.2f}".format(amount)

            payment_data = {
                "amount": {
                    "value": formatted_amount,
                    "currency": "RUB"
                },
                "confirmation": {
                    "type": "redirect",
                    "return_url": f"https://t.me/{BOT_USERNAME}?start=payment_"
                },
                "capture": True,
                "description": f"Пополнение баланса",
                "metadata": {
                    "user_id": str(telegram_id)
                },
                "receipt": {
                    "customer": {
                        "email": email
                    },
                    "items": [
                        {
                            "description": "Пополнение баланса",
                            "amount": {
                                "value": formatted_amount,
                                "currency": "RUB"
                            },
                            "vat_code": "1",
                            "quantity": "1",
                            "measure": "piece",
                            "payment_mode": "full_prepayment",
                            "payment_subject": "service"
                        }
                    ]
                }
            }

            logger.info(f"Payment data prepared: {payment_data}")

            # Создаем платеж в ЮKassa
            payment = Payment.create(payment_data)
            logger.info(f"Payment created in YooKassa: {payment.id}")

            # Создаем транзакцию в статусе pending
            transaction = Transaction(
                user_id=telegram_id,  # Используем user_id как имя атрибута
                amount=amount,
                transaction_type='top_up',
                status='pending',
                payment_id=payment.id
            )
            transaction_id = self.db_manager.add_transaction(transaction)
            logger.info(f"Created transaction {transaction_id} for payment {payment.id}")

            return {
                'success': True,
                'payment_url': payment.confirmation.confirmation_url,
                'payment_id': payment.id
            }

        except Exception as e:
            logger.error(f"Error creating payment: {e}")
            return None

    def check_payment_status(self, payment_id: str) -> Optional[Dict[str, Any]]:
        """Check payment status in YooKassa."""
        try:
            logger.info(f"Checking payment status for payment_id: {payment_id}")

            payment = Payment.find_one(payment_id)
            logger.info(f"Payment status from YooKassa: {payment.status}")

            if payment.status == 'succeeded':
                # Если платеж успешен
                user_id = int(payment.metadata['user_id'])
                amount = float(payment.amount.value)

                logger.info(f"Payment succeeded. Updating balance for user {user_id}, amount {amount}")

                # Обновляем баланс пользователя
                self.db_manager.update_balance(user_id, amount)

                # Обновляем статус транзакции
                self.db_manager.update_transaction_status(payment_id, 'completed')

                return {
                    'status': payment.status,
                    'paid': True,
                    'amount': amount,
                    'user_id': user_id
                }

            return {
                'status': payment.status,
                'paid': payment.status == 'succeeded',
                'amount': float(payment.amount.value),
                'user_id': int(payment.metadata.get('user_id')) if payment.metadata.get('user_id') else None
            }

        except Exception as e:
            logger.error(f"Error checking payment status: {str(e)}", exc_info=True)
            return None

    def handle_payment_notification(self, notification_data: dict) -> bool:
        """Handle payment notification from YooKassa."""
        try:
            if notification_data['event'] == 'payment.succeeded':
                payment = notification_data['object']
                user_id = int(payment['metadata']['user_id'])
                amount = float(payment['amount']['value'])

                # Создаем успешную транзакцию
                transaction = Transaction(
                    user_id=user_id,
                    amount=amount,
                    transaction_type='top_up',
                    status='completed'
                )
                transaction_id = self.db_manager.add_transaction(transaction)

                # Обновляем баланс пользователя
                if transaction_id:
                    self.db_manager.update_balance(user_id, amount)

                    # Проверяем реферала и начисляем бонус
                    referrer = self.db_manager.get_referrer(user_id)
                    if referrer:
                        bonus = amount * 0.15  # 15% от суммы
                        self.db_manager.add_referral_bonus(referrer['referrer_id'], bonus)

                    logger.info(f"Successfully processed payment for user {user_id}")
                    return True

            return False

        except Exception as e:
            logger.error(f"Error handling payment notification: {e}")
            return False

    @staticmethod
    def _validate_payment_amount(amount: float) -> bool:
        """Validate payment amount."""
        try:
            amount = float(amount)
            return 10.0 <= amount <= 10000.0
        except (ValueError, TypeError):
            return False

    def handle_notification(self, data: dict) -> bool:
        try:
            if data['event'] != 'payment.succeeded':
                return False

            payment = data['object']
            payer_telegram_id = int(payment['metadata']['user_id'])
            amount = float(payment['amount']['value'])

            # Обновляем баланс плательщика
            self.db_manager.update_balance(payer_telegram_id, amount)

            # Обновляем статус транзакции
            self.db_manager.update_transaction_status(payment['id'], 'completed')

            # Проверяем и обрабатываем реферальный бонус
            self.db_manager.process_referral_payment(payer_telegram_id, amount)

            return True

        except Exception as e:
            logger.error(f"Error handling payment: {e}")
            return False

    def get_user_by_id(self, user_id: int) -> Optional[User]:
        """Get user by ID from database."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT telegram_id, username, first_name, last_name, 
                       balance, agreement_accepted, total_referral_bonus,
                       current_referral_bonus, created_at, id
                FROM users 
                WHERE id = ?
            """, (user_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return User(
                telegram_id=row['telegram_id'],
                username=row['username'],
                first_name=row['first_name'],
                last_name=row['last_name'],
                balance=row['balance'],
                agreement_accepted=row['agreement_accepted'],
                total_referral_bonus=row['total_referral_bonus'],
                current_referral_bonus=row['current_referral_bonus'],
                created_at=row['created_at'],
                id=row['id']
            )
