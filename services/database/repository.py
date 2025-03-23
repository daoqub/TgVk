import logging
from typing import Optional, Dict, List
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

class DatabaseRepository:
    """Репозиторий для работы с базой данных"""
    
    def __init__(self, supabase):
        self.supabase = supabase
        if not supabase:
            logger.warning("Supabase клиент не инициализирован, используется локальное хранилище")
    
    def get_channel_settings(self, channel_id: int):
        """Получение настроек канала для кросспостинга"""
        try:
            if not self.supabase:
                return None
                
            # Пробуем найти канал по исходному ID
            channel_response = self.supabase.table("telegram_channels").select("id,user_id,channel_username").eq("channel_id", channel_id).execute()
            
            if not channel_response.data or len(channel_response.data) == 0:
                # Пробуем преобразовать ID
                if str(channel_id).startswith("-100"):
                    converted_id = int(str(channel_id)[4:])
                    channel_response = self.supabase.table("telegram_channels").select("id,user_id,channel_username").eq("channel_id", converted_id).execute()
                else:
                    converted_id = int(f"-100{channel_id}")
                    channel_response = self.supabase.table("telegram_channels").select("id,user_id,channel_username").eq("channel_id", converted_id).execute()
            
            if not channel_response.data or len(channel_response.data) == 0:
                logger.info(f"Канал с ID {channel_id} не найден")
                return None
                
            channel_data = channel_response.data[0]
            
            # Получаем настройки кросспостинга
            settings_response = self.supabase.table("crosspost_settings")\
                .select("vk_target_id,post_as_group")\
                .eq("telegram_channel_id", channel_data["id"])\
                .eq("is_active", True)\
                .execute()
                
            if not settings_response.data or len(settings_response.data) == 0:
                logger.info(f"Настройки кросспостинга для канала ID {channel_id} не найдены")
                return None
                
            settings_data = settings_response.data[0]
            
            # Получаем информацию о цели VK
            vk_response = self.supabase.table("vk_targets")\
                .select("target_id,access_token,refresh_token,expires_at")\
                .eq("id", settings_data["vk_target_id"])\
                .eq("is_active", True)\
                .execute()
                
            if not vk_response.data or len(vk_response.data) == 0:
                logger.info(f"Цель VK для канала ID {channel_id} не найдена или не активна")
                return None
                
            vk_data = vk_response.data[0]
            
            # Формируем настройки
            return {
                "user_id": channel_data["user_id"],
                "channel_username": channel_data.get("channel_username", ""),
                "target_id": vk_data["target_id"],
                "access_token": vk_data["access_token"],
                "refresh_token": vk_data["refresh_token"],
                "expires_at": vk_data["expires_at"],
                "post_as_group": settings_data.get("post_as_group", 1),
                "channel_id": channel_data["id"],
                "vk_target_id": settings_data["vk_target_id"]
            }
        except Exception as e:
            logger.error(f"Ошибка при получении настроек канала {channel_id}: {e}")
            return None
    
    def save_post_mapping(self, user_id: int, telegram_message_id: int, vk_post_id: str, 
                          telegram_channel_id: int = None, content: str = None,
                          media_group_id: str = None):
        """Сохранение соответствия между сообщением Telegram и постом VK"""
        try:
            if not self.supabase:
                logger.warning("Supabase не инициализирован, данные не сохранены")
                return False
            
            # Проверяем существование записи
            check = self.supabase.table("posts").select("id")\
                .eq("telegram_message_id", telegram_message_id)\
                .eq("user_id", user_id)\
                .execute()
            
            post_data = {
                "vk_post_id": vk_post_id,
                "status": "published",
                "published_at": datetime.now(timezone.utc).isoformat()
            }
            
            if content:
                post_data["content"] = content
                
            if media_group_id:
                post_data["media_group_id"] = media_group_id
                
            if telegram_channel_id:
                post_data["telegram_channel_id"] = telegram_channel_id
            
            if check.data and len(check.data) > 0:
                # Обновляем существующую запись
                self.supabase.table("posts").update(post_data)\
                    .eq("telegram_message_id", telegram_message_id)\
                    .eq("user_id", user_id)\
                    .execute()
                logger.info(f"Обновлена связь поста: telegram_id={telegram_message_id}, vk_id={vk_post_id}")
            else:
                # Создаем новую запись
                post_data.update({
                    "user_id": user_id,
                    "telegram_message_id": telegram_message_id,
                    "processing_attempts": 1
                })
                self.supabase.table("posts").insert(post_data).execute()
                logger.info(f"Создана связь поста: telegram_id={telegram_message_id}, vk_id={vk_post_id}")
            
            return True
        except Exception as e:
            logger.error(f"Ошибка при сохранении связи постов: {e}")
            return False
    
    def get_post_by_message_id(self, telegram_message_id: int, user_id: int):
        """Получение информации о посте по ID сообщения Telegram"""
        try:
            if not self.supabase:
                return None
            
            response = self.supabase.table("posts").select("*")\
                .eq("telegram_message_id", telegram_message_id)\
                .eq("user_id", user_id)\
                .execute()
            
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error(f"Ошибка при получении поста по ID сообщения {telegram_message_id}: {e}")
            return None
    
    def save_media_item(self, post_id: int, file_data: Dict):
        """Сохранение информации о медиафайле"""
        try:
            if not self.supabase:
                return None
            
            media_data = {
                "post_id": post_id,
                "file_id": file_data.get("file_id"),
                "file_type": file_data.get("file_type"),
                "file_size": file_data.get("file_size"),
                "width": file_data.get("width"),
                "height": file_data.get("height"),
                "duration": file_data.get("duration"),
                "media_group_id": file_data.get("media_group_id"),
                "vk_attachment_id": file_data.get("vk_attachment_id"),
                "processed": file_data.get("processed", False)
            }
            
            response = self.supabase.table("media_items").insert(media_data).execute()
            
            return response.data[0]["id"] if response.data else None
        except Exception as e:
            logger.error(f"Ошибка при сохранении медиафайла: {e}")
            return None
    
    def close_connection(self):
        """Закрытие соединения с базой данных"""
        # Для Supabase не требуется явное закрытие соединения
        logger.info("Соединение с базой данных закрыто")
