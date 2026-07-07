# Руководство по тестированию CodeRAG

## Предварительные требования

Перед запуском системы убедитесь, что у вас установлены:

1. **Python 3.9+**
2. **Docker и Docker Compose** (для полного функционала)
3. **Node.js** (для frontend, если потребуется)

## Структура проекта

```
.
├── backend/                 # Backend API и логика
│   ├── app/
│   │   ├── core/           # Ядро системы
│   │   ├── ingestion/      # Обработка репозиториев
│   │   ├── api/            # REST API эндпоинты
│   │   └── models/         # Модели данных
├── frontend/               # Frontend интерфейс
├── data/                   # Данные
│   ├── qdrant_storage/     # Хранилище векторов
│   └── repos/              # Клонированные репозитории
├── docker-compose.yml      # Конфигурация Docker
├── Dockerfile              # Dockerfile для backend
├── Dockerfile.ui           # Dockerfile для frontend
├── requirements.txt        # Зависимости Python
└── README.md               # Основная документация
```

## Запуск системы

### Вариант 1: Через Docker (рекомендуется)

```bash
# Сборка и запуск контейнеров
docker-compose up --build

# Для фонового запуска
docker-compose up -d --build
```

Сервисы будут доступны по адресам:
- **Backend API**: http://localhost:8000
- **Swagger UI**: http://localhost:8000/docs
- **Frontend UI**: http://localhost:8501

### Вариант 2: Локальный запуск

1. Установите зависимости:
```bash
pip install -r requirements.txt
```

2. Запустите необходимые сервисы вручную:
   - Qdrant (векторное хранилище)
   - MongoDB (если используется)

3. Запустите backend:
```bash
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
```

4. Запустите frontend:
```bash
streamlit run frontend/streamlit_app.py
```

## Тестирование API

После запуска API будет доступен по адресу: http://localhost:8000/docs

### Основные эндпоинты:

1. **POST /api/repo/clone** - Клонирование репозитория
2. **POST /api/chat** - Чат с репозиторием
3. **POST /api/search** - Поиск по коду
4. **GET /api/health** - Проверка состояния

### Примеры запросов:

#### Клонирование репозитория:
```json
{
  "repo_url": "https://github.com/user/repo",
  "branch": "main",
  "force_reindex": false
}
```

#### Чат с репозиторием:
```json
{
  "repo_url": "https://github.com/user/repo",
  "question": "How does authorization work?",
  "max_chunks": 15,
  "stream": false
}
```

#### Поиск по коду:
```json
{
  "repo_url": "https://github.com/user/repo",
  "query": "authorization function",
  "top_k": 10,
  "language": "python",
  "symbol_type": "function"
}
```

## Тестирование функциональности

### 1. Проверка структуры проекта

Запустите тест структуры:
```bash
python tests/test_system_structure.py
```

### 2. Тестирование API эндпоинтов

После запуска контейнеров можно использовать Swagger UI для тестирования всех эндпоинтов.

### 3. Тестирование UI

После запуска frontend будет доступен по адресу: http://localhost:8501

## Настройка переменных окружения

Создайте файл `.env` на основе `.env.example`:

```bash
cp .env.example .env
```

Обязательные переменные:
- `DEEPSEEK_API_KEY` - API ключ для DeepSeek
- `DEEPSEEK_BASE_URL` - URL API DeepSeek
- `DEEPSEEK_MODEL` - Используемая модель

## Пример ответа от системы

При успешном запросе к чату вы получите ответ в формате:

```json
{
  "answer": "The authorization works by...",
  "sources": [
    {
      "file_path": "auth/login.py",
      "start_line": 42,
      "end_line": 58,
      "symbol_name": "login_user",
      "symbol_type": "function",
      "snippet": "def login_user(username, password):",
      "relevance_score": 0.95,
      "github_url": "https://github.com/user/repo/blob/main/auth/login.py#L42"
    }
  ],
  "repo_name": "user/repo",
  "question": "How does authorization work?"
}
```

## Решение проблем

### Если Docker не запускается:
1. Убедитесь, что Docker Desktop установлен
2. Проверьте, запущен ли Docker daemon
3. Попробуйте запустить команду от имени администратора

### Если API не отвечает:
1. Проверьте логи контейнеров: `docker-compose logs`
2. Убедитесь, что все порты свободны
3. Проверьте переменные окружения

### Если нет ответа от LLM:
1. Проверьте правильность API ключа
2. Убедитесь, что DeepSeek API доступен
3. Проверьте настройки модели

## Дополнительные инструменты

Для разработки и тестирования рекомендуются:

1. **Postman** - для тестирования API
2. **curl** - для командной строки тестов
3. **VSCode** - с плагинами для Python и Docker
4. **Streamlit** - для интерактивного UI тестирования

## Поддержка

Если возникнут проблемы с запуском, обратитесь к документации или создайте issue в репозитории.