#!/usr/bin/env python3
"""
Главный модуль запуска системы Telegram-ботов с RAG
Координирует работу UI (tkinter) и асинхронных процессов (asyncio)
"""

import asyncio
import threading
from db import Database
from ui_workflow import UIWorkflow
from main_workflow import MainWorkflow
from chat_monitor import ChatMonitor
from proactive_workflow import ProactiveWorkflow
from logger import logger, LogLevel

class BotSystem:
    """
    Главный класс системы
    Объединяет UI, базу данных, workflow и мониторинг Telegram
    """

    def __init__(self):
        # Инициализация базы данных
        self.db = Database()
        logger.info("Database initialized", "SYSTEM")

        # Создание asyncio event loop для фоновых задач
        self.loop = asyncio.new_event_loop()

        # Главный workflow для обработки сообщений
        self.main_workflow = MainWorkflow(self.db, self.ui_callback)

        # Мониторинг Telegram чата
        self.chat_monitor = ChatMonitor(self.main_workflow.handle_incoming_message)

        # Проактивный workflow для автоматических сообщений
        self.proactive_workflow = ProactiveWorkflow(
            self.db,
            self.send_proactive_message
        )
        self.main_workflow.set_proactive(self.proactive_workflow)

        # Пользовательский интерфейс (UI)
        self.ui = UIWorkflow(self.db, self.start_system, self.stop_system)

        # Установка callback для логгера
        logger.set_ui_callback(self.log_callback)

        # Установка уровня логирования из настроек
        log_level_str = self.db.get_setting('log_level', 'INFO')
        log_level = getattr(LogLevel, log_level_str, LogLevel.INFO)
        logger.set_level(log_level)

        logger.info("Bot system initialized", "SYSTEM")

    def log_callback(self, level: LogLevel, message: str, component: str):
        """
        Callback для передачи логов в UI
        Вызывается из logger при каждом событии
        """
        # Проверка текущего уровня логирования из настроек
        log_level_str = self.db.get_setting('log_level', 'INFO')
        min_level = getattr(LogLevel, log_level_str, LogLevel.INFO)

        # Фильтрация по уровню
        if level >= min_level:
            # Передача лога в UI thread-safe способом
            self.ui.root.after(0, lambda: self.ui.add_log(level, message, component))

    def ui_callback(self, event_type: str, data):
        """
        Callback для событий из main_workflow
        Обновляет UI в ответ на события системы
        """
        if event_type == 'queue_size':
            # Обновление размера очереди
            self.ui.root.after(0, lambda: self.ui.update_queue_size(data))

        elif event_type == 'processed_count':
            # Обновление счетчика обработанных сообщений
            self.ui.root.after(0, lambda: self.ui.update_processed_count(data))

        elif event_type == 'incoming_message':
            # Отображение входящего сообщения
            nick = data['nick']
            text = data['text']
            self.ui.root.after(0, lambda: self.ui.add_message(nick, text, is_incoming=True))

        elif event_type == 'outgoing_message':
            # Отображение исходящего сообщения (ответа бота)
            nick = data['nick']
            text = data['text']
            self.ui.root.after(0, lambda: self.ui.add_message(nick, text, is_incoming=False))

        elif event_type == 'status':
            # Обновление статуса системы
            logger.info(f"System status changed: {data}", "SYSTEM")

    async def send_proactive_message(self, role: str, target_nick: str):
        """
        Отправка проактивного сообщения от имени роли
        Используется для вовлечения пользователей при длительной неактивности
        """
        logger.info(f"Sending proactive message as {role} to {target_nick}", "PROACTIVE")

        # Формирование промпта для проактивного сообщения
        prompt = f"You are {role}. Send a proactive message to engage the user. Keep it brief and friendly."

        from llm_subworkflow import LLMSubworkflow
        llm = LLMSubworkflow(self.db)

        # Получение списка моделей
        models = self.db.get_free_llms()
        if models:
            # Генерация проактивного сообщения
            response = await llm.call_llm(models[0][0], prompt, 0.5)

            if response and self.chat_monitor:
                # Отправка через Telegram
                await self.chat_monitor.send_message(target_nick, response)
                logger.info(f"Proactive message sent to {target_nick}", "PROACTIVE")
            else:
                logger.warning("Failed to generate proactive message", "PROACTIVE")
        else:
            logger.error("No models available for proactive message", "PROACTIVE")

    async def start_system(self):
        """Асинхронный запуск всех компонентов системы"""
        logger.info("Starting system components...", "SYSTEM")

        # Запуск главного workflow
        await self.main_workflow.start()

        # Запуск мониторинга Telegram
        await self.chat_monitor.start()

        logger.info("All system components started", "SYSTEM")

    async def stop_system(self):
        """Асинхронная остановка всех компонентов системы"""
        logger.info("Stopping system components...", "SYSTEM")

        # Остановка главного workflow
        await self.main_workflow.stop()

        # Остановка мониторинга Telegram
        await self.chat_monitor.stop()

        logger.info("All system components stopped", "SYSTEM")

    def run_async_loop(self):
        """
        Запуск asyncio event loop в отдельном потоке
        Позволяет UI работать в главном потоке, а async задачи - в фоновом
        """
        asyncio.set_event_loop(self.loop)
        logger.debug("Async loop started in background thread", "SYSTEM")
        self.loop.run_forever()

    def run(self):
        """
        Главный метод запуска системы
        1. Запуск asyncio loop в отдельном потоке
        2. Запуск UI в главном потоке
        """
        # Запуск async потока
        async_thread = threading.Thread(target=self.run_async_loop, daemon=True)
        async_thread.start()
        logger.info("Background async thread started", "SYSTEM")

        # Запуск UI (блокирующий вызов)
        logger.info("Starting UI main loop", "SYSTEM")
        self.ui.run()

        # После закрытия UI - остановка async loop
        logger.info("UI closed, stopping async loop", "SYSTEM")
        self.loop.call_soon_threadsafe(self.loop.stop)

def main():
    """Точка входа в программу"""
    print("=" * 60)
    print("Telegram Bot RAG System")
    print("Multi-Role Bot Management with LLM and Vector Database")
    print("=" * 60)

    # Создание и запуск системы
    system = BotSystem()
    system.run()

    logger.info("System shutdown complete", "SYSTEM")

if __name__ == '__main__':
    main()
