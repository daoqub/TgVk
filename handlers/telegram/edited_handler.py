# handlers/edited_handler.py
import asyncio
import logging
from aiogram.types import Message
from .base_handler import BaseHandler
from services.vk.client import VkClient
from config import Config

class EditedHandler(BaseHandler):
    """Обработчик редактирования сообщений"""
    
    def __init__(self, vk_client: VkClient, config: Config):
        super().__init__(vk_client, config)
        self.max_edit_attempts = 3
        self.logger = logging.getLogger(__name__)

    async def handle(self, message: Message) -> bool:
        """Основной метод обработки редактирования"""
        settings = await self._get_settings(message)
        if not settings:
            return False

        try:
            post_id = self.config.get_post_mapping(message.message_id)
            if not post_id:
                self.logger.warning(f"Пост {message.message_id} не найден")
                return False

            new_text = message.text or message.caption or ''
            for attempt in range(self.max_edit_attempts):
                try:
                    success = await self.vk_client.edit_post(post_id, new_text)
                    if success:
                        self.logger.info(f"Пост {post_id} успешно обновлен")
                        return True
                    else:
                        if attempt == self.max_edit_attempts - 1:
                            self.logger.warning(f"Не удалось обновить пост {post_id} после {self.max_edit_attempts} попыток")
                            return False
                except Exception as e:
                    if attempt == self.max_edit_attempts - 1:
                        self.logger.error(f"Ошибка редактирования поста {post_id}: {e}")
                        return False
                    self.logger.warning(f"Попытка {attempt+1}/{self.max_edit_attempts} редактирования поста {post_id} не удалась: {e}")
                
                # Экспоненциальная задержка между попытками
                await asyncio.sleep(2 ** attempt)
            
            return False
        except Exception as e:
            self.logger.error(f"Критическая ошибка при редактировании: {e}")
            return False
