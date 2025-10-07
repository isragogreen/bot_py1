import asyncio
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes
from typing import Callable, Optional
from env_loader import env_loader

class ChatMonitor:
    def __init__(self, on_message: Callable):
        self.token = env_loader.get('TELEGRAM_BOT_TOKEN')
        self.enabled = bool(self.token)
        self.on_message = on_message
        self.app: Optional[Application] = None
        self.running = False

    async def message_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.message and update.message.text:
            nick = update.effective_user.username or str(update.effective_user.id)
            text = update.message.text

            await self.on_message(nick, text)

    async def send_message(self, chat_id: str, text: str):
        if self.app and self.running:
            try:
                await self.app.bot.send_message(chat_id=chat_id, text=text)
            except Exception as e:
                print(f"Error sending message: {e}")

    async def start(self):
        if not self.enabled or self.running:
            return

        try:
            self.app = Application.builder().token(self.token).build()

            self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.message_handler))

            await self.app.initialize()
            await self.app.start()
            await self.app.updater.start_polling()

            self.running = True
            print("Telegram bot started")

        except Exception as e:
            print(f"Error starting Telegram bot: {e}")
            self.enabled = False

    async def stop(self):
        if self.app and self.running:
            try:
                await self.app.updater.stop()
                await self.app.stop()
                await self.app.shutdown()
                self.running = False
                print("Telegram bot stopped")
            except Exception as e:
                print(f"Error stopping Telegram bot: {e}")

chat_monitor: Optional[ChatMonitor] = None
