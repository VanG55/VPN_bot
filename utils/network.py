import socket
import requests
from functools import wraps
import logging
from time import sleep
from typing import Callable, Any

logger = logging.getLogger('network')


class NetworkError(Exception):
    pass


def retry_on_network_error(max_retries: int = 3, delay: int = 1):
    """Декоратор для повторных попыток при сетевых ошибках."""

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            retries = 0
            while retries < max_retries:
                try:
                    return func(*args, **kwargs)
                except (requests.exceptions.RequestException,
                        socket.error, NetworkError) as e:
                    retries += 1
                    if retries == max_retries:
                        logger.error(f"Network error after {max_retries} retries: {e}")
                        raise NetworkError(f"Network operation failed: {e}")
                    logger.warning(f"Network error (attempt {retries}): {e}")
                    sleep(delay * retries)
            return None

        return wrapper

    return decorator


def check_network_connectivity() -> bool:
    """Проверка наличия сетевого подключения."""
    try:
        # Пробуем подключиться к нескольким надежным серверам
        test_hosts = [
            ("8.8.8.8", 53),  # Google DNS
            ("1.1.1.1", 53),  # Cloudflare DNS
            ("api.telegram.org", 443)  # Telegram API
        ]

        for host, port in test_hosts:
            try:
                socket.create_connection((host, port), timeout=3)
                logger.info(f"Successfully connected to {host}:{port}")
                return True
            except socket.error:
                continue

        logger.error("Could not connect to any test hosts")
        return False
    except Exception as e:
        logger.error(f"Error checking network connectivity: {e}")
        return False


@retry_on_network_error(max_retries=3)
def test_telegram_api() -> bool:
    """Проверка доступности Telegram API."""
    try:
        response = requests.get('https://api.telegram.org', timeout=5)
        return response.status_code == 200
    except requests.exceptions.RequestException as e:
        logger.error(f"Error testing Telegram API: {e}")
        return False


def validate_config_connection(config: str, timeout: int = 5) -> bool:
    """Проверка доступности конфигурации VPN."""
    try:
        # Извлекаем сервер и порт из конфигурации
        server = config.split('server = ')[1].split('\n')[0].strip()
        port = int(config.split('port = ')[1].split('\n')[0].strip())

        # Пробуем подключиться
        socket.create_connection((server, port), timeout=timeout)
        logger.info(f"Successfully validated connection to {server}:{port}")
        return True
    except Exception as e:
        logger.error(f"Error validating config connection: {e}")
        return False