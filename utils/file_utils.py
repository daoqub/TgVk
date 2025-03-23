# utils/file_utils.py

import os
import logging
import hashlib
import asyncio
import mimetypes
import time
import uuid
import shutil
from pathlib import Path
from typing import Optional, Tuple, List
from aiogram import Bot
from PIL import Image, UnidentifiedImageError
from contextlib import contextmanager

logger = logging.getLogger(__name__)

class FileManager:
    """Класс для безопасной работы с файлами"""
    
    def __init__(self, base_dir: str = './temp_files'):
        """
        Инициализация менеджера файлов.
        
        Args:
            base_dir: Базовая директория для временных файлов
        """
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.active_files = set()  # Отслеживание активных файлов для гарантированной очистки
    
    def _validate_file_type(self, file_path: Path) -> bool:
        """
        Проверка MIME-типа файла на допустимость.
        
        Args:
            file_path: Путь к файлу
            
        Returns:
            bool: True если тип файла допустим, иначе False
        """
        mime, _ = mimetypes.guess_type(file_path)
        allowed_types = [
            'image/jpeg', 'image/png', 'video/mp4',
            'application/pdf', 'audio/mpeg'
        ]
        return mime in allowed_types
    
    def _generate_checksum(self, file_path: Path) -> str:
        """
        Генерация контрольной суммы файла для проверки целостности.
        
        Args:
            file_path: Путь к файлу
            
        Returns:
            str: SHA256 хеш файла
        """
        hash_sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_sha256.update(chunk)
        return hash_sha256.hexdigest()
    
    async def download_file(
        self,
        bot: Bot,
        file_id: str,
        destination: Path,
        max_size: int = 100*1024*1024,  # 100 MB
        retries: int = 3
    ) -> Tuple[bool, Optional[str]]:
        """
        Безопасная загрузка файлов с валидацией размера и типа.
        
        Args:
            bot: Экземпляр бота Telegram
            file_id: ID файла для загрузки
            destination: Путь для сохранения файла
            max_size: Максимальный размер файла в байтах
            retries: Количество попыток загрузки
            
        Returns:
            Tuple[bool, Optional[str]]: (успех, код ошибки)
        """
        try:
            for attempt in range(retries):
                try:
                    file = await bot.get_file(file_id)
                    
                    # Проверка размера файла
                    if file.file_size > max_size:
                        logger.warning(f"Файл превышает лимит размера: {file.file_size}")
                        return False, "FILE_SIZE_EXCEEDED"
                    
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    await bot.download_file(file.file_path, destination)
                    
                    # Проверка типа файла
                    if not self._validate_file_type(destination):
                        logger.error(f"Недопустимый тип файла: {destination}")
                        destination.unlink(missing_ok=True)
                        return False, "INVALID_FILE_TYPE"
                    
                    # Проверка целостности
                    checksum = self._generate_checksum(destination)
                    logger.info(f"Успешная загрузка: {destination} (SHA256: {checksum})")
                    self.active_files.add(str(destination))
                    return True, None
                except Exception as e:
                    logger.error(f"Ошибка загрузки (попытка {attempt+1}/{retries}): {e}")
                    await asyncio.sleep(2**attempt)
                    if attempt == retries-1:
                        raise
            return False, "DOWNLOAD_FAILED"
        except Exception as e:
            logger.error(f"Критическая ошибка загрузки: {e}")
            return False, "CRITICAL_ERROR"
    
    def get_temp_path(self, prefix: str, suffix: str = None) -> Path:
        """
        Создает путь к временному файлу.
        
        Args:
            prefix: Префикс имени файла
            suffix: Суффикс имени файла (расширение)
            
        Returns:
            Path: Путь к временному файлу
        """
        filename = f"{prefix}_{uuid.uuid4().hex}"
        if suffix:
            if not suffix.startswith('.'):
                suffix = f".{suffix}"
            filename += suffix
        
        return self.base_dir / filename
    
    async def convert_image(
        self,
        input_path: Path,
        output_format: str = 'JPEG',
        max_dim: int = 4096
    ) -> Optional[Path]:
        """
        Конвертация изображений с проверкой безопасности.
        
        Args:
            input_path: Путь к исходному изображению
            output_format: Формат выходного изображения
            max_dim: Максимальный размер изображения
            
        Returns:
            Optional[Path]: Путь к конвертированному изображению
        """
        try:
            output_path = input_path.with_suffix(f'.{output_format.lower()}')
            with Image.open(input_path) as img:
                # Проверка размеров
                if max(img.size) > max_dim:
                    ratio = max_dim / max(img.size)
                    new_size = (int(img.size[0]*ratio), int(img.size[1]*ratio))
                    img = img.resize(new_size, Image.LANCZOS)
                
                # Конвертация с проверкой режима
                if img.mode not in ['RGB', 'L']:
                    img = img.convert('RGB')
                
                img.save(output_path, format=output_format, quality=85)
                return output_path
        except UnidentifiedImageError:
            logger.error("Обнаружен поврежденный файл изображения")
            return None
        except Exception as e:
            logger.error(f"Ошибка конвертации: {e}")
            return None
    
    async def cleanup(self, path: Path) -> None:
        """
        Гарантированная очистка файлов.
        
        Args:
            path: Путь к файлу для удаления
        """
        try:
            if path.exists():
                path.unlink()
                self.active_files.discard(str(path))
                logger.info(f"Файл удален: {path}")
        except Exception as e:
            logger.error(f"Ошибка удаления файла {path}: {e}")
    
    def cleanup_old_files(self, max_age_hours: int = 24) -> int:
        """
        Удаляет старые временные файлы.
        
        Args:
            max_age_hours: Максимальный возраст файлов в часах
            
        Returns:
            int: Количество удаленных файлов
        """
        count = 0
        current_time = time.time()
        max_age_seconds = max_age_hours * 3600
        
        try:
            for file_path in self.base_dir.glob('*'):
                if not file_path.is_file():
                    continue
                
                file_age = current_time - file_path.stat().st_mtime
                if file_age > max_age_seconds:
                    try:
                        file_path.unlink()
                        count += 1
                        logger.debug(f"Удален старый файл: {file_path}")
                    except Exception as e:
                        logger.error(f"Ошибка при удалении файла {file_path}: {e}")
            
            return count
        except Exception as e:
            logger.error(f"Ошибка при очистке временных файлов: {e}")
            return count
    
    async def emergency_cleanup(self) -> None:
        """Аварийная очистка всех временных файлов"""
        for file in list(self.active_files):
            await self.cleanup(Path(file))
    
    def get_disk_usage(self) -> int:
        """
        Возвращает общий размер всех файлов в байтах.
        
        Returns:
            int: Общий размер файлов в байтах
        """
        total_size = 0
        try:
            for file_path in self.base_dir.glob('*'):
                if file_path.is_file():
                    total_size += file_path.stat().st_size
            return total_size
        except Exception as e:
            logger.error(f"Ошибка при получении размера файлов: {e}")
            return total_size

    def check_disk_space(self, required_space: int) -> bool:
        """
        Проверяет наличие свободного места на диске.
        
        Args:
            required_space: Требуемое свободное место в байтах
        
        Returns:
            bool: True если достаточно места, иначе False
        """
        total, used, free = shutil.disk_usage(self.base_dir)
        return free > required_space

    @contextmanager
    def safe_open_file(self, file_path: Path, mode='rb'):
        """
        Контекстный менеджер для безопасного открытия файлов.
        
        Args:
            file_path: Путь к файлу
            mode: Режим открытия файла
        """
        try:
            with open(file_path, mode) as f:
                yield f
        except Exception as e:
            logger.error(f"Ошибка при открытии файла {file_path}: {e}")
            raise

