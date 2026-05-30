"""Authentication module for DocuSense.

Provides:
  - User storage (data/users.json)
  - Password hashing with PBKDF2-HMAC-SHA256 + per-user salt
  - HMAC-signed session tokens
  - Password reset tokens + Gmail SMTP email sending
  - Google OAuth 2.0 helpers
  - FastAPI dependency `require_auth`
"""

import hashlib
import hmac
import json
import os
import secrets
import smtplib
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
load_dotenv()

from fastapi import Request
from fastapi.responses import RedirectResponse

# ---------------------------------------------------------------------------
# Storage paths
# ---------------------------------------------------------------------------

_DATA_DIR = Path("./data")
_DATA_DIR.mkdir(parents=True, exist_ok=True)

_USERS_FILE       = _DATA_DIR / "users.json"
_RESET_FILE       = _DATA_DIR / "reset_tokens.json"
_SECRET_KEY_FILE  = _DATA_DIR / ".auth_secret"


def _get_secret() -> bytes:
    """Load or generate a persistent HMAC secret key."""
    if _SECRET_KEY_FILE.exists():
        return _SECRET_KEY_FILE.read_bytes()
    key = secrets.token_bytes(32)
    _SECRET_KEY_FILE.write_bytes(key)
    return key


_SECRET = _get_secret()


# ---------------------------------------------------------------------------
# User storage helpers
# ---------------------------------------------------------------------------

