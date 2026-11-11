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
   | `RODZIC_HASLO_APP` | (opcjonalnie) hasło rodzica, min. 10 znaków. Odblokowuje całą trójkę naraz, przycisk „Jestem rodzicem” na ekranie logowania |
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
- Gdy Librus nie odpowiada albo odrzuci hasło, przebieg jest zielony z ostrzeżeniem, a strona zostaje z ostatnimi danymi. O tym, jak świeże są dane, mówi godzina na dole ekranu w aplikacji.

## Pewniejszy harmonogram: cron-job.org

Wbudowany harmonogram GitHuba w darmowych repo często pomija uruchomienia (zdarza się 1–2 razy na dobę zamiast co 30 minut). Darmowy serwis cron-job.org może wywoływać workflow punktualnie.

**1. Token GitHuba (tylko do uruchamiania tego workflow)**
- github.com → zdjęcie profilu → **Settings → Developer settings → Personal access tokens → Fine-grained tokens → Generate new token**
- Nazwa: `cron-dziennik`, Expiration: 1 rok (wpisz sobie w kalendarz odnowienie)
- Repository access: **Only select repositories → dziennik**
- Permissions → Repository permissions → **Actions: Read and write** (nic więcej)
- Skopiuj token (`github_pat_...`). Zobaczysz go tylko raz.

**2. Zadanie w cron-job.org**
- Załóż konto na https://cron-job.org i kliknij **Create cronjob**
- URL: `https://api.github.com/repos/kamilkamil85/dziennik/actions/workflows/dziennik.yml/dispatches`
- Schedule: **Custom**: co 30 minut, godziny 6–21, strefa czasowa **Europe/Warsaw**
- Zakładka **Advanced**:
  - Request method: **POST**
  - Headers:
    - `Authorization`: `Bearer github_pat_...` (Twój token)
    - `Accept`: `application/vnd.github+json`
    - `X-GitHub-Api-Version`: `2022-11-28`
  - Request body: `{"ref":"main"}`
- Zapisz i kliknij **Test run**. Poprawna odpowiedź to **204**, a w zakładce Actions pojawi się nowy przebieg.

Wbudowany harmonogram może zostać. Przebiegi nigdy nie idą jednocześnie, bo GitHub uruchamia je po kolei.

**Odnowienie tokenu:** wygeneruj nowy token tak samo, podmień go w cron-job.org (nagłówek `Authorization`), a nową datę ważności wpisz w repo: **Settings → Secrets and variables → Actions → Variables → `TOKEN_WAZNY_DO`**, w formacie `RRRR-MM-DD`. Aplikacja w trybie rodzica pokazuje tę datę pod godziną aktualizacji, a 14 dni przed końcem wyświetla ją na czerwono.
