import json
import math  # keep after Flask imports for readability
import os
import secrets
import sqlite3
from datetime import timedelta
from functools import wraps
from pathlib import Path
from typing import Any, Optional

from flask import Flask, jsonify, redirect, render_template, request, session, url_for
from webauthn import (
    generate_authentication_options,
    generate_registration_options,
    verify_authentication_response,
    verify_registration_response,
)
from webauthn.helpers import (
    base64url_to_bytes,
    bytes_to_base64url,
    options_to_json,
)
from webauthn.helpers.structs import (
    AttestationConveyancePreference,
    AuthenticatorSelectionCriteria,
    AuthenticatorTransport,
    PublicKeyCredentialDescriptor,
    PublicKeyCredentialType,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)


# --- Configuration ---
RP_ID = os.getenv("RP_ID", "localhost")
RP_NAME = os.getenv("RP_NAME", "Circle Calculator Passkey")
ORIGIN = os.getenv("ORIGIN", "https://localhost:30443")
SESSION_SECRET = os.getenv("SESSION_SECRET") or secrets.token_hex(32)
DB_PATH = Path(os.getenv("DB_PATH", "data/app.db"))
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

app = Flask(__name__, static_folder="static", template_folder="templates")
app.secret_key = SESSION_SECRET
app.permanent_session_lifetime = timedelta(days=1)
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.getenv("SESSION_COOKIE_SECURE", "true").lower() == "true",
)


# --- Helpers: database ---
def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = get_db()
    cur = conn.cursor()
    cur.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            user_handle BLOB NOT NULL
        );
        CREATE TABLE IF NOT EXISTS credentials (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            credential_id TEXT NOT NULL UNIQUE,
            credential_public_key TEXT NOT NULL,
            sign_count INTEGER NOT NULL,
            transports TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        """
    )
    conn.commit()
    conn.close()


def get_user_by_username(username: str) -> Optional[sqlite3.Row]:
    with get_db() as conn:
        cur = conn.execute("SELECT * FROM users WHERE username = ?", (username,))
        return cur.fetchone()


def get_user_by_id(user_id: int) -> Optional[sqlite3.Row]:
    with get_db() as conn:
        cur = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        return cur.fetchone()


def create_user(username: str) -> sqlite3.Row:
    handle = secrets.token_bytes(32)
    with get_db() as conn:
        cur = conn.execute(
            "INSERT INTO users (username, user_handle) VALUES (?, ?)",
            (username, handle),
        )
        conn.commit()
        user_id = cur.lastrowid
    return get_user_by_id(user_id)  # type: ignore


def get_credentials_for_user(user_id: int) -> list[sqlite3.Row]:
    with get_db() as conn:
        cur = conn.execute(
            "SELECT * FROM credentials WHERE user_id = ? ORDER BY id ASC", (user_id,)
        )
        return cur.fetchall()


def parse_transports(raw: str) -> list[AuthenticatorTransport]:
    transports: list[AuthenticatorTransport] = []
    try:
        for t in json.loads(raw or "[]"):
            try:
                transports.append(AuthenticatorTransport(t))
            except Exception:
                continue
    except Exception:
        pass
    return transports


def get_credential_by_b64id(cred_id: str) -> Optional[sqlite3.Row]:
    with get_db() as conn:
        cur = conn.execute(
            "SELECT * FROM credentials WHERE credential_id = ?", (cred_id,)
        )
        return cur.fetchone()


def upsert_credential(
    user_id: int,
    credential_id_b64: str,
    credential_public_key_b64: str,
    sign_count: int,
    transports: str = "",
) -> None:
    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO credentials (user_id, credential_id, credential_public_key, sign_count, transports)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(credential_id) DO UPDATE SET
                user_id = excluded.user_id,
                credential_public_key = excluded.credential_public_key,
                sign_count = excluded.sign_count,
                transports = excluded.transports
            """,
            (user_id, credential_id_b64, credential_public_key_b64, sign_count, transports),
        )
        conn.commit()


def update_sign_count(credential_id_b64: str, new_count: int) -> None:
    with get_db() as conn:
        conn.execute(
            "UPDATE credentials SET sign_count = ? WHERE credential_id = ?",
            (new_count, credential_id_b64),
        )
        conn.commit()


# --- Helpers: auth + calc ---
def calc(radius: float) -> tuple[float, float]:
    """Return (area, circumference) for a circle."""
    area = math.pi * radius * radius
    circumference = 2 * math.pi * radius
    return area, circumference


