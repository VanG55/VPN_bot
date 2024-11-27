import os
from typing import List, Dict

# Payment Configuration
YOOKASSA_ACCOUNT_ID = '490714'
YOOKASSA_SECRET_KEY = 'live_bU6jpk2314izChK8KdS1TAm6tuWQj7ywYbGLau5ab64'

# Bot Configuration
TOKEN: str = os.getenv('BOT_TOKEN', '7212816626:AAEbnxhIOSAgx8AZdj0_PZbBsfXiFkpkjls')
DB_NAME: str = os.getenv('DB_NAME', 'vpn_bot.db')
BOT_USERNAME = "VangVPN_bot"

# Support Configuration
SUPPORT_GROUP_ID: int = -1002228541514  # ID группы поддержки
SUPPORT_WELCOME_MESSAGE: str = "Опишите вашу проблему или задайте вопрос. Мы постараемся ответить как можно скорее."

# URLs
PAYMENT_URL: str = os.getenv('PAYMENT_URL', 'https://yoomoney.ru')

# Device Configuration
DEVICE_TYPES: List[str] = ["IOS", "Android", "Windows", "Linux", "MacOS"]

# Payment Configuration
DEFAULT_PLAN_PRICE: float = float(os.getenv('DEFAULT_PLAN_PRICE', '10'))
MIN_TOP_UP: int = int(os.getenv('MIN_TOP_UP', '100'))
MAX_TOP_UP: int = int(os.getenv('MAX_TOP_UP', '1000'))
TOP_UP_OPTIONS: List[int] = [100, 300, 500, 1000]

# Message Templates
MESSAGE_TEMPLATES: Dict[str, str] = {
    'welcome': """
🏠 *Ваш личный кабинет*

👋 Рады видеть вас, {display_name}!
🆔 Ваш ID: `{user_id}`
💰 Баланс: *{balance:.2f} руб.*
💼 Тариф: *{plan_price} руб/сутки* (за одно устройство)

📱 У вас *{devices_count}* {devices_word}
💸 Общая стоимость: *{total_cost}₽ в сутки*
⏳ Хватит на *{days_left}* {days_word}

⚠️ _При недостаточности баланса конфигурации удаляются._

🕒 Обновлено: {current_time}

_(для установки VPN перейдите в раздел "Мои устройства")_
""",
    'top_up_info': """
💰 *Пополнение баланса*

• Пополнение баланса является однократной операцией (не подписка).
• Мы не имеем доступа к вашим личным и платежным данным.
• Списание средств с баланса осуществляется в момент создания конфигурации.

💳 *Доступные способы оплаты:*
• Карты РФ
• Карты других стран
• СБП
• Электронные деньги
• Онлайн-банк

Выберите сумму пополнения:
""",
    'help': """
ℹ️ *Раздел помощи*

Если у вас возникли вопросы или проблемы, напишите нам, и мы постараемся помочь.

Чтобы начать диалог с поддержкой, просто отправьте ваше сообщение.
*Внимание:* Старайтесь описать проблему максимально подробно.
"""
}