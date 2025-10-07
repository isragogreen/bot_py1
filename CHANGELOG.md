# Changelog

## v1.1 — Расширение логирования и UI (2025-10-08)

### Добавлено

- **Новая система логирования (`logger.py`):**
  - 4 уровня: DEBUG, INFO, WARNING, ERROR
  - Цветовая кодировка в консоли и UI
  - Компонентная структура (теги модулей)
  - Thread-safe передача логов в UI через callback
  - Фильтрация по уровням в реальном времени

- **Улучшенный UI Monitor:**
  - Счетчик обработанных сообщений
  - Блок Recent Messages (входящие/исходящие, цвет, стрелки, временные метки, лимит 50)
  - Event Log с цветовым выделением (лимит 1000 строк)
  - Выбор уровня логирования через радиокнопки (Bot Control)
  - Настройка уровня логирования сохраняется в БД и применяется динамически

- **Документация и комментарии:**
  - Русскоязычные docstrings и комментарии
  - Пошаговое описание процессов
  - Объяснение назначения каждой таблицы БД

### Изменено

- `main.py`: добавлен log_callback, улучшен ui_callback, расширена документация
- `main_workflow.py`: print заменён на logger, добавлены DEBUG-логи, пошаговое описание, счетчик сообщений, уведомления UI
- `ui_workflow.py`: новый блок статистики, отдельный ScrolledText для Recent Messages, цветовое выделение, методы add_message/add_log, увеличено окно до 1100x750px
- `README.md`: описание системы логирования, панели Monitor, цветовой кодировки, инструкции по выбору уровня логирования

### Технические детали

- Архитектура логирования: logger.py → main.py → ui_workflow.py
- Поток данных сообщений: Telegram → chat_monitor.py → main_workflow → ui_workflow

### Примеры логов и сообщений

```
[2025-10-07 14:30:15] [INFO   ] [MAIN] Main workflow initialized
[2025-10-07 14:30:16] [DEBUG  ] [RAG] Message upserted to RAG (namespace=user123)
[2025-10-07 14:30:17] [WARNING] [LLM] No model found for user123, using default
[2025-10-07 14:30:18] [ERROR  ] [TELEGRAM] Failed to send message: Connection timeout
```

```
[14:30:15] ← user123: Hello, how are you?
[14:30:17] → user123: I'm doing great! How can I help you today?
```

# Telegram RAG LLM Bot

## Описание

Автономная система управления Telegram-ботами с поддержкой Retrieval-Augmented Generation (RAG), скорингом моделей LLM, обработкой документов из репозитория и расширенным UI.

## Основные возможности

- Асинхронная обработка сообщений Telegram, перевод и работа с векторной БД
- Синхронная логика очереди, скоринга, Doc Processing
- UI на tkinter/ttk с вкладками: сервисы, управление ботами, монитор
- Хранение данных в SQLite
- Автоматическое обновление знаний из репозитория
- Скоринг и выбор оптимальной LLM для каждого пользователя
- Поддержка blacklist и proactive-агентов
- **Цветовая кодировка логов и сообщений**
- **Выбор уровня логирования в UI**
- **Мониторинг входящих/исходящих сообщений с временными метками**

## Архитектура логирования

```
logger.py (централизованный логгер)
    ↓
main.py (log_callback)
    ↓
ui_workflow.py (add_log с цветовым выделением)
```

## Поток данных сообщений

```
Telegram → chat_monitor.py
    ↓
main_workflow.handle_incoming_message()
    ↓ (callback: incoming_message)
ui_workflow.add_message(is_incoming=True)

main_workflow.process_message()
    ↓ (генерация ответа)
    ↓ (callback: outgoing_message)
ui_workflow.add_message(is_incoming=False)
```

## Использование

### Выбор уровня логирования

1. Откройте вкладку **Bot Control**
2. В секции **Log Level** выберите нужный уровень
3. Изменения применяются мгновенно

### Просмотр сообщений

- Вкладка **Monitor** → секция **Recent Messages**
- Синие (←) — входящие от пользователей
- Зеленые (→) — исходящие ответы бота
- Серые временные метки

### Мониторинг событий

- Вкладка **Monitor** → секция **Event Log**
- Цветовая кодировка по важности
- Прокрутка автоматически к последнему событию

## Примеры логов

```
[2025-10-07 14:30:15] [INFO   ] [MAIN] Main workflow initialized
[2025-10-07 14:30:16] [DEBUG  ] [RAG] Message upserted to RAG (namespace=user123)
[2025-10-07 14:30:17] [WARNING] [LLM] No model found for user123, using default
[2025-10-07 14:30:18] [ERROR  ] [TELEGRAM] Failed to send message: Connection timeout
```

## Примеры сообщений

```
[14:30:15] ← user123: Hello, how are you?
[14:30:17] → user123: I'm doing great! How can I help you today?
[14:30:25] ← user456: What's the weather like?
[14:30:27] → user456: I don't have access to weather data, but I can help with other questions!
```

## Лицензия

MIT
