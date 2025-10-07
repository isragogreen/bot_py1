import asyncio
import random
from datetime import datetime, timedelta
from typing import Optional
from db import Database
from env_loader import env_loader

class ProactiveWorkflow:
    def __init__(self, db: Database, send_message_callback):
        self.db = db
        self.send_message = send_message_callback
        self.inactivity_n = env_loader.get_int('INACTIVITY_N', 10)
        self.random_min = env_loader.get_int('RANDOM_MULTIPLIER_MIN', 1)
        self.random_max = env_loader.get_int('RANDOM_MULTIPLIER_MAX', 5)
        self.enabled = False
        self.task: Optional[asyncio.Task] = None

    async def check_inactivity(self):
        while self.enabled:
            try:
                last_message_time = self.db.get_setting('last_message_time')

                if last_message_time:
                    elapsed = datetime.now().timestamp() - last_message_time
                    multiplier = random.randint(self.random_min, self.random_max)
                    threshold = self.inactivity_n * multiplier * 60

                    if elapsed > threshold:
                        operator_nick = env_loader.get('OPERATOR_NICK', 'admin_operator')

                        await self.send_message('AGITATOR', operator_nick)

                        self.db.set_setting('last_message_time', datetime.now().timestamp())
                        self.db.add_history('system', f'Proactive message sent after {elapsed/60:.1f} min', 'system_log')

                await asyncio.sleep(60)

            except Exception as e:
                print(f"Proactive workflow error: {e}")
                await asyncio.sleep(60)

    def start(self):
        if not self.enabled and not self.task:
            self.enabled = True
            self.task = asyncio.create_task(self.check_inactivity())
            print("Proactive workflow started")

    async def stop(self):
        if self.task:
            self.enabled = False
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
            self.task = None
            print("Proactive workflow stopped")
