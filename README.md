# Telegram Exporter (TGExporter)

Prosta i dostępna aplikacja desktopowa do eksportowania historii czatów, zdjęć, wiadomości głosowych i plików z Telegrama.

Aplikacja została zaprojektowana z myślą o dostępności oraz wygodzie użytkowania, wykorzystując natywne kontrolki systemu Windows.

## Funkcje

*   **Eksport Selektywny:** Wybierz konkretne czaty oraz typy danych do pobrania (Tekst, Zdjęcia, Głosówki, Wideo, Pliki).
*   **Filtrowanie Nadawcy:** Przy eksporcie pojedynczego czatu możesz wybrać, aby pobrać wiadomości tylko od konkretnej osoby (np. tylko głosówki osoby z wybranego chatu z pominięciem twoich).
*   **Bezpieczeństwo:** Opcja "Zapamiętaj mnie" szyfruje sesję logowania przy użyciu unikalnego identyfikatora sprzętowego (Windows Machine GUID). Plik konfiguracyjny nie zadziała na innym komputerze.
*   **Dostępność:** Interfejs oparty na `wxPython` z pełną obsługą nawigacji klawiaturą.

## Wymagania

*   Python 3.8+
*   Konto Telegram (API ID oraz API Hash)

## Instalacja

1.  Sklonuj repozytorium:
    ```bash
    git clone https://github.com/TWOJA_NAZWA_UZYTKOWNIKA/TGExporter.git
    cd TGExporter
    ```

2.  Zainstaluj wymagane biblioteki:
    ```bash
    pip install -r requirements.txt
    ```

3.  Skonfiguruj API:
    *   Zmień nazwę pliku `config.example.py` na `config.py`.
    *   Edytuj `config.py` i wpisz swoje `API_ID` oraz `API_HASH`. Możesz je uzyskać za darmo na stronie [my.telegram.org](https://my.telegram.org).

## Użycie

Uruchom aplikację komendą:
```bash
python gui.py
```

1.  Zaloguj się numerem telefonu.
2.  Zaznacz czaty na liście (Spacja zaznacza/odznacza).
3.  Wybierz typy danych do eksportu.
4.  Kliknij "Dalej / Eksportuj".

## Struktura Plików

*   `gui.py` - Główny interfejs graficzny.
*   `tg_logic.py` - Logika komunikacji z Telegramem (Telethon).
*   `security.py` - Moduł szyfrowania konfiguracji.
*   `export/` - Tutaj trafią wyeksportowane dane (folder tworzony automatycznie).
