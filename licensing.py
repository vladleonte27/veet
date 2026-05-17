"""License check for Veet.

- Validates against https://veet.space/api/validate?email=... (server hits Stripe).
- HMAC-signed local cache in %LOCALAPPDATA%/Veet/license.json.
- Online success → unlock for 14 days; if app starts offline within those 14
  days, the cached unlock still applies. After 14 days with no successful
  re-check, the app locks until the next online validation.
"""
import hashlib
import hmac
import json
import os
import time
import urllib.parse
import urllib.request
import urllib.error
from pathlib import Path

VALIDATE_URL = os.environ.get("VEET_VALIDATE_URL", "https://veet.space/api/validate")
GRACE_DAYS = 14
# Embedded in the binary; not a secret per se — just makes tampering with the
# cache file require more than a text editor.
_HMAC_KEY = b"veet-license-cache-v1"


def _data_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA") or str(Path.home())
    d = Path(base) / "Veet"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _cache_path() -> Path:
    return _data_dir() / "license.json"


def _sign(payload: dict) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hmac.new(_HMAC_KEY, raw, hashlib.sha256).hexdigest()


def _save_cache(email: str, active: bool, tier: str) -> None:
    body = {
        "email": email,
        "active": bool(active),
        "tier": tier or "",
        "checked_at": int(time.time()),
    }
    body["sig"] = _sign(body)
    try:
        _cache_path().write_text(json.dumps(body), encoding="utf-8")
    except Exception:
        pass


def _load_cache() -> dict | None:
    p = _cache_path()
    if not p.is_file():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None
    sig = data.pop("sig", None)
    if not sig or _sign(data) != sig:
        return None
    return data


def _online_check(email: str) -> dict | None:
    """POST/GET the validate endpoint. Returns dict or None if unreachable."""
    try:
        url = f"{VALIDATE_URL}?email={urllib.parse.quote(email)}"
        req = urllib.request.Request(url, headers={"User-Agent": "Veet"})
        with urllib.request.urlopen(req, timeout=6) as r:
            return json.loads(r.read())
    except (urllib.error.URLError, TimeoutError, OSError):
        return None
    except Exception:
        return None


def cached_email() -> str | None:
    c = _load_cache()
    return c.get("email") if c else None


def status() -> dict:
    """Return {'active': bool, 'tier': str, 'email': str|None, 'reason': str}.
    Does an online check if possible; falls back to signed cache; honours
    the 14-day offline grace period."""
    cache = _load_cache()
    email = cache.get("email") if cache else None
    if not email:
        return {"active": False, "tier": "", "email": None, "reason": "no_email"}

    fresh = _online_check(email)
    if fresh is not None:
        _save_cache(email, fresh.get("active", False), fresh.get("tier", ""))
        return {
            "active": bool(fresh.get("active")),
            "tier": fresh.get("tier", ""),
            "email": email,
            "reason": fresh.get("reason", ""),
        }

    # Offline path — trust cache if recent + previously active
    if cache and cache.get("active"):
        age_days = (time.time() - cache.get("checked_at", 0)) / 86400.0
        if age_days < GRACE_DAYS:
            return {
                "active": True,
                "tier": cache.get("tier", ""),
                "email": email,
                "reason": "offline_cached",
            }
        return {"active": False, "tier": "", "email": email, "reason": "offline_grace_expired"}

    return {"active": False, "tier": "", "email": email, "reason": "offline_no_cache"}


def activate(email: str) -> dict:
    """Try to activate with the given email. Returns the same shape as status()."""
    email = (email or "").strip().lower()
    if not email or "@" not in email:
        return {"active": False, "tier": "", "email": None, "reason": "bad_email"}
    fresh = _online_check(email)
    if fresh is None:
        return {"active": False, "tier": "", "email": email, "reason": "offline"}
    _save_cache(email, fresh.get("active", False), fresh.get("tier", ""))
    return {
        "active": bool(fresh.get("active")),
        "tier": fresh.get("tier", ""),
        "email": email,
        "reason": fresh.get("reason", ""),
    }


def deactivate() -> None:
    try:
        _cache_path().unlink(missing_ok=True)
    except Exception:
        pass
