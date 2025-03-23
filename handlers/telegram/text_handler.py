 
from .base_handler import BaseHandler 
from aiogram.types import Message 
from services.database.repository import add_entry 
 
class TextHandler(BaseHandler): 
    async def handle(self, message: Message): 
        settings = await self.setup(message) 
        if not settings: 
            return 
        source_link = self.get_source_link(message.chat.username, message.chat.id, message.message_id) 
        try: 
            response = await self.vk_client.create_post( 
                message=message.text, 
                copyright=source_link 
            ) 
            if response and 'post_id' in response: 
                add_entry(message.message_id, response['post_id'], settings['user_id']) 
        except Exception as e: 
            self.logger.error(f"Ошибка при обработке текстового сообщения: {e}") 
