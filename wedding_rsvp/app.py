"""
Wedding Confirmation — Adeline & Mussa
======================================
A bilingual (English / Polish) confirmation app for the wedding on
June 20, 2026 in Łódź, Poland.

Two faces:
  - Guest side (/)        : confirm attendance, edit your own submission
  - Admin side (/admin)   : login-protected dashboard with totals, search,
                           filters, edit, delete, CSV export

Run locally
-----------
    pip install -r requirements.txt
    python app.py
Open http://127.0.0.1:5002 for the guest form, /admin for the dashboard.

Deploy (Render / Railway / Fly / Heroku)
----------------------------------------
    Procfile: web: gunicorn app:app
    Required env vars in production:
        SECRET_KEY        random string (Flask session signing)
        ADMIN_PASSWORD    your admin password
        PORT              automatically provided by host
    Optional:
        SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, NOTIFY_EMAIL
"""

import csv
import io
import os
import secrets
import smtplib
import ssl
import uuid
from datetime import datetime
from email.message import EmailMessage
from functools import wraps
from pathlib import Path

from flask import (
    Flask, render_template, request, redirect, url_for, abort, session,
    Response, flash,
)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).parent
RESPONSES_FILE = BASE_DIR / "responses.csv"

WEDDING = {
    "bride": "Adeline Helga Munezero",
    "groom": "Mussa Justin Muhindo",
    "date_iso": "2026-06-20",
    "date_pretty_en": "June 20, 2026",
    "date_pretty_pl": "20 czerwca 2026",
    "ceremony_time": "2:00 PM",
    "ceremony_venue_en": "Parish of Saint Theresa and Saint John Bosco",
    "ceremony_venue_pl": "Parafia św. Teresy i św. Jana Bosko",
    "ceremony_address": "Kopcińskiego 1/3, Łódź",
    "reception_time": "4:00 PM – 9:00 PM",
    "reception_venue": "Arche Hotel",
    "reception_address": "Lodz, Matejki 11",
    "phones": ["+48 513 741 751", "+48 781 208 797"],
    "rsvp_deadline_en": "June 10, 2026",
    "rsvp_deadline_pl": "10 czerwca 2026",
}

ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "muhindo2026")

# Flask session signing key — SET A REAL VALUE IN PRODUCTION.
SECRET_KEY = os.environ.get("SECRET_KEY") or secrets.token_hex(32)

SMTP_HOST = os.environ.get("SMTP_HOST", "")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASS = os.environ.get("SMTP_PASS", "")
NOTIFY_EMAIL = os.environ.get("NOTIFY_EMAIL", "jmussamuhindo@gmail.com")

CSV_HEADERS = [
    "id",
    "submitted_at",
    "language",
    "full_name",
    "additional_names",
    "phone",
    "attending",
    "number_of_guests",
    "children_under_5",
    "meal_preference",
    "message",
]

EDITABLE_FIELDS = [
    "full_name",
    "additional_names",
    "phone",
    "attending",
    "number_of_guests",
    "children_under_5",
    "meal_preference",
    "message",
]

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = Flask(__name__)
app.secret_key = SECRET_KEY


