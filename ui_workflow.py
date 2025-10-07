"""
Модуль пользовательского интерфейса (UI) на базе tkinter
Предоставляет графический интерфейс для управления системой ботов
"""

import tkinter as tk
from tkinter import ttk, scrolledtext
import asyncio
from typing import Callable
from db import Database
from env_loader import env_loader
from logger import LogLevel

class UIWorkflow:
    """
    Главное окно UI системы
    Содержит 3 вкладки: Services, Bot Control, Monitor
    """

    def __init__(self, db: Database, on_start: Callable, on_stop: Callable):
        self.db = db
        self.on_start = on_start
        self.on_stop = on_stop

        # Главное окно
        self.root = tk.Tk()
        self.root.title("Telegram Bot RAG System")
        self.root.geometry("1100x750")

        # Список последних сообщений для отображения
        self.recent_messages = []
        self.max_recent_messages = 10

        self.create_ui()
        self.update_service_status()

    def create_ui(self):
        """Создание основного интерфейса с вкладками"""
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill='both', expand=True, padx=10, pady=10)

        # Вкладка 1: Статус сервисов
        services_frame = ttk.Frame(notebook)
        notebook.add(services_frame, text='Services')
        self.create_services_panel(services_frame)

        # Вкладка 2: Управление ботами
        control_frame = ttk.Frame(notebook)
        notebook.add(control_frame, text='Bot Control')
        self.create_control_panel(control_frame)

        # Вкладка 3: Монитор событий
        monitor_frame = ttk.Frame(notebook)
        notebook.add(monitor_frame, text='Monitor')
        self.create_monitor_panel(monitor_frame)

    def create_services_panel(self, parent):
        """
        Панель статуса сервисов
        Показывает наличие API ключей для каждого сервиса
        """
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

            # Индикатор: 🟢 ключ есть, 🔴 ключа нет
            indicator = ttk.Label(frame, text='●', font=('Arial', 20))
            indicator.pack(side='left', padx=10)

            self.service_indicators[env_key] = indicator

    def update_service_status(self):
        """Обновление индикаторов статуса сервисов"""
        for env_key, indicator in self.service_indicators.items():
            has_key = env_loader.has_key(env_key)
            indicator.config(text='🟢' if has_key else '🔴')

    def create_control_panel(self, parent):
        """
        Панель управления ботом
        Настройки ролей, опций и кнопки запуска/остановки
        """
        ttk.Label(parent, text="Bot Configuration", font=('Arial', 14, 'bold')).pack(pady=10)

        # Блок управления черным списком ролей
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

        # Блок опций
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

        # Блок уровня логирования
        log_level_frame = ttk.LabelFrame(parent, text="Log Level", padding=10)
        log_level_frame.pack(fill='x', padx=20, pady=10)

        self.log_level_var = tk.StringVar(value=self.db.get_setting('log_level', 'INFO'))

        for level in ['DEBUG', 'INFO', 'WARNING', 'ERROR']:
            ttk.Radiobutton(
                log_level_frame,
                text=level,
                variable=self.log_level_var,
                value=level,
                command=self.save_options
            ).pack(anchor='w', pady=2)

        # Кнопки управления
        control_frame = ttk.Frame(parent)
        control_frame.pack(pady=20)

        self.start_btn = ttk.Button(control_frame, text="Start", command=self.start_bot)
        self.start_btn.pack(side='left', padx=5)

        self.stop_btn = ttk.Button(control_frame, text="Stop", command=self.stop_bot, state='disabled')
        self.stop_btn.pack(side='left', padx=5)

        # Индикатор статуса
        self.status_label = ttk.Label(parent, text="Status: Stopped", font=('Arial', 12))
        self.status_label.pack(pady=10)

    def toggle_blacklist(self, role: str, var: tk.BooleanVar):
        """Добавление/удаление роли из черного списка"""
        if var.get():
            self.db.add_to_blacklist(role.lower())
        else:
            self.db.remove_from_blacklist(role.lower())

    def save_options(self):
        """Сохранение всех настроек в БД"""
        self.db.set_setting('remove_emoji', self.remove_emoji_var.get())
        self.db.set_setting('SAVE_ALL_MSGS', self.save_msgs_var.get())
        self.db.set_setting('only_free_llms', self.only_free_var.get())
        self.db.set_setting('monitor_chat', self.monitor_chat_var.get())
        self.db.set_setting('log_level', self.log_level_var.get())

    def start_bot(self):
        """Запуск бота"""
        self.start_btn.config(state='disabled')
        self.stop_btn.config(state='normal')
        self.status_label.config(text="Status: Running", foreground='green')
        self.db.set_setting('bot_enabled', True)

        asyncio.create_task(self.on_start())

    def stop_bot(self):
        """Остановка бота"""
        self.start_btn.config(state='normal')
        self.stop_btn.config(state='disabled')
        self.status_label.config(text="Status: Stopped", foreground='red')
        self.db.set_setting('bot_enabled', False)

        asyncio.create_task(self.on_stop())

    def create_monitor_panel(self, parent):
        """
        Панель мониторинга
        Отображает: статистику, последние сообщения, логи событий
        """
        ttk.Label(parent, text="System Monitor", font=('Arial', 14, 'bold')).pack(pady=5)

        # Статистика
        stats_frame = ttk.Frame(parent)
        stats_frame.pack(fill='x', padx=20, pady=5)

        self.queue_label = ttk.Label(stats_frame, text="Queue size: 0", font=('Arial', 10))
        self.queue_label.pack(side='left', padx=10)

        self.processed_label = ttk.Label(stats_frame, text="Processed: 0", font=('Arial', 10))
        self.processed_label.pack(side='left', padx=10)

        # Последние сообщения
        messages_frame = ttk.LabelFrame(parent, text="Recent Messages", padding=5)
        messages_frame.pack(fill='both', padx=20, pady=5, expand=False)

        self.messages_text = scrolledtext.ScrolledText(messages_frame, height=8, wrap=tk.WORD)
        self.messages_text.pack(fill='both', expand=True)

        # Настройка тегов для цветового выделения
        self.messages_text.tag_config('incoming', foreground='blue')
        self.messages_text.tag_config('outgoing', foreground='green')
        self.messages_text.tag_config('timestamp', foreground='gray')

        # Логи событий
        log_frame = ttk.LabelFrame(parent, text="Event Log", padding=5)
        log_frame.pack(fill='both', padx=20, pady=5, expand=True)

        self.log_text = scrolledtext.ScrolledText(log_frame, height=12, wrap=tk.WORD)
        self.log_text.pack(fill='both', expand=True)

        # Настройка тегов для уровней логирования
        self.log_text.tag_config('DEBUG', foreground='cyan')
        self.log_text.tag_config('INFO', foreground='green')
        self.log_text.tag_config('WARNING', foreground='orange')
        self.log_text.tag_config('ERROR', foreground='red')

    def add_log(self, level: LogLevel, message: str, component: str = "SYSTEM"):
        """
        Добавление лога с указанным уровнем
        Применяется цветовое выделение в зависимости от уровня
        """
        level_name = level.name

        # Вставка текста с тегом для цвета
        self.log_text.insert(tk.END, message + '\n', level_name)
        self.log_text.see(tk.END)

        # Ограничение размера лога (последние 1000 строк)
        lines = int(self.log_text.index('end-1c').split('.')[0])
        if lines > 1000:
            self.log_text.delete('1.0', f'{lines-1000}.0')

    def add_message(self, nick: str, text: str, is_incoming: bool = True):
        """
        Отображение сообщения в блоке Recent Messages
        is_incoming: True - входящее, False - исходящее
        """
        from datetime import datetime
        timestamp = datetime.now().strftime('%H:%M:%S')

        # Форматирование сообщения
        direction = "←" if is_incoming else "→"
        msg_type = 'incoming' if is_incoming else 'outgoing'

        # Вставка с цветовым выделением
        self.messages_text.insert(tk.END, f"[{timestamp}] ", 'timestamp')
        self.messages_text.insert(tk.END, f"{direction} {nick}: ", msg_type)
        self.messages_text.insert(tk.END, f"{text}\n")
        self.messages_text.see(tk.END)

        # Ограничение количества отображаемых сообщений
        lines = int(self.messages_text.index('end-1c').split('.')[0])
        if lines > 50:
            self.messages_text.delete('1.0', f'{lines-50}.0')

    def update_queue_size(self, size: int):
        """Обновление счетчика очереди"""
        self.queue_label.config(text=f"Queue size: {size}")

    def update_processed_count(self, count: int):
        """Обновление счетчика обработанных сообщений"""
        self.processed_label.config(text=f"Processed: {count}")

    def run(self):
        """Запуск главного цикла UI"""
        self.root.mainloop()
