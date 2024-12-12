import logging
import requests
from typing import Optional, Dict, Any
from datetime import datetime

logger = logging.getLogger('node_manager')


class NodeManager:
    def __init__(self):
        """
        Инициализация NodeManager.
        Теперь работаем только с главным сервером Marzban, так как он сам управляет нодами.
        """
        self.nodes = {
            'Master': {
                'host': 'http://150.241.108.35:7575',
                'current_users': 0,
                'max_users': 2
            },
            'Marzban2': {
                'host': 'http://150.241.108.166:62051',
                'current_users': 0,
                'max_users': 2
            }
        }
        self.initialize_nodes()

    def initialize_nodes(self):
        """
        Инициализация начального состояния нод
        """
        try:
            for node_name in self.nodes:
                logger.info(f"Initializing node: {node_name}")
                self.update_node_stats(node_name)
        except Exception as e:
            logger.error(f"Error initializing nodes: {e}")

    def update_node_stats(self, node_name: str):
        """
        Обновление статистики ноды
        """
        try:
            node = self.nodes[node_name]
            logger.info(f"Updating stats for node {node_name}")
            # В будущем здесь можно добавить получение реальной статистики
            # Пока используем локальный счетчик
        except Exception as e:
            logger.error(f"Error updating node stats for {node_name}: {e}")

    def get_node_users(self, host: str) -> int:
        """
        Получение количества пользователей на узле
        """
        for node in self.nodes.values():
            if host in node['host']:
                return node['current_users']
        return 0

    def increment_node_users(self, host: str) -> bool:
        """
        Увеличение счетчика пользователей для узла
        """
        try:
            for node in self.nodes.values():
                if host in node['host']:
                    if node['current_users'] < node['max_users']:
                        node['current_users'] += 1
                        logger.info(f"Incremented users for node {host}: {node['current_users']}")
                        return True
            return False
        except Exception as e:
            logger.error(f"Error incrementing node users: {e}")
            return False

    def decrement_node_users(self, host: str):
        """
        Уменьшение счетчика пользователей для узла
        """
        try:
            for node in self.nodes.values():
                if host in node['host']:
                    if node['current_users'] > 0:
                        node['current_users'] -= 1
                        logger.info(f"Decremented users for node {host}: {node['current_users']}")
        except Exception as e:
            logger.error(f"Error decrementing node users: {e}")

    def get_node_host(self, node_name: str) -> str:
        """
        Получение хоста ноды по имени
        """
        return self.nodes[node_name]['host']

    def get_nodes_status(self) -> Dict[str, Any]:
        """
        Получение статуса всех нод
        """
        status = {}
        for node_name, node in self.nodes.items():
            status[node_name] = {
                'host': node['host'],
                'current_users': node['current_users'],
                'max_users': node['max_users']
            }
        return status

    def select_optimal_config(self, config_data: dict) -> Optional[str]:
        """
        Выбирает оптимальную конфигурацию на основе загрузки серверов.

        Args:
            config_data: Словарь с данными конфигурации от Marzban

        Returns:
            str: Оптимальная ссылка для подключения или None в случае ошибки
        """
        try:
            links = config_data.get('links', [])
            if not links:
                logger.error("No links found in config data")
                return None

            # Собираем статистику по нодам
            node_stats = {}
            for link in links:
                try:
                    # Извлекаем хост из ссылки
                    host = link.split('@')[1].split(':')[0]

                    # Проверяем, что это известная нода
                    node_info = None
                    for node_name, node in self.nodes.items():
                        if host in node['host']:
                            node_info = node
                            break

                    if node_info:
                        current_users = node_info['current_users']
                        max_users = node_info['max_users']

                        # Вычисляем процент загрузки
                        load_percentage = (current_users / max_users * 100) if max_users > 0 else 100

                        node_stats[link] = {
                            'load': load_percentage,
                            'users': current_users,
                            'max_users': max_users,
                            'host': host
                        }

                        logger.info(f"Node {host}: {current_users}/{max_users} users ({load_percentage:.1f}%)")

                except Exception as e:
                    logger.error(f"Error processing link {link}: {e}")
                    continue

            if not node_stats:
                logger.warning("No valid nodes found, returning first link")
                return links[0]

            # Выбираем ноду с наименьшей загрузкой
            optimal_link = min(node_stats.items(), key=lambda x: x[1]['load'])[0]
            optimal_stats = node_stats[optimal_link]

            logger.info(f"Selected optimal node {optimal_stats['host']} "
                        f"with {optimal_stats['users']}/{optimal_stats['max_users']} users "
                        f"({optimal_stats['load']:.1f}% load)")

            return optimal_link

        except Exception as e:
            logger.error(f"Error selecting optimal config: {e}")
            if links:
                return links[0]
            return None
