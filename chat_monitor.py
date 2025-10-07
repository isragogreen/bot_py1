"""
Модуль для приема и отправки сообщений через Telegram.
Асинхронная интеграция с основной очередью сообщений.
"""

import asyncio
from env_loader import get_env
from error_handler import log_error
from main_workflow import MainWorkflow

from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor

TELEGRAM_BOT_TOKEN = get_env("TELEGRAM_BOT_TOKEN")

class ChatMonitor:
    """
    Класс для асинхронного мониторинга Telegram-чата.
    Получает входящие сообщения и передает их в основной workflow.
    """

    def __init__(self, workflow: MainWorkflow):
        self.workflow = workflow
        self.running = False
        self.bot = Bot(token=TELEGRAM_BOT_TOKEN)
        self.dp = Dispatcher(self.bot)

    async def start(self):
        """
        Запуск мониторинга Telegram.
        """
        self.running = True
        try:
            @self.dp.message_handler()
            async def handle_message(message: types.Message):
                nick = message.from_user.username or str(message.from_user.id)
                text = message.text
                await self.workflow.handle_incoming_message(nick, text)

            # Запуск aiogram event loop
            await self.dp.start_polling()
        except Exception as e:
            log_error(e, "ChatMonitor")

    async def stop(self):
        """
        Остановка мониторинга.
        """
        self.running = False
        await self.dp.storage.close()
        await self.dp.storage.wait_closed()
        await self.bot.session.close()
