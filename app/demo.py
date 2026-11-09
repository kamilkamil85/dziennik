"""Przykładowe dane do podglądu wyglądu (DEMO=1). Nie łączy się z Librusem."""

from datetime import date, timedelta
from typing import Any


def _d(n: int) -> str:
    return (date.today() + timedelta(days=n)).isoformat()


def today(name: str) -> dict[str, Any]:
    plan = [
        ("8:00", "8:45", "Matematyka", "Kowalska J.", "12"),
        ("8:55", "9:40", "Język polski", "Nowak A.", "21"),
        ("9:50", "10:35", "Historia", "Wiśniewski P.", "8"),
        ("10:55", "11:40", "Wychowanie fizyczne", "Lis M.", "sala gim."),
        ("11:50", "12:35", "Język angielski", "Smith K.", "14"),
    ]
    lessons = []
    for i, (f, t, s, te, r) in enumerate(plan, 1):
        lessons.append({"no": i, "from": f, "to": t, "subject": s, "teacher": te, "room": r,
                        "canceled": i == 3, "substitution": i == 5, "note": None,
                        "original": "Biologia" if i == 5 else None})
        if i == 5:
            lessons[-1]["subject"] = "Język angielski"
    return {
        "student": name, "today": _d(0),
        "days": [{"date": _d(0), "lessons": lessons}, {"date": _d(1), "lessons": [dict(l, canceled=False, substitution=False, original=None) for l in lessons[:4]]}],
        "soon": [
            {"date": _d(2), "category": "Sprawdzian", "subject": "Matematyka", "content": "Ułamki dziesiętne, dział 3"},
            {"date": _d(4), "category": "Kartkówka", "subject": "Język angielski", "content": "Słówka unit 4"},
        ],
        "updated": "demo",
    }


def grades() -> dict[str, Any]:
    def g(v: str, cat: str, w: int, d: int, kind: str = "normal") -> dict[str, Any]:
        return {"value": v, "date": _d(-d), "category": cat, "weight": w, "semester": 1, "kind": kind, "comments": [], "teacher": None}
    subs = [
        {"subject": "Język angielski", "grades": [g("5", "Kartkówka", 2, 3), g("4+", "Odpowiedź", 1, 12)], "average": {"1": 4.84}},
        {"subject": "Matematyka", "grades": [g("4", "Sprawdzian", 3, 1), g("5-", "Kartkówka", 2, 9), g("3+", "Praca domowa", 1, 20), g("1", "Kartkówka", 2, 30)], "average": {"1": 3.48}},
        {"subject": "Historia", "grades": [g("6", "Projekt", 2, 5), g("5", "Sprawdzian", 3, 18)], "average": {"1": 5.4}},
    ]
    newest = sorted(({**x, "subject": s["subject"]} for s in subs for x in s["grades"]), key=lambda x: x["date"], reverse=True)[:6]
    return {"subjects": subs, "newest": newest, "updated": "demo"}


def agenda() -> dict[str, Any]:
    return {
        "events": [
            {"date": _d(2), "time": None, "category": "Sprawdzian", "subject": "Matematyka", "content": "Ułamki dziesiętne, dział 3"},
            {"date": _d(4), "time": None, "category": "Kartkówka", "subject": "Język angielski", "content": "Słówka unit 4"},
            {"date": _d(9), "time": "17:00", "category": "Wywiadówka", "subject": "", "content": "Zebranie z rodzicami, sala 12"},
        ],
        "homework": [{"topic": "Wypracowanie", "text": "Opis przeżyć wewnętrznych, min. 200 słów.", "date": _d(-1), "due": _d(3), "attachments": 0}],
        "updated": "demo",
    }


def messages() -> dict[str, Any]:
    return {
        "messages": [
            {"id": "1", "sender": "Kowalska Anna", "topic": "Wycieczka do muzeum", "preview": "Szanowni Państwo, w przyszły piątek klasa jedzie...", "date": _d(-1), "unread": True, "attachment": True, "important": True},
            {"id": "2", "sender": "Sekretariat", "topic": "Ubezpieczenie NNW", "preview": "Przypominamy o wpłatach do końca miesiąca.", "date": _d(-6), "unread": False, "attachment": False, "important": False},
        ],
        "notices": [{"id": "a", "subject": "Dzień sportu", "content": "W czwartek lekcje do 11:40, potem zawody na boisku.", "date": _d(-2)}],
        "updated": "demo",
    }


def message(mid: str) -> dict[str, Any]:
    return {"id": mid, "sender": "Kowalska Anna", "topic": "Wycieczka do muzeum", "date": _d(-1),
            "content": "Szanowni Państwo,\n\nw przyszły piątek klasa jedzie do muzeum. Zbiórka 7:45 przed szkołą.\n\nPozdrawiam", "attachments": ["zgoda.pdf"]}
