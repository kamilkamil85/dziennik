"""Librus dla dzieci: mały serwer, który pobiera dane z Librusa i podaje je aplikacji PWA."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from dataclasses import asdict
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Awaitable, Callable
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from librus_synergia import Librus, LibrusError, LibrusInvalidCredentialsError
from librus_synergia.client import LibrusSessionData
from librus_synergia.parsers import parse_grade_value
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

TZ = ZoneInfo("Europe/Warsaw")
DATA_DIR = Path(os.environ.get("DATA_DIR", ROOT / "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
STATIC_DIR = ROOT / "static"

CACHE_TTL = int(os.environ.get("CACHE_MINUTES", "15")) * 60
MIN_REFRESH_GAP = 120  # "odśwież" nie częściej niż co 2 minuty
COOKIE_NAME = "ld_auth"
COOKIE_MAX_AGE = 180 * 24 * 3600
DEMO = os.environ.get("DEMO", "0") == "1"
WAZNI_NADAWCY = [
    s.strip().lower() for s in os.environ.get("WAZNI_NADAWCY", "").split(",") if s.strip()
]


def _secret() -> bytes:
    """Klucz do podpisywania ciasteczek. Z .env albo wygenerowany raz i zapisany w data/."""
    if os.environ.get("APP_SECRET"):
        return os.environ["APP_SECRET"].encode()
    path = DATA_DIR / "app_secret"
    if not path.exists():
        path.write_text(secrets.token_hex(32))
        os.chmod(path, 0o600)
    return path.read_text().strip().encode()


SECRET = _secret()


# ---------- dzieci ----------

class Child:
    def __init__(self, n: int, name: str, login: str, password: str, pin: str) -> None:
        self.n = n
        self.name = name
        self.login = login
        self.password = password
        self.pin = pin
        self.session_file = DATA_DIR / f"session_{n}.json"
        self.lock = asyncio.Lock()
        self.cache: dict[str, tuple[float, Any]] = {}
        self._librus: Librus | None = None
        self.bad_login_until = 0.0  # po odrzuconym haśle nie próbujemy przez 30 min

    def librus(self) -> Librus:
        if self._librus is None:
            saved = None
            if self.session_file.exists():
                try:
                    saved = LibrusSessionData(**json.loads(self.session_file.read_text()))
                except (ValueError, TypeError):
                    saved = None
            self._librus = Librus(
                self.login,
                self.password,
                session_data=saved,
                on_session_update=self._save_session,
                cache_reference_data=True,
            )
        return self._librus

    def _save_session(self, data: LibrusSessionData) -> None:
        tmp = self.session_file.with_suffix(".tmp")
        tmp.write_text(json.dumps(asdict(data)))
        try:
            os.chmod(tmp, 0o600)
        except OSError:
            pass
        tmp.replace(self.session_file)

    async def cached(self, key: str, loader: Callable[[Librus], Awaitable[Any]], refresh: bool) -> Any:
        if DEMO:
            from app import demo
            if key.startswith("msg:"):
                return demo.message(key[4:])
            return demo.today(self.name) if key == "today" else getattr(demo, key)()

        def usable(hit: tuple[float, Any] | None) -> bool:
            if not hit:
                return False
            age = time.time() - hit[0]
            return age < MIN_REFRESH_GAP or (not refresh and age < CACHE_TTL)

        if usable(self.cache.get(key)):
            return self.cache[key][1]
        if time.time() < self.bad_login_until:
            raise HTTPException(502, "Librus nie przyjął loginu lub hasła tego dziecka. Sprawdź dane w pliku .env.")
        async with self.lock:
            hit = self.cache.get(key)
            if usable(hit):
                return hit[1]  # type: ignore[index]
            try:
                value = await loader(self.librus())
            except LibrusInvalidCredentialsError:
                self.bad_login_until = time.time() + 1800
                raise HTTPException(502, "Librus nie przyjął loginu lub hasła tego dziecka.")
            except LibrusError as err:
                if hit:  # Librus nie odpowiada: pokaż ostatnie dane zamiast błędu
                    stale = dict(hit[1]) if isinstance(hit[1], dict) else hit[1]
                    if isinstance(stale, dict):
                        stale["stale"] = True
                    return stale
                raise HTTPException(503, f"Librus nie odpowiada ({type(err).__name__}). Spróbuj za chwilę.")
            if isinstance(value, dict):
                value["updated"] = datetime.now(TZ).strftime("%H:%M")
            self.cache[key] = (time.time(), value)
            return value


def load_children() -> dict[int, Child]:
    out: dict[int, Child] = {}
    for n in range(1, 10):
        login = os.environ.get(f"LIBRUS{n}_LOGIN")
        password = os.environ.get(f"LIBRUS{n}_HASLO")
        if not DEMO and (not login or not password):
            continue
        if DEMO and not os.environ.get(f"DZIECKO{n}_IMIE"):
            continue
        name = os.environ.get(f"DZIECKO{n}_IMIE", f"Dziecko {n}")
        pin = os.environ.get(f"DZIECKO{n}_PIN", "")
        out[n] = Child(n, name, login or "", password or "", pin)
    return out


CHILDREN = load_children()


# ---------- logowanie PIN-em (podpisane ciasteczko) ----------

def _sign(payload: str) -> str:
    sig = hmac.new(SECRET, payload.encode(), hashlib.sha256).hexdigest()[:32]
    return base64.urlsafe_b64encode(f"{payload}|{sig}".encode()).decode()


def _unlocked(request: Request) -> set[int]:
    raw = request.cookies.get(COOKIE_NAME)
    if not raw:
        return set()
    try:
        payload, sig = base64.urlsafe_b64decode(raw.encode()).decode().rsplit("|", 1)
    except (ValueError, UnicodeDecodeError):
        return set()
    good = hmac.new(SECRET, payload.encode(), hashlib.sha256).hexdigest()[:32]
    if not hmac.compare_digest(sig, good):
        return set()
    return {int(x) for x in payload.split(",") if x.isdigit()}


def child_dep(n: int, request: Request) -> Child:
    child = CHILDREN.get(n)
    if child is None:
        raise HTTPException(404, "Nie ma takiego dziecka.")
    if child.pin and n not in _unlocked(request):
        raise HTTPException(401, "Podaj PIN.")
    return child


_failed: dict[str, list[float]] = {}


class PinIn(BaseModel):
    pin: str


app = FastAPI(title="Librus dla dzieci", docs_url=None, redoc_url=None)


@app.get("/api/children")
def children(request: Request) -> list[dict[str, Any]]:
    unlocked = _unlocked(request)
    return [
        {"n": c.n, "name": c.name, "locked": bool(c.pin) and c.n not in unlocked}
        for c in CHILDREN.values()
    ]


@app.post("/api/{n}/unlock")
def unlock(n: int, body: PinIn, request: Request, response: Response) -> dict[str, bool]:
    child = CHILDREN.get(n)
    if child is None:
        raise HTTPException(404, "Nie ma takiego dziecka.")
    ip = request.client.host if request.client else "?"
    now = time.time()
    tries = [t for t in _failed.get(ip, []) if now - t < 300]
    if len(tries) >= 5:
        raise HTTPException(429, "Za dużo prób. Odczekaj 5 minut.")
    if child.pin and not hmac.compare_digest(body.pin, child.pin):
        _failed[ip] = tries + [now]
        raise HTTPException(403, "Zły PIN.")
    ids = _unlocked(request) | {n}
    response.set_cookie(
        COOKIE_NAME, _sign(",".join(map(str, sorted(ids)))),
        max_age=COOKIE_MAX_AGE, httponly=True, samesite="strict",
        secure=os.environ.get("COOKIE_SECURE", "0") == "1",
    )
    return {"ok": True}


# ---------- dane ----------

def _today() -> date:
    return datetime.now(TZ).date()


def _lesson(lesson: Any, subjects: dict, teachers: dict, rooms: dict) -> dict[str, Any]:
    orig = lesson.original
    return {
        "no": lesson.lesson_no,
        "from": lesson.hour_from,
        "to": lesson.hour_to,
        "subject": subjects.get(lesson.subject_id, "?"),
        "teacher": teachers.get(lesson.teacher_id, ""),
        "room": rooms.get(lesson.classroom_id, ""),
        "canceled": lesson.is_canceled,
        "substitution": lesson.is_substitution,
        "note": lesson.substitution_note,
        "original": subjects.get(orig.subject_id) if orig else None,
    }


async def _load_today(lib: Librus) -> dict[str, Any]:
    today = _today()
    subjects, teachers, rooms = await asyncio.gather(lib.subjects(), lib.teachers(), lib.classrooms())
    week = await lib.timetable()
    if today.weekday() >= 4:  # od piątku warto widzieć też poniedziałek
        try:
            week = {**week, **await lib.timetable(week_of=today + timedelta(days=7))}
        except LibrusError:
            pass
    days = sorted(d for d, lessons in week.items() if d >= today and lessons)[:2]
    agenda, cats = await asyncio.gather(lib.agenda(), lib.agenda_categories())
    soon = []
    for ev in agenda:
        if ev.date and today.isoformat() <= ev.date <= (today + timedelta(days=7)).isoformat():
            soon.append({
                "date": ev.date,
                "category": cats.get(ev.category_id, "Wydarzenie") if ev.category_id else "Wydarzenie",
                "subject": subjects.get(ev.subject_id, "") if ev.subject_id else "",
                "content": ev.content,
            })
    soon.sort(key=lambda e: e["date"])
    me = await lib.me()
    return {
        "student": f"{me.first_name} {me.last_name}".strip(),
        "today": today.isoformat(),
        "days": [
            {"date": d.isoformat(), "lessons": [_lesson(l, subjects, teachers, rooms) for l in week[d]]}
            for d in days
        ],
        "soon": soon,
    }


async def _load_grades(lib: Librus) -> dict[str, Any]:
    grades, subjects, cats, grading = await asyncio.gather(
        lib.grades(), lib.subjects(), lib.grade_categories(), lib.grading_system()
    )
    by_subject: dict[str, dict[str, Any]] = {}
    for g in grades:
        name = subjects.get(g.subject_id, "Inne")
        s = by_subject.setdefault(name, {"subject": name, "grades": [], "sum": {}, "w": {}})
        cat = cats.get(g.category_id) if g.category_id is not None else None
        weight = getattr(cat, "weight", None) if cat else None
        counts = bool(cat.count_to_average) if cat else False
        num = parse_grade_value(g.value, grading)
        kind = "final" if g.is_final else "semester" if g.is_semester else \
            "proposal" if (g.is_final_proposition or g.is_semester_proposition) else "normal"
        s["grades"].append({
            "value": g.value, "date": g.add_date[:10] if g.add_date else None,
            "category": cat.name if cat else "", "weight": weight, "semester": g.semester,
            "kind": kind, "comments": g.comments, "teacher": None,
        })
        if kind == "normal" and counts and num is not None and weight:
            sem = str(g.semester or 0)
            s["sum"][sem] = s["sum"].get(sem, 0) + num * weight
            s["w"][sem] = s["w"].get(sem, 0) + weight
    out = []
    for s in by_subject.values():
        avg = {sem: round(s["sum"][sem] / s["w"][sem], 2) for sem in s["sum"] if s["w"][sem]}
        s["grades"].sort(key=lambda x: x["date"] or "", reverse=True)
        out.append({"subject": s["subject"], "grades": s["grades"], "average": avg})
    out.sort(key=lambda s: s["subject"].lower())
    newest = sorted(
        ({**g, "subject": s["subject"]} for s in out for g in s["grades"] if g["date"]),
        key=lambda g: g["date"], reverse=True,
    )[:8]
    return {"subjects": out, "newest": newest}


async def _load_agenda(lib: Librus) -> dict[str, Any]:
    today = _today().isoformat()
    agenda, cats, subjects, hw = await asyncio.gather(
        lib.agenda(), lib.agenda_categories(), lib.subjects(), lib.homework()
    )
    events = [
        {
            "date": ev.date, "time": ev.time_from,
            "category": cats.get(ev.category_id, "Wydarzenie") if ev.category_id else "Wydarzenie",
            "subject": subjects.get(ev.subject_id, "") if ev.subject_id else "",
            "content": ev.content,
        }
        for ev in agenda if ev.date and ev.date >= today
    ]
    events.sort(key=lambda e: (e["date"], e["time"] or ""))
    homework = [
        {"topic": h.topic, "text": h.text, "date": h.date, "due": h.due_date,
         "attachments": len(h.attachments)}
        for h in hw if (h.due_date or h.date or "") >= today
    ]
    homework.sort(key=lambda h: h["due"] or h["date"] or "")
    return {"events": events, "homework": homework}


def _important(sender: str, topic: str) -> bool:
    text = f"{sender} {topic}".lower()
    return any(n in text for n in WAZNI_NADAWCY)


async def _load_messages(lib: Librus) -> dict[str, Any]:
    msgs, notices = await asyncio.gather(lib.messages(limit=25), lib.announcements())
    return {
        "messages": [
            {"id": m.id, "sender": m.sender_name, "topic": m.topic, "preview": m.content[:160], "body": m.content,
             "date": m.send_date, "unread": m.read_date is None, "attachment": m.has_attachment,
             "important": _important(m.sender_name, m.topic)}
            for m in msgs
        ],
        "notices": [
            {"id": a.id, "subject": a.subject, "content": a.content,
             "date": a.start_date or a.creation_date}
            for a in sorted(notices, key=lambda a: a.start_date or a.creation_date or "", reverse=True)[:15]
        ],
    }


def _refresh(request: Request) -> bool:
    return request.query_params.get("refresh") == "1"


@app.get("/api/{n}/today")
async def today(request: Request, child: Child = Depends(child_dep)) -> Any:
    return await child.cached("today", _load_today, _refresh(request))


@app.get("/api/{n}/grades")
async def grades(request: Request, child: Child = Depends(child_dep)) -> Any:
    return await child.cached("grades", _load_grades, _refresh(request))


@app.get("/api/{n}/agenda")
async def agenda(request: Request, child: Child = Depends(child_dep)) -> Any:
    return await child.cached("agenda", _load_agenda, _refresh(request))


@app.get("/api/{n}/messages")
async def messages(request: Request, child: Child = Depends(child_dep)) -> Any:
    return await child.cached("messages", _load_messages, _refresh(request))


@app.get("/api/{n}/messages/{message_id}")
async def message(message_id: str, child: Child = Depends(child_dep)) -> Any:
    """Pełna treść. Uwaga: Librus oznacza wiadomość jako przeczytaną, tak jak przy otwarciu w przeglądarce."""
    async def load(lib: Librus) -> dict[str, Any]:
        m = await lib.message(message_id)
        if m is None:
            raise HTTPException(404, "Nie ma takiej wiadomości.")
        return {"id": m.id, "sender": m.sender_name, "topic": m.topic, "content": m.content,
                "date": m.send_date, "attachments": [a.filename or "załącznik" for a in m.attachments]}
    return await child.cached(f"msg:{message_id}", load, False)


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {"ok": True, "children": len(CHILDREN)}


@app.on_event("shutdown")
async def _close() -> None:
    for c in CHILDREN.values():
        if c._librus is not None:
            await c._librus.close()


# ---------- frontend ----------

@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html", headers={"Cache-Control": "no-cache"})


@app.get("/sw.js")
def sw() -> FileResponse:
    return FileResponse(STATIC_DIR / "sw.js", media_type="text/javascript", headers={"Cache-Control": "no-cache"})


app.mount("/", StaticFiles(directory=STATIC_DIR), name="static")
