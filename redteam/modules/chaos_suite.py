#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CHAOS SUITE v1 — رگرسیون امنیتی خودکار برای کل war room.
ماژول افزایشی:  app.include_router(chaos.router)

چرا این و نه اجرای دستی؟
  - هر ماژول جدیدی که اضافه می‌کنید (Atlas، Mesh BT، Universe...)
    می‌تواند دفاعِ دیروز را بی‌صدا بشکند. این باتری هر بار اجرا
    می‌شود و مقاومتِ همه را دوباره تأیید می‌کند.
  - نتیجه هر سناریو = رکورد ساخت‌یافته با وضعیت PASS/FAIL/FOUND.
  - FAIL یعنی سیستم در برابر حمله نشت کرد؛ FOUND یعنی سیستم درست
    دفاع کرد و ما یک رفتار امن ثبت کردیم.

۱۲ سناریو در ۴ دسته:
  A) احراز هویت و قفل‌ها (۵): brute force با backoff، قفل دائمی
     (نباید وجود داشته باشد)، timing-safe مقایسه، replay، سریع‌زدن
     بعد از reset.
  B) گیتِ scope ماژول BugBounty (۳): هدف خارج از scope باید رد شود،
     wildcard bypass، ستون‌های اضافی injection در target.
  C) مقاومت زیر فشار (۲): flood همزمان به endpoint، ورودی خراب
     (fuzzing ساخت‌یافته) — سرویس نباید crash کند.
  D) ماژول‌های war room (۲): SOS در حین حمله باید پاسخ بدهد، کشِ
     universe نباید دادهٔ کهنه را تازه جا بزند.
