# handlers/base_handler.py
import os
import asyncio
from typing import Optional, List
from aiogram.types import Message
from pathlib import Path
from services.database.repository import get_channel_settings_by_id
from services.vk.client import VkClient

class BaseHandler:
    def __init__(self, vk_client: VkClient):
        self.vk_client = vk_client
        self.logger = logging.getLogger(__name__)
        self.temp_dir = Path(config.TEMP_DIR)
        self.temp_dir.mkdir(exist_ok=True)

    async def setup(self, message: Message) -> Optional[dict]:
        """Общая инициализация для всех обработчиков"""
        try:
            if await self.is_user_forward(message):
                self.logger.info(f"Пропуск репоста от пользователя: {message.message_id}")
                return None

            chat = await message.bot.get_chat(message.chat.id)
            settings = get_channel_settings_by_id(chat.id)
            
            if not settings or not settings.get('is_active'):
                return None
            
            self.vk_client.configure(
                access_token=settings["access_token"],
                target_id=settings["target_id"],
                post_as_group=settings.get("post_as_group", 1)
            )
            return {
                'settings': settings,
                'chat': chat,
                'source_link': self.generate_source_link(chat, message.message_id)
            }
        except Exception as e:
            self.logger.error(f"Ошибка инициализации: {e}")
            return None

    async def is_user_forward(self, message: Message) -> bool:
        """Проверка на репост от пользователя"""
        return message.forward_from is not None and message.forward_from_chat is None

    def generate_source_link(self, chat, message_id: int) -> str:
        """Генерация ссылки на источник"""
        if chat.username:
            return f'https://t.me/{chat.username}/{message_id}'
        clean_id = str(chat.id).removeprefix("-100")
        return f'https://t.me/c/{clean_id}/{message_id}'

    async def handle_oversized_file(self, message: Message, context: dict, file_type: str):
        """Обработка слишком больших файлов"""
        try:
            text = f"{message.caption or ''}\n\n{file_type} доступен по ссылке: {context['source_link']}"
            return await self.vk_client.create_post(
                text=text,
                copyright=context['source_link']
            )
        except Exception as e:
            self.logger.error(f"Ошибка публикации ссылки: {e}")

    async def process_file(self, bot, file_id: str, prefix: str, ext: str) -> Optional[Path]:
        """Безопасная обработка файла с повторами"""
        temp_path = self.temp_dir / f"{prefix}_{file_id}.{ext}"
        try:
            success = await download_file_with_retries(
                bot=bot,
                file_id=file_id,
                destination=str(temp_path),
                retries=config.VK_API_MAX_RETRIES,
                delay=config.VK_API_RETRY_DELAY
            )
            return temp_path if success else None
        except Exception as e:
            self.logger.error(f"Ошибка обработки файла: {e}")
            return None

    async def cleanup_files(self, *paths: List[Path]):
        """Гарантированная очистка файлов"""
        for path in paths:
            try:
                if path and path.exists():
                    path.unlink()
            except Exception as e:
                self.logger.warning(f"Ошибка удаления файла: {path} - {e}")

async def is_channel_forward(self, message: Message) -> bool:
    return message.forward_from_chat is not None
