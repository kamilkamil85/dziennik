"""Dane dla tablicy na lodówce: godziny lekcji, zajęcia dodatkowe, smog i dojazd.

Celowo okrojone: bez ocen, wiadomości i sprawdzianów. Szyfrowane osobnym hasłem (TABLICA_HASLO).
"""

from __future__ import annotations

import json
import os
import urllib.request
from datetime import datetime
from typing import Any

UA = "dziennik-tablica/1.0 (prywatny dashboard rodzinny)"
DAYS = ["poniedziałek", "wtorek", "środa", "czwartek", "piątek", "sobota", "niedziela"]
THEMES = {1: "legia", 2: "fiolet", 3: "magia"}


def _get_json(url: str, timeout: int = 20) -> Any:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def school_days(today_section: dict | None) -> list[dict[str, Any]]:
    """Dla każdego dnia: od której do której są lekcje (bez odwołanych) i co się zmieniło."""
    out = []
    for day in (today_section or {}).get("days", []):
        lessons = day.get("lessons", [])
        held = [l for l in lessons if not l.get("canceled") and l.get("from")]
        notes = []
        if lessons and lessons[0].get("canceled"):
            notes.append(f"{lessons[0].get('no') or 1}. lekcja odwołana")
        if len(lessons) > 1 and lessons[-1].get("canceled"):
            notes.append("ostatnia lekcja odwołana")
        if lessons and not held:
            notes.append("wszystkie lekcje odwołane")
        out.append({
            "date": day["date"],
            "start": held[0]["from"] if held else None,
            "end": held[-1]["to"] if held else None,
            "notes": notes,
        })
    return out


def activities() -> list[dict[str, Any]]:
    """Zajęcia dodatkowe ze zmiennej ZAJECIA (JSON). Błędny JSON nie psuje reszty."""
    raw = os.environ.get("ZAJECIA", "").strip()
    if not raw:
        return []
    try:
        items = json.loads(raw)
    except ValueError as err:
        print(f"::warning::ZAJECIA: błędny JSON ({err}), zajęcia pominięte")
        return []
    out = []
    for it in items if isinstance(items, list) else []:
        days = [d.strip().lower() for d in str(it.get("dzien", "")).split(",") if d.strip()]
        out.append({
            "kto": str(it.get("kto", "")), "co": str(it.get("co", "")),
            "dni": [DAYS.index(d) for d in days if d in DAYS],
            "data": it.get("data"),  # jednorazowe zajęcia: "RRRR-MM-DD"
            "od": it.get("od") or "", "do": it.get("do") or "",
            "bez": it.get("bez", []),  # daty, kiedy zajęć nie ma
        })
    return out


def smog() -> dict[str, Any] | None:
    probe = os.environ.get("SMOGTOK_ID", "3219")
    try:
        d = _get_json(f"https://smogtok.com/apprest/probedata/{probe}")
        regs = {r["REGNAME"]: r for r in d.get("REGS", [])}
        return {
            "name": d.get("NAME"), "index": d.get("IJP"), "dt": d.get("DT"),
            "pm25": regs.get("PM 2,5", {}).get("VALUE"), "pm10": regs.get("PM 10", {}).get("VALUE"),
        }
    except Exception as err:
        print(f"  smog: brak danych ({type(err).__name__})")
        return None


def commute(now: datetime) -> dict[str, Any] | None:
    """Czas dojazdu z korkami (TomTom), tylko rano w godzinach z DOJAZD_GODZINY."""
    key = os.environ.get("TOMTOM_KEY", "")
    hours = os.environ.get("DOJAZD_GODZINY", "6:45-9:15")
    start, end = [datetime.strptime(x, "%H:%M").time() for x in hours.split("-")]
    if not key or not (start <= now.time() <= end):
        return None
    src = os.environ.get("DOJAZD_Z", "52.0874,21.2492")
    dst = os.environ.get("DOJAZD_DO", "52.1920,20.9722")
    url = (f"https://api.tomtom.com/routing/1/calculateRoute/{src}:{dst}/json"
           f"?traffic=true&travelMode=car&routeType=fastest&computeTravelTimeFor=all&key={key}")
    try:
        s = _get_json(url)["routes"][0]["summary"]
        return {
            "minutes": round(s["travelTimeInSeconds"] / 60),
            "normal": round(s.get("noTrafficTravelTimeInSeconds", s["travelTimeInSeconds"]) / 60),
            "delay": round(s.get("trafficDelayInSeconds", 0) / 60),
            "at": now.strftime("%H:%M"),
        }
    except Exception as err:
        print(f"  dojazd: brak danych ({type(err).__name__})")
        return None