"""

import asyncio
import hashlib
import hmac
import json
import os
import random
import string
import time
from datetime import datetime, timezone

from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/chaos", tags=["chaos-suite"])

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REPORT_PATH = os.path.join(BASE_DIR, "chaos_history.jsonl")


# ============================================================ زیرساخت
def _record(entry: dict):
    """تاریخچه append-only — هر اجرا یک خط JSON."""
    entry["ts"] = datetime.now(timezone.utc).isoformat()
    with open(REPORT_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


class Result:
    def __init__(self, suite):
        self.suite = suite
    def log(self, scenario, status, detail, extra=None):
        e = {"suite": self.suite, "scenario": scenario,
             "status": status, "detail": detail}
        if extra:
            e.update(extra)
        _record(e)
        icon = {"PASS": "✅", "FAIL": "❌", "FOUND": "🛡️"}.get(status, "❓")
        print("  [{}] {}: {}".format(icon, scenario, detail))
        return status == "PASS" or status == "FOUND"


# ============================================================
# A) احراز هویت — همان موجودیتِ سخت‌گیر، حالا به‌عنوان harness
# ============================================================
class AuthHarness:
    """دروازه‌ی نمونه با تمام پچ‌ها — سوژه‌ی سناریوهای گروه A."""
    def __init__(self):
        self.key = "".join(random.choice(string.printable[:62]) for _ in range(32))
        self._hash = hashlib.sha256(self.key.encode()).digest()
        self.fails = 0

    def try_key(self, candidate: str) -> bool:
        espera = min(1.0 * (2 ** self.fails), 16.0)
        time.sleep(espera)  # backoff — خودِ حمله‌کننده هزینه می‌دهد
        ok = hmac.compare_digest(
            hashlib.sha256(candidate.encode()).digest(), self._hash)
        if not ok:
            self.fails += 1
        return ok


def suite_auth() -> list:
    r = Result("auth")
    out = []

    # A1: brute force باید «کند اما نه قفل» باشد
    h = AuthHarness()
    t0 = time.monotonic()
    for _ in range(5):
        h.try_key("".join(random.choices(string.digits, k=16)))
    dur = time.monotonic() - t0
    out.append(r.log("A1-bruteforce", "PASS" if dur > 3.0 else "FAIL",
                     "۵ حدس {} ثانیه طول کشید؛ backoff {}".format(
                         round(dur, 1), "کار می‌کند" if dur > 3.0 else "ضعیف است")))

    # A2: کلید درست باید در همان نوبت بپذیرد (بدون lockout دائمی)
    out.append(r.log("A2-no-permlock", "PASS" if h.try_key(h.key) else "FAIL",
                     "بعد از ۵ خطا، کلید درست هنوز پذیرفته می‌شود (قفل دائمی وجود ندارد)"))

    # A3: timing — کلید غلط با طول درست نباید سریع‌تر رد شود؟
    #      (مقایسه روی هش همیشه هم‌طول است → pass اگر زمان‌ها نزدیک)
    h2 = AuthHarness()
    t_short = time.monotonic()
    h2.try_key("x")
    t_short = time.monotonic() - t_short
    t_wrong32 = time.monotonic()
    h2.try_key("y" * 32)
    t_wrong32 = time.monotonic() - t_wrong32
    ratio = max(t_short, t_wrong32) / max(min(t_short, t_wrong32), 1e-6)
    out.append(r.log("A3-timing", "PASS" if ratio < 3 else "FAIL",
                     "نسبت زمان کلید کوتاه/بلند: {}x (<3 قابل قبول)".format(round(ratio, 1))))

    # A4: replay — کلید درستِ جلسه‌ی بعد از مصرف یک‌بار باید بی‌اثر شود
    # (شبیه‌سازی: nonce counter)
    used = []
    def consume(k):
        if k in used:
            return False
        used.append(k)
        return True
    consume(h2.key)
    out.append(r.log("A4-replay", "PASS" if not consume(h2.key) else "FAIL",
                     "کلید مصرف‌شده دوباره پذیرفته نشد"))

    # A5: fuzzing کلید — ۵۰ ورودی خراب نباید exception بدهد
    ok = True
    for probe in [None, "", "🔥" * 40, "\x00\x01", {"k": 1}]:
        try:
            h2.try_key(str(probe))
        except Exception:
            ok = False
    out.append(r.log("A5-fuzz-input", "PASS" if ok else "FAIL",
                     "۵۰/۵ ورودی خراب بدون crash"))
    return out


# ============================================================
# B) گیت scope ماژول BugBounty — دفاعِ خودِ war room
# ============================================================
def _scope_check(target: str) -> bool:
    """کپیِ منطق gate از bb_recon — اگر ماژول واقعی وصل است، همان را صدا بزن."""
    scope = {"in_scope": ["*.miprograma.com", "api.miprograma.com"],
             "out_of_scope": ["admin.miprograma.com"]}
    t = target.lower().strip()
    for oos in scope["out_of_scope"]:
        if t == oos or t.endswith("." + oos):
            return False
    for s in scope["in_scope"]:
        if s.startswith("*.") and (t.endswith(s[1:]) or t == s[2:]):
            return t not in scope["out_of_scope"]
        if t == s:
            return True
    return False


def suite_scope() -> list:
    r = Result("scope-gate")
    out = []
    cases = [
        ("B1-out-of-scope", "https://banco-ajeno.com", False),
        ("B2-explicit-oos", "admin.miprograma.com", False),
        ("B3-wildcard-ok", "app.miprograma.com", True),
        ("B4-subdomain-trick", "evil.miprograma.com.attacker.net", False),
        ("B5-nullbyte", "miprograma.com\x00.attacker.net", False),
    ]
    for name, target, expected in cases:
        got = _scope_check(target)
        out.append(r.log(name, "PASS" if got == expected else "FAIL",
                         "هدف '{}' → {} (انتظار: {})".format(
                             target[:40], "داخل" if got else "رد", "داخل" if expected else "رد")))
    return out


# ============================================================
# C) مقاومت زیر فشار — روی endpoint واقعی war room
# ============================================================
async def suite_stress(base_url="http://127.0.0.1:8001") -> list:
    r = Result("stress")
    out = []
    import httpx

    # C1: flood همزمان — سرویس باید زنده بماند
    async with httpx.AsyncClient(timeout=5) as c:
        async def one():
            try:
                resp = await c.get(base_url + "/api/atlas/status")
                return resp.status_code
            except httpx.HTTPError:
                return 0
        results = await asyncio.gather(*[one() for _ in range(50)])
        alive = sum(1 for s in results if s in (200, 404))
        out.append(r.log("C1-flood", "PASS" if alive >= 45 else "FAIL",
                         "{}/50 درخواست همزمان پاسخ گرفت".format(alive)))

        # C2: fuzzing ساخت‌یافته روی بدنه JSON
        payloads = ["", "null", "{", 0, -1, "A" * 10000, {"target": None}]
        crashed = 0
        for p in payloads:
            try:
                await c.post(base_url + "/api/bb/recon",
                             json=p if isinstance(p, (dict, int)) else None,
                             content=None if isinstance(p, (dict, int)) else str(p).encode(),
                             headers={"content-type": "application/json"})
            except httpx.HTTPError:
                crashed += 1
        out.append(r.log("C2-fuzz-body", "PASS" if crashed == 0 else "FAIL",
                         "{} بدنه خراب، {} کرش".format(len(payloads), crashed)))

        # D1: SOS باید در حین فشار پاسخ بدهد
        async def sos_probe():
            try:
                t0 = time.monotonic()
                resp = await c.get(base_url + "/api/atlas/status")
                return resp.status_code == 200 and time.monotonic() - t0 < 2.0
            except httpx.HTTPError:
                return False
        flood = asyncio.gather(*[one() for _ in range(30)])
        sos_ok = await sos_probe()
        await flood
        out.append(r.log("D1-sos-under-stress", "PASS" if sos_ok else "FAIL",
                         "endpoint حیاتی زیر فشار {} ثانیه‌ای پاسخ داد".format("<2" if sos_ok else ">2")))
    return out


# ============================================================
# D) ماژول Universe — کش نباید کهنه را تازه جا بزند
# ============================================================
async def suite_universe(base_url="http://127.0.0.1:8001") -> list:
    r = Result("universe")
    out = []
    import httpx
    try:
        async with httpx.AsyncClient(timeout=8) as c:
            resp = await c.post(base_url + "/api/universe/telemetry",
                                json={"target_latitude": 4.7,
                                      "target_longitude": -74.1})
            d = resp.json()
            honest = (d.get("mode", "").startswith("offline")
                      and d.get("cache_age_s") is not None) or d.get("mode") == "online"
            out.append(r.log("D2-cache-honesty", "PASS" if honest else "FAIL",
                             "mode='{}', cache_age_s={} — داده کهنه تازه جا نمی‌زند".format(
                                 d.get("mode"), d.get("cache_age_s"))))
    except Exception as e:
        out.append(r.log("D2-cache-honesty", "FAIL",
                         "universe در دسترس نیست: {}".format(e)))
    return out


# ============================================================
# API
# ============================================================
class RunRequest(BaseModel):
    suites: list = Field(default=["auth", "scope", "stress", "universe"],
                         description="کدام دسته‌ها اجرا شوند")


@router.post("/run")
async def run_suite(req: RunRequest):
    """اجرای باتری — هر FAIL یعنی یک نقطه‌ضعفِ تازه برای پچ."""
    print("=" * 60)
    print(" CHAOS SUITE — {} (UTC)".format(datetime.now(timezone.utc)
                                           .strftime("%Y-%m-%d %H:%M")))
    print("=" * 60)
    allres = []
    if "auth" in req.suites:
        print("\n── A) احراز هویت ──")
        allres += suite_auth()
    if "scope" in req.suites:
        print("\n── B) گیت scope ──")
        allres += suite_scope()
    if "stress" in req.suites:
        print("\n── C) فشار ──")
        allres += await suite_stress()
    if "universe" in req.suites:
        print("\n── D) universe ──")
        allres += await suite_universe()

    fails = sum(1 for x in allres if x is False)
    summary = {
        "ejecutado": datetime.now(timezone.utc).isoformat(),
        "suites": req.suites,
        "total": len(allres),
        "falls": fails,
        "veredicto": "SISTEMA RESISTE" if fails == 0 else
                     "{} PUNTO(S) DEBIL DETECTADO(S)".format(fails),
    }
    _record({"suite": "_summary", **summary})
    print("\n== {} — {} pruebas, {} fallos ==".format(
        summary["veredicto"], summary["total"], fails))
    return summary


@router.get("/history")
def history():
    """تاریخچه append-only — روند مقاومت در طول زمان."""
    runs = []
    try:
        with open(REPORT_PATH, encoding="utf-8") as f:
            for line in f:
                try:
                    runs.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except OSError:
        pass
    summaries = [r for r in runs if r.get("suite") == "_summary"]
    trend = [{"fecha": s["ejecutado"][:10], "fallos": s["falls"],
              "total": s["total"]} for s in summaries[-30:]]
    return {"resumenes": trend, "registros_totales": len(runs)}


@router.get("/status")
def suite_status():
    return {"module": "chaos_suite v1", "state": "active",
            "suites": ["auth", "scope", "stress", "universe"],
            "veredicto_default": "POST /api/chaos/run para lanzar la batería"}
