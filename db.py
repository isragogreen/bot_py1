import sqlite3
import json
from datetime import datetime
from threading import Lock
from typing import Optional, List, Tuple, Any

class Database:
    def __init__(self, db_path: str = 'bot_system.db'):
        self.db_path = db_path
        self.lock = Lock()
        self._init_db()

    def _get_connection(self):
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self.lock:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS free_llms (
                    id TEXT PRIMARY KEY,
                    name TEXT
                )
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS queue (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nick TEXT,
                    text TEXT,
                    ts REAL
                )
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nick TEXT,
                    text TEXT,
                    ts REAL,
                    role TEXT
                )
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS llm_name (
                    nick TEXT PRIMARY KEY,
                    llm TEXT
                )
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS model_scores (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nick TEXT,
                    model TEXT,
                    score REAL,
                    UNIQUE(nick, model)
                )
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS blacklist (
                    nick TEXT PRIMARY KEY
                )
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS doc_state (
                    repo TEXT PRIMARY KEY,
                    commit_hash TEXT,
                    updated_ts REAL
                )
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS iteration_counter (
                    id INTEGER PRIMARY KEY,
                    count INTEGER DEFAULT 0
                )
            ''')
            cursor.execute('INSERT OR IGNORE INTO iteration_counter (id, count) VALUES (1, 0)')

            conn.commit()
            conn.close()

    def set_setting(self, key: str, value: Any):
        with self.lock:
            conn = self._get_connection()
            conn.execute('INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)',
                        (key, json.dumps(value)))
            conn.commit()
            conn.close()

    def get_setting(self, key: str, default=None):
        with self.lock:
            conn = self._get_connection()
            cursor = conn.execute('SELECT value FROM settings WHERE key = ?', (key,))
            row = cursor.fetchone()
            conn.close()

            if row:
                try:
                    return json.loads(row[0])
                except:
                    return row[0]
            return default

    def add_to_queue(self, nick: str, text: str):
        with self.lock:
            conn = self._get_connection()
            conn.execute('INSERT INTO queue (nick, text, ts) VALUES (?, ?, ?)',
                        (nick, text, datetime.now().timestamp()))
            conn.commit()
            conn.close()

    def get_queue_item(self) -> Optional[Tuple[int, str, str, float]]:
        with self.lock:
            conn = self._get_connection()
            cursor = conn.execute('SELECT id, nick, text, ts FROM queue ORDER BY id LIMIT 1')
            row = cursor.fetchone()
            conn.close()

            if row:
                return (row[0], row[1], row[2], row[3])
            return None

    def remove_from_queue(self, item_id: int):
        with self.lock:
            conn = self._get_connection()
            conn.execute('DELETE FROM queue WHERE id = ?', (item_id,))
            conn.commit()
            conn.close()

    def get_queue_size(self) -> int:
        with self.lock:
            conn = self._get_connection()
            cursor = conn.execute('SELECT COUNT(*) FROM queue')
            count = cursor.fetchone()[0]
            conn.close()
            return count

    def add_history(self, nick: str, text: str, role: str = 'user'):
        with self.lock:
            conn = self._get_connection()
            conn.execute('INSERT INTO history (nick, text, ts, role) VALUES (?, ?, ?, ?)',
                        (nick, text, datetime.now().timestamp(), role))
            conn.commit()
            conn.close()

    def get_history(self, nick: str, limit: int = 10) -> List[dict]:
        with self.lock:
            conn = self._get_connection()
            cursor = conn.execute(
                'SELECT text, ts, role FROM history WHERE nick = ? ORDER BY ts DESC LIMIT ?',
                (nick, limit)
            )
            rows = cursor.fetchall()
            conn.close()

            return [{'text': r[0], 'ts': r[1], 'role': r[2]} for r in reversed(rows)]

    def set_free_llms(self, llms: List[Tuple[str, str]]):
        with self.lock:
            conn = self._get_connection()
            conn.execute('DELETE FROM free_llms')
            conn.executemany('INSERT INTO free_llms (id, name) VALUES (?, ?)', llms)
            conn.commit()
            conn.close()

    def get_free_llms(self) -> List[Tuple[str, str]]:
        with self.lock:
            conn = self._get_connection()
            cursor = conn.execute('SELECT id, name FROM free_llms')
            rows = cursor.fetchall()
            conn.close()
            return [(r[0], r[1]) for r in rows]

    def set_model_score(self, nick: str, model: str, score: float):
        with self.lock:
            conn = self._get_connection()
            cursor = conn.execute(
                'SELECT score FROM model_scores WHERE nick = ? AND model = ?',
                (nick, model)
            )
            existing = cursor.fetchone()

            if existing:
                new_score = (existing[0] + score) / 2
                conn.execute(
                    'UPDATE model_scores SET score = ? WHERE nick = ? AND model = ?',
                    (new_score, nick, model)
                )
            else:
                conn.execute(
                    'INSERT INTO model_scores (nick, model, score) VALUES (?, ?, ?)',
                    (nick, model, score)
                )
            conn.commit()
            conn.close()

    def get_best_model_for_user(self, nick: str) -> Optional[str]:
        with self.lock:
            conn = self._get_connection()
            cursor = conn.execute(
                'SELECT model FROM model_scores WHERE nick = ? ORDER BY score DESC LIMIT 1',
                (nick,)
            )
            row = cursor.fetchone()
            conn.close()
            return row[0] if row else None

    def get_top_models(self, limit: int = 10) -> List[str]:
        with self.lock:
            conn = self._get_connection()
            cursor = conn.execute('''
                SELECT model, AVG(score) as avg_score
                FROM model_scores
                GROUP BY model
                ORDER BY avg_score DESC
                LIMIT ?
            ''', (limit,))
            rows = cursor.fetchall()
            conn.close()
            return [r[0] for r in rows]

    def set_user_model(self, nick: str, model: str):
        with self.lock:
            conn = self._get_connection()
            conn.execute('INSERT OR REPLACE INTO llm_name (nick, llm) VALUES (?, ?)',
                        (nick, model))
            conn.commit()
            conn.close()

    def get_user_model(self, nick: str) -> Optional[str]:
        with self.lock:
            conn = self._get_connection()
            cursor = conn.execute('SELECT llm FROM llm_name WHERE nick = ?', (nick,))
            row = cursor.fetchone()
            conn.close()
            return row[0] if row else None

    def add_to_blacklist(self, nick: str):
        with self.lock:
            conn = self._get_connection()
            conn.execute('INSERT OR IGNORE INTO blacklist (nick) VALUES (?)', (nick,))
            conn.commit()
            conn.close()

    def remove_from_blacklist(self, nick: str):
        with self.lock:
            conn = self._get_connection()
            conn.execute('DELETE FROM blacklist WHERE nick = ?', (nick,))
            conn.commit()
            conn.close()

    def is_blacklisted(self, nick: str) -> bool:
        with self.lock:
            conn = self._get_connection()
            cursor = conn.execute('SELECT 1 FROM blacklist WHERE nick = ?', (nick,))
            result = cursor.fetchone() is not None
            conn.close()
            return result

    def get_blacklist(self) -> List[str]:
        with self.lock:
            conn = self._get_connection()
            cursor = conn.execute('SELECT nick FROM blacklist')
            rows = cursor.fetchall()
            conn.close()
            return [r[0] for r in rows]

    def set_doc_state(self, repo: str, commit_hash: str):
        with self.lock:
            conn = self._get_connection()
            conn.execute(
                'INSERT OR REPLACE INTO doc_state (repo, commit_hash, updated_ts) VALUES (?, ?, ?)',
                (repo, commit_hash, datetime.now().timestamp())
            )
            conn.commit()
            conn.close()

    def get_doc_state(self, repo: str) -> Optional[str]:
        with self.lock:
            conn = self._get_connection()
            cursor = conn.execute('SELECT commit_hash FROM doc_state WHERE repo = ?', (repo,))
            row = cursor.fetchone()
            conn.close()
            return row[0] if row else None

    def increment_iteration(self) -> int:
        with self.lock:
            conn = self._get_connection()
            conn.execute('UPDATE iteration_counter SET count = count + 1 WHERE id = 1')
            cursor = conn.execute('SELECT count FROM iteration_counter WHERE id = 1')
            count = cursor.fetchone()[0]
            conn.commit()
            conn.close()
            return count

    def get_iteration_count(self) -> int:
        with self.lock:
            conn = self._get_connection()
            cursor = conn.execute('SELECT count FROM iteration_counter WHERE id = 1')
            count = cursor.fetchone()[0]
            conn.close()
            return count