def calendars(now: datetime) -> list[dict[str, Any]]:
    """Wydarzenia z kalendarzy Google (tajne adresy iCal) na dziś i 6 kolejnych dni.

    KALENDARZE: jeden kalendarz na linię, "Nazwa|#kolor|https://...ics".
    """
    raw = os.environ.get("KALENDARZE", "").strip()
    if not raw:
        return []
    import icalendar
    import recurring_ical_events
    from datetime import date as _date, timedelta
    from zoneinfo import ZoneInfo

    tz = ZoneInfo("Europe/Warsaw")
    start = now.date()
    end = start + timedelta(days=7)
    out: list[dict[str, Any]] = []
    for line in raw.splitlines():
        parts = [p.strip() for p in line.split("|")]
        if len(parts) != 3 or not parts[2].startswith("http"):
            continue
        name, color, url = parts
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=30) as r:
                cal = icalendar.Calendar.from_ical(r.read())
            for ev in recurring_ical_events.of(cal).between(start, end):
                s, e = ev.get("DTSTART").dt, ev.get("DTEND").dt if ev.get("DTEND") else None
                all_day = isinstance(s, _date) and not isinstance(s, datetime)
                if not all_day:
                    s = s.astimezone(tz) if s.tzinfo else s.replace(tzinfo=tz)
                    e = (e.astimezone(tz) if e.tzinfo else e.replace(tzinfo=tz)) if e else None
                first = s if all_day else s.date()
                last = (e - timedelta(days=1)) if (all_day and e) else (e.date() if e else first)
                d = max(first, start)
                while d <= min(last, end - timedelta(days=1)):  # wielodniowe wydarzenia na każdy dzień
                    out.append({
                        "date": d.isoformat(), "cal": name, "color": color,
                        "title": str(ev.get("SUMMARY", "")).strip() or "(bez tytułu)",
                        "allDay": all_day,
                        "from": None if all_day else s.strftime("%H:%M"),
                        "to": None if all_day or not e else e.strftime("%H:%M"),
                    })
                    d += timedelta(days=1)
        except Exception as err:
            print(f"::warning::Kalendarz {name}: nie udało się pobrać ({type(err).__name__})")
    out.sort(key=lambda x: (x["date"], not x["allDay"], x["from"] or ""))
    return out


def _demo_events(now: datetime) -> list[dict[str, Any]]:
    if os.environ.get("DEMO") != "1":
        return []
    from datetime import timedelta
    d = lambda n: (now.date() + timedelta(days=n)).isoformat()
    return [
        {"date": d(0), "cal": "Rodzina", "color": "#3a7bd5", "title": "Dentysta Hela", "allDay": False, "from": "16:00", "to": "16:30"},
        {"date": d(1), "cal": "Kamil", "color": "#e67e22", "title": "Wyjazd służbowy", "allDay": True, "from": None, "to": None},
        {"date": d(2), "cal": "Rodzina", "color": "#3a7bd5", "title": "Urodziny babci", "allDay": True, "from": None, "to": None},
        {"date": d(4), "cal": "Rodzina", "color": "#3a7bd5", "title": "Zebranie w szkole", "allDay": False, "from": "17:30", "to": "18:30"},
    ]


def patron(now: datetime) -> dict[str, Any] | None:
    """Patron dnia z pliku patroni.json w repo (dwuzdaniowe notki na każdy dzień)."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "patroni.json")
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f).get(now.strftime("%m-%d"))
    except (OSError, ValueError):
        return None


def build(everything: dict[str, dict], children: dict, now: datetime) -> dict[str, Any]:
    kids = []
    for n, child in children.items():
        data = everything.get(str(n), {})
        kids.append({"n": n, "name": child.name, "theme": THEMES.get(n, ""),
                     "days": school_days(data.get("today"))})
    return {
        "generated": now.strftime("%Y-%m-%d %H:%M"),
        "kids": kids,
        "activities": activities(),
        "events": calendars(now) or _demo_events(now),
        "patron": patron(now),
        "smog": smog(),
        "commute": commute(now),
        "place": {"name": "Karczew", "lat": 52.0874, "lon": 21.2492, "teryt": os.environ.get("TERYT_POWIAT", "1417")},
    }
