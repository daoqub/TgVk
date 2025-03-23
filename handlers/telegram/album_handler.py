 
import os 
from .base_handler import BaseHandler 
from aiogram.types import Message 
from aiogram_media_group import MediaGroupFilter, media_group_handler 
from services.database.repository import add_entry 
from utils.file_utils import download_file_with_retries 
 
class AlbumHandler(BaseHandler): 
    @media_group_handler 
    async def handle(self, messages: List[Message]): 
        if not messages: 
            return 
        settings = await self.setup(messages[0]) 
        if not settings: 
            return 
        source_link = self.get_source_link(messages[0].chat.username, messages[0].chat.id, messages[0].message_id) 
        try: 
            attachments = [] 
            caption = '' 
            for message in messages: 
                if message.caption and not caption: 
                    caption = message.caption 
                if message.photo: 
                    attachment = await self._handle_photo(message) 
                elif message.video: 
                    attachment = await self._handle_video(message) 
                elif message.document: 
                    attachment = await self._handle_document(message) 
                else: 
                    continue 
                if attachment: 
                    attachments.append(attachment) 
            if attachments: 
                response = await self.vk_client.create_post( 
                    message=caption, 
                    attachments=attachments, 
                    copyright=source_link 
                ) 
                if response and 'post_id' in response: 
                    add_entry(messages[0].message_id, response['post_id'], settings['user_id']) 
        except Exception as e: 
            self.logger.error(f"Ошибка при обработке альбома: {e}") 
 
    async def _handle_photo(self, message: Message): 
        file_path = f'./files/photo_{message.message_id}.jpg' 
        if await download_file_with_retries(message.bot, message.photo[-1].file_id, file_path): 
            try: 
                return await self.vk_client.upload_photo(file_path) 
            finally: 
                os.remove(file_path) 
        return None 
 
    async def _handle_video(self, message: Message): 
        file_path = f'./files/video_{message.message_id}.mp4' 
        if await download_file_with_retries(message.bot, message.video.file_id, file_path): 
            try: 
                return await self.vk_client.upload_video(file_path, message.video.file_name) 
            finally: 
                os.remove(file_path) 
        return None 
 
    async def _handle_document(self, message: Message): 
        file_path = f'./files/doc_{message.message_id}_{message.document.file_name}' 
        if await download_file_with_retries(message.bot, message.document.file_id, file_path): 
            try: 
                return await self.vk_client.upload_document(file_path, message.document.file_name) 
            finally: 
                os.remove(file_path) 
        return None 
