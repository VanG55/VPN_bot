import os
from typing import List, Dict

# Bot Configuration
TOKEN = os.getenv('BOT_TOKEN', '7212816626:AAEbnxhIOSAgx8AZdj0_PZbBsfXiFkpkjls')
DB_NAME = os.getenv('DB_NAME', 'vpn_bot.db')
BOT_USERNAME = "VangVPN_bot"

# Marzban Configuration
MARZBAN_HOST = os.getenv('MARZBAN_HOST', 'http://150.241.108.35:7575')
MARZBAN_USERNAME = os.getenv('MARZBAN_USERNAME', 'admin')
MARZBAN_PASSWORD = os.getenv('MARZBAN_PASSWORD', 'JmnutmenfBp7')
MARZBAN_PROTOCOLS = {
    "IOS": {"vmess": True, "vless": True, "trojan": False, "shadowsocks": False},
    "Android": {"vmess": True, "vless": True, "trojan": True, "shadowsocks": True},
    "Windows": {"vmess": True, "vless": True, "trojan": True, "shadowsocks": True},
    "MacOS": {"vmess": True, "vless": True, "trojan": False, "shadowsocks": False},
    "Linux": {"vmess": True, "vless": True, "trojan": True, "shadowsocks": True}
}
# YooKassa Configuration
YOOKASSA_ACCOUNT_ID = '490714'
YOOKASSA_SECRET_KEY = 'live_bU6jpk2314izChK8KdS1TAm6tuWQj7ywYbGLau5ab64'

# Payment Configuration
DEFAULT_PLAN_PRICE = float(os.getenv('DEFAULT_PLAN_PRICE', '10'))
MIN_TOP_UP = int(os.getenv('MIN_TOP_UP', '100'))
MAX_TOP_UP = int(os.getenv('MAX_TOP_UP', '1000'))
TOP_UP_OPTIONS = [100, 300, 500, 1000]

# Support Configuration
SUPPORT_GROUP_ID = -1002228541514
SUPPORT_WELCOME_MESSAGE = "Опишите вашу проблему"

# Device Types
DEVICE_TYPES = ["IOS", "Android", "Windows", "Linux", "MacOS"]

# Message Templates
MESSAGE_TEMPLATES = {
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

- Пополнение баланса является однократной операцией (не подписка).
- Списание средств с баланса осуществляется в момент создания конфигурации.

💳 *Доступные способы оплаты:*
- Карты РФ
- Карты других стран
- СБП
- Электронные деньги
- Онлайн-банк

Выберите сумму пополнения:
""",
    'help': """
ℹ️ *Раздел помощи*

Если у вас возникли вопросы или проблемы, напишите нам, и мы постараемся помочь.
"""
}