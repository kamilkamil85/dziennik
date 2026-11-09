# Wersja na GitHubie (bez serwera)

GitHub Actions co 30 minut w dni szkolne (w weekend co 3 godziny) loguje się do Librusa, szyfruje dane każdego dziecka jego hasłem i publikuje je na GitHub Pages. Telefon pobiera zaszyfrowany plik i odszyfrowuje go u siebie.

## Jednorazowa konfiguracja

1. Repo musi być **publiczne**, bo darmowe GitHub Pages nie działa z prywatnym. W kodzie nie ma żadnych haseł, a na stronie leżą tylko zaszyfrowane dane i imiona dzieci.
2. **Settings → Pages → Build and deployment → Source: GitHub Actions.**
3. **Settings → Secrets and variables → Actions → Secrets**, dodaj:

   | Sekret | Co wpisać |
   |---|---|
   | `LIBRUS1_LOGIN`, `LIBRUS1_HASLO` | login i hasło Librusa (tak samo dla 2 i 3) |
   | `DZIECKO1_HASLO_APP` | hasło do aplikacji dla dziecka 1, **min. 10 znaków**, najlepiej 3–4 losowe słowa (tak samo dla 2 i 3) |
   | `SESSION_KEY` | dowolny długi losowy ciąg, np. z generatora haseł (40+ znaków) |
   | `WAZNI_NADAWCY` | np. `nowak jan,kowalska anna` |

4. **Variables** (ta sama strona, zakładka Variables): `DZIECKO1_IMIE`, `DZIECKO2_IMIE`, `DZIECKO3_IMIE`.
5. **Actions → Dziennik → Run workflow**, żeby uruchomić pierwszy raz od razu.
6. Adres aplikacji: `https://<twoj-login>.github.io/<nazwa-repo>/`. Na telefonie w Chrome: menu ⋮ → „Dodaj do ekranu głównego”.

## Dobrze wiedzieć
- Hasło do aplikacji wpisuje się na telefonie raz. Telefon zapamiętuje klucz, a nie samo hasło.
- Zmiana `DZIECKO*_HASLO_APP` wylogowuje telefon tego dziecka i trzeba wpisać nowe hasło.
- Wiadomości mają skróconą treść, taką jak na liście w Librusie. Aplikacja nie otwiera ich w Librusie, więc nie zmienia ich statusu na przeczytane.
- GitHub uruchamia zadania z harmonogramu z opóźnieniem, czasem 10–20 minut.
- Jeśli Librus odrzuci hasło, przebieg w zakładce Actions będzie czerwony, a GitHub wyśle Ci maila.
