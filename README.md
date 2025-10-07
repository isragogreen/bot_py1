# Telegram Bot RAG System

Автономная система управления Telegram-ботами с использованием LLM и RAG (Retrieval-Augmented Generation).

## Возможности

- 🤖 Множественные роли ботов (TECH, FRIEND, ADVISOR, AGITATOR, OPERATOR)
- 📚 RAG с автоматическим обновлением знаний из GitHub/GitLab
- 🎯 Автоматический скоринг и выбор оптимальной LLM-модели
- 🌐 Мультиязычная поддержка с автоматическим переводом
- 🔒 Система черного списка для фильтрации пользователей
- 💾 Persistent очереди и история сообщений
- 🎨 Графический интерфейс на tkinter
- ⚡ Проактивные агенты для вовлечения пользователей

## Установка

1. Установите зависимости:
```bash
pip install -r requirements.txt
```

2. Создайте `.env` файл на основе `.env.example` и заполните необходимые ключи:
```bash
cp .env.example .env
```

3. Обязательные переменные:
- `OPENROUTER_API_KEY` - для доступа к LLM моделям
- `TELEGRAM_BOT_TOKEN` - токен Telegram бота
- `PINECONE_API_KEY` или `QDRANT_API_KEY` - для vector database

4. Опциональные переменные:
- `TRANSLATE_API_KEY` - для Google Translate API
- `GITHUB_TOKEN` / `GITLAB_TOKEN` - для доступа к репозиториям
- `REPO_URL` - URL репозитория с документами

## Запуск

```bash
python main.py
```

## Архитектура

### Модули

- **main.py** - точка входа, координация UI и asyncio
- **ui_workflow.py** - графический интерфейс
- **main_workflow.py** - основная логика обработки сообщений
- **llm_subworkflow.py** - работа с LLM и скоринг моделей
- **rag_subworkflow.py** - vector database и RAG запросы
- **doc_processing.py** - обработка документов из репозиториев
- **chat_monitor.py** - интеграция с Telegram
- **proactive_workflow.py** - проактивные агенты
- **db.py** - работа с SQLite
- **env_loader.py** - загрузка конфигурации
- **translate.py** - мультиязычная поддержка
- **embeddings.py** - генерация векторов

### База данных

SQLite с таблицами:
- `settings` - настройки системы
- `queue` - очередь сообщений
- `history` - история диалогов
- `free_llms` - список моделей
- `model_scores` - результаты скоринга
- `llm_name` - привязка моделей к пользователям
- `blacklist` - черный список
- `doc_state` - состояние репозиториев

## Использование

### Панель управления

1. **Services** - статус API ключей
2. **Bot Control** - управление ботом и настройки
3. **Monitor** - логи и статистика

### Настройки

- **Role Blacklist** - отключение системных ролей
- **Remove emojis** - очистка эмодзи из сообщений
- **Save all messages** - сохранение всех сообщений
- **Only free LLMs** - использование только бесплатных моделей
- **Monitor chat** - отслеживание чата

### Скоринг моделей

Система автоматически:
1. Тестирует все модели при первом запуске
2. Для каждого пользователя выбирает топ-N моделей
3. Каждые M итераций обновляет рейтинг
4. Закрепляет лучшую модель за пользователем

### Проактивные агенты

При длительной неактивности (INACTIVITY_N * random(MIN, MAX) минут) AGITATOR отправляет сообщение оператору.

## Конфигурация

Основные параметры в `.env`:

```env
# Vector DB
VECTOR_DB=pinecone
EMBED_DIM=384
RAG_TOPK_DOCS=5
RAG_TOPK_USER=10

# Chunking
CHUNK_LENGTH=300
OVERLAP=50

# Scoring
SCORE_TOP_N=10
SCORE_REFRESH_EVERY=5
QUALITY_THRESHOLD=7.0
TRIAL_COUNT=3

# Proactive
INACTIVITY_N=10
RANDOM_MULTIPLIER_MIN=1
RANDOM_MULTIPLIER_MAX=5

# Temperatures
TECH_temp=0.1
FRIEND_temp=0.9
ADVISOR_temp=0.4
AGITATOR_temp=0.5
OPERATOR_temp=0.3
```

## Лицензия

MIT
