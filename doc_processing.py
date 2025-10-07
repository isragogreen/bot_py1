import asyncio
import os
import tempfile
import shutil
from pathlib import Path
from typing import List, Optional
from git import Repo
from github import Github
from gitlab import Gitlab
from langchain.text_splitter import RecursiveCharacterTextSplitter
from rag_subworkflow import rag
from translate import translator
from env_loader import env_loader
from db import Database

class DocProcessing:
    def __init__(self, db: Database):
        self.db = db
        self.repo_url = env_loader.get('REPO_URL')
        self.github_token = env_loader.get('GITHUB_TOKEN')
        self.gitlab_token = env_loader.get('GITLAB_TOKEN')
        self.chunk_length = env_loader.get_int('CHUNK_LENGTH', 300)
        self.overlap = env_loader.get_int('OVERLAP', 50)

        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_length,
            chunk_overlap=self.overlap,
            length_function=len
        )

    async def get_latest_commit(self) -> Optional[str]:
        if not self.repo_url:
            return None

        try:
            if 'github.com' in self.repo_url and self.github_token:
                repo_path = self.repo_url.split('github.com/')[-1].replace('.git', '')
                g = Github(self.github_token)
                repo = g.get_repo(repo_path)
                return repo.get_commits()[0].sha

            elif 'gitlab.com' in self.repo_url and self.gitlab_token:
                repo_path = self.repo_url.split('gitlab.com/')[-1].replace('.git', '')
                gl = Gitlab('https://gitlab.com', private_token=self.gitlab_token)
                project = gl.projects.get(repo_path.replace('/', '%2F'))
                commits = project.commits.list(per_page=1)
                return commits[0].id if commits else None
        except Exception as e:
            print(f"Error getting latest commit: {e}")

        return None

    async def clone_and_process(self):
        if not self.repo_url:
            print("No repository URL configured")
            return

        latest_commit = await self.get_latest_commit()
        if not latest_commit:
            print("Could not fetch latest commit")
            return

        stored_commit = self.db.get_doc_state(self.repo_url)

        if stored_commit == latest_commit:
            print(f"Repository is up to date (commit: {latest_commit[:8]})")
            return

        print(f"Processing repository update (new commit: {latest_commit[:8]})")

        temp_dir = tempfile.mkdtemp()

        try:
            if self.github_token and 'github.com' in self.repo_url:
                auth_url = self.repo_url.replace('https://', f'https://{self.github_token}@')
            elif self.gitlab_token and 'gitlab.com' in self.repo_url:
                auth_url = self.repo_url.replace('https://', f'https://oauth2:{self.gitlab_token}@')
            else:
                auth_url = self.repo_url

            Repo.clone_from(auth_url, temp_dir)

            await self.process_documents(temp_dir)

            self.db.set_doc_state(self.repo_url, latest_commit)

            print(f"Repository processed successfully")

        except Exception as e:
            print(f"Error processing repository: {e}")

        finally:
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)

    async def process_documents(self, repo_path: str):
        supported_extensions = ['.md', '.txt', '.pdf']

        for root, _, files in os.walk(repo_path):
            for file in files:
                if any(file.endswith(ext) for ext in supported_extensions):
                    file_path = os.path.join(root, file)
                    await self.process_file(file_path)

    async def process_file(self, file_path: str):
        try:
            if file_path.endswith('.pdf'):
                text = self.extract_pdf_text(file_path)
            else:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    text = f.read()

            if not text.strip():
                return

            chunks = self.text_splitter.split_text(text)

            for chunk in chunks:
                translated = await translator.translate_to_english(chunk)

                await rag.upsert(chunk, '0', {'source': file_path})

                if translated != chunk:
                    await rag.upsert(translated, '0', {'source': file_path, 'translated': True})

        except Exception as e:
            print(f"Error processing file {file_path}: {e}")

    def extract_pdf_text(self, file_path: str) -> str:
        try:
            import PyPDF2
            with open(file_path, 'rb') as f:
                reader = PyPDF2.PdfReader(f)
                text = ''
                for page in reader.pages:
                    text += page.extract_text()
                return text
        except Exception as e:
            print(f"Error extracting PDF text: {e}")
            return ''
