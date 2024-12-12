import logging
import requests
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import json

logger = logging.getLogger('marzban_service')


class MarzbanService:
    def __init__(self, host: str, username: str, password: str, node_manager):
        self.host = host.rstrip('/')
        self.username = username
        self.password = password
        self.token = None
        self.node_manager = node_manager
        self.logger = logging.getLogger('marzban_service')

    def _get_token(self) -> Optional[str]:
        """Получение токена для API Marzban."""
        try:
            response = requests.post(
                f"{self.host}/api/admin/token",
                data={"username": self.username, "password": self.password}
            )
            if response.status_code == 200:
                return response.json()["access_token"]
            return None
        except Exception as e:
            self.logger.error(f"Error getting token: {e}")
            return None

    def _get_headers(self) -> Dict[str, str]:
        """Получение заголовков с токеном."""
        if not self.token:
            self.token = self._get_token()
        return {"Authorization": f"Bearer {self.token}"}

    def create_user(self, username: str, days: int) -> Optional[Dict]:
        try:
            response = requests.post(
                f"{self.host}/api/user",
                json={
                    "username": username,
                    "expire": int((datetime.now() + timedelta(days=days)).timestamp()),
                    "data_limit": 0,
                    "proxies": {"vless": {"flow": ""}},
                    "inbounds": {"vless": ["VLESS TCP REALITY"]},
                    "limit_ip": 1,
                    "hosts": {
                        "VLESS TCP REALITY": [
                            {"remark": "Marz", "address": "150.241.108.35"},
                            {"remark": "Marzban2", "address": "150.241.108.166"}
                        ]
                    }
                },
                headers=self._get_headers(),
                verify=False
            )

            if response.status_code == 200:
                return response.json()

            return None

        except Exception as e:
            logger.error(f"Error creating user: {e}")
            return None

    def get_nodes_health(self) -> Dict[str, Any]:
        """Получение информации о здоровье всех нод"""
        return self.node_manager.get_nodes_status()

    def get_user_config(self, username: str) -> Optional[Dict]:
        """Получение конфигурации пользователя."""
        try:
            self.logger.info(f"Getting config for user {username}")
            self.logger.info(f"Making request to: {self.host}/api/user/{username}")

            response = requests.get(
                f"{self.host}/api/user/{username}",
                headers=self._get_headers(),
                verify=False
            )

            self.logger.info(f"Response status: {response.status_code}")
            self.logger.info(f"Response text: {response.text}")

            if response.status_code == 200:
                return response.json()
            return None

        except Exception as e:
            self.logger.error(f"Error getting user config: {e}")
            return None

    def delete_user(self, username: str) -> bool:
        """Удаление пользователя."""
        try:
            response = requests.delete(
                f"{self.host}/api/user/{username}",
                headers=self._get_headers()
            )
            return response.status_code == 200
        except Exception as e:
            self.logger.error(f"Error deleting user: {e}")
            return False

    def get_user_usage(self, username: str) -> Optional[Dict[str, Any]]:
        """Получение статистики использования."""
        try:
            response = requests.get(
                f"{self.host}/api/user/{username}/usage",
                headers=self._get_headers()
            )
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            self.logger.error(f"Error getting user usage: {e}")
            return None

    def reset_user_traffic(self, username: str) -> bool:
        """Сброс статистики трафика пользователя."""
        try:
            response = requests.post(
                f"{self.host}/api/user/{username}/reset",
                headers=self._get_headers()
            )
            return response.status_code == 200
        except Exception as e:
            self.logger.error(f"Error resetting user traffic: {e}")
            return False

    def get_server_info(self) -> Optional[Dict[str, Any]]:
        """Получение информации о сервере Marzban."""
        try:
            response = requests.get(
                f"{self.host}/api/system",
                headers=self._get_headers()
            )
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            self.logger.error(f"Error getting server info: {e}")
            return None

    def get_active_users_count(self) -> Optional[int]:
        """Получение количества активных пользователей."""
        try:
            response = requests.get(
                f"{self.host}/api/users",
                headers=self._get_headers()
            )
            if response.status_code == 200:
                users = response.json()
                return len([u for u in users if u.get('status') == 'active'])
            return None
        except Exception as e:
            self.logger.error(f"Error getting active users count: {e}")
            return None

    def update_user_config(self, username: str, days: int = None) -> Optional[Dict[str, Any]]:
        """Обновление конфигурации пользователя."""
        try:
            current_config = self.get_user_config(username)
            if not current_config:
                return None

            update_data = {}
            if days:
                update_data["expire"] = (datetime.now() + timedelta(days=days)).isoformat()

            response = requests.put(
                f"{self.host}/api/user/{username}",
                headers=self._get_headers(),
                json=update_data
            )

            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            self.logger.error(f"Error updating user config: {e}")
            return None