def validate_file_extension(filename: str) -> bool:
    """
    Проверяет допустимость расширения файла.
    
    Args:
        filename: Имя файла
    
    Returns:
        bool: True если расширение допустимо, иначе False
    """
    allowed = {'.jpg', '.jpeg', '.png', '.mp4', '.pdf', '.mp3'}
    return Path(filename).suffix.lower() in allowed

async def download_file_with_retries(bot: Bot, file_id: str, destination: str, retries: int = 3, delay: int = 5) -> bool:
    """
    Загружает файл из Telegram с поддержкой повторных попыток.
    
    Args:
        bot: Экземпляр бота Telegram
        file_id: ID файла для загрузки
        destination: Путь для сохранения файла
        retries: Количество попыток загрузки
        delay: Задержка между попытками в секундах
        
    Returns:
        bool: True если загрузка успешна, иначе False
    """
    os.makedirs(os.path.dirname(destination), exist_ok=True)
    
    for attempt in range(retries):
        try:
            file = await bot.get_file(file_id)
            await bot.download_file(file.file_path, destination)
            logger.debug(f"Файл {file_id} успешно загружен в {destination}")
            return True
        except Exception as e:
            logger.error(f"Ошибка при загрузке файла (попытка {attempt + 1}/{retries}): {e}")
            if attempt < retries - 1:
                await asyncio.sleep(delay)
    
    logger.error(f"Не удалось загрузить файл {file_id} после {retries} попыток")
    return False
