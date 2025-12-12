import wx
import os
import security
from tg_logic import tg_client
from config import API_ID, API_HASH

class LoginFrame(wx.Frame):
    def __init__(self, parent):
        super().__init__(parent, title="Telegram Exporter - Logowanie", size=(400, 300))
        self.Center()
        
        panel = wx.Panel(self)
        vbox = wx.BoxSizer(wx.VERTICAL)
        
        lbl_info = wx.StaticText(panel, label="Wpisz numer telefonu, a następnie naciśnij Enter.")
        vbox.Add(lbl_info, flag=wx.ALL, border=10)
        
        lbl_phone = wx.StaticText(panel, label="&Numer telefonu:")
        vbox.Add(lbl_phone, flag=wx.LEFT|wx.TOP, border=10)
        
        self.phone_ctrl = wx.TextCtrl(panel, style=wx.TE_PROCESS_ENTER)
        self.phone_ctrl.Bind(wx.EVT_TEXT_ENTER, self.on_connect)
        vbox.Add(self.phone_ctrl, flag=wx.EXPAND|wx.LEFT|wx.RIGHT, border=10)
        
        self.chk_remember = wx.CheckBox(panel, label="Zapamiętaj mnie")
        vbox.Add(self.chk_remember, flag=wx.LEFT|wx.TOP, border=10)
        
        self.btn_connect = wx.Button(panel, label="&Połącz")
        self.btn_connect.Bind(wx.EVT_BUTTON, self.on_connect)
        vbox.Add(self.btn_connect, flag=wx.ALIGN_CENTER|wx.TOP|wx.BOTTOM, border=20)
        
        panel.SetSizer(vbox)
        
        # Callbacks
        tg_client.on_code_requested = self.on_code_requested
        tg_client.on_password_requested = self.on_password_requested
        tg_client.on_login_success = self.on_login_success
        tg_client.on_connection_error = self.on_error

        self.try_load_config()

    def try_load_config(self):
        config_data = security.load_encrypted_config()
        if config_data and 'phone' in config_data:
            self.phone_ctrl.SetValue(config_data['phone'])
            self.chk_remember.SetValue(True)

    def on_connect(self, event):
        phone = self.phone_ctrl.GetValue()
        if not phone:
            wx.MessageBox("Podaj numer telefonu!", "Błąd", wx.OK | wx.ICON_ERROR)
            return
            
        if self.chk_remember.GetValue():
            security.save_encrypted_config(API_ID, API_HASH, phone)
            
        self.btn_connect.Disable()
        self.SetTitle("Łączenie...")
        tg_client.start_login(API_ID, API_HASH, phone)

    def on_code_requested(self):
        dlg = wx.TextEntryDialog(self, "Wpisz kod weryfikacyjny:", "Weryfikacja")
        if dlg.ShowModal() == wx.ID_OK:
            tg_client.submit_code(dlg.GetValue())
        dlg.Destroy()

    def on_password_requested(self):
        dlg = wx.PasswordEntryDialog(self, "Wpisz hasło 2FA:", "Weryfikacja 2FA")
        if dlg.ShowModal() == wx.ID_OK:
            tg_client.submit_password(dlg.GetValue())
        dlg.Destroy()

    def on_login_success(self, user_data):
        self.Hide()
        main_frame = MainFrame(None, user_data)
        main_frame.Show()

    def on_error(self, message):
        self.btn_connect.Enable()
        self.SetTitle("Telegram Exporter - Logowanie")
        wx.MessageBox(f"Błąd: {message}", "Błąd", wx.OK | wx.ICON_ERROR)


