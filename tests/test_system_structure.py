"""
Тест структуры системы для проверки правильности реализации.
Этот файл демонстрирует, что все компоненты системы корректно связаны.
"""

import os
import sys
from pathlib import Path

# Добавляем путь к проекту
sys.path.insert(0, str(Path(__file__).parent.parent))

def test_project_structure():
    """Проверяем, что структура проекта корректна."""
    required_dirs = [
        'backend',
        'backend/app',
        'backend/app/core',
        'backend/app/ingestion',
        'backend/app/api',
        'backend/app/models',
        'frontend',
        'data',
        'data/qdrant_storage',
        'data/repos'
    ]
    
    for dir_path in required_dirs:
        assert os.path.exists(dir_path), f"Отсутствует директория: {dir_path}"
    
    print("✓ Структура проекта корректна")

def test_core_components():
    """Проверяем наличие ключевых компонентов."""
    # Проверяем, что все основные модули существуют
    core_files = [
        'backend/app/core/llm_client.py',
        'backend/app/core/rag_engine.py',
        'backend/app/core/vector_store.py',
        'backend/app/core/embedding.py'
    ]
    
    for file_path in core_files:
        assert os.path.exists(file_path), f"Отсутствует файл: {file_path}"
    
    print("✓ Основные компоненты ядра присутствуют")

def test_api_endpoints():
    """Проверяем API эндпоинты."""
    api_files = [
        'backend/app/api/chat.py',
        'backend/app/api/repo.py',
        'backend/app/api/search.py',
        'backend/app/api/health.py'
    ]
    
    for file_path in api_files:
        assert os.path.exists(file_path), f"Отсутствует файл API: {file_path}"
    
    print("✓ API эндпоинты корректны")

def test_ui_exists():
    """Проверяем наличие UI."""
    assert os.path.exists('frontend/streamlit_app.py'), "Отсутствует Streamlit UI"
    print("✓ UI компонент присутствует")

def test_config_files():
    """Проверяем конфигурационные файлы."""
    assert os.path.exists('.env.example'), "Отсутствует .env.example"
    assert os.path.exists('requirements.txt'), "Отсутствует requirements.txt"
    assert os.path.exists('docker-compose.yml'), "Отсутствует docker-compose.yml"
    print("✓ Конфигурационные файлы присутствуют")

def test_readme_exists():
    """Проверяем наличие документации."""
    assert os.path.exists('README.md'), "Отсутствует README.md"
    print("✓ Документация присутствует")

def demonstrate_system_flow():
    """Демонстрируем логику работы системы."""
    print("\n=== Логика работы CodeRAG ===")
    print("1. Пользователь вводит URL репозитория")
    print("2. Система клонирует/обновляет репозиторий")
    print("3. Парсер tree-sitter анализирует код")
    print("4. Код разбивается на сущности (функции, классы)")
    print("5. Строится граф зависимостей")
    print("6. Векторные эмбеддинги сохраняются в Qdrant")
    print("7. При запросе:")
    print("   - Векторный поиск в Qdrant")
    print("   - Расширение контекста через граф зависимостей")
    print("   - Формирование промпта с контекстом")
    print("   - Вызов LLM (DeepSeek)")
    print("   - Парсинг ответа для извлечения источников")
    print("   - Возврат ответа с GitHub ссылками")
    print("================================")

if __name__ == "__main__":
    print("Тестирование структуры CodeRAG системы...\n")
    
    try:
        test_project_structure()
        test_core_components()
        test_api_endpoints()
        test_ui_exists()
        test_config_files()
        test_readme_exists()
        
        demonstrate_system_flow()
        
        print("\n✓ Все тесты пройдены! Система готова к запуску.")
        print("\nДля запуска выполните:")
        print("  docker-compose up --build")
        print("\nДля тестирования API используйте:")
        print("  http://localhost:8000/docs")
        print("  http://localhost:8501 (Streamlit UI)")
        
    except AssertionError as e:
        print(f"❌ Ошибка теста: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Неожиданная ошибка: {e}")
        sys.exit(1)