"""
Модуль логирования с уровнями DEBUG, INFO, WARNING, ERROR
Поддерживает вывод в консоль и передачу в UI callback
"""

from enum import IntEnum
from datetime import datetime
from typing import Optional, Callable
import logging

class LogLevel(IntEnum):
    """Уровни логирования"""
    DEBUG = 0
    INFO = 1
    WARNING = 2
    ERROR = 3

class Logger:
    """
    Централизованный логгер системы
    Поддерживает фильтрацию по уровням и callback для UI
    """

    def __init__(self, min_level: LogLevel = LogLevel.INFO):
        self.min_level = min_level
        self.ui_callback: Optional[Callable] = None

    def set_ui_callback(self, callback: Callable):
        """Установить callback для передачи логов в UI"""
        self.ui_callback = callback

    def set_level(self, level: LogLevel):
        """Установить минимальный уровень логирования"""
        self.min_level = level

    def _log(self, level: LogLevel, message: str, component: str = "SYSTEM"):
        """Внутренний метод логирования"""
        if level < self.min_level:
            return

        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        level_name = level.name

        # Форматирование сообщения
        log_msg = f"[{timestamp}] [{level_name:7}] [{component}] {message}"

        # Вывод в консоль с цветами
        color_codes = {
            LogLevel.DEBUG: '\033[36m',    # Cyan
            LogLevel.INFO: '\033[32m',      # Green
            LogLevel.WARNING: '\033[33m',   # Yellow
            LogLevel.ERROR: '\033[31m'      # Red
        }
        reset = '\033[0m'

        colored_msg = f"{color_codes.get(level, '')}{log_msg}{reset}"
        print(colored_msg)

        # Передача в UI
        if self.ui_callback:
            self.ui_callback(level, log_msg, component)

    def debug(self, message: str, component: str = "SYSTEM"):
        """Отладочная информация"""
        self._log(LogLevel.DEBUG, message, component)

    def info(self, message: str, component: str = "SYSTEM"):
        """Информационное сообщение"""
        self._log(LogLevel.INFO, message, component)

    def warning(self, message: str, component: str = "SYSTEM"):
        """Предупреждение"""
        self._log(LogLevel.WARNING, message, component)

    def error(self, message: str, component: str = "SYSTEM"):
        """Ошибка"""
        self._log(LogLevel.ERROR, message, component)

# Глобальный экземпляр логгера
logger = Logger(LogLevel.DEBUG)

"""
Модуль для логирования событий системы.
"""

import logging
from enum import Enum

class LogLevel(Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"

logging.basicConfig(
    filename="bot_system.log",
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)

def logger(msg: str, context: str = "", level: LogLevel = LogLevel.INFO):
    """
    Логирует сообщение с уровнем и контекстом.
    """
    full_msg = f"[{context}] {msg}"
    if level == LogLevel.INFO:
        logging.info(full_msg)
    elif level == LogLevel.WARNING:
        logging.warning(full_msg)
    elif level == LogLevel.ERROR:
        logging.error(full_msg)
    print(full_msg)