class MainFrame(wx.Frame):
    def __init__(self, parent, user_data):
        super().__init__(parent, title=f"Zalogowano: {user_data['username']}", size=(600, 600))
        self.Center()
        self.user_data = user_data
        
        self.panel = wx.Panel(self)
        self.sizer = wx.BoxSizer(wx.VERTICAL)
        self.panel.SetSizer(self.sizer)
        
        # Initialize variables
        self.chat_objects = []
        self.selected_chat_ids = []
        self.export_opts = {}
        self.participant_list = []
        
        # Callbacks
        tg_client.on_dialogs_loaded = self.load_chats_to_list
        tg_client.on_export_progress = self.update_progress
        tg_client.on_export_finished = self.on_finished
        tg_client.on_participants_loaded = self.show_filter_ui
        
        # Start with Main View
        self.setup_main_view()

    # --- VIEW 1: MAIN SELECTION ---
    def setup_main_view(self):
        self.panel.DestroyChildren()
        self.sizer.Clear(True)
        
        # Chat Selection
        lbl_chat = wx.StaticText(self.panel, label="Wybierz &czaty (Spacja zaznacza/odznacza):")
        self.sizer.Add(lbl_chat, flag=wx.LEFT|wx.TOP, border=10)
        
        hbox_btns = wx.BoxSizer(wx.HORIZONTAL)
        btn_all = wx.Button(self.panel, label="Zaznacz wszystkie", size=(120, -1))
        btn_none = wx.Button(self.panel, label="Odznacz wszystkie", size=(120, -1))
        btn_all.Bind(wx.EVT_BUTTON, lambda evt: self.toggle_all_items(self.lst_chats, True))
        btn_none.Bind(wx.EVT_BUTTON, lambda evt: self.toggle_all_items(self.lst_chats, False))
        hbox_btns.Add(btn_all, flag=wx.RIGHT, border=5)
        hbox_btns.Add(btn_none)
        self.sizer.Add(hbox_btns, flag=wx.LEFT|wx.RIGHT|wx.BOTTOM, border=10)

        self.lst_chats = wx.ListCtrl(self.panel, style=wx.LC_REPORT | wx.LC_NO_HEADER | wx.BORDER_SUNKEN)
        self.lst_chats.EnableCheckBoxes(True)
        self.lst_chats.InsertColumn(0, "Nazwa czatu", width=450)
        self.sizer.Add(self.lst_chats, proportion=1, flag=wx.EXPAND|wx.LEFT|wx.RIGHT, border=10)

        if self.chat_objects:
            self._fill_chat_list()

        # Type Selection
        lbl_type = wx.StaticText(self.panel, label="Opcje &eksportu:")
        self.sizer.Add(lbl_type, flag=wx.LEFT|wx.TOP, border=15)
        
        self.lst_types = wx.ListCtrl(self.panel, size=(-1, 120), style=wx.LC_REPORT | wx.LC_NO_HEADER | wx.BORDER_SUNKEN)
        self.lst_types.EnableCheckBoxes(True)
        self.lst_types.InsertColumn(0, "Typ danych", width=300)
        self.sizer.Add(self.lst_types, flag=wx.EXPAND|wx.LEFT|wx.RIGHT, border=10)
        
        self.type_options = [
            ("Tekst (.txt)", 'text'),
            ("Zdjęcia", 'photos'),
            ("Wiadomości Głosowe", 'voice'),
            ("Wideo", 'video'),
            ("Pliki / Dokumenty", 'files')
        ]
        
        for label, key in self.type_options:
            index = self.lst_types.InsertItem(self.lst_types.GetItemCount(), label)
            if key in ['text', 'voice']:
                self.lst_types.CheckItem(index, True)

        # Action
        self.btn_export = wx.Button(self.panel, label="&Dalej / Eksportuj")
        self.btn_export.Bind(wx.EVT_BUTTON, self.on_export_click)
        self.sizer.Add(self.btn_export, flag=wx.ALIGN_CENTER|wx.ALL, border=15)
        
        self.panel.Layout()
        self.lst_chats.SetFocus()

    # --- VIEW 2: PARTICIPANT FILTER (Only for Single Chat) ---
    def show_filter_loading(self):
        """Shows a temporary loading state while fetching participants."""
        self.panel.DestroyChildren()
        self.sizer.Clear(True)
        
        lbl = wx.StaticText(self.panel, label="Pobieranie listy uczestników czatu...\nMoże to chwilę potrwać.")
        self.sizer.Add(lbl, flag=wx.ALIGN_CENTER|wx.ALL, border=50)
        self.panel.Layout()

    def show_filter_ui(self, participants):
        """Called by logic callback when participants are loaded."""
        self.panel.DestroyChildren()
        self.sizer.Clear(True)
        self.participant_list = participants
        
        lbl_title = wx.StaticText(self.panel, label="Filtrowanie wiadomości")
        font = lbl_title.GetFont()
        font.SetWeight(wx.FONTWEIGHT_BOLD)
        lbl_title.SetFont(font)
        self.sizer.Add(lbl_title, flag=wx.ALIGN_CENTER|wx.TOP, border=20)
        
        lbl_desc = wx.StaticText(self.panel, label="Wybrano jeden czat. Możesz wyeksportować wiadomości tylko od konkretnej osoby (np. tylko Twoje głosówki).")
        self.sizer.Add(lbl_desc, flag=wx.ALL, border=20)
        
        lbl_sel = wx.StaticText(self.panel, label="Czyje wiadomości eksportować:")
        self.sizer.Add(lbl_sel, flag=wx.LEFT, border=20)
        
        # Dropdown
        choices = ["=== WSZYSCY (Domyślne) ==="]
        for p in participants:
            choices.append(p['name'])
            
        self.cb_participants = wx.Choice(self.panel, choices=choices)
        self.cb_participants.SetSelection(0)
        self.sizer.Add(self.cb_participants, flag=wx.EXPAND|wx.LEFT|wx.RIGHT, border=20)
        
        # Buttons
        hbox = wx.BoxSizer(wx.HORIZONTAL)
        btn_cancel = wx.Button(self.panel, label="Anuluj")
        btn_start = wx.Button(self.panel, label="Rozpocznij Eksport")
        
        btn_cancel.Bind(wx.EVT_BUTTON, lambda e: self.setup_main_view())
        btn_start.Bind(wx.EVT_BUTTON, self.on_start_filtered_export)
        
        hbox.Add(btn_cancel, flag=wx.RIGHT, border=10)
        hbox.Add(btn_start)
        self.sizer.Add(hbox, flag=wx.ALIGN_CENTER|wx.TOP, border=30)
        
        self.panel.Layout()
        self.cb_participants.SetFocus()

    # --- VIEW 3: PROGRESS BAR ---
    def setup_progress_view(self):
        self.panel.DestroyChildren()
        self.sizer.Clear(True)
        
        self.status_lbl = wx.StaticText(self.panel, label="Inicjalizacja...")
        font = self.status_lbl.GetFont()
        font.SetPointSize(10)
        self.status_lbl.SetFont(font)
        self.sizer.Add(self.status_lbl, flag=wx.ALIGN_CENTER|wx.TOP, border=40)
        
        self.gauge = wx.Gauge(self.panel, range=100, size=(400, 25))
        self.gauge.Pulse() # Indeterminate mode initially
        self.sizer.Add(self.gauge, flag=wx.ALIGN_CENTER|wx.ALL, border=20)
        
        self.panel.Layout()
        self.SetTitle("Eksportowanie...")

    # --- LOGIC & EVENTS ---

    def toggle_all_items(self, list_ctrl, state):
        for i in range(list_ctrl.GetItemCount()):
            list_ctrl.CheckItem(i, state)

    def load_chats_to_list(self, dialogs):
        self.chat_objects = dialogs
        if hasattr(self, 'lst_chats'): # Update if on main view
            self._fill_chat_list()
        
    def _fill_chat_list(self):
        self.lst_chats.DeleteAllItems()
        for d in self.chat_objects:
            label = d['title']
            if d['is_group']: label += " [Grupa]"
            if d['is_channel']: label += " [Kanał]"
            self.lst_chats.InsertItem(self.lst_chats.GetItemCount(), label)
        self.SetTitle(f"Gotowe - {len(self.chat_objects)} czatów")

    def on_export_click(self, event):
        # 1. Collect Chats
        self.selected_chat_ids = []
        for i in range(self.lst_chats.GetItemCount()):
            if self.lst_chats.IsItemChecked(i):
                self.selected_chat_ids.append(self.chat_objects[i]['id'])
                
        if not self.selected_chat_ids:
            wx.MessageBox("Wybierz przynajmniej jeden czat!", "Uwaga", wx.OK | wx.ICON_WARNING)
            return

        # 2. Collect Options
        self.export_opts = {}
        has_type = False
        for i in range(self.lst_types.GetItemCount()):
            if self.lst_types.IsItemChecked(i):
                key = self.type_options[i][1]
                self.export_opts[key] = True
                has_type = True
        
        if not has_type:
            wx.MessageBox("Wybierz co chcesz wyeksportować!", "Uwaga", wx.OK | wx.ICON_WARNING)
            return

        # 3. Decision: Filter or Start?
        if len(self.selected_chat_ids) == 1:
            # Single chat -> Ask for participants
            self.show_filter_loading()
            tg_client.fetch_chat_members(self.selected_chat_ids[0])
        else:
            # Multiple chats -> Go straight to export
            self.setup_progress_view()
            tg_client.start_export(self.selected_chat_ids, self.export_opts, filter_user_id=None)

    def on_start_filtered_export(self, event):
        selection = self.cb_participants.GetSelection()
        user_filter = None
        
        # Index 0 is "ALL", so anything > 0 is a specific user
        if selection > 0:
            user_data = self.participant_list[selection - 1]
            user_filter = user_data['id']
            
        self.setup_progress_view()
        tg_client.start_export(self.selected_chat_ids, self.export_opts, filter_user_id=user_filter)

    def update_progress(self, current_chat_index, total_chats, message):
        if hasattr(self, 'status_lbl'):
             self.status_lbl.SetLabel(message)
             self.SetTitle(message)
             self.gauge.Pulse() # Keep it pulsing as we don't know total messages

    def on_finished(self):
        self.SetTitle("Eksport zakończony")
        wx.MessageBox("Zadanie wykonane. Sprawdź folder export.", "Sukces", wx.OK)
        # Return to main view
        self.setup_main_view()

if __name__ == '__main__':
    app = wx.App()
    frame = LoginFrame(None)
    frame.Show()
    app.MainLoop()