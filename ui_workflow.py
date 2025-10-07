"""
Модуль пользовательского интерфейса (UI) на tkinter/ttk.
Три вкладки: сервисы, управление ботами, монитор.
"""

import tkinter as tk
from tkinter import ttk
from env_loader import get_env
from logger import logger

class UIWorkflow:
    """
    Класс для управления пользовательским интерфейсом.
    """

    def __init__(self, main_workflow):
        self.main_workflow = main_workflow
        self.root = tk.Tk()
        self.root.title("Telegram RAG LLM Bot")
        self.root.geometry("900x600")
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.create_widgets()

    def create_widgets(self):
        """
        Создает все элементы интерфейса.
        """
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill='both', expand=True)

        # Вкладка сервисов
        frame_services = ttk.Frame(notebook)
        notebook.add(frame_services, text="Сервисы")
        self._init_services_tab(frame_services)

        # Вкладка управления ботами
        frame_bots = ttk.Frame(notebook)
        notebook.add(frame_bots, text="Боты")
        self._init_bots_tab(frame_bots)

        # Вкладка мониторинга
        frame_monitor = ttk.Frame(notebook)
        notebook.add(frame_monitor, text="Монитор")
        self._init_monitor_tab(frame_monitor)

    def _init_services_tab(self, frame):
        """
        Инициализация вкладки сервисов.
        """
        services = [
            ("OpenRouter", "OPENROUTER_API_KEY"),
            ("Pinecone", "PINECONE_API_KEY"),
            ("Qdrant", "QDRANT_API_KEY"),
            ("Translator", "TRANSLATE_API_KEY"),
            ("Telegram", "TELEGRAM_BOT_TOKEN"),
            ("GitHub/GitLab", "REPO_NAME")
        ]
        for idx, (name, env_key) in enumerate(services):
            key = get_env(env_key)
            status = "🟢" if key else "🔴"
            label = ttk.Label(frame, text=f"{name}: {status}")
            label.grid(row=idx, column=0, sticky="w", padx=10, pady=5)

    def _init_bots_tab(self, frame):
        """
        Инициализация вкладки управления ботами.
        """
        roles = ["TECH", "FRIEND", "ADVISOR", "AGITATOR", "OPERATOR"]
        self.role_vars = {}
        for idx, role in enumerate(roles):
            var = tk.BooleanVar()
            chk = ttk.Checkbutton(frame, text=role, variable=var)
            chk.grid(row=idx, column=0, sticky="w", padx=10, pady=5)
            self.role_vars[role] = var

        # Кнопки управления
        btn_start = ttk.Button(frame, text="Start", command=self.on_start)
        btn_stop = ttk.Button(frame, text="Stop", command=self.on_stop)
        btn_save = ttk.Button(frame, text="Save settings", command=self.on_save)
        btn_start.grid(row=0, column=1, padx=10)
        btn_stop.grid(row=1, column=1, padx=10)
        btn_save.grid(row=2, column=1, padx=10)

    def _init_monitor_tab(self, frame):
        """
        Инициализация вкладки мониторинга.
        """
        # Лог событий
        self.log_text = tk.Text(frame, height=15, width=100)
        self.log_text.pack(fill='x', expand=False)
        logger.set_ui_callback(self._ui_log_callback)

        # Окно сообщений и ответов
        self.msg_text = tk.Text(frame, height=10, width=100, bg="#f0f0f0")
        self.msg_text.pack(fill='both', expand=True)

        # Пример: статус очереди
        self.status_label = ttk.Label(frame, text="Статус: ожидание")
        self.status_label.pack(anchor="w", padx=10, pady=5)

    def _ui_log_callback(self, level, msg, component):
        """
        Callback для вывода логов в UI.
        """
        self.log_text.insert(tk.END, f"{msg}\n")
        self.log_text.see(tk.END)

    def on_start(self):
        """
        Обработчик кнопки Start.
        """
        logger.info("Бот запущен", "UI")
        self.main_workflow.start_processing()

    def on_stop(self):
        """
        Обработчик кнопки Stop.
        """
        logger.info("Бот остановлен", "UI")
        self.main_workflow.stop_processing()

    def on_save(self):
        """
        Обработчик кнопки Save settings.
        """
        logger.info("Настройки сохранены", "UI")
        # TODO: Реализовать сохранение настроек в базу

    def on_close(self):
        """
        Обработчик закрытия окна.
        """
        logger.info("UI закрыт", "UI")
        self.root.destroy()

    def run(self):
        """
        Запуск интерфейса.
        """
        self.root.mainloop()
