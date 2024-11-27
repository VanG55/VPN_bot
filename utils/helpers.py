import logging
from functools import wraps
from typing import Callable, Any


def setup_logger(name: str) -> logging.Logger:
    """Setup logger with custom format."""
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    handler = logging.StreamHandler()
    handler.setFormatter(formatter)

    logger.addHandler(handler)
    return logger


def handle_exceptions(func: Callable) -> Callable:
    """Decorator to handle exceptions in bot handlers."""

    @wraps(func)
    def wrapper(*args, **kwargs) -> Any:
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.error(f"Error in {func.__name__}: {str(e)}", exc_info=True)

            # If this is a callback query
            if len(args) > 0 and hasattr(args[0], 'id'):
                try:
                    from telebot import TeleBot
                    bot = TeleBot.__new__(TeleBot)
                    bot.answer_callback_query(
                        args[0].id,
                        "❌ Произошла ошибка. Попробуйте позже."
                    )
                except:
                    pass

    return wrapper


def print_fancy_header(token: str, db_name: str) -> None:
    """Print fancy header with bot information."""
    print("\n" + "=" * 50)
    print("🚀 VPN Config Bot Starting 🚀".center(50))
    print("=" * 50)
    print("📊 Bot Information:")
    print(f"🆔 Bot Token: {token[:5]}...{token[-5:]}")
    print(f"💾 Database: {db_name}")
    print("=" * 50 + "\n")