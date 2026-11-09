# Dziennik – uruchomienie na serwerze

Cześć Mariusz, dzięki, że to u siebie postawisz. Całość to jeden mały kontener (Python, około 100 MB RAM). Do Librusa łączy się najwyżej raz na 15 minut na każde dziecko.

## Czego potrzebujesz
- Docker z Compose v2 (`docker compose version`)
- Plik `.env` ode mnie. Są w nim loginy i hasła dzieci do Librusa, więc trzymaj go tylko na serwerze i nie wrzucaj do gita.

## Krok 1. Kod i konfiguracja
```bash
git clone <adres-repo> dziennik
cd dziennik
# wgraj .env ode mnie do tego katalogu
chmod 600 .env
```

## Krok 2. Wybierz jeden wariant dostępu

### Wariant A: Tailscale (nic nie wystawiamy do internetu)
1. W panelu Tailscale wygeneruj klucz: **Settings → Keys → Generate auth key** (bez „Reusable” i bez „Ephemeral”).
2. Wpisz go w `.env` jako `TS_AUTHKEY=tskey-...`.
3. Upewnij się, że w tailnecie masz włączone **HTTPS certificates** i **MagicDNS** (Admin → DNS).
4. Uruchom:
   ```bash
   docker compose --profile tailscale up -d --build
   ```
5. Aplikacja będzie pod adresem `https://dziennik.<twoj-tailnet>.ts.net`.
6. Udostępnij mi maszynę `dziennik`: **Machines → dziennik → Share**, na mój adres e-mail. Dzieci instalują Tailscale na telefonach i logują się na moje konto, a ich telefonami zarządzam ja.

Klucz jest potrzebny tylko przy pierwszym uruchomieniu. Potem stan trzymany jest w `tailscale/state/`.

### Wariant B: Cloudflare Tunnel (domena, bez otwierania portów)
1. W Cloudflare: **Zero Trust → Networks → Tunnels → Create tunnel** (typ Cloudflared) i skopiuj token.
2. W tunelu dodaj **Public hostname**, np. `dziennik.twojadomena.pl` → Service `HTTP` → `dziennik:8000`.
3. Wpisz token w `.env` jako `CLOUDFLARE_TUNNEL_TOKEN=...`.
4. Uruchom:
   ```bash
   docker compose --profile cloudflare up -d --build
   ```

### Wariant C: Twój reverse proxy (Caddy, nginx, Traefik)
```bash
docker compose up -d --build
```
Aplikacja słucha na `127.0.0.1:8000`. Port zmienisz przez `DZIENNIK_PORT` w `.env`. Przykład dla Caddy:
```
dziennik.twojadomena.pl {
    reverse_proxy 127.0.0.1:8000
}
```
Dla nginx wystarczy `proxy_pass http://127.0.0.1:8000;` z `proxy_set_header X-Forwarded-Proto $scheme;`, a HTTPS jest konieczny.

W wariantach B i C aplikacja jest widoczna w internecie. Każde dziecko ma swój PIN, a po 5 błędnych próbach jest 5 minut blokady.

## Krok 3. Sprawdzenie
```bash
docker compose ps
docker compose logs -f dziennik
curl -s http://127.0.0.1:8000/api/health    # {"ok":true,"children":3}
```

## Aktualizacje
```bash
git pull
docker compose --profile <wariant> up -d --build
```
Przy wariancie C pomiń `--profile`.

## Co jest gdzie
- `.env` – loginy i hasła do Librusa oraz PIN-y. **Poufne.**
- `data/` – zapisane sesje Librusa (dzięki nim apka nie loguje się co chwilę) i klucz do ciasteczek. **Też poufne.** Jeśli zginie, nic złego się nie stanie: apka zaloguje się od nowa.
- `tailscale/state/` – tożsamość maszyny w Tailscale (tylko wariant A).

Jeśli coś nie działa, wyślij mi wynik `docker compose logs --tail 50 dziennik`.