# ---------------------------------------------------------------------------
# CSV helpers
# ---------------------------------------------------------------------------
def ensure_csv() -> None:
    """Create responses.csv with headers if it doesn't exist; migrate old data
    to whatever the current CSV_HEADERS schema is (missing columns get '')."""
    if not RESPONSES_FILE.exists():
        with RESPONSES_FILE.open("w", newline="", encoding="utf-8") as f:
            csv.DictWriter(f, fieldnames=CSV_HEADERS).writeheader()
        return
    with RESPONSES_FILE.open("r", newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        return
    needs_migration = False
    for row in rows:
        if "id" not in row or not row.get("id"):
            row["id"] = uuid.uuid4().hex
            needs_migration = True
        for h in CSV_HEADERS:
            if h not in row:
                row[h] = ""
                needs_migration = True
    if needs_migration:
        _write_all(rows)


def _write_all(rows: list[dict]) -> None:
    with RESPONSES_FILE.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADERS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({h: row.get(h, "") for h in CSV_HEADERS})


def load_responses() -> list[dict]:
    if not RESPONSES_FILE.exists():
        return []
    with RESPONSES_FILE.open("r", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def save_response(data: dict) -> str:
    ensure_csv()
    new_id = uuid.uuid4().hex
    data = {**data, "id": new_id}
    with RESPONSES_FILE.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADERS, extrasaction="ignore")
        writer.writerow({h: data.get(h, "") for h in CSV_HEADERS})
    return new_id


def update_response(row_id: str, new_data: dict) -> bool:
    rows = load_responses()
    found = False
    for row in rows:
        if row.get("id") == row_id:
            for field in EDITABLE_FIELDS:
                if field in new_data:
                    row[field] = new_data[field]
            original_ts = row.get("submitted_at", "").split(" (edited")[0]
            row["submitted_at"] = (
                f"{original_ts} (edited {datetime.now().strftime('%Y-%m-%d %H:%M')})"
            )
            found = True
            break
    if found:
        _write_all(rows)
    return found


def delete_response(row_id: str) -> bool:
    rows = load_responses()
    new_rows = [r for r in rows if r.get("id") != row_id]
    if len(new_rows) == len(rows):
        return False
    _write_all(new_rows)
    return True


def find_by_id(row_id: str) -> dict | None:
    for row in load_responses():
        if row.get("id") == row_id:
            return row
    return None


def _normalize_name(name: str) -> str:
    return " ".join(name.lower().split())


def find_id_by_name(full_name: str) -> str | None:
    target = _normalize_name(full_name)
    if not target:
        return None
    for row in load_responses():
        if _normalize_name(row.get("full_name", "")) == target:
            return row.get("id")
    return None


def _to_int(value: str, default: int = 0) -> int:
    try:
        return int((value or "").strip())
    except (ValueError, TypeError):
        return default


def compute_totals(rows: list[dict]) -> dict:
    attending = [r for r in rows if r.get("attending") == "yes"]
    declining = [r for r in rows if r.get("attending") == "no"]
    total_guests = sum(_to_int(r.get("number_of_guests"), 1) for r in attending)
    total_children = sum(_to_int(r.get("children_under_5"), 0) for r in attending)

    # ---- Meal breakdown across attending people ----
    meal_breakdown = {"standard": 0, "vegetarian": 0, "unspecified": 0}
    for r in attending:
        meal = (r.get("meal_preference") or "").strip()
        n = _to_int(r.get("number_of_guests"), 1)
        if meal == "standard":
            meal_breakdown["standard"] += n
        elif meal == "vegetarian":
            meal_breakdown["vegetarian"] += n
        else:
            meal_breakdown["unspecified"] += n

    return {
        "total_responses": len(rows),
        "attending_responses": len(attending),
        "declining_responses": len(declining),
        "total_guests": total_guests,
        "total_children": total_children,
        "meal_standard": meal_breakdown["standard"],
        "meal_vegetarian": meal_breakdown["vegetarian"],
        "meal_unspecified": meal_breakdown["unspecified"],
    }


def _form_to_data(form) -> dict:
    """Derive the headcount from the structured fields:
        - attending=yes  → submitter counts as 1
        - +1 companion (additional_names filled in) → +1
        - children under 5 → + that number
        - attending=no    → all counts forced to 0
    The form no longer asks for a manual "# people" — it's computed.
    """
    attending = form.get("attending", "no")
    additional_names = form.get("additional_names", "").strip()
    bringing_kids = form.get("bringing_kids") == "yes"

    if attending == "yes":
        kids = max(0, _to_int(form.get("children_under_5", "0"), 0)) if bringing_kids else 0
        total = 1 + (1 if additional_names else 0) + kids
        num_guests = str(total)
        num_kids = str(kids)
    else:
        num_guests = "0"
        num_kids = "0"
        additional_names = ""  # clear companion name when declining

    return {
        "language": form.get("language", "en"),
        "full_name": form.get("full_name", "").strip(),
        "additional_names": additional_names,
        "phone": form.get("phone", "").strip(),
        "attending": attending,
        "number_of_guests": num_guests,
        "children_under_5": num_kids,
        "meal_preference": form.get("meal_preference", "").strip(),
        "message": form.get("message", "").strip(),
    }


def send_notification_email(data: dict, edited: bool = False) -> None:
    if not SMTP_HOST or not SMTP_USER or not SMTP_PASS:
        return
    msg = EmailMessage()
    attending = "YES" if data.get("attending") == "yes" else "NO"
    verb = "UPDATED" if edited else "NEW"
    msg["Subject"] = f"Wedding Confirmation [{verb}] — {data['full_name']} ({attending})"
    msg["From"] = SMTP_USER
    msg["To"] = NOTIFY_EMAIL
    body_lines = [
        f"A confirmation was {'updated' if edited else 'submitted'}.",
        "",
        f"Name: {data['full_name']}",
        f"Attending: {attending}",
        f"Number of guests: {data.get('number_of_guests', '')}",
        f"Children under 5: {data.get('children_under_5', '')}",
        f"Companion: {data.get('additional_names') or '—'}",
        f"Phone: {data.get('phone') or '—'}",
        f"Meal preference: {data.get('meal_preference') or '—'}",
        f"Message: {data.get('message') or '—'}",
        "",
        f"Language: {data.get('language', 'en')}",
    ]
    msg.set_content("\n".join(body_lines))
    context = ssl.create_default_context()
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls(context=context)
        server.login(SMTP_USER, SMTP_PASS)
        server.send_message(msg)


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------
def admin_required(view):
    """Decorator: redirect to /admin/login if not logged in."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("is_admin"):
            return redirect(url_for("admin_login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


# ---------------------------------------------------------------------------
# Public guest routes
# ---------------------------------------------------------------------------
@app.route("/")
def rsvp_form():
    return render_template("rsvp.html", wedding=WEDDING)


@app.route("/submit", methods=["POST"])
def submit():
    data = _form_to_data(request.form)
    if not data["full_name"]:
        return redirect(url_for("rsvp_form"))

    existing_id = find_id_by_name(data["full_name"])
    if existing_id:
        return render_template(
            "already_submitted.html",
            wedding=WEDDING,
            name=data["full_name"],
            edit_id=existing_id,
            language=data["language"],
        )

    data["submitted_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    save_response(data)

    try:
        send_notification_email(data)
    except Exception as exc:  # pragma: no cover
        app.logger.warning("Failed to send notification email: %s", exc)

    return render_template(
        "thank_you.html",
        wedding=WEDDING,
        name=data["full_name"],
        attending=data["attending"] == "yes",
        language=data["language"],
    )


@app.route("/edit/<row_id>", methods=["GET", "POST"])
def edit(row_id: str):
    """Edit an existing submission. Both guests (with their unique link) and
    admins (via the dashboard) reach this route."""
    row = find_by_id(row_id)
    if not row:
        abort(404)

    is_admin = bool(session.get("is_admin"))

    if request.method == "POST":
        new_data = _form_to_data(request.form)
        if not new_data["full_name"]:
            return render_template("edit.html", wedding=WEDDING, row=row,
                                   error="name_required", is_admin=is_admin)

        collision = find_id_by_name(new_data["full_name"])
        if collision and collision != row_id:
            return render_template("edit.html", wedding=WEDDING, row=row,
                                   error="name_collision", is_admin=is_admin)

        update_response(row_id, new_data)

        try:
            send_notification_email({**new_data, "submitted_at": ""}, edited=True)
        except Exception as exc:  # pragma: no cover
            app.logger.warning("Failed to send notification email: %s", exc)

        # If the editor is an admin, send them back to the dashboard.
        if session.get("is_admin"):
            return redirect(url_for("admin"))

        return render_template(
            "thank_you.html",
            wedding=WEDDING,
            name=new_data["full_name"],
            attending=new_data["attending"] == "yes",
            language=new_data["language"],
            edited=True,
        )

    return render_template("edit.html", wedding=WEDDING, row=row, is_admin=is_admin)


# ---------------------------------------------------------------------------
# Admin routes
# ---------------------------------------------------------------------------
@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    error = None
    if request.method == "POST":
        if request.form.get("password") == ADMIN_PASSWORD:
            session["is_admin"] = True
            next_url = request.args.get("next") or request.form.get("next") or url_for("admin")
            # Prevent open-redirect — only allow same-host paths
            if not next_url.startswith("/"):
                next_url = url_for("admin")
            return redirect(next_url)
        error = "wrong_password"
    return render_template("admin_login.html", wedding=WEDDING, error=error,
                           next_url=request.args.get("next", ""))


@app.route("/admin/logout")
def admin_logout():
    session.pop("is_admin", None)
    return redirect(url_for("admin_login"))


@app.route("/admin")
@admin_required
def admin():
    rows = load_responses()

    # Heal any bad data left over from older versions of the app:
    # "yes" with 0 guests is a contradiction → bump to 1 (the submitter themselves).
    dirty = False
    for row in rows:
        if row.get("attending") == "yes" and _to_int(row.get("number_of_guests"), 0) < 1:
            row["number_of_guests"] = "1"
            dirty = True
    if dirty:
        _write_all(rows)

    totals = compute_totals(rows)
    # Split rows: only attending in the main guest list (numbered 1..N).
    # Declined go to a separate section so they never inflate the numbering.
    ordered = list(reversed(rows))  # newest first
    attending_rows = [r for r in ordered if r.get("attending") == "yes"]
    declined_rows = [r for r in ordered if r.get("attending") != "yes"]
    return render_template(
        "admin.html",
        wedding=WEDDING,
        attending_rows=attending_rows,
        declined_rows=declined_rows,
        totals=totals,
    )


@app.route("/admin/export")
@admin_required
def admin_export():
    """Download all responses as a clean CSV file."""
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=CSV_HEADERS, extrasaction="ignore")
    writer.writeheader()
    for row in load_responses():
        writer.writerow({h: row.get(h, "") for h in CSV_HEADERS})
    csv_data = buf.getvalue()
    filename = f"wedding_confirmations_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.route("/admin/delete/<row_id>", methods=["POST"])
@admin_required
def admin_delete(row_id: str):
    """Delete a confirmation row. Admin only."""
    delete_response(row_id)
    return redirect(url_for("admin"))


# ---------------------------------------------------------------------------
# Error handlers
# ---------------------------------------------------------------------------
@app.errorhandler(401)
def unauthorized(_):
    return redirect(url_for("admin_login"))


@app.errorhandler(404)
def not_found(_):
    return (
        "<h1>404 — Not found</h1>"
        "<p>The page you tried to open doesn't exist. "
        '<a href="/">Go back to the form</a>.</p>',
        404,
    )


if __name__ == "__main__":
    ensure_csv()
    port = int(os.environ.get("PORT", "5002"))
    debug = os.environ.get("FLASK_DEBUG", "1") == "1"
    app.run(host="0.0.0.0", port=port, debug=debug)
