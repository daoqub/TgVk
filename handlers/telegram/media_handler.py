# handlers/media_handler.py
import os
import asyncio
from typing import Optional, List
from aiogram.types import Message, ContentType
from .base_handler import BaseHandler
from services.vk.client import VkClient
from utils.file_utils import FileManager
from config import Config

class MediaHandler(BaseHandler):
    """Обработчик медиаконтента (фото, видео, документы)"""
    
    SUPPORTED_TYPES = {
        ContentType.PHOTO: ('photo', 'jpg'),
        ContentType.VIDEO: ('video', 'mp4'),
        ContentType.DOCUMENT: ('document', None),
        ContentType.VIDEO_NOTE: ('video_note', 'mp4')
    }
    
    def __init__(self, vk_client: VkClient, config: Config, file_manager: FileManager):
        super().__init__(vk_client, config)
        self.file_manager = file_manager
    
    async def handle(self, message: Message) -> Optional[int]:
        """
        Основной метод обработки медиа.
        
        Args:
            message: Сообщение из Telegram
            
        Returns:
            Optional[int]: ID созданного поста в VK или None
        """
        # Проверяем, является ли сообщение репостом от пользователя
        if await self.is_user_forward(message):
            self.logger.info(f"Пропуск репоста от пользователя: {message.message_id}")
            return None
            
        # Получаем настройки канала
        context = await self.setup(message)
        if not context:
            return None
        
        try:
            content_type = message.content_type
            if content_type not in self.SUPPORTED_TYPES:
                return None
            
            handler_name, ext = self.SUPPORTED_TYPES[content_type]
            return await getattr(self, f'_handle_{handler_name}')(message, context, ext)
        except Exception as e:
            self.logger.error(f"Ошибка обработки медиа: {e}")
            return None
    
    async def _handle_photo(self, message: Message, context: dict, ext: str) -> Optional[int]:
        """
        Обработка фотографий.
        
        Args:
            message: Сообщение с фото
            context: Контекст обработки
            ext: Расширение файла
            
        Returns:
            Optional[int]: ID созданного поста в VK или None
        """
        file = message.photo[-1]  # Берем самую большую версию фото
        
        # Проверка на превышение размера
        if file.file_size > self.config.MAX_FILE_SIZE:
            return await self.handle_oversized_file(message, context, "Фото")
        
        # Создаем временный путь и загружаем файл
        temp_path = self.file_manager.get_temp_path("photo", ext)
        success, error_code = await self.file_manager.download_file(
            message.bot, file.file_id, temp_path, self.config.MAX_FILE_SIZE
        )
        
        if not success:
            self.logger.error(f"Не удалось загрузить фото: {error_code}")
            return None
        
        try:
            # Загружаем фото в VK
            attachment = await self.vk_client.upload_media(temp_path, 'photo')
            return await self._publish_post(message, context, [attachment])
        finally:
            # Гарантированная очистка
            await self.file_manager.cleanup(temp_path)
    
    async def _handle_video(self, message: Message, context: dict, ext: str) -> Optional[int]:
        """
        Обработка видео.
        
        Args:
            message: Сообщение с видео
            context: Контекст обработки
            ext: Расширение файла
            
        Returns:
            Optional[int]: ID созданного поста в VK или None
        """
        file = message.video
        
        # Проверка на превышение размера
        if file.file_size > self.config.MAX_FILE_SIZE:
            return await self.handle_oversized_file(message, context, "Видео")
        
        # Создаем временный путь и загружаем файл
        temp_path = self.file_manager.get_temp_path("video", ext)
        success, error_code = await self.file_manager.download_file(
            message.bot, file.file_id, temp_path, self.config.MAX_FILE_SIZE
        )
        
        if not success:
            self.logger.error(f"Не удалось загрузить видео: {error_code}")
            return None
        
        try:
            # Загружаем видео в VK
            attachment = await self.vk_client.upload_media(
                temp_path, 'video', name=file.file_name
            )
            return await self._publish_post(message, context, [attachment])
        finally:
            # Гарантированная очистка
            await self.file_manager.cleanup(temp_path)
    
    async def _handle_video_note(self, message: Message, context: dict, ext: str) -> Optional[int]:
        """
        Обработка круглых видео.
        
        Args:
            message: Сообщение с круглым видео
            context: Контекст обработки
            ext: Расширение файла
            
        Returns:
            Optional[int]: ID созданного поста в VK или None
        """
        file = message.video_note
        
        # Проверка на превышение размера
        if file.file_size > self.config.MAX_FILE_SIZE:
            return await self.handle_oversized_file(message, context, "Круглое видео")
        
        # Создаем временный путь и загружаем файл
        temp_path = self.file_manager.get_temp_path("video_note", ext)
        success, error_code = await self.file_manager.download_file(
            message.bot, file.file_id, temp_path, self.config.MAX_FILE_SIZE
        )
        
        if not success:
            self.logger.error(f"Не удалось загрузить круглое видео: {error_code}")
            return None
        
        try:
            # Загружаем видео в VK
            attachment = await self.vk_client.upload_media(
                temp_path, 'video', name=f"video_note_{message.message_id}"
            )
            return await self._publish_post(message, context, [attachment])
        finally:
            # Гарантированная очистка
            await self.file_manager.cleanup(temp_path)
    
    async def _handle_document(self, message: Message, context: dict, ext: str) -> Optional[int]:
        """
        Обработка документов.
        
        Args:
            message: Сообщение с документом
            context: Контекст обработки
            ext: Расширение файла
            
        Returns:
            Optional[int]: ID созданного поста в VK или None
        """
        file = message.document
        
        # Проверка на превышение размера
        if file.file_size > self.config.MAX_FILE_SIZE:
            return await self.handle_oversized_file(message, context, "Документ")
        
        # Создаем временный путь и загружаем файл
        file_ext = os.path.splitext(file.file_name)[1] if file.file_name else None
        temp_path = self.file_manager.get_temp_path("document", file_ext)
        success, error_code = await self.file_manager.download_file(
            message.bot, file.file_id, temp_path, self.config.MAX_FILE_SIZE
        )
        
        if not success:
            self.logger.error(f"Не удалось загрузить документ: {error_code}")
            return None
        
        try:
            # Загружаем документ в VK
            attachment = await self.vk_client.upload_media(
                temp_path, 'doc', title=file.file_name
            )
            return await self._publish_post(message, context, [attachment])
        finally:
            # Гарантированная очистка
            await self.file_manager.cleanup(temp_path)

