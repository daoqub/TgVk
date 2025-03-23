import logging
import importlib
import inspect
import asyncio
import sys
from pathlib import Path
from typing import Dict, Type

from aiogram import Bot, Dispatcher
from aiogram.types import ContentType

from config.settings import Config
from config.logging_config import setup_logging
from handlers.telegram.base_handler import BaseHandler
from services.vk.client import VkClient
from services.database.repository import DatabaseRepository
from config import supabase, cleanup_temp_files

def discover_handlers() -> Dict[str, Type[BaseHandler]]:
    """
    Автоматически обнаруживает все обработчики в директории handlers/telegram
    
    Returns:
        Dict[str, Type[BaseHandler]]: Словарь с обнаруженными обработчиками
    """
    handlers = {}
    handlers_dir = Path(__file__).parent / "handlers" / "telegram"
    
    # Игнорируем базовые и служебные файлы
    ignore_files = {"__init__.py", "base_handler.py"}
    
    for handler_file in handlers_dir.glob("*_handler.py"):
        if handler_file.name in ignore_files:
            continue
        
        try:
            # Получаем имя модуля (относительный импорт)
            module_name = f"handlers.telegram.{handler_file.stem}"
            
            # Динамически импортируем модуль
            module = importlib.import_module(module_name)
            
            # Ищем классы-обработчики в модуле
            for name, obj in inspect.getmembers(module, inspect.isclass):
                if issubclass(obj, BaseHandler) and obj != BaseHandler:
                    handlers[name] = obj
                    logging.info(f"Обнаружен обработчик: {name}")
        except Exception as e:
            logging.error(f"Ошибка при импорте обработчика {handler_file.name}: {e}")
    
    return handlers

async def main():
    """Основная функция запуска бота"""
    # Настройка логирования
    setup_logging()
    
    # Загрузка конфигурации
    config = Config()
    
    # Проверка обязательных настроек
    if not config.TELEGRAM_TOKEN:
        logging.critical("Отсутствует TELEGRAM_TOKEN в переменных окружения!")
        return
    
    # Очистка старых временных файлов при запуске
    cleanup_temp_files('./temp_files/')
    logging.info("Старые временные файлы очищены")
    
    # Инициализация клиентов
    vk_client = VkClient(max_retries=config.VK_API_MAX_RETRIES)
    
    # Инициализация репозитория базы данных
    db_repo = DatabaseRepository(supabase)
    
    # Инициализация Telegram бота
    bot = Bot(token=config.TELEGRAM_TOKEN)
    dp = Dispatcher(bot)
    
    # Обнаружение и инициализация обработчиков
    handler_classes = discover_handlers()
    
    # Регистрация обработчиков в диспетчере
    for name, handler_class in handler_classes.items():
        try:
            # Создаем экземпляр обработчика
            handler = handler_class(vk_client, db_repo, config)
            
            # Получаем типы контента, которые поддерживает обработчик
            content_types = getattr(handler, 'supported_content_types', [ContentType.TEXT])
            
            # Регистрируем обработчик
            dp.register_message_handler(
                handler.handle, 
                content_types=content_types
            )
            
            logging.info(f"Зарегистрирован обработчик {name} для типов контента: {content_types}")
        except Exception as e:
            logging.error(f"Ошибка при регистрации обработчика {name}: {e}")
    
    # Запуск бота
    try:
        logging.info("Бот запущен и готов к работе")
        await dp.start_polling(bot)
    except Exception as e:
        logging.error(f"Ошибка при запуске бота: {e}")
    finally:
        # Закрытие соединений
        logging.info("Бот завершил работу")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Бот остановлен вручную")
    except Exception as e:
        logging.critical(f"Критическая ошибка: {e}")
        sys.exit(1)
