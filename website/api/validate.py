"""Veet license validation — Vercel serverless function.

GET /api/validate?email=foo@bar.com
  Looks up the customer in Stripe by email, returns whether they have:
    - an active subscription (monthly / yearly), or
    - a successful one-time payment of $99+ (lifetime).

Returns JSON: { active: bool, tier: "monthly"|"yearly"|"lifetime"|"", reason: str }

Required env var:  STRIPE_SECRET_KEY  (restricted key with read access to
customers + subscriptions + payment_intents).
"""
from http.server import BaseHTTPRequestHandler
import json
import os
import urllib.parse
import urllib.request
import urllib.error


STRIPE_KEY = os.environ.get("STRIPE_SECRET_KEY", "").strip()
STRIPE_BASE = "https://api.stripe.com/v1"
LIFETIME_THRESHOLD_CENTS = 9900  # $99 — anyone who paid this much one-time = lifetime

# Founder / comp accounts. Always return active lifetime regardless of Stripe.
OVERRIDE_LIFETIME = {
    "vlad@vlmedia.online",
}


def _stripe(path: str) -> dict:
    req = urllib.request.Request(
        STRIPE_BASE + path,
        headers={"Authorization": f"Bearer {STRIPE_KEY}"},
    )
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())


def _validate(email: str) -> dict:
    if not email or "@" not in email:
        return {"active": False, "reason": "bad_email"}
    email = email.strip().lower()

    # Founder / comp accounts bypass Stripe entirely.
    if email in OVERRIDE_LIFETIME:
        return {"active": True, "tier": "lifetime", "reason": "override"}

    if not STRIPE_KEY:
        return {"active": False, "reason": "server_misconfigured"}

    # 1. Find the customer by email
    try:
        # search query needs the email value to be quoted
        q = urllib.parse.quote(f'email:"{email}"')
        result = _stripe(f"/customers/search?query={q}&limit=5")
    except urllib.error.HTTPError as e:
        return {"active": False, "reason": f"stripe_error_{e.code}"}
    except Exception as e:
        return {"active": False, "reason": f"stripe_error"}

    customers = result.get("data", [])
    if not customers:
        return {"active": False, "reason": "no_customer"}

    # Check each matching customer (Stripe may have duplicates).
    for cust in customers:
        cid = cust["id"]
        # 2a. Active subscription?
        try:
            subs = _stripe(f"/subscriptions?customer={cid}&status=active&limit=5")
            for s in subs.get("data", []):
                # Tier from billing interval
                interval = (
                    s.get("items", {}).get("data", [{}])[0]
                    .get("price", {}).get("recurring", {}).get("interval", "")
                )
                tier = "yearly" if interval == "year" else "monthly"
                return {"active": True, "tier": tier, "reason": "active_sub"}
        except Exception:
            pass

        # 2b. Successful lifetime payment? (one-time, ≥ $99)
        try:
            payments = _stripe(f"/payment_intents?customer={cid}&limit=20")
            for pi in payments.get("data", []):
                if pi.get("status") != "succeeded":
                    continue
                if pi.get("amount", 0) >= LIFETIME_THRESHOLD_CENTS:
                    return {"active": True, "tier": "lifetime", "reason": "lifetime_paid"}
        except Exception:
            pass

    return {"active": False, "reason": "no_active_plan"}


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        email = (query.get("email") or [""])[0]
        out = _validate(email)
        body = json.dumps(out).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        # CORS preflight (in case the Veet app or a future web frontend calls this)
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