# handlers/media_handler.py (продолжение)
    async def _publish_post(self, message: Message, context: dict, attachments: List[str]) -> Optional[int]:
        """
        Публикация поста с обработкой ошибок.
        
        Args:
            message: Исходное сообщение
            context: Контекст обработки
            attachments: Список вложений
            
        Returns:
            Optional[int]: ID созданного поста в VK или None
        """
        try:
            # Обновляем токен при необходимости
            if not refresh_token_if_needed(context['settings']['target_id']):
                self.logger.error("Не удалось обновить токен VK")
                return None

            post_id = await self.vk_client.create_post(
                text=message.caption or '',
                attachments=attachments,
                copyright=context['source_link']
            )
            
            if post_id:
                # Сохраняем связь между сообщением в Telegram и постом в VK
                supabase.table('posts').insert({
                    'message_id': message.message_id,
                    'vk_post_id': post_id,
                    'user_id': context['settings']['user_id'],
                    'channel_id': context['settings']['channel_id']
                }).execute()
                
                self.logger.info(f"Успешно опубликован пост {post_id}")
                return post_id
            return None
        except Exception as e:
            self.logger.error(f"Ошибка публикации: {e}")
            return None

    async def handle_oversized_file(self, message: Message, context: dict, file_type: str) -> Optional[int]:
        """
        Обработка файлов, превышающих максимальный размер
        
        Args:
            message: Исходное сообщение
            context: Контекст обработки
            file_type: Тип файла для сообщения
            
        Returns:
            Optional[int]: ID созданного поста с ссылкой или None
        """
        try:
            text = f"{message.caption or ''}\n\n{file_type} доступен по ссылке: {context['source_link']}"
            return await self.vk_client.create_post(
                text=text,
                copyright=context['source_link']
            )
        except Exception as e:
            self.logger.error(f"Ошибка публикации ссылки: {e}")
            return None
