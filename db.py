import sqlite3
import json
import os
from datetime import datetime
from threading import Lock
from typing import Optional, List, Tuple, Any
from env_loader import get_env


DB_PATH = str(get_env("DB_PATH", "bot_db.sqlite3"))
HISTORY_LIMIT = int(get_env("HISTORY_LIMIT", 10))
SCORE_TOP_N = int(get_env("SCORE_TOP_N", 10))

class Database:
    """
    Класс для работы с базой данных SQLite.
    Все операции потокобезопасны, структура таблиц соответствует требованиям промта.
    """

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self.lock = Lock()
        self._init_db()

    def _get_connection(self):
        try:
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            return conn
        except Exception as e:
            print(f"Ошибка подключения к базе данных: {e}")
            raise

    def _init_db(self):
        """
        Инициализация базы данных.
        Создает все необходимые таблицы, если их нет.
        """
        db_exists = os.path.exists(self.db_path)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        # Основные таблицы
        tables_sql = {
            "settings": "CREATE TABLE IF NOT EXISTS settings (k TEXT PRIMARY KEY, v TEXT);",
            "free_llms": "CREATE TABLE IF NOT EXISTS free_llms (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE, is_active INTEGER DEFAULT 1);",
            "queue": "CREATE TABLE IF NOT EXISTS queue (id INTEGER PRIMARY KEY, nick TEXT, text TEXT, ts REAL);",
            "history": "CREATE TABLE IF NOT EXISTS history (id INTEGER PRIMARY KEY, nick TEXT, text TEXT, ts REAL, role TEXT);",
            "llm_name": "CREATE TABLE IF NOT EXISTS llm_name (nick TEXT PRIMARY KEY, llm TEXT);",
            "model_scores": "CREATE TABLE IF NOT EXISTS model_scores (nick TEXT, model TEXT, score REAL);",
            "blacklist": "CREATE TABLE IF NOT EXISTS blacklist (nick TEXT PRIMARY KEY);",
            "doc_state": "CREATE TABLE IF NOT EXISTS doc_state (repo TEXT PRIMARY KEY, commit_hash TEXT, updated_ts REAL);",
            "iteration_counter": "CREATE TABLE IF NOT EXISTS iteration_counter (id INTEGER PRIMARY KEY, count INTEGER);"
        }
        for sql in tables_sql.values():
            cursor.execute(sql)
        # Инициализация счетчика итераций
        cursor.execute("SELECT count(*) FROM iteration_counter WHERE id = 1")
        if cursor.fetchone()[0] == 0:
            cursor.execute("INSERT INTO iteration_counter (id, count) VALUES (1, 0)")
        conn.commit()
        conn.close()

    # --- Методы для settings ---
    def set_setting(self, key: str, value: Any):
        """Сохраняет настройку в таблицу settings."""
        with self.lock:
            conn = self._get_connection()
            conn.execute('INSERT OR REPLACE INTO settings (k, v) VALUES (?, ?)',
                        (key, json.dumps(value)))
            conn.commit()
            conn.close()

    def get_setting(self, key: str, default=None):
        """Получает настройку из таблицы settings."""
        with self.lock:
            conn = self._get_connection()
            cursor = conn.execute('SELECT v FROM settings WHERE k = ?', (key,))
            row = cursor.fetchone()
            conn.close()
            if row:
                try:
                    return json.loads(row[0])
                except Exception:
                    return row[0]
            return default

    # --- Методы для очереди сообщений ---
    def add_to_queue(self, nick: str, text: str):
        """Добавляет сообщение в очередь."""
        with self.lock:
            conn = self._get_connection()
            conn.execute('INSERT INTO queue (nick, text, ts) VALUES (?, ?, ?)',
                        (nick, text, datetime.now().timestamp()))
            conn.commit()
            conn.close()

    def get_queue_item(self) -> Optional[Tuple[int, str, str, float]]:
        """Получает первый элемент из очереди."""
        with self.lock:
            conn = self._get_connection()
            cursor = conn.execute('SELECT id, nick, text, ts FROM queue ORDER BY id LIMIT 1')
            row = cursor.fetchone()
            conn.close()
            if row:
                return (row[0], row[1], row[2], row[3])
            return None

    def remove_from_queue(self, item_id: int):
        """Удаляет элемент из очереди по id."""
        with self.lock:
            conn = self._get_connection()
            conn.execute('DELETE FROM queue WHERE id = ?', (item_id,))
            conn.commit()
            conn.close()

    def get_queue_size(self) -> int:
        """Возвращает размер очереди."""
        with self.lock:
            conn = self._get_connection()
            cursor = conn.execute('SELECT COUNT(*) FROM queue')
            count = cursor.fetchone()[0]
            conn.close()
            return count

    # --- Методы для истории сообщений ---
    def add_history(self, nick: str, text: str, role: str = 'user'):
        """Добавляет сообщение в историю."""
        with self.lock:
            conn = self._get_connection()
            conn.execute('INSERT INTO history (nick, text, ts, role) VALUES (?, ?, ?, ?)',
                        (nick, text, datetime.now().timestamp(), role))
            conn.commit()
            conn.close()

    def get_history(self, nick: str, limit: Optional[int] = None) -> List[dict]:
        """
        Получает историю сообщений пользователя.
        Лимит задается через переменную окружения HISTORY_LIMIT.
        """
        if limit is None:
            limit = HISTORY_LIMIT
        with self.lock:
            conn = self._get_connection()
            cursor = conn.execute(
                'SELECT text, ts, role FROM history WHERE nick = ? ORDER BY ts DESC LIMIT ?',
                (nick, limit)
            )
            rows = cursor.fetchall()
            conn.close()
            return [{'text': r[0], 'ts': r[1], 'role': r[2]} for r in reversed(rows)]

    # --- Методы для моделей LLM ---
    def set_free_llms(self, llms: List[str]):
        """
        Мягкое обновление списка моделей: актуальные is_active=1, устаревшие is_active=0.
        """
        with self.lock:
            conn = self._get_connection()
            # Сначала помечаем все как неактивные
            conn.execute('UPDATE free_llms SET is_active = 0')
            # Затем добавляем или обновляем актуальные
            for name in llms:
                cursor = conn.execute('SELECT id FROM free_llms WHERE name = ?', (name,))
                row = cursor.fetchone()
                if row:
                    conn.execute('UPDATE free_llms SET is_active = 1 WHERE name = ?', (name,))
                else:
                    conn.execute('INSERT INTO free_llms (name, is_active) VALUES (?, 1)', (name,))
            conn.commit()
            conn.close()

    def get_free_llms(self) -> List[Tuple[int, str]]:
        """Получает список бесплатных моделей."""
        with self.lock:
            conn = self._get_connection()
            cursor = conn.execute('SELECT id, name FROM free_llms')
            rows = cursor.fetchall()
            conn.close()
            return [(r[0], r[1]) for r in rows]

    def get_active_llms(self) -> List[str]:
        """Получает список активных моделей."""
        with self.lock:
            conn = self._get_connection()
            cursor = conn.execute('SELECT name FROM free_llms WHERE is_active = 1')
            rows = cursor.fetchall()
            conn.close()
            return [r[0] for r in rows]

    # --- Методы для скоринга моделей ---
    def set_model_score(self, model: str, score: float):
        """
        Добавляет новую оценку модели, нормализует средний скоринг.
        Скоринг глобальный, не зависит от пользователя.
        """
        with self.lock:
            conn = self._get_connection()
            cursor = conn.execute(
                'SELECT score_sum, score_count FROM model_scores WHERE model = ?',
                (model,)
            )
            existing = cursor.fetchone()
            if existing:
                score_sum = existing[0] + score
                score_count = existing[1] + 1
                avg_score = score_sum / score_count
                conn.execute(
                    'UPDATE model_scores SET score_sum = ?, score_count = ?, avg_score = ? WHERE model = ?',
                    (score_sum, score_count, avg_score, model)
                )
            else:
                conn.execute(
                    'INSERT INTO model_scores (model, score_sum, score_count, avg_score) VALUES (?, ?, ?, ?)',
                    (model, score, 1, score)
                )
            conn.commit()
            conn.close()

    def get_best_model(self) -> Optional[str]:
        """
        Получает модель с максимальным средним скорингом.
        """
        with self.lock:
            conn = self._get_connection()
            cursor = conn.execute(
                'SELECT model FROM model_scores ORDER BY avg_score DESC LIMIT 1'
            )
            row = cursor.fetchone()
            conn.close()
            return row[0] if row else None

    def get_top_models(self, limit: int = None) -> List[str]:
        """
        Получает топ моделей по среднему скору.
        Лимит задается через SCORE_TOP_N.
        """
        if limit is None:
            limit = SCORE_TOP_N
        with self.lock:
            conn = self._get_connection()
            cursor = conn.execute('''
                SELECT model FROM model_scores
                ORDER BY avg_score DESC
                LIMIT ?
            ''', (limit,))
            rows = cursor.fetchall()
            conn.close()
            return [r[0] for r in rows]

    def set_user_model(self, nick: str, model: str):
        """Закрепляет модель за пользователем."""
        with self.lock:
            conn = self._get_connection()
            conn.execute('INSERT OR REPLACE INTO llm_name (nick, llm) VALUES (?, ?)',
                        (nick, model))
            conn.commit()
            conn.close()

    def get_user_model(self, nick: str) -> Optional[str]:
        """Получает закрепленную модель пользователя."""
        with self.lock:
            conn = self._get_connection()
            cursor = conn.execute('SELECT llm FROM llm_name WHERE nick = ?', (nick,))
            row = cursor.fetchone()
            conn.close()
            return row[0] if row else None

    # --- Методы для blacklist ---
    def add_to_blacklist(self, nick: str):
        """Добавляет пользователя в черный список."""
        with self.lock:
            conn = self._get_connection()
            conn.execute('INSERT OR IGNORE INTO blacklist (nick) VALUES (?)', (nick,))
            conn.commit()
            conn.close()

    def remove_from_blacklist(self, nick: str):
        """Удаляет пользователя из черного списка."""
        with self.lock:
            conn = self._get_connection()
            conn.execute('DELETE FROM blacklist WHERE nick = ?', (nick,))
            conn.commit()
            conn.close()

    def is_blacklisted(self, nick: str) -> bool:
        """Проверяет, находится ли пользователь в черном списке."""
        with self.lock:
            conn = self._get_connection()
            cursor = conn.execute('SELECT 1 FROM blacklist WHERE nick = ?', (nick,))
            result = cursor.fetchone() is not None
            conn.close()
            return result

    def get_blacklist(self) -> List[str]:
        """Получает список всех пользователей в черном списке."""
        with self.lock:
            conn = self._get_connection()
            cursor = conn.execute('SELECT nick FROM blacklist')
            rows = cursor.fetchall()
            conn.close()
            return [r[0] for r in rows]

    # --- Методы для состояния документов ---
    def set_doc_state(self, repo: str, commit_hash: str):
        """Сохраняет состояние документов (commit)."""
        with self.lock:
            conn = self._get_connection()
            conn.execute(
                'INSERT OR REPLACE INTO doc_state (repo, commit_hash, updated_ts) VALUES (?, ?, ?)',
                (repo, commit_hash, datetime.now().timestamp())
            )
            conn.commit()
            conn.close()

    def get_doc_state(self, repo: str) -> Optional[str]:
        """Получает commit-hash для указанного репозитория."""
        with self.lock:
            conn = self._get_connection()
            cursor = conn.execute('SELECT commit_hash FROM doc_state WHERE repo = ?', (repo,))
            row = cursor.fetchone()
            conn.close()
            return row[0] if row else None

    # --- Методы для итераций скоринга ---
    def increment_iteration(self) -> int:
        """Увеличивает счетчик итераций скоринга."""
        with self.lock:
            conn = self._get_connection()
            conn.execute('UPDATE iteration_counter SET count = count + 1 WHERE id = 1')
            cursor = conn.execute('SELECT count FROM iteration_counter WHERE id = 1')
            count = cursor.fetchone()[0]
            conn.commit()
            conn.close()
            return count

    def get_iteration_count(self) -> int:
        """Получает текущее значение счетчика итераций."""
        with self.lock:
            conn = self._get_connection()
            cursor = conn.execute('SELECT count FROM iteration_counter WHERE id = 1')
            count = cursor.fetchone()[0]
            conn.close()
            return count
