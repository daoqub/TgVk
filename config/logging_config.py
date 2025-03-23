# config/logging_config.py
import logging
import os
from pathlib import Path

def setup_logging(log_level=logging.INFO, log_file="bot.log"):
    """Настройка системы логирования приложения"""
    
    # Создаем директорию для логов, если она не существует
    log_dir = os.path.dirname(log_file)
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    # Форматирование логов
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    date_format = '%Y-%m-%d %H:%M:%S'
    formatter = logging.Formatter(log_format, date_format)
    
    # Настройка корневого логгера
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # Очищаем существующие обработчики
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Обработчик для вывода в консоль
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # Обработчик для записи в файл с ротацией
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)
    
    # Отключаем лишнее логирование от библиотек
    logging.getLogger('supabase').setLevel(logging.WARNING)
    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('httpcore').setLevel(logging.WARNING)
    
    # Логирование необработанных исключений
    def handle_exception(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            # Стандартная обработка для Ctrl+C
            return
        
        root_logger.error("Необработанное исключение", exc_info=(exc_type, exc_value, exc_traceback))
    
    # Установка обработчика необработанных исключений
    import sys
    sys.excepthook = handle_exception
    
    logging.info("Система логирования инициализирована")
