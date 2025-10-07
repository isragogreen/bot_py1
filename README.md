# Telegram RAG LLM Bot

## Описание

Автономная система управления Telegram-ботами с поддержкой Retrieval-Augmented Generation (RAG), скорингом моделей LLM, обработкой документов из репозитория и простым UI.

## Основные возможности

- Асинхронная обработка сообщений Telegram, перевод и работа с векторной БД
- Синхронная логика очереди, скоринга, Doc Processing
- UI на tkinter/ttk (без ручного ввода токенов/чисел)
- Хранение данных в SQLite
- Автоматическое обновление знаний из репозитория
- Скоринг и выбор оптимальной LLM для каждого пользователя
- Поддержка blacklist и proactive-агентов

## Установка

```bash
pip install -r requirements.txt
```

## Запуск

```bash
python main.py
```

## Конфигурация

Все параметры задаются в `.env` (см. пример в репозитории).

## Структура проекта

- `main.py` — точка входа
- `ui_workflow.py` — пользовательский интерфейс
- `main_workflow.py` — основная логика
- `db.py` — работа с SQLite
- `doc_processing.py` — обработка документов
- `llm_subworkflow.py` — работа с LLM и скоринг
- `rag_subworkflow.py` — запросы к RAG
- `proactive_workflow.py` — проактивные агенты
- `chat_monitor.py` — Telegram-интеграция
- `translate.py` — переводчик
- `embeddings.py` — генерация эмбеддингов

## Лицензия

MIT
