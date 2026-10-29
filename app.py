"""
Standardized Hiring Assessment Platform - working prototype.

One standardized, multi-round assessment that a candidate sits once. The score
report is shared with partner companies, but only for candidates who have
explicitly consented.

Rounds, and the weight each carries, follow the blueprint:
    Speed & working ability   15%
    Analytical                40%
    Communication (written)   35%
    Behavioural (SJT)         10%
"""

import json
import os
import secrets
import sqlite3
import socket
from datetime import datetime, timezone

from flask import (
    Flask, g, redirect, render_template, request, session, url_for, abort, jsonify
)

import scorer
import storage

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("DB_PATH", "/data/assessment.db")
COMPANY_PASSCODE = os.environ.get("COMPANY_PASSCODE", "partner2026")
REVIEWER_PASSCODE = os.environ.get("REVIEWER_PASSCODE", "reviewer2026")

with open(os.path.join(BASE_DIR, "questions.json")) as fh:
    BANK = json.load(fh)

WEIGHTS = BANK["weights"]

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", secrets.token_hex(16))


# --------------------------------------------------------------------------
# Database
# --------------------------------------------------------------------------

def get_db():
    if "db" not in g:
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(_exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


SCHEMA = """
CREATE TABLE IF NOT EXISTS attempts (
    id                 TEXT PRIMARY KEY,
    name               TEXT NOT NULL,
    email              TEXT NOT NULL,
    college            TEXT NOT NULL,
    consent            INTEGER NOT NULL DEFAULT 0,
    created_at         TEXT NOT NULL,
    mcq_started_at     TEXT,
    mcq_elapsed        REAL,
    tab_switches       INTEGER DEFAULT 0,
    analytical_score   REAL,
    behavioural_score  REAL,
    speed_score        REAL,
    written_text       TEXT,
    comm_score         REAL,
    comm_breakdown     TEXT,
    comm_engine        TEXT,
    comm_note          TEXT,
    reviewed           INTEGER DEFAULT 0,
    reviewer_note      TEXT,
    final_score        REAL,
    status             TEXT NOT NULL DEFAULT 'registered',
    is_seed            INTEGER DEFAULT 0,
    storage_location   TEXT
);
"""


def init_db():
    db = get_db()
    db.executescript(SCHEMA)
    db.commit()
    seed_cohort()


def seed_cohort():
    """
    A percentile is meaningless against an empty cohort, so the database ships
    with a synthetic reference cohort. These rows are flagged is_seed = 1 and
    are clearly labelled as synthetic wherever they are shown.
    """
    db = get_db()
    existing = db.execute("SELECT COUNT(*) c FROM attempts WHERE is_seed = 1").fetchone()
    if existing["c"] > 0:
        return

    import random
    rng = random.Random(42)
    colleges = [
        "Jain University", "Christ University", "Mount Carmel College",
        "St Joseph's", "PES University", "RV College", "BMS College",
    ]
    first = ["Aarav", "Diya", "Rohan", "Isha", "Kabir", "Ananya", "Vihaan",
             "Meera", "Arjun", "Sara", "Dev", "Nisha", "Karan", "Tara",
             "Yash", "Riya", "Advait", "Prisha", "Neel", "Anika"]
    last = ["Shah", "Rao", "Menon", "Iyer", "Gupta", "Nair", "Reddy",
            "Patel", "Joshi", "Verma"]

    rows = []
    for i in range(42):
        name = f"{rng.choice(first)} {rng.choice(last)}"
        # A roughly normal spread of ability.
        base = max(18.0, min(96.0, rng.gauss(58, 15)))
        analytical = max(0.0, min(100.0, base + rng.gauss(0, 8)))
        behavioural = max(0.0, min(100.0, base + rng.gauss(0, 12)))
        speed = max(0.0, min(100.0, base + rng.gauss(5, 10)))
        comm = max(0.0, min(100.0, base + rng.gauss(0, 10)))
        final = (
            speed * WEIGHTS["speed"]
            + analytical * WEIGHTS["analytical"]
            + comm * WEIGHTS["communication"]
            + behavioural * WEIGHTS["behavioral"]
        ) / 100.0
        rows.append((
            f"seed-{i:03d}", name, f"seed{i}@example.edu", rng.choice(colleges),
            1 if rng.random() < 0.8 else 0,
            datetime.now(timezone.utc).isoformat(),
            round(analytical, 1), round(behavioural, 1), round(speed, 1),
            round(comm, 1), round(final, 1),
        ))

    db.executemany(
        """INSERT INTO attempts
           (id, name, email, college, consent, created_at,
            analytical_score, behavioural_score, speed_score,
            comm_score, final_score, status, is_seed, reviewed)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,'complete',1,1)""",
        rows,
    )
    db.commit()


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def percentile_for(score):
    db = get_db()
    row = db.execute(
        "SELECT COUNT(*) total, SUM(CASE WHEN final_score < ? THEN 1 ELSE 0 END) below "
        "FROM attempts WHERE final_score IS NOT NULL",
        (score,),
    ).fetchone()
    total = row["total"] or 0
    if total <= 1:
        return None
    return round((row["below"] or 0) / total * 100)


def band(score):
    if score >= 75:
        return "Strong"
    if score >= 60:
        return "Above average"
    if score >= 45:
        return "Developing"
    return "Needs work"


def strengths_and_gaps(parts):
    """
    Strengths are rounds scored well in absolute terms, not merely the best of a
    weak set. Gaps work the same way in reverse, so a candidate who scores highly
    everywhere is not handed an invented weakness.
    """
    ordered = sorted(parts.items(), key=lambda kv: kv[1], reverse=True)
    strengths = [k for k, v in ordered if v >= 65][:2]
    gaps = [k for k, v in reversed(ordered) if v < 65][:2]

    if not strengths:
        strengths = [ordered[0][0]]  # relatively strongest, even if low
    return strengths, gaps


@app.template_filter("from_json")
def from_json_filter(value):
    try:
        return json.loads(value or "{}")
    except (ValueError, TypeError):
        return {}


@app.context_processor
def inject_globals():
    return {
        "storage_backend": storage.backend_name(),
        "host_name": socket.gethostname(),
        "container_id": os.environ.get("HOSTNAME", socket.gethostname()),
    }


# --------------------------------------------------------------------------
# Candidate journey
# --------------------------------------------------------------------------

@app.route("/")
def index():
    return render_template("index.html", bank=BANK)


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        email = (request.form.get("email") or "").strip()
        college = (request.form.get("college") or "").strip()
        consent = 1 if request.form.get("consent") == "yes" else 0

        if not name or not email or not college:
            return render_template(
                "register.html", error="Please fill in every field.",
                form=request.form,
            )

        attempt_id = secrets.token_urlsafe(8)
        db = get_db()
        db.execute(
            """INSERT INTO attempts (id, name, email, college, consent, created_at, status)
               VALUES (?,?,?,?,?,?, 'registered')""",
            (attempt_id, name, email, college, consent,
             datetime.now(timezone.utc).isoformat()),
        )
        db.commit()
        session["attempt_id"] = attempt_id
        return redirect(url_for("test", attempt_id=attempt_id))

    return render_template("register.html", error=None, form={})


@app.route("/test/<attempt_id>")
def test(attempt_id):
    db = get_db()
    row = db.execute("SELECT * FROM attempts WHERE id = ?", (attempt_id,)).fetchone()
    if row is None:
        abort(404)
    if row["status"] not in ("registered",):
        return redirect(url_for("written", attempt_id=attempt_id))

    db.execute(
        "UPDATE attempts SET mcq_started_at = ? WHERE id = ? AND mcq_started_at IS NULL",
        (datetime.now(timezone.utc).isoformat(), attempt_id),
    )
    db.commit()

    return render_template(
        "test.html",
        attempt=row,
        analytical=BANK["analytical"],
        behavioural=BANK["behavioral"],
        limit=BANK["mcq_time_limit_seconds"],
    )


@app.route("/test/<attempt_id>", methods=["POST"])
def submit_test(attempt_id):
    db = get_db()
    row = db.execute("SELECT * FROM attempts WHERE id = ?", (attempt_id,)).fetchone()
    if row is None:
        abort(404)

    started = row["mcq_started_at"]
    if started:
        elapsed = (
            datetime.now(timezone.utc)
            - datetime.fromisoformat(started)
        ).total_seconds()
    else:
        elapsed = float(BANK["mcq_time_limit_seconds"])

    try:
        tab_switches = int(request.form.get("tab_switches") or 0)
    except ValueError:
        tab_switches = 0

    answered = 0
    correct = 0
    for q in BANK["analytical"]:
        given = request.form.get(q["id"])
        if given is not None and given != "":
            answered += 1
            if int(given) == q["answer"]:
                correct += 1
    analytical = round(correct / len(BANK["analytical"]) * 100, 1)

    b_answered = 0
    b_correct = 0
    for q in BANK["behavioral"]:
        given = request.form.get(q["id"])
        if given is not None and given != "":
            b_answered += 1
            if int(given) == q["answer"]:
                b_correct += 1
    behavioural = round(b_correct / len(BANK["behavioral"]) * 100, 1)

    speed = scorer.score_speed(
        elapsed,
        BANK["mcq_time_limit_seconds"],
        answered + b_answered,
        len(BANK["analytical"]) + len(BANK["behavioral"]),
    )

    db.execute(
        """UPDATE attempts
           SET mcq_elapsed = ?, tab_switches = ?, analytical_score = ?,
               behavioural_score = ?, speed_score = ?, status = 'mcq_done'
           WHERE id = ?""",
        (round(elapsed, 1), tab_switches, analytical, behavioural, speed, attempt_id),
    )
    db.commit()
    return redirect(url_for("written", attempt_id=attempt_id))


@app.route("/written/<attempt_id>")
def written(attempt_id):
    db = get_db()
    row = db.execute("SELECT * FROM attempts WHERE id = ?", (attempt_id,)).fetchone()
    if row is None:
        abort(404)
    if row["status"] == "complete":
        return redirect(url_for("scorecard", attempt_id=attempt_id))
    if row["status"] == "registered":
        return redirect(url_for("test", attempt_id=attempt_id))
    return render_template(
        "written.html",
        attempt=row,
        spec=BANK["written"],
        limit=BANK["written_time_limit_seconds"],
    )


@app.route("/written/<attempt_id>", methods=["POST"])
def submit_written(attempt_id):
    db = get_db()
    row = db.execute("SELECT * FROM attempts WHERE id = ?", (attempt_id,)).fetchone()
    if row is None:
        abort(404)

    text = (request.form.get("answer") or "").strip()
    result = scorer.score_written(text, BANK["written"])

    penalty = scorer.integrity_penalty(row["tab_switches"] or 0)
    final = (
        (row["speed_score"] or 0) * WEIGHTS["speed"]
        + (row["analytical_score"] or 0) * WEIGHTS["analytical"]
        + result["score"] * WEIGHTS["communication"]
        + (row["behavioural_score"] or 0) * WEIGHTS["behavioral"]
    ) / 100.0
    final = round(max(0.0, final - penalty), 1)

    needs_review = 1 if result["engine"].startswith("ai") else 0

    db.execute(
        """UPDATE attempts
           SET written_text = ?, comm_score = ?, comm_breakdown = ?, comm_engine = ?,
               comm_note = ?, final_score = ?, status = 'complete', reviewed = ?
           WHERE id = ?""",
        (text, result["score"], json.dumps(result["breakdown"]), result["engine"],
         result.get("note", ""), final, 0 if needs_review else 1, attempt_id),
    )
    db.commit()

    fresh = db.execute("SELECT * FROM attempts WHERE id = ?", (attempt_id,)).fetchone()
    location = storage.save_scorecard(attempt_id, {
        "attempt_id": attempt_id,
        "candidate": fresh["name"],
        "college": fresh["college"],
        "consent_to_share": bool(fresh["consent"]),
        "scores": {
            "speed": fresh["speed_score"],
            "analytical": fresh["analytical_score"],
            "communication": fresh["comm_score"],
            "behavioural": fresh["behavioural_score"],
            "final": fresh["final_score"],
        },
        "rubric_breakdown": result["breakdown"],
        "scoring_engine": result["engine"],
        "integrity": {"tab_switches": fresh["tab_switches"], "penalty_applied": penalty},
    })
    db.execute("UPDATE attempts SET storage_location = ? WHERE id = ?",
               (location, attempt_id))
    db.commit()

    return redirect(url_for("scorecard", attempt_id=attempt_id))


@app.route("/scorecard/<attempt_id>")
def scorecard(attempt_id):
    db = get_db()
    row = db.execute("SELECT * FROM attempts WHERE id = ?", (attempt_id,)).fetchone()
    if row is None or row["status"] != "complete":
        abort(404)

    parts = {
        "Speed & working ability": row["speed_score"] or 0,
        "Analytical": row["analytical_score"] or 0,
        "Communication": row["comm_score"] or 0,
        "Behavioural": row["behavioural_score"] or 0,
    }
    strengths, gaps = strengths_and_gaps(parts)
    breakdown = json.loads(row["comm_breakdown"] or "{}")

    return render_template(
        "scorecard.html",
        attempt=row,
        parts=parts,
        weights=WEIGHTS,
        strengths=strengths,
        gaps=gaps,
        breakdown=breakdown,
        rubric=BANK["written"]["rubric"],
        percentile=percentile_for(row["final_score"] or 0),
        band=band(row["final_score"] or 0),
        penalty=scorer.integrity_penalty(row["tab_switches"] or 0),
    )


@app.route("/consent/<attempt_id>", methods=["POST"])
def toggle_consent(attempt_id):
    """A candidate can withdraw or give consent after seeing their own score."""
    db = get_db()
    row = db.execute("SELECT consent FROM attempts WHERE id = ?", (attempt_id,)).fetchone()
    if row is None:
        abort(404)
    db.execute("UPDATE attempts SET consent = ? WHERE id = ?",
               (0 if row["consent"] else 1, attempt_id))
    db.commit()
    return redirect(url_for("scorecard", attempt_id=attempt_id))


# --------------------------------------------------------------------------
# Company journey
# --------------------------------------------------------------------------

@app.route("/company", methods=["GET", "POST"])
def company():
    if request.method == "POST" and request.form.get("passcode"):
        if request.form.get("passcode") == COMPANY_PASSCODE:
            session["company"] = True
        else:
            return render_template("company_login.html", error="Incorrect passcode.")
        return redirect(url_for("company"))

    if not session.get("company"):
        return render_template("company_login.html", error=None)

    try:
        threshold = float(request.args.get("threshold", 60))
    except ValueError:
        threshold = 60.0

    db = get_db()
    rows = db.execute(
        """SELECT * FROM attempts
           WHERE status = 'complete' AND consent = 1 AND final_score >= ?
           ORDER BY final_score DESC""",
        (threshold,),
    ).fetchall()

    withheld = db.execute(
        "SELECT COUNT(*) c FROM attempts WHERE status = 'complete' AND consent = 0"
    ).fetchone()["c"]

    return render_template(
        "company.html",
        rows=rows,
        threshold=threshold,
        withheld=withheld,
        band=band,
    )


@app.route("/company/logout")
def company_logout():
    session.pop("company", None)
    return redirect(url_for("index"))


# --------------------------------------------------------------------------
# Human reviewer (the "human-reviewed" half of AI-assisted scoring)
# --------------------------------------------------------------------------

@app.route("/reviewer", methods=["GET", "POST"])
def reviewer():
    if request.method == "POST" and request.form.get("passcode"):
        if request.form.get("passcode") == REVIEWER_PASSCODE:
            session["reviewer"] = True
        else:
            return render_template("reviewer_login.html", error="Incorrect passcode.")
        return redirect(url_for("reviewer"))

    if not session.get("reviewer"):
        return render_template("reviewer_login.html", error=None)

    db = get_db()
    rows = db.execute(
        """SELECT * FROM attempts
           WHERE status = 'complete' AND is_seed = 0
           ORDER BY reviewed ASC, created_at DESC"""
    ).fetchall()
    return render_template("reviewer.html", rows=rows, rubric=BANK["written"]["rubric"])


@app.route("/reviewer/<attempt_id>", methods=["POST"])
def review_submit(attempt_id):
    if not session.get("reviewer"):
        abort(403)
    db = get_db()
    row = db.execute("SELECT * FROM attempts WHERE id = ?", (attempt_id,)).fetchone()
    if row is None:
        abort(404)

    try:
        new_comm = float(request.form.get("comm_score"))
    except (TypeError, ValueError):
        new_comm = row["comm_score"] or 0.0
    new_comm = max(0.0, min(100.0, new_comm))
    note = (request.form.get("reviewer_note") or "").strip()

    penalty = scorer.integrity_penalty(row["tab_switches"] or 0)
    final = (
        (row["speed_score"] or 0) * WEIGHTS["speed"]
        + (row["analytical_score"] or 0) * WEIGHTS["analytical"]
        + new_comm * WEIGHTS["communication"]
        + (row["behavioural_score"] or 0) * WEIGHTS["behavioral"]
    ) / 100.0
    final = round(max(0.0, final - penalty), 1)

    db.execute(
        """UPDATE attempts
           SET comm_score = ?, final_score = ?, reviewed = 1, reviewer_note = ?
           WHERE id = ?""",
        (round(new_comm, 1), final, note, attempt_id),
    )
    db.commit()
    return redirect(url_for("reviewer"))


# --------------------------------------------------------------------------
# Operations endpoints - these are what you point at during the cloud demo
# --------------------------------------------------------------------------

@app.route("/health")
def health():
    """Load balancers and the Docker HEALTHCHECK call this."""
    return jsonify({
        "status": "ok",
        "served_by": socket.gethostname(),
        "storage_backend": storage.backend_name(),
        "scoring_engine": "ai-assisted" if os.environ.get("GEMINI_API_KEY") else "rule-based",
        "time": datetime.now(timezone.utc).isoformat(),
    })


@app.route("/admin/info")
def admin_info():
    """
    Shows which machine and container served the request, and lists the objects
    in the scorecard store. Useful on the slide about horizontal scaling: run
    two containers and refresh to watch the hostname change.
    """
    db = get_db()
    stats = db.execute(
        """SELECT COUNT(*) total,
                  SUM(CASE WHEN is_seed = 0 THEN 1 ELSE 0 END) real_attempts,
                  SUM(CASE WHEN consent = 1 THEN 1 ELSE 0 END) consented
           FROM attempts WHERE status = 'complete'"""
    ).fetchone()
    return render_template(
        "admin.html",
        stats=stats,
        objects=storage.list_scorecards(),
        env_flags={
            "DB_PATH": DB_PATH,
            "SCORECARD_DIR": storage.LOCAL_DIR,
            "AZURE_STORAGE_CONNECTION_STRING": "set" if os.environ.get(
                "AZURE_STORAGE_CONNECTION_STRING") else "not set",
            "GEMINI_API_KEY": "set" if os.environ.get("GEMINI_API_KEY") else "not set",
        },
    )


with app.app_context():
    init_db()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8000)), debug=False)
