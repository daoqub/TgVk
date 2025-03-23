# handlers/audio_handler.py
import os
from pathlib import Path
from aiogram.types import Message
from .base_handler import BaseHandler
from utils.file_utils import download_file_with_retries

class AudioHandler(BaseHandler):
    """Обработчик аудиофайлов с метаданными"""
    
    def __init__(self, vk_client: VkClient, config: Config):
        super().__init__(vk_client, config)
        self.temp_dir = Path(config.TEMP_DIR)

    async def handle(self, message: Message) -> Optional[int]:
        """Основной метод обработки аудио"""
        return await self._process_media(
            message=message,
            processor=self._upload_audio,
            file_type="Аудио",
            file_attr="audio"
        )

    async def _upload_audio(self, message: Message, settings: dict, audio) -> Optional[int]:
        """Логика загрузки аудио"""
        temp_path = self.temp_dir / f"audio_{message.message_id}_{audio.file_name}"
        try:
            if await download_file_with_retries(message.bot, audio.file_id, temp_path):
                attachment = await self.vk_client.upload_media(
                    temp_path,
                    'audio',
                    artist=audio.performer,
                    title=audio.title
                )
                return await self._publish_post(message, settings, attachment)
        finally:
            await self._cleanup_files(temp_path)

    async def _publish_post(self, message: Message, settings: dict, attachment: str) -> Optional[int]:
        """Публикация аудиопоста"""
        source_link = self._generate_source_link(message)
        try:
            post_id = await self.vk_client.create_post(
                text=message.caption or '',
                attachments=[attachment],
                copyright=source_link
            )
            if post_id:
                self.config.add_post_mapping(
                    message_id=message.message_id,
                    vk_post_id=post_id,
                    user_id=settings['user_id']
                )
                return post_id
        except Exception as e:
            self.logger.error(f"Ошибка публикации аудио: {e}")
            raise
