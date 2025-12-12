import asyncio
import threading
import os
import wx
from datetime import datetime
from telethon import TelegramClient as TelethonClient
from telethon.errors import SessionPasswordNeededError, PhoneCodeInvalidError, PhoneNumberInvalidError, FloodWaitError
from telethon.tl.types import MessageMediaPhoto, MessageMediaDocument, DocumentAttributeAudio, DocumentAttributeVideo

# Domyślna ścieżka eksportu
EXPORT_DIR = os.path.join(os.getcwd(), 'export')

class TelegramExporterClient:
    def __init__(self):
        self.client = None
        self.is_connected = False
        self.user_data = None
        self.dialogs = []
        
        # Callbacks dla GUI
        self.on_connection_error = None
        self.on_code_requested = None
        self.on_password_requested = None
        self.on_login_success = None
        self.on_dialogs_loaded = None
        self.on_participants_loaded = None  # Nowy callback
        self.on_export_progress = None
        self.on_export_finished = None
        
        self.event_loop = None
        self.connection_thread = None
        
        # Zmienne kontrolne logowania
        self._phone = None
        self._api_id = None
        self._api_hash = None
        self._code_future = None
        self._password_future = None

    def start_login(self, api_id, api_hash, phone_number):
        """Rozpoczyna proces logowania w osobnym wątku."""
        self._api_id = int(api_id)
        self._api_hash = api_hash
        self._phone = phone_number
        
        if self.connection_thread and self.connection_thread.is_alive():
            return
        
        self.connection_thread = threading.Thread(
            target=self._run_client,
            daemon=True
        )
        self.connection_thread.start()

    def _run_client(self):
        """Uruchamia pętlę zdarzeń asyncio."""
        self.event_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.event_loop)
        
        session_file = os.path.join(os.getcwd(), 'exporter_session')
        
        try:
            self.event_loop.run_until_complete(
                self._connect_and_login(session_file)
            )
        except Exception as e:
            if self.on_connection_error:
                wx.CallAfter(self.on_connection_error, str(e))
        finally:
            if self.event_loop:
                self.event_loop.close()

    async def _connect_and_login(self, session_file):
        """Główna korutyna logowania."""
        try:
            self.client = TelethonClient(session_file, self._api_id, self._api_hash)
            await self.client.connect()
            
            if not await self.client.is_user_authorized():
                await self.client.send_code_request(self._phone)
                
                # Poproś GUI o kod
                if self.on_code_requested:
                    wx.CallAfter(self.on_code_requested)
                
                # Czekaj na kod z GUI
                self._code_future = self.event_loop.create_future()
                code = await self._code_future
                
                try:
                    await self.client.sign_in(self._phone, code)
                except SessionPasswordNeededError:
                    # 2FA
                    if self.on_password_requested:
                        wx.CallAfter(self.on_password_requested)
                    
                    self._password_future = self.event_loop.create_future()
                    password = await self._password_future
                    
                    await self.client.sign_in(password=password)
            
            # Pobierz dane użytkownika
            me = await self.client.get_me()
            self.user_data = {
                'id': me.id,
                'username': me.username or f"{me.first_name} {me.last_name or ''}".strip(),
                'phone': me.phone
            }
            self.is_connected = True
            
            if self.on_login_success:
                wx.CallAfter(self.on_login_success, self.user_data)
                
            # Załaduj listę czatów
            await self._load_dialogs()
            
            # Utrzymuj połączenie aktywne
            await self.client.run_until_disconnected()
            
        except Exception as e:
            if self.on_connection_error:
                wx.CallAfter(self.on_connection_error, str(e))
            self.is_connected = False

    def submit_code(self, code):
        """Przekazuje kod weryfikacyjny do wątku asyncio."""
        if self.event_loop and self._code_future and not self._code_future.done():
            self.event_loop.call_soon_threadsafe(self._code_future.set_result, code)

    def submit_password(self, password):
        """Przekazuje hasło 2FA do wątku asyncio."""
        if self.event_loop and self._password_future and not self._password_future.done():
            self.event_loop.call_soon_threadsafe(self._password_future.set_result, password)

    async def _load_dialogs(self):
        """Pobiera listę czatów."""
        self.dialogs = []
        async for dialog in self.client.iter_dialogs():
            self.dialogs.append({
                'id': dialog.id,
                'title': dialog.title,
                'is_group': dialog.is_group,
                'is_channel': dialog.is_channel,
                'entity': dialog.entity
            })
            
        if self.on_dialogs_loaded:
            wx.CallAfter(self.on_dialogs_loaded, self.dialogs)

    def fetch_chat_members(self, chat_id):
        """Pobiera uczestników danego czatu."""
        asyncio.run_coroutine_threadsafe(
            self._fetch_members_coro(chat_id),
            self.event_loop
        )

    async def _fetch_members_coro(self, chat_id):
        try:
            # Znajdź dialog
            dialog = next((d for d in self.dialogs if d['id'] == chat_id), None)
            if not dialog:
                return

            participants = []
            # Limit do 200, żeby nie muliło przy wielkich grupach
            async for user in self.client.iter_participants(dialog['entity'], limit=200):
                if user.deleted: continue
                name = f"{user.first_name} {user.last_name or ''}".strip()
                if not name: name = "Bez nazwy"
                if user.username: name += f" (@{user.username})"
                participants.append({'id': user.id, 'name': name})
            
            if self.on_participants_loaded:
                wx.CallAfter(self.on_participants_loaded, participants)
        except Exception as e:
            print(f"Błąd pobierania uczestników: {e}")
            if self.on_connection_error:
                wx.CallAfter(self.on_connection_error, f"Nie udało się pobrać uczestników: {str(e)}")

    def start_export(self, selected_chat_ids, export_options, filter_user_id=None):
        """Uruchamia proces eksportu w tle."""
        threading.Thread(
            target=self._run_export_task,
            args=(selected_chat_ids, export_options, filter_user_id),
            daemon=True
        ).start()

    def _run_export_task(self, selected_chat_ids, options, filter_user_id):
        """Wrapper wątku dla zadania eksportu."""
        future = asyncio.run_coroutine_threadsafe(
            self._export_process(selected_chat_ids, options, filter_user_id),
            self.event_loop
        )
        try:
            future.result()
        except Exception as e:
            if self.on_connection_error:
                wx.CallAfter(self.on_connection_error, f"Błąd eksportu: {e}")

    async def _export_process(self, selected_chat_ids, options, filter_user_id):
        """Główna pętla eksportu."""
        total_chats = len(selected_chat_ids)
        
        for index, chat_id in enumerate(selected_chat_ids):
            # Znajdź dialog
            dialog = next((d for d in self.dialogs if d['id'] == chat_id), None)
            if not dialog:
                continue
                
            safe_title = "".join([c for c in dialog['title'] if c.isalpha() or c.isdigit() or c==' ']).strip()
            chat_dir = os.path.join(EXPORT_DIR, safe_title)
            os.makedirs(chat_dir, exist_ok=True)
            
            # Plik tekstowy
            txt_file_path = os.path.join(chat_dir, 'chat_history.txt')
            txt_file = open(txt_file_path, 'w', encoding='utf-8') if options.get('text') else None
            
            count = 0
            status_msg = f"Eksportowanie: {safe_title}"
            if self.on_export_progress:
                wx.CallAfter(self.on_export_progress, index, total_chats, f"{status_msg}...")
            
            try:
                async for message in self.client.iter_messages(dialog['entity']):
                    # FILTR UCZESTNIKA (Jeśli ustawiony)
                    if filter_user_id is not None:
                        if message.sender_id != filter_user_id:
                            continue

                    # 1. Eksport Tekstu
                    if options.get('text') and message.text:
                        sender = await message.get_sender()
                        sender_name = getattr(sender, 'first_name', 'Unknown') if sender else 'Unknown'
                        date_str = message.date.strftime('%Y-%m-%d %H:%M:%S')
                        txt_file.write(f"[{date_str}] {sender_name}: {message.text}\n")
                    
                    # 2. Multimedia
                    file_path = None
                    download = False
                    
                    if message.media:
                        # Zdjęcia
                        if options.get('photos') and isinstance(message.media, MessageMediaPhoto):
                            download = True
                            media_dir = os.path.join(chat_dir, 'photos')
                        # Głosówki
                        elif options.get('voice') and isinstance(message.media, MessageMediaDocument):
                            if any(isinstance(a, DocumentAttributeAudio) and a.voice for a in message.media.document.attributes):
                                download = True
                                media_dir = os.path.join(chat_dir, 'voice')
                        # Wideo
                        elif options.get('video') and isinstance(message.media, MessageMediaDocument):
                             if any(isinstance(a, DocumentAttributeVideo) for a in message.media.document.attributes):
                                download = True
                                media_dir = os.path.join(chat_dir, 'videos')
                        # Inne pliki
                        elif options.get('files') and isinstance(message.media, MessageMediaDocument):
                            # Wykluczamy głosówki i wideo jeśli nie są zaznaczone, ale 'files' jest
                            is_voice = any(isinstance(a, DocumentAttributeAudio) and a.voice for a in message.media.document.attributes)
                            is_video = any(isinstance(a, DocumentAttributeVideo) for a in message.media.document.attributes)
                            
                            if not is_voice and not is_video:
                                download = True
                                media_dir = os.path.join(chat_dir, 'files')

                    if download:
                        os.makedirs(media_dir, exist_ok=True)
                        try:
                            await message.download_media(file=media_dir)
                        except Exception as e:
                            print(f"Błąd pobierania pliku: {e}")
                    
                    count += 1
                    if count % 20 == 0:
                         if self.on_export_progress:
                            wx.CallAfter(self.on_export_progress, index, total_chats, f"{status_msg} ({count} wiadomości)")
            
            except Exception as e:
                print(f"Błąd podczas przetwarzania czatu {safe_title}: {e}")
            finally:
                if txt_file:
                    txt_file.close()
        
        if self.on_export_finished:
            wx.CallAfter(self.on_export_finished)

# Globalna instancja (jak w przykładzie)
tg_client = TelegramExporterClient()
