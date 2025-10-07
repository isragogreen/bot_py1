import tkinter as tk
from tkinter import ttk, scrolledtext
import asyncio
from typing import Callable
from db import Database
from env_loader import env_loader

class UIWorkflow:
    def __init__(self, db: Database, on_start: Callable, on_stop: Callable):
        self.db = db
        self.on_start = on_start
        self.on_stop = on_stop

        self.root = tk.Tk()
        self.root.title("Telegram Bot RAG System")
        self.root.geometry("900x700")

        self.create_ui()

        self.update_service_status()

    def create_ui(self):
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill='both', expand=True, padx=10, pady=10)

        services_frame = ttk.Frame(notebook)
        notebook.add(services_frame, text='Services')
        self.create_services_panel(services_frame)

        control_frame = ttk.Frame(notebook)
        notebook.add(control_frame, text='Bot Control')
        self.create_control_panel(control_frame)

        monitor_frame = ttk.Frame(notebook)
        notebook.add(monitor_frame, text='Monitor')
        self.create_monitor_panel(monitor_frame)

    def create_services_panel(self, parent):
        services = [
            ('OpenRouter', 'OPENROUTER_API_KEY'),
            ('Pinecone', 'PINECONE_API_KEY'),
            ('Qdrant', 'QDRANT_API_KEY'),
            ('Translator', 'TRANSLATE_API_KEY'),
            ('Telegram', 'TELEGRAM_BOT_TOKEN'),
            ('GitHub', 'GITHUB_TOKEN'),
            ('GitLab', 'GITLAB_TOKEN')
        ]

        ttk.Label(parent, text="Service Status", font=('Arial', 14, 'bold')).pack(pady=10)

        self.service_indicators = {}

        for service_name, env_key in services:
            frame = ttk.Frame(parent)
            frame.pack(fill='x', padx=20, pady=5)

            ttk.Label(frame, text=service_name, width=15).pack(side='left')

            indicator = ttk.Label(frame, text='●', font=('Arial', 20))
            indicator.pack(side='left', padx=10)

            self.service_indicators[env_key] = indicator

    def update_service_status(self):
        for env_key, indicator in self.service_indicators.items():
            has_key = env_loader.has_key(env_key)
            indicator.config(text='🟢' if has_key else '🔴')

    def create_control_panel(self, parent):
        ttk.Label(parent, text="Bot Configuration", font=('Arial', 14, 'bold')).pack(pady=10)

        roles_frame = ttk.LabelFrame(parent, text="Role Blacklist", padding=10)
        roles_frame.pack(fill='x', padx=20, pady=10)

        self.role_vars = {}
        roles = ['TECH', 'FRIEND', 'ADVISOR', 'AGITATOR', 'OPERATOR']

        for role in roles:
            var = tk.BooleanVar(value=self.db.is_blacklisted(role.lower()))
            cb = ttk.Checkbutton(
                roles_frame,
                text=f"Blacklist {role}",
                variable=var,
                command=lambda r=role, v=var: self.toggle_blacklist(r, v)
            )
            cb.pack(anchor='w', pady=2)
            self.role_vars[role] = var

        options_frame = ttk.LabelFrame(parent, text="Options", padding=10)
        options_frame.pack(fill='x', padx=20, pady=10)

        self.remove_emoji_var = tk.BooleanVar(value=self.db.get_setting('remove_emoji', True))
        ttk.Checkbutton(
            options_frame,
            text="Remove emojis from messages",
            variable=self.remove_emoji_var,
            command=self.save_options
        ).pack(anchor='w', pady=2)

        self.save_msgs_var = tk.BooleanVar(value=self.db.get_setting('SAVE_ALL_MSGS', True))
        ttk.Checkbutton(
            options_frame,
            text="Save all messages",
            variable=self.save_msgs_var,
            command=self.save_options
        ).pack(anchor='w', pady=2)

        self.only_free_var = tk.BooleanVar(value=self.db.get_setting('only_free_llms', True))
        ttk.Checkbutton(
            options_frame,
            text="Use only free LLMs",
            variable=self.only_free_var,
            command=self.save_options
        ).pack(anchor='w', pady=2)

        self.monitor_chat_var = tk.BooleanVar(value=self.db.get_setting('monitor_chat', True))
        ttk.Checkbutton(
            options_frame,
            text="Monitor chat",
            variable=self.monitor_chat_var,
            command=self.save_options
        ).pack(anchor='w', pady=2)

        control_frame = ttk.Frame(parent)
        control_frame.pack(pady=20)

        self.start_btn = ttk.Button(control_frame, text="Start", command=self.start_bot)
        self.start_btn.pack(side='left', padx=5)

        self.stop_btn = ttk.Button(control_frame, text="Stop", command=self.stop_bot, state='disabled')
        self.stop_btn.pack(side='left', padx=5)

        self.status_label = ttk.Label(parent, text="Status: Stopped", font=('Arial', 12))
        self.status_label.pack(pady=10)

    def toggle_blacklist(self, role: str, var: tk.BooleanVar):
        if var.get():
            self.db.add_to_blacklist(role.lower())
        else:
            self.db.remove_from_blacklist(role.lower())

    def save_options(self):
        self.db.set_setting('remove_emoji', self.remove_emoji_var.get())
        self.db.set_setting('SAVE_ALL_MSGS', self.save_msgs_var.get())
        self.db.set_setting('only_free_llms', self.only_free_var.get())
        self.db.set_setting('monitor_chat', self.monitor_chat_var.get())

    def start_bot(self):
        self.start_btn.config(state='disabled')
        self.stop_btn.config(state='normal')
        self.status_label.config(text="Status: Running", foreground='green')
        self.db.set_setting('bot_enabled', True)

        asyncio.create_task(self.on_start())

    def stop_bot(self):
        self.start_btn.config(state='normal')
        self.stop_btn.config(state='disabled')
        self.status_label.config(text="Status: Stopped", foreground='red')
        self.db.set_setting('bot_enabled', False)

        asyncio.create_task(self.on_stop())

    def create_monitor_panel(self, parent):
        ttk.Label(parent, text="System Monitor", font=('Arial', 14, 'bold')).pack(pady=10)

        stats_frame = ttk.Frame(parent)
        stats_frame.pack(fill='x', padx=20, pady=10)

        self.queue_label = ttk.Label(stats_frame, text="Queue size: 0")
        self.queue_label.pack(side='left', padx=20)

        ttk.Label(parent, text="Event Log", font=('Arial', 12, 'bold')).pack(pady=5)

        self.log_text = scrolledtext.ScrolledText(parent, height=25, wrap=tk.WORD)
        self.log_text.pack(fill='both', expand=True, padx=20, pady=10)

    def log(self, message: str):
        self.log_text.insert(tk.END, message + '\n')
        self.log_text.see(tk.END)

    def update_queue_size(self, size: int):
        self.queue_label.config(text=f"Queue size: {size}")

    def run(self):
        self.root.mainloop()
