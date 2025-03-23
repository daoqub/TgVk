# services/vk/client.py
import logging
import asyncio
import os
import time
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from vk_api import VkApi
from vk_api.upload import VkUpload
from vk_api.exceptions import VkApiError
import requests
from config import supabase, format_owner_id, VK_CLIENT_ID, VK_CLIENT_SECRET

logger = logging.getLogger(__name__)

class VkClient:
    """Клиент для работы с VK API с поддержкой всех необходимых операций"""
    
    def __init__(self, max_retries: int = 3):
        self._api = None
        self._upload = None
        self._config = {}
        self.max_retries = max_retries
        self.logger = logging.getLogger(__name__)
        
    def configure(self, access_token: str, target_id: int, post_as_group: int = 1):
        """Конфигурация клиента с валидацией параметров"""
        if not all([access_token, target_id]):
            raise ValueError("Неверные параметры конфигурации VK")
        
        # Используем метод из TokenManager для форматирования ID
        if post_as_group == 1:  # Публикация от имени группы
            formatted_target_id = abs(format_owner_id(target_id))
        else:  # Публикация на странице пользователя
            formatted_target_id = abs(target_id)
        
        self._config.update({
            'access_token': access_token,
            'target_id': formatted_target_id,
            'post_as_group': post_as_group
        })
        self._reinitialize_client()
    
    def _reinitialize_client(self):
        """Инициализация клиента VK API с обработкой ошибок"""
        try:
            session = VkApi(token=self._config['access_token'])
            self._api = session.get_api()
            self._upload = VkUpload(session)
        except VkApiError as e:
            self.logger.error(f"Ошибка инициализации VK API: {e}")
            raise
    
    async def _execute_with_retry(self, func, *args, **kwargs):
        """Выполнение операции с повторными попытками и многопоточностью"""
        for attempt in range(self.max_retries):
            try:
                # Используем asyncio.to_thread для выполнения блокирующих операций
                return await asyncio.to_thread(func, *args, **kwargs)
            except VkApiError as e:
                if attempt == self.max_retries - 1:
                    raise
                self.logger.warning(f"Повторная попытка {attempt + 1}/{self.max_retries}: {e}")
                await asyncio.sleep(2 ** attempt)  # Экспоненциальная задержка
        return None
    
    async def refresh_token_if_needed(self, target_id: int):
        """Проверяет и обновляет токен VK API при необходимости"""
        if not supabase:
            return False
            
        try:
            # Проверяем состояние токена
            response = supabase.table("vk_targets") \
                .select("access_token,refresh_token,expires_at") \
                .eq("target_id", target_id) \
                .eq("is_active", True) \
                .execute()
                
            if not response.data or len(response.data) == 0:
                self.logger.error(f"Нет данных для цели {target_id}")
                return False
                
            target_data = response.data[0]
            expires_at = target_data.get("expires_at")
            
            # Проверяем, истек ли токен или истекает в ближайшие 5 минут
            buffer_time = 300  # 5 минут в секундах
            current_time = time.time()
            
            if expires_at:
                # Преобразуем строку в timestamp
                expires_timestamp = datetime.fromisoformat(expires_at.replace("Z", "+00:00")).timestamp()
                
                if current_time + buffer_time >= expires_timestamp:
                    # Токен истек или скоро истечет, обновляем
                    refresh_token = target_data.get("refresh_token")
                    new_token = await self._refresh_vk_token(target_id, refresh_token)
                    if new_token:
                        # Обновляем конфигурацию клиента
                        self._config['access_token'] = new_token
                        self._reinitialize_client()
                        return True
                    return False
                else:
                    # Токен действителен
                    if self._config.get('access_token') != target_data.get("access_token"):
                        # Обновляем конфигурацию с актуальным токеном
                        self._config['access_token'] = target_data.get("access_token")
                        self._reinitialize_client()
                    return True
            else:
                # Нет данных об истечении токена, пытаемся обновить
                refresh_token = target_data.get("refresh_token")
                new_token = await self._refresh_vk_token(target_id, refresh_token)
                if new_token:
                    self._config['access_token'] = new_token
                    self._reinitialize_client()
                    return True
                return False
                
        except Exception as e:
            self.logger.error(f"Ошибка при проверке токена: {e}")
            return False
    
    async def _refresh_vk_token(self, target_id, refresh_token=None):
        """Обновляет токен доступа VK API"""
        try:
            # Если refresh_token не передан, пытаемся получить его из базы
            if not refresh_token and supabase:
                response = supabase.table("vk_targets").select("refresh_token").eq("target_id", target_id).eq("is_active", True).execute()
                if not response.data or len(response.data) == 0:
                    self.logger.error(f"Нет токена обновления для группы {target_id}")
                    return None
                refresh_token = response.data[0]["refresh_token"]
            
            # Проверяем наличие идентификатора и секрета приложения VK
            if not VK_CLIENT_ID or not VK_CLIENT_SECRET:
                self.logger.error("Отсутствуют VK_CLIENT_ID или VK_CLIENT_SECRET в переменных окружения")
                return None
            
            # Запрос нового access_token через API ВКонтакте
            response = requests.get(
                "https://oauth.vk.com/access_token",
                params={
                    "grant_type": "refresh_token",
                    "client_id": VK_CLIENT_ID,
                    "client_secret": VK_CLIENT_SECRET,
                    "refresh_token": refresh_token
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                new_access_token = data.get("access_token")
                new_refresh_token = data.get("refresh_token")
                expires_in = data.get("expires_in", 3300)  # По умолчанию 55 минут
                
                # Обновляем токен в базе данных если есть supabase
                if supabase:
                    expires_at = time.time() + expires_in
                    # Форматируем дату в ISO формат для PostgreSQL
                    formatted_expires_at = datetime.fromtimestamp(expires_at, tz=timezone.utc).isoformat()
                    
                    supabase.table("vk_targets").update({
                        "access_token": new_access_token,
                        "refresh_token": new_refresh_token,
                        "expires_at": formatted_expires_at
                    }).eq("target_id", target_id).eq("is_active", True).execute()
                
                self.logger.info(f"Токен VK успешно обновлен для группы {target_id}")
                return new_access_token
            
            self.logger.error(f"Не удалось обновить токен VK: {response.text}")
            return None
            
        except Exception as e:
            self.logger.error(f"Ошибка при обновлении токена VK: {e}")
            return None
    
    async def upload_media(self, file_path: str, media_type: str, **kwargs):
        """Универсальный метод загрузки медиафайлов"""
        upload_methods = {
            'photo': self._upload.photo_wall,
            'video': self._upload.video,
            'audio': self._upload.audio,
            'doc': self._upload.document
        }
        
        if media_type not in upload_methods:
            raise ValueError(f"Неподдерживаемый тип медиа: {media_type}")
        
        try:
            # Проверяем существование файла
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"Файл не найден: {file_path}")
                
            # Проверка размера файла
            file_size = os.path.getsize(file_path)
            max_sizes = {
                'photo': 50 * 1024 * 1024,  # 50MB
                'video': 2 * 1024 * 1024 * 1024,  # 2GB
                'audio': 200 * 1024 * 1024,  # 200MB
                'doc': 200 * 1024 * 1024  # 200MB
            }
            
            if file_size > max_sizes.get(media_type, 100 * 1024 * 1024):
                raise ValueError(f"Файл превышает максимальный размер для типа {media_type}")
            
            # Обновляем токен если нужно
            target_id = self._config.get('target_id')
            if target_id:
                await self.refresh_token_if_needed(target_id)
            
            result = await self._execute_with_retry(upload_methods[media_type], file_path, **kwargs)
            
            # Форматируем результат в строку аттачмента
            if media_type == 'photo' and result:
                return f"photo{result[0]['owner_id']}_{result[0]['id']}"
            elif media_type == 'video' and result:
                return f"video{result['owner_id']}_{result['video_id']}"
            elif media_type == 'audio' and result:
                return f"audio{result['owner_id']}_{result['id']}"
            elif media_type == 'doc' and result:
                return f"doc{result['doc']['owner_id']}_{result['doc']['id']}"
            return None
        except Exception as e:
            self.logger.error(f"Ошибка загрузки {media_type}: {e}")
            return None
    
    async def create_post(self, text: str, attachments: List[str] = None, copyright: str = None):
        """Создание поста с обработкой ошибок"""
        if not self._api:
            self.logger.error("VK API не инициализирован")
            return None
            
        # Обновляем токен если нужно
        target_id = self._config.get('target_id')
        if target_id:
            await self.refresh_token_if_needed(target_id)
            
        # Учитываем параметр post_as_group для корректной публикации
        if self._config.get('post_as_group') == 0:
            owner_id = self._config.get('target_id')
        else:
            owner_id = -abs(self._config.get('target_id'))
        
        params = {
            'owner_id': owner_id,
            'from_group': self._config.get('post_as_group'),
            'message': text or '',
            'attachments': ','.join(attachments) if attachments else '',
            'copyright': copyright
        }
        
        try:
            response = await self._execute_with_retry(
                self._api.wall.post,
                **params
            )
            return response.get('post_id')
        except Exception as e:
            self.logger.error(f"Ошибка создания поста: {e}")
            return None
    
    async def edit_post(self, post_id: int, new_text: str, message_id: int = None):
        """Редактирование существующего поста с сохранением вложений"""
        if not self._api:
            self.logger.error("VK API не инициализирован")
            return False
            
        # Обновляем токен если нужно
        target_id = self._config.get('target_id')
        if target_id:
            await self.refresh_token_if_needed(target_id)
            
        try:
            # Получаем оригинальный пост для сохранения вложений
            if self._config.get('post_as_group') == 0:
                owner_id = self._config.get('target_id')
            else:
                owner_id = -abs(self._config.get('target_id'))
                
            posts = f"{owner_id}_{post_id}"
            
            old_post = await self._execute_with_retry(
                self._api.wall.getById,
                posts=posts
            )
            
            if not old_post:
                self.logger.error(f"Не удалось получить информацию о посте {post_id}")
                return False
            
            # Получаем список вложений
            attachments = []
            for attachment in old_post[0].get('attachments', []):
                attach_type = attachment.get('type')
                if attach_type and attach_type in attachment:
                    owner = attachment[attach_type].get('owner_id')
                    attach_id = attachment[attach_type].get('id')
                    if owner and attach_id:
                        attachments.append(f"{attach_type}{owner}_{attach_id}")
            
            # Получаем ссылку на исходное сообщение
            source_link = None
            if message_id:
                source_link = await self.get_source_link_for_edit(message_id)
            
            # Редактируем пост
            await self._execute_with_retry(
                self._api.wall.edit,
                owner_id=owner_id,
                post_id=post_id,
                message=new_text,
                attachments=','.join(attachments) if attachments else '',
                copyright=source_link
            )
            
            return True
        except Exception as e:
            self.logger.error(f"Ошибка редактирования поста {post_id}: {e}")
            return False
    
    async def get_post_by_message_id(self, message_id: int):
        """Получает ID поста VK по ID сообщения Telegram"""
        try:
            if supabase:
                response = supabase.table("posts").select("vk_post_id").eq("telegram_message_id", message_id).execute()
                if response.data and len(response.data) > 0:
                    post_id = response.data[0].get("vk_post_id")
                    return int(post_id) if post_id else None
            
            # Запасной вариант - чтение из файла
            if os.path.exists('data.txt'):
                with open('data.txt', 'r') as f:
                    for line in f:
                        parts = line.strip().split(':')
                        if len(parts) == 2 and int(parts[0]) == message_id:
                            return int(parts[1])
            
            return None
        except Exception as e:
            self.logger.error(f"Ошибка при получении соответствия ID: {e}")
            return None
    
    async def save_post_mapping(self, message_id: int, post_id: int, user_id: int = None, channel_id: int = None):
        """Сохраняет соответствие ID сообщения Telegram и поста VK"""
        try:
            if supabase and user_id:
                # Проверяем, существует ли запись
                check = supabase.table("posts").select("id").eq("telegram_message_id", message_id).eq("user_id", user_id).execute()
                
                post_data = {
                    "vk_post_id": str(post_id),
                    "status": "published",
                    "published_at": datetime.now(timezone.utc).isoformat()
                }
                
                if channel_id:
                    post_data["telegram_channel_id"] = channel_id
                
                if check.data and len(check.data) > 0:
                    # Обновляем существующую запись
                    supabase.table("posts").update(post_data).eq("telegram_message_id", message_id).eq("user_id", user_id).execute()
                else:
                    # Создаем новую запись
                    post_data.update({
                        "user_id": user_id,
                        "telegram_message_id": message_id
                    })
                    supabase.table("posts").insert(post_data).execute()
                return True
            else:
                # Запасной вариант - запись в файл
                with open('data.txt', 'a') as f:
                    f.write(f'{message_id}:{post_id}\n')
                return True
        except Exception as e:
            self.logger.error(f"Ошибка при сохранении соответствия ID: {e}")
            # Запасной вариант - запись в файл
            try:
                with open('data.txt', 'a') as f:
                    f.write(f'{message_id}:{post_id}\n')
            except Exception as write_error:
                self.logger.error(f"Ошибка записи в файл: {write_error}")
            return False
    
    async def get_source_link_for_edit(self, message_id: int):
        """Формирует ссылку на сообщение в Telegram для редактирования"""
        try:
            if not supabase:
                return f'https://t.me/{message_id}'
            
            # Получаем информацию о сообщении
            response = supabase.table("posts")\
                .select("telegram_message_id,telegram_channel_id")\
                .eq("telegram_message_id", message_id)\
                .execute()
                
            if not response.data or len(response.data) == 0:
                return f'https://t.me/{message_id}'
            
            # Получаем информацию о канале
            channel_response = supabase.table("telegram_channels")\
                .select("channel_id,channel_username")\
                .eq("id", response.data[0].get("telegram_channel_id"))\
                .execute()
                
            if not channel_response.data or len(channel_response.data) == 0:
                return f'https://t.me/{message_id}'
                
            channel = channel_response.data[0]
            
            if channel.get("channel_username"):
                return f'https://t.me/{channel["channel_username"]}/{message_id}'
            else:
                clean_id = str(channel.get("channel_id", ""))
                if clean_id.startswith("-100"):
                    clean_id = clean_id[4:]
                return f'https://t.me/c/{clean_id}/{message_id}'
        except Exception as e:
            self.logger.error(f"Ошибка при формировании ссылки: {e}")
            return f'https://t.me/{message_id}'