def load_users() -> dict:
    if not _USERS_FILE.exists():
        return {}
    try:
        return json.loads(_USERS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_users(users: dict) -> None:
    _USERS_FILE.write_text(json.dumps(users, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# Password hashing  (PBKDF2-HMAC-SHA256)
# ---------------------------------------------------------------------------

def hash_password(password: str, salt: Optional[str] = None) -> tuple[str, str]:
    if salt is None:
        salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac(
        "sha256", password.encode(), salt.encode(), iterations=260_000
    )
    return dk.hex(), salt


def verify_password(password: str, stored_hash: str, salt: str) -> bool:
    candidate, _ = hash_password(password, salt)
    return hmac.compare_digest(candidate, stored_hash)


# ---------------------------------------------------------------------------
# Session tokens  ("<email>.<timestamp>.<sig>")
# ---------------------------------------------------------------------------

_TOKEN_TTL = 60 * 60 * 24 * 7   # 7 days


def create_session_token(user_id: str) -> str:
    ts = str(int(time.time()))
    payload = f"{user_id}.{ts}"
    sig = hmac.new(_SECRET, payload.encode(), "sha256").hexdigest()
    return f"{payload}.{sig}"


def verify_session_token(token: str) -> Optional[str]:
    """Return user_id if valid & not expired, else None."""
    try:
        # split from the right: last segment = sig, second-last = ts
        last_dot = token.rfind(".")
        if last_dot == -1:
            return None
        sig  = token[last_dot + 1:]
        rest = token[:last_dot]
        second_last_dot = rest.rfind(".")
        if second_last_dot == -1:
            return None
        ts      = rest[second_last_dot + 1:]
        user_id = rest[:second_last_dot]
        payload = rest
        expected = hmac.new(_SECRET, payload.encode(), "sha256").hexdigest()
        if not hmac.compare_digest(expected, sig):
            return None
        if time.time() - int(ts) > _TOKEN_TTL:
            return None
        if user_id not in load_users():
            return None
        return user_id
    except Exception:
        return None


# ---------------------------------------------------------------------------
# FastAPI dependency / helpers
# ---------------------------------------------------------------------------

COOKIE_NAME = "ds_session"


def get_current_user(request: Request) -> Optional[str]:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return None
    return verify_session_token(token)


def require_auth(request: Request) -> str:
    user_id = get_current_user(request)
    if not user_id:
        raise _redirect_to_login()
    return user_id


class _redirect_to_login(Exception):
    pass


# ---------------------------------------------------------------------------
# User CRUD
# ---------------------------------------------------------------------------

def create_user(name: str, email: str, password: str,
                google_id: Optional[str] = None) -> tuple[bool, str]:
    users   = load_users()
    user_id = email.lower().strip()
    if user_id in users:
        return False, "An account with this email already exists."
    if password and len(password) < 8:
        return False, "Password must be at least 8 characters."
    pw_hash, salt = hash_password(password) if password else ("", "")
    users[user_id] = {
        "name":       name.strip(),
        "email":      user_id,
        "pw_hash":    pw_hash,
        "salt":       salt,
        "google_id":  google_id,
        "created_at": int(time.time()),
    }
    save_users(users)
    return True, ""


def authenticate_user(email: str, password: str) -> tuple[str, str]:
    """Returns (user_id, error). user_id is '' on failure."""
    users   = load_users()
    user_id = email.lower().strip()
    user    = users.get(user_id)
    if not user:
        return "", "No account found with that email."
    if not user.get("pw_hash"):
        return "", "This account was created with Google Sign-In. Please use 'Continue with Google'."
    if not verify_password(password, user["pw_hash"], user["salt"]):
        return "", "Incorrect password."
    return user_id, ""


# ---------------------------------------------------------------------------
# Password reset tokens
# ---------------------------------------------------------------------------

_RESET_TTL = 60 * 60   # 1 hour


def _load_resets() -> dict:
    if not _RESET_FILE.exists():
        return {}
    try:
        return json.loads(_RESET_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_resets(resets: dict) -> None:
    _RESET_FILE.write_text(json.dumps(resets, indent=2), encoding="utf-8")


def create_reset_token(email: str) -> Optional[str]:
    """
    Generate a reset token for the given email.
    Returns the token string, or None if no account exists.
    """
    users   = load_users()
    user_id = email.lower().strip()
    if user_id not in users:
        return None
    token   = secrets.token_urlsafe(32)
    resets  = _load_resets()
    # purge expired tokens for this user
    resets  = {t: d for t, d in resets.items()
               if time.time() - d["created_at"] < _RESET_TTL}
    resets[token] = {"user_id": user_id, "created_at": int(time.time())}
    _save_resets(resets)
    return token


def verify_reset_token(token: str) -> Optional[str]:
    """Return user_id if token valid & not expired, else None."""
    resets = _load_resets()
    data   = resets.get(token)
    if not data:
        return None
    if time.time() - data["created_at"] > _RESET_TTL:
        return None
    return data["user_id"]


def consume_reset_token(token: str, new_password: str) -> tuple[bool, str]:
    """Validate token, update password, delete token. Returns (ok, error)."""
    user_id = verify_reset_token(token)
    if not user_id:
        return False, "This reset link is invalid or has expired."
    if len(new_password) < 8:
        return False, "Password must be at least 8 characters."
    users = load_users()
    if user_id not in users:
        return False, "Account not found."
    pw_hash, salt = hash_password(new_password)
    users[user_id]["pw_hash"] = pw_hash
    users[user_id]["salt"]    = salt
    save_users(users)
    # delete used token
    resets = _load_resets()
    resets.pop(token, None)
    _save_resets(resets)
    return True, ""


# ---------------------------------------------------------------------------
# Email sending (Gmail SMTP)
# ---------------------------------------------------------------------------

def send_reset_email(to_email: str, reset_url: str) -> tuple[bool, str]:
    """
    Send a password reset email via Gmail SMTP.
    Reads GMAIL_USER and GMAIL_APP_PASSWORD from environment.
    """
    gmail_user = os.getenv("GMAIL_USER", "").strip()
    gmail_pass = os.getenv("GMAIL_APP_PASSWORD", "").strip()

    if not gmail_user or not gmail_pass:
        return False, "Email not configured (set GMAIL_USER and GMAIL_APP_PASSWORD in .env)"

    subject = "DocuSense — Reset Your Password"
    html_body = f"""
    <html><body style="font-family:Inter,sans-serif;background:#000;color:#ede9fe;padding:40px;">
      <div style="max-width:480px;margin:0 auto;background:rgba(10,5,20,.97);
                  border:1px solid rgba(168,85,247,.3);border-radius:20px;padding:40px;">
        <h2 style="color:#a855f7;margin-bottom:8px;">Reset Your Password</h2>
        <p style="color:#7c6fa0;margin-bottom:24px;">
          We received a request to reset your DocuSense password.
          Click the button below — this link expires in <strong>1 hour</strong>.
        </p>
        <a href="{reset_url}"
           style="display:inline-block;padding:12px 28px;
                  background:linear-gradient(135deg,#a855f7,#7c3aed);
                  color:#fff;border-radius:10px;text-decoration:none;
                  font-weight:700;font-size:15px;">
          Reset Password
        </a>
        <p style="color:#7c6fa0;margin-top:24px;font-size:13px;">
          If you didn't request this, you can safely ignore this email.
        </p>
        <hr style="border-color:rgba(168,85,247,.2);margin:24px 0;">
        <p style="color:#4a4060;font-size:12px;">DocuSense · AI-powered text extraction</p>
      </div>
    </body></html>
    """

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = f"DocuSense <{gmail_user}>"
    msg["To"]      = to_email
    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(gmail_user, gmail_pass)
            server.sendmail(gmail_user, to_email, msg.as_string())
        return True, ""
    except Exception as e:
        return False, str(e)


# ---------------------------------------------------------------------------
# Google OAuth helpers
# ---------------------------------------------------------------------------

GOOGLE_AUTH_URL     = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL    = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"

_OAUTH_STATES: dict = {}   # state -> expiry (simple in-memory store)


def get_google_config() -> dict:
    return {
        "client_id":     os.getenv("GOOGLE_CLIENT_ID", ""),
        "client_secret": os.getenv("GOOGLE_CLIENT_SECRET", ""),
    }


def google_is_configured() -> bool:
    cfg = get_google_config()
    return bool(cfg["client_id"] and cfg["client_secret"])


def build_google_auth_url(redirect_uri: str) -> str:
    """Return Google OAuth authorization URL with a fresh CSRF state."""
    import urllib.parse
    cfg   = get_google_config()
    state = secrets.token_urlsafe(16)
    _OAUTH_STATES[state] = time.time() + 600   # expire in 10 min
    params = {
        "client_id":     cfg["client_id"],
        "redirect_uri":  redirect_uri,
        "response_type": "code",
        "scope":         "openid email profile",
        "state":         state,
        "access_type":   "online",
        "prompt":        "select_account",
    }
    return GOOGLE_AUTH_URL + "?" + urllib.parse.urlencode(params)


def validate_google_state(state: str) -> bool:
    expiry = _OAUTH_STATES.pop(state, None)
    if expiry is None or time.time() > expiry:
        return False
    return True


async def exchange_google_code(code: str, redirect_uri: str) -> Optional[dict]:
    """Exchange authorization code for user info dict."""
    import httpx
    cfg = get_google_config()
    token_resp = httpx.post(GOOGLE_TOKEN_URL, data={
        "code":          code,
        "client_id":     cfg["client_id"],
        "client_secret": cfg["client_secret"],
        "redirect_uri":  redirect_uri,
        "grant_type":    "authorization_code",
    })
    if token_resp.status_code != 200:
        return None
    access_token = token_resp.json().get("access_token")
    if not access_token:
        return None
    info_resp = httpx.get(GOOGLE_USERINFO_URL,
                          headers={"Authorization": f"Bearer {access_token}"})
    if info_resp.status_code != 200:
        return None
    return info_resp.json()   # {sub, email, name, picture, ...}


def login_or_create_google_user(google_info: dict) -> str:
    """
    Given Google userinfo, return user_id.
    Creates account automatically on first sign-in.
    """
    email     = google_info.get("email", "").lower().strip()
    name      = google_info.get("name", email.split("@")[0])
    google_id = google_info.get("sub", "")
    picture   = google_info.get("picture", "")
    users     = load_users()

    if email in users:
        updated = False
        # update google_id if missing
        if not users[email].get("google_id"):
            users[email]["google_id"] = google_id
            updated = True
        # update picture if missing or changed
        if picture and users[email].get("picture") != picture:
            users[email]["picture"] = picture
            updated = True
        if updated:
            save_users(users)
        return email

    # New user — create with no password (Google-only account)
    create_user(name, email, password="", google_id=google_id)
    if picture:
        users = load_users()
        users[email]["picture"] = picture
        save_users(users)
    return email