def require_login(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("user_id"):
            return redirect(url_for("index"))
        return fn(*args, **kwargs)

    return wrapper


# --- Routes ---
@app.get("/")
def index():
    user = None
    if session.get("user_id"):
        user = get_user_by_id(session["user_id"])
    return render_template("index.html", user=user, result=None)


@app.post("/calc")
@require_login
def do_calc():
    r_raw = request.form.get("radius", "").strip()
    error = None
    result = None
    try:
        r = float(r_raw)
        if r <= 0:
            raise ValueError("Radius must be > 0")
        area, circ = calc(r)
        result = {
            "radius": r,
            "area": area,
            "circumference": circ,
        }
    except Exception:
        error = "Masukkan radius angka positif (contoh: 7 atau 7.5)."

    user = get_user_by_id(session["user_id"]) if session.get("user_id") else None
    return render_template("index.html", result=result, error=error, radius=r_raw, user=user)


@app.get("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


@app.post("/auth/register/start")
def register_start():
    data = request.get_json(force=True)
    username = (data.get("username") or "").strip()
    if not username:
        return jsonify({"error": "Username wajib diisi"}), 400

    user = get_user_by_username(username)
    if not user:
        user = create_user(username)

    existing_credentials = get_credentials_for_user(user["id"])
    exclude = [
        PublicKeyCredentialDescriptor(
            type=PublicKeyCredentialType.PUBLIC_KEY,
            id=base64url_to_bytes(row["credential_id"]),
            transports=parse_transports(row["transports"]),
        )
        for row in existing_credentials
    ]

    options = generate_registration_options(
        rp_id=RP_ID,
        rp_name=RP_NAME,
        user_name=user["username"],
        user_id=user["user_handle"],
        timeout=60000,
        attestation=AttestationConveyancePreference.NONE,
        authenticator_selection=AuthenticatorSelectionCriteria(
            user_verification=UserVerificationRequirement.REQUIRED,
            resident_key=ResidentKeyRequirement.PREFERRED,
        ),
        exclude_credentials=exclude,
    )
    session["challenge"] = bytes_to_base64url(options.challenge)
    session["pending_user_id"] = user["id"]
    return jsonify(json.loads(options_to_json(options)))


@app.post("/auth/register/finish")
def register_finish():
    if not session.get("challenge") or not session.get("pending_user_id"):
        return jsonify({"error": "Challenge tidak ada"}), 400

    body = request.get_json(force=True)
    user = get_user_by_id(session["pending_user_id"])
    if not user:
        return jsonify({"error": "User tidak ditemukan"}), 400

    try:
        verification = verify_registration_response(
            credential=body,
            expected_challenge=base64url_to_bytes(session["challenge"]),
            expected_rp_id=RP_ID,
            expected_origin=ORIGIN,
            require_user_verification=True,
        )
        cred_id_b64 = bytes_to_base64url(verification.credential_id)
        cred_pub_key_b64 = bytes_to_base64url(verification.credential_public_key)
        transports = body.get("response", {}).get("transports", [])
        upsert_credential(
            user_id=user["id"],
            credential_id_b64=cred_id_b64,
            credential_public_key_b64=cred_pub_key_b64,
            sign_count=verification.sign_count,
            transports=json.dumps(transports),
        )
        session["user_id"] = user["id"]
        return jsonify({"verified": True})
    except Exception as exc:  # pragma: no cover - shallow API error
        return jsonify({"error": f"Registrasi gagal: {exc}"}), 400
    finally:
        session.pop("challenge", None)
        session.pop("pending_user_id", None)


@app.post("/auth/login/start")
def login_start():
    data = request.get_json(force=True)
    username = (data.get("username") or "").strip()
    if not username:
        return jsonify({"error": "Username wajib diisi"}), 400

    user = get_user_by_username(username)
    if not user:
        return jsonify({"error": "User tidak ditemukan"}), 404

    creds = get_credentials_for_user(user["id"])
    allow = [
        PublicKeyCredentialDescriptor(
            type=PublicKeyCredentialType.PUBLIC_KEY,
            id=base64url_to_bytes(row["credential_id"]),
            transports=parse_transports(row["transports"]),
        )
        for row in creds
    ]

    options = generate_authentication_options(
        rp_id=RP_ID,
        allow_credentials=allow or None,
        user_verification=UserVerificationRequirement.REQUIRED,
        timeout=60000,
    )
    session["challenge"] = bytes_to_base64url(options.challenge)
    session["pending_user_id"] = user["id"]
    return jsonify(json.loads(options_to_json(options)))


@app.post("/auth/login/finish")
def login_finish():
    if not session.get("challenge") or not session.get("pending_user_id"):
        return jsonify({"error": "Challenge tidak ada"}), 400

    body = request.get_json(force=True)
    raw_id_b64 = body.get("rawId")
    if not raw_id_b64:
        return jsonify({"error": "Credential ID hilang"}), 400

    credential = get_credential_by_b64id(raw_id_b64)
    if not credential:
        return jsonify({"error": "Credential tidak terdaftar"}), 404

    try:
        verification = verify_authentication_response(
            credential=body,
            expected_challenge=base64url_to_bytes(session["challenge"]),
            expected_rp_id=RP_ID,
            expected_origin=ORIGIN,
            credential_public_key=base64url_to_bytes(credential["credential_public_key"]),
            credential_current_sign_count=credential["sign_count"],
            require_user_verification=True,
        )
        if verification.new_sign_count is not None:
            update_sign_count(raw_id_b64, verification.new_sign_count)
        session["user_id"] = credential["user_id"]
        return jsonify({"verified": True})
    except Exception as exc:  # pragma: no cover
        return jsonify({"error": f"Login gagal: {exc}"}), 400
    finally:
        session.pop("challenge", None)
        session.pop("pending_user_id", None)


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=8080, debug=False)


# Ensure DB tables exist on import (for Gunicorn)
init_db()
