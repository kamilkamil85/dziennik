# Dziennik – Librus dla dzieci

Prosta aplikacja na telefon (PWA): plan na dziś i jutro, oceny ze średnimi, terminarz z zadaniami, wiadomości i ogłoszenia. Dane bierze z Librusa Synergia przez bibliotekę [librus-synergia](https://pypi.org/project/librus-synergia/). To nieoficjalne API, które może przestać działać, a jego używanie może być niezgodne z regulaminem Librusa.

## Uruchomienie (Docker)

Pełna instrukcja dla serwera, z wariantami Tailscale, Cloudflare Tunnel i reverse proxy, jest w [INSTRUKCJA-MARIUSZ.md](INSTRUKCJA-MARIUSZ.md). Skrót:

1. Skopiuj `.env.example` jako `.env` i uzupełnij loginy, hasła, imiona i PIN-y.
2. `docker compose up -d --build`
3. Aplikacja słucha na `127.0.0.1:8000`. Dostęp dla telefonów:
   - **Tailscale (polecane):** `tailscale serve --bg 8000`, a dzieci otwierają `https://<nazwa-serwera>.<tailnet>.ts.net`. Udostępnij maszynę dzieciom przez „Share” w panelu Tailscale.
   - **Domena:** reverse proxy (Caddy, nginx, Cloudflare Tunnel) na `127.0.0.1:8000` z HTTPS. Wtedy w `.env` ustaw `COOKIE_SECURE=1` i **koniecznie** nadaj każdemu dziecku PIN.
4. Na telefonie w Chrome: menu ⋮ → „Dodaj do ekranu głównego”.

Aktualizacja: `git pull && docker compose up -d --build`.

## Co trzeba wiedzieć
- `.env` i katalog `data/` (sesje Librusa) dają dostęp do kont dzieci. Nie wrzucaj ich do gita i nikomu ich nie wysyłaj.
- Dane z Librusa są pobierane najwyżej raz na 15 minut (`CACHE_MINUTES`). Przycisk odświeżania działa najwyżej co 2 minuty.
- Otwarcie wiadomości w aplikacji oznacza ją w Librusie jako przeczytaną, tak samo jak w przeglądarce.
- Gdy Librus nie odpowiada, aplikacja pokazuje ostatnio pobrane dane.

## Lokalnie bez Dockera (Windows)
```
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python -m uvicorn app.main:app --port 8000
```
Podgląd bez haseł: w `.env` ustaw `DEMO=1` oraz imiona dzieci.
