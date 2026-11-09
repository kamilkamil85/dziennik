"""Wersja statyczna: pobiera dane z Librusa, szyfruje je hasłem każdego dziecka i zapisuje stronę w site/.

Uruchamiane przez GitHub Actions (patrz .github/workflows/dziennik.yml), lokalnie:
    python build.py            # prawdziwe dane (.env)
    python build.py --demo     # przykładowe dane, hasło każdego dziecka: demo
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.hashes import SHA256
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

ROOT = Path(__file__).resolve().parent
SITE = ROOT / "site"
ITERATIONS = 310_000
DEMO = "--demo" in sys.argv
if DEMO:
    os.environ["DEMO"] = "1"
os.environ.setdefault("DATA_DIR", str(ROOT / "data"))

from app import main as m  # noqa: E402  (po ustawieniu zmiennych środowiskowych)

SESSION_KEY = os.environ.get("SESSION_KEY", "")


def b64(b: bytes) -> str:
    return base64.b64encode(b).decode()


def derive(password: str, salt: bytes) -> bytes:
    return PBKDF2HMAC(SHA256(), 32, salt, ITERATIONS).derive(password.encode())


def encrypt(obj: object, password: str, n: int) -> dict[str, object]:
    # Sól stała dla dziecka: telefon zapamiętuje klucz (nie hasło) i działa po każdej aktualizacji danych.
    salt = hashlib.sha256(f"dziennik-salt-{n}-{os.environ.get('SALT_EXTRA', '')}".encode()).digest()[:16]
    iv = os.urandom(12)
    ct = AESGCM(derive(password, salt)).encrypt(iv, json.dumps(obj, ensure_ascii=False).encode(), None)
    return {"v": 1, "kdf": "PBKDF2-SHA256", "iter": ITERATIONS, "salt": b64(salt), "iv": b64(iv), "ct": b64(ct)}


# --- sesje Librusa między uruchomieniami Actions: zapisane zaszyfrowane SESSION_KEY ---

def _session_box(raw: bytes, decrypt: bool) -> bytes | None:
    key = PBKDF2HMAC(SHA256(), 32, b"dziennik-session", 100_000).derive(SESSION_KEY.encode())
    if decrypt:
        try:
            return AESGCM(key).decrypt(raw[:12], raw[12:], None)
        except Exception:
            return None
    iv = os.urandom(12)
    return iv + AESGCM(key).encrypt(iv, raw, None)


def unpack_sessions() -> None:
    if not SESSION_KEY:
        return
    for enc in Path(m.DATA_DIR).glob("session_*.enc"):
        plain = _session_box(enc.read_bytes(), decrypt=True)
        if plain:
            enc.with_suffix(".json").write_bytes(plain)


def pack_sessions() -> None:
    if not SESSION_KEY:
        return
    for js in Path(m.DATA_DIR).glob("session_*.json"):
        js.with_suffix(".enc").write_bytes(_session_box(js.read_bytes(), decrypt=False))  # type: ignore[arg-type]
        js.unlink()


async def collect(child: m.Child) -> dict[str, object]:
    out: dict[str, object] = {"name": child.name}
    errors = []
    for key, loader in (("today", m._load_today), ("grades", m._load_grades),
                        ("agenda", m._load_agenda), ("messages", m._load_messages)):
        try:
            out[key] = await child.cached(key, loader, False)
        except Exception as err:  # jedna sekcja nie psuje reszty
            errors.append(key)
            out[key] = None
            print(f"  {child.name}: {key} nie pobrane ({type(err).__name__}: {getattr(err, 'detail', '')})")
    if child._librus is not None:
        await child._librus.close()
    out["errors"] = errors
    return out


def password_for(child: m.Child) -> str:
    if DEMO:
        return "demo"
    pw = os.environ.get(f"DZIECKO{child.n}_HASLO_APP", "")
    if len(pw) < 10:
        raise SystemExit(f"DZIECKO{child.n}_HASLO_APP: ustaw hasło do aplikacji (min. 10 znaków).")
    return pw


async def main() -> None:
    if SITE.exists():
        shutil.rmtree(SITE)
    shutil.copytree(ROOT / "static", SITE)
    (SITE / "data").mkdir()
    unpack_sessions()
    stamp = datetime.now(m.TZ).strftime("%Y-%m-%d %H:%M")
    kids, failed, everything = [], 0, {}
    for child in m.CHILDREN.values():
        print(f"- {child.name}")
        data = await collect(child)
        data["generated"] = stamp
        if len(data["errors"]) == 4:  # type: ignore[arg-type]
            failed += 1
        (SITE / "data" / f"{child.n}.json").write_text(json.dumps(encrypt(data, password_for(child), child.n)), encoding="utf-8")
        kids.append({"n": child.n, "name": child.name})
        everything[str(child.n)] = data
    parent_pw = "demo" if DEMO else os.environ.get("RODZIC_HASLO_APP", "")
    if parent_pw:
        if len(parent_pw) < 10 and not DEMO:
            raise SystemExit("RODZIC_HASLO_APP: min. 10 znaków.")
        # Plik rodzica: dane wszystkich dzieci zaszyfrowane jednym hasłem.
        (SITE / "data" / "0.json").write_text(json.dumps(encrypt({"kids": everything, "generated": stamp}, parent_pw, 0)), encoding="utf-8")
    pack_sessions()
    (SITE / "data" / "kids.json").write_text(json.dumps({"kids": kids, "parent": bool(parent_pw), "generated": stamp}, ensure_ascii=False), encoding="utf-8")
    (SITE / "config.js").write_text('window.DZ_STATIC = true;\n')
    (SITE / ".nojekyll").write_text("")
    print(f"Gotowe: {len(kids)} dzieci, {stamp}")
    if kids and failed == len(kids):
        raise SystemExit("Żadne konto nie zadziałało.")


if __name__ == "__main__":
    asyncio.run(main())
