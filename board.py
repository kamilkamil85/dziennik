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
        "smog": smog(),
        "commute": commute(now),
        "place": {"name": "Karczew", "lat": 52.0874, "lon": 21.2492, "teryt": os.environ.get("TERYT_POWIAT", "1417")},
    }
