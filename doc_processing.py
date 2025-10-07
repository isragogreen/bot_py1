import os
from env_loader import get_env
from db import Database
from error_handler import log_error
from langchain.text_splitter import RecursiveCharacterTextSplitter
from rag_subworkflow import rag
from translate import translator

# --- Конфигурация ---
REPO_NAME = get_env("REPO_NAME")
DOCS_FOLDER = get_env("DOCS_FOLDER")
CHUNK_LENGTH = int(get_env("CHUNK_LENGTH", 300))
OVERLAP = int(get_env("OVERLAP", 50))
SUPPORTED_EXTENSIONS = ['.md', '.txt', '.pdf']

class DocProcessing:
    """
    Класс для обработки документов из указанной папки репозитория.
    Синхронная логика: парсинг, чанкинг, перевод, embeddings, upsert.
    """

    def __init__(self, db: Database):
        self.db = db
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=CHUNK_LENGTH,
            chunk_overlap=OVERLAP,
            length_function=len
        )
        # Путь к папке с документами
        self.docs_path = os.path.join(REPO_NAME, DOCS_FOLDER)
        if not os.path.exists(self.docs_path):
            log_error(FileNotFoundError(f"Папка документов не найдена: {self.docs_path}"), "init")
            os.makedirs(self.docs_path)

    def get_latest_commit(self) -> str:
        """
        Получить последний commit-hash для папки документов.
        Используется только локальный репозиторий.
        """
        try:
            import subprocess
            result = subprocess.run(
                ["git", "-C", REPO_NAME, "rev-parse", "HEAD"],
                capture_output=True, text=True
            )
            return result.stdout.strip()
        except Exception as e:
            log_error(e, "get_latest_commit")
            return ""

    def process(self):
        """
        Основная функция обработки документов.
        Проверяет commit, парсит новые/изменённые документы.
        """
        latest_commit = self.get_latest_commit()
        if not latest_commit:
            print("Не удалось получить commit репозитория")
            return

        stored_commit = self.db.get_doc_state(self.docs_path)
        if stored_commit == latest_commit:
            print(f"Документы актуальны (commit: {latest_commit[:8]})")
            return

        print(f"Обработка новых документов (commit: {latest_commit[:8]})")
        self.process_documents()
        self.db.set_doc_state(self.docs_path, latest_commit)
        print("Документы обработаны успешно")

    def process_documents(self):
        """
        Обходит все файлы в docs_path и обрабатывает их.
        """
        for root, _, files in os.walk(self.docs_path):
            for file in files:
                if any(file.endswith(ext) for ext in SUPPORTED_EXTENSIONS):
                    file_path = os.path.join(root, file)
                    self.process_file(file_path)

    def process_file(self, file_path: str):
        """
        Обработка одного файла: чтение, чанкинг, перевод, upsert в RAG.
        """
        try:
            if not os.path.exists(file_path):
                log_error(FileNotFoundError(f"Файл не найден: {file_path}"), "process_file")
                return

            if file_path.endswith('.pdf'):
                text = self.extract_pdf_text(file_path)
            else:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    text = f.read()

            if not text.strip():
                return

            chunks = self.text_splitter.split_text(text)
            for chunk in chunks:
                translated = translator.translate_to_english(chunk)
                rag.upsert(chunk, '0', {'source': file_path})
                if translated != chunk:
                    rag.upsert(translated, '0', {'source': file_path, 'translated': True})

        except Exception as e:
            log_error(e, f"process_file:{file_path}")

    def extract_pdf_text(self, file_path: str) -> str:
        """
        Извлечение текста из PDF-файла.
        """
        try:
            import PyPDF2
            with open(file_path, 'rb') as f:
                reader = PyPDF2.PdfReader(f)
                text = ''
                for page in reader.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text
                return text
        except Exception as e:
            log_error(e, f"extract_pdf_text:{file_path}")
            return ""
