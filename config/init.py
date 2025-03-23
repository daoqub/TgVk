#init.py
import os
import logging
import time
from datetime import datetime, timezone
from supabase import create_client, Client
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("bot.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)

# Отключаем лишнее логирование от библиотек
logging.getLogger('supabase').setLevel(logging.WARNING)
logging.getLogger('httpx').setLevel(logging.WARNING)
logging.getLogger('httpcore').setLevel(logging.WARNING)

# Инициализация Supabase
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')

supabase = None
if SUPABASE_URL and SUPABASE_KEY:
    try:
        supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
        logging.info("Supabase клиент успешно инициализирован")
    except Exception as e:
        logging.critical(f"Не удалось инициализировать Supabase клиент: {e}")
else:
    logging.warning("Данные для подключения к Supabase отсутствуют в переменных окружения")

# Константы API
TELEGRAM_API_TOKEN = os.getenv('TELEGRAM_API_TOKEN')
VK_CLIENT_ID = os.getenv('VK_CLIENT_ID')
VK_CLIENT_SECRET = os.getenv('VK_CLIENT_SECRET')

def format_owner_id(target_id):
    """Форматирует ID группы ВКонтакте в правильный формат owner_id"""
    try:
        str_id = str(target_id).strip()
        if str_id.startswith('-'):
            return int(str_id)
        else:
            return -1 * int(str_id)
    except (ValueError, TypeError) as e:
        logging.error(f"Ошибка при форматировании owner_id: {e}")
        return -1 * abs(int(target_id))

def cleanup_temp_files(directory='./files/', max_age_hours=24):
    """Очищает временные файлы старше указанного возраста"""
    try:
        if not os.path.exists(directory):
            return
            
        current_time = time.time()
        for filename in os.listdir(directory):
            file_path = os.path.join(directory, filename)
            if os.path.isfile(file_path) and current_time - os.path.getmtime(file_path) > max_age_hours * 3600:
                try:
                    os.remove(file_path)
                    logging.debug(f"Удален устаревший файл: {file_path}")
                except Exception as e:
                    logging.error(f"Не удалось удалить файл {filename}: {e}")
    except Exception as e:
        logging.error(f"Ошибка при очистке временных файлов: {e}")
