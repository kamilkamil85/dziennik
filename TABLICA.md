# Tablica na lodówce

Adres: **https://kamilkamil85.github.io/dziennik/tablica/**

Tablica pokazuje zegar, pogodę (IMGW i Open-Meteo), ostrzeżenia IMGW dla powiatu otwockiego, godziny lekcji dzieci z zajęciami dodatkowymi, jakość powietrza z czujnika SmogTok „Karczew, Andersa” oraz rano (6:45–9:15) czas dojazdu do pracy z korkami. Od 17:00 pokazuje plan na jutro, a w nocy (22:00–6:00) tylko zegar i pogodę.

Dane z Librusa na tablicy są okrojone: tylko godzina pierwszej i ostatniej lekcji oraz odwołane lekcje. Bez ocen i wiadomości. Plik jest zaszyfrowany osobnym hasłem.

## 1. Ustawienia w repo (jednorazowo)

**Settings → Secrets and variables → Actions → Secrets:**

| Sekret | Co wpisać |
|---|---|
| `TABLICA_HASLO` | hasło tablicy, min. 10 znaków. Wpisujesz je raz na tablecie. |
| `TOMTOM_KEY` | klucz z https://developer.tomtom.com (darmowe konto, bez karty): Dashboard → Keys. Bez klucza tablica po prostu nie pokazuje dojazdu. |

**Variables:**

| Zmienna | Co wpisać |
|---|---|
| `ZAJECIA` | lista zajęć dodatkowych w JSON (wzór niżej) |
| `DOJAZD_Z`, `DOJAZD_DO` | (opcjonalnie) współrzędne „szerokość,długość”. Domyślnie Karczew, Roweckiego → Warszawa, Leżajska. |
| `SMOGTOK_ID` | (opcjonalnie) numer czujnika SmogTok, domyślnie 3219 |

## 2. Zajęcia dodatkowe: edycja

Settings → Secrets and variables → Actions → **Variables → `ZAJECIA` → ołówek**. Zmiana pojawi się na tablicy przy najbliższym przebiegu.

```json
[
  {"kto": "Tadek", "co": "Crossfit", "dzien": "poniedziałek, środa", "od": "18:30", "do": "19:30"},
  {"kto": "Hela", "co": "Lekkoatletyka", "dzien": "wtorek, piątek", "od": "17:00", "do": "18:00"}
]
```

- `kto`: imię dokładnie jak w aplikacji.
- `dzien`: dni tygodnia małymi literami, po przecinku.
- `do` może być puste (`""`), jeśli nie znasz godziny końca.
- Odwołane zajęcia w konkretny dzień: `"bez": ["2026-12-02"]`.
- Jednorazowe zajęcia: zamiast `dzien` wpisz `"data": "2026-12-05"`.

Jeśli JSON będzie miał błąd (np. brak przecinka), tablica pokaże wszystko poza zajęciami, a w zakładce Actions pojawi się ostrzeżenie.

## 3. Tablet (Huawei MediaPad T5)

1. Sklep Play: zaktualizuj **Android System WebView** i **Chrome**.
2. Zainstaluj **Fully Kiosk Browser** (wersja darmowa wystarczy).
3. W Fully: **Settings**:
   - *Web Content Settings → Start URL:* `https://kamilkamil85.github.io/dziennik/tablica/`
   - *Device Management → Keep Screen On:* włączone
   - *Device Management → Launch on Boot:* włączone
   - *Web Browsing Settings → Enable Pull to Refresh:* wyłączone
   - *Fullscreen Mode / Hide navigation bar:* włączone
4. Otwórz tablicę i wpisz hasło tablicy. Tablet je zapamięta.
5. Jasność ekranu ustaw ręcznie na ok. 40–50%: na tablicę patrzy się z daleka.

**Bateria:** tablet stale na ładowarce może z czasem mieć spuchniętą baterię. Bezpieczniej podłączyć go przez gniazdko z timerem albo inteligentną wtyczkę i ładować np. 6:00–8:00 i 15:00–17:00. Ekran włączony cały czas zużyje baterię mniej więcej w tym tempie, więc sprawdź pierwszego dnia, czy poziom się utrzymuje, i w razie potrzeby wydłuż okna ładowania.

**Test wyglądu o innej godzinie:** dopisz do adresu np. `?czas=2026-11-25T07:40`.
