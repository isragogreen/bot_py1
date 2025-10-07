#!/usr/bin/env python3
import asyncio
import threading
from db import Database
from ui_workflow import UIWorkflow
from main_workflow import MainWorkflow
from chat_monitor import ChatMonitor
from proactive_workflow import ProactiveWorkflow

class BotSystem:
    def __init__(self):
        self.db = Database()
        self.loop = asyncio.new_event_loop()

        self.main_workflow = MainWorkflow(self.db, self.ui_callback)

        self.chat_monitor = ChatMonitor(self.main_workflow.handle_incoming_message)

        self.proactive_workflow = ProactiveWorkflow(
            self.db,
            self.send_proactive_message
        )
        self.main_workflow.set_proactive(self.proactive_workflow)

        self.ui = UIWorkflow(self.db, self.start_system, self.stop_system)

    def ui_callback(self, event_type: str, data):
        if event_type == 'log':
            self.ui.root.after(0, lambda: self.ui.log(data))
        elif event_type == 'queue_size':
            self.ui.root.after(0, lambda: self.ui.update_queue_size(data))
        elif event_type == 'response':
            self.ui.root.after(0, lambda: self.ui.log(f"Response to {data['nick']}: {data['text'][:50]}..."))

    async def send_proactive_message(self, role: str, target_nick: str):
        prompt = f"You are {role}. Send a proactive message to engage the user. Keep it brief and friendly."

        from llm_subworkflow import LLMSubworkflow
        llm = LLMSubworkflow(self.db)

        models = self.db.get_free_llms()
        if models:
            response = await llm.call_llm(models[0][0], prompt, 0.5)
            if response and self.chat_monitor:
                await self.chat_monitor.send_message(target_nick, response)

    async def start_system(self):
        print("Starting system...")
        await self.main_workflow.start()
        await self.chat_monitor.start()

    async def stop_system(self):
        print("Stopping system...")
        await self.main_workflow.stop()
        await self.chat_monitor.stop()

    def run_async_loop(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def run(self):
        async_thread = threading.Thread(target=self.run_async_loop, daemon=True)
        async_thread.start()

        self.ui.run()

        self.loop.call_soon_threadsafe(self.loop.stop)

def main():
    print("=" * 60)
    print("Telegram Bot RAG System")
    print("=" * 60)

    system = BotSystem()
    system.run()

if __name__ == '__main__':
    main()
