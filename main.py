from __future__ import annotations

import json
import os
import secrets
from dataclasses import asdict, dataclass
from functools import wraps
from pathlib import Path
from typing import Callable, List
from dotenv import load_dotenv
from flask import Flask, flash, redirect, render_template, request, session, url_for
load_dotenv()
app = Flask(__name__)

app.secret_key =  os.getenv("ADMIN_SECRET_KEY", "OEWRHREWOIHROIHWLOIHGOIWRHGOIHWIOGOLIWRHGH")

BASE_DIR = Path(__file__).resolve().parent
DATA_FILE = BASE_DIR / "profiles.json"
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")
MIN_AGE = 16
MAX_AGE = 100


@dataclass
class CandidateProfile:
    id: int
    namn: str
    alder: str
    utbildning: str
    erfarenheter: str
    beskrivning: str

    @property
    def initialer(self) -> str:
        delar = [deltext for deltext in self.namn.split() if deltext]
        if not delar:
            return "??"
        if len(delar) == 1:
            return delar[0][:2].upper()
        return f"{delar[0][0]}{delar[-1][0]}".upper()

    @classmethod
    def from_dict(cls, profile_data: dict) -> "CandidateProfile":
        return cls(
            id=profile_data["id"],
            namn=profile_data.get("namn", "").strip(),
            alder=str(profile_data.get("alder", "Ej angivet")).strip(),
            utbildning=profile_data.get("utbildning", "Ej angivet").strip(),
            erfarenheter=(
                profile_data.get("erfarenheter")
                or profile_data.get("erfarenhet")
                or "Ej angivet"
            ).strip(),
            beskrivning=profile_data.get("beskrivning", "").strip(),
        )


def default_profiles() -> List[CandidateProfile]:
    return [
        CandidateProfile(
            id=1,
            namn="Anna Berg",
            alder="34",
            utbildning="YH-utbildning i projektledning",
            erfarenheter="8 års erfarenhet av projektledning inom service och leverans.",
            beskrivning="Strukturerad och trygg person som gillar att skapa ordning och hålla ihop team.",
        ),
        CandidateProfile(
            id=2,
            namn="Johan Lind",
            alder="29",
            utbildning="Gymnasieutbildning inom administration",
            erfarenheter="5 års erfarenhet av administration, bokning och intern support.",
            beskrivning="Noggrann och lugn administratör med tydligt fokus på service och struktur.",
        ),
        CandidateProfile(
            id=3,
            namn="Sara Holm",
            alder="31",
            utbildning="Kandidatexamen i företagsekonomi",
            erfarenheter="6 års erfarenhet av försäljning, kundrelationer och offertarbete.",
            beskrivning="Social och målinriktad person som bygger förtroende snabbt och arbetar långsiktigt.",
        ),
    ]


def save_profiles(profile_items: List[CandidateProfile]) -> None:
    DATA_FILE.write_text(
        json.dumps([asdict(profile) for profile in profile_items], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def load_profiles() -> List[CandidateProfile]:
    if DATA_FILE.exists():
        try:
            raw_profiles = json.loads(DATA_FILE.read_text(encoding="utf-8"))
            return [CandidateProfile.from_dict(profile_data) for profile_data in raw_profiles]
        except (json.JSONDecodeError, TypeError, ValueError, KeyError):
            pass

    profiles = default_profiles()
    save_profiles(profiles)
    return profiles


profiles: List[CandidateProfile] = load_profiles()


def admin_logged_in() -> bool:
    return bool(session.get("is_admin"))


def get_csrf_token() -> str:
    token = session.get("csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["csrf_token"] = token
    return token


def csrf_is_valid() -> bool:
    token = request.form.get("csrf_token", "")
    session_token = session.get("csrf_token", "")
    return bool(session_token) and secrets.compare_digest(token, session_token)


def age_is_valid(value: str) -> bool:
    if not value.isdigit():
        return False
    age = int(value)
    return MIN_AGE <= age <= MAX_AGE


def login_required(view: Callable) -> Callable:
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if not admin_logged_in():
            flash("Logga in som admin för att hantera profiler.", "error")
            return redirect(url_for("index"))
        return view(*args, **kwargs)

    return wrapped_view


@app.context_processor
def inject_layout_data() -> dict:
    return {
        "admin_logged_in": admin_logged_in(),
        "csrf_token": get_csrf_token(),
    }


@app.route("/")
def index():
    return render_template(
        "index.html",
        title="Profilöversikt",
        profiles=profiles,
    )


@app.post("/admin/login")
def admin_login():
    if not csrf_is_valid():
        flash("Din session kunde inte verifieras. Försök igen.", "error")
        return redirect(url_for("index"))

    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")

    if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
        session["is_admin"] = True
        flash("Admin är nu inloggad.", "success")
    else:
        flash("Fel användarnamn eller lösenord.", "error")

    return redirect(url_for("index"))


@app.post("/admin/logout")
def admin_logout():
    if not csrf_is_valid():
        flash("Din session kunde inte verifieras. Försök igen.", "error")
        return redirect(url_for("index"))

    session.clear()
    flash("Du är nu utloggad.", "success")
    return redirect(url_for("index"))


@app.route("/admin")
def admin():
    return redirect(url_for("admin_add" if admin_logged_in() else "index"))


@app.route("/admin/add", methods=["GET", "POST"])
@login_required
def admin_add():
    if request.method == "POST":
        if not csrf_is_valid():
            flash("Din session kunde inte verifieras. Försök igen.", "error")
            return redirect(url_for("admin_add"))

        namn = request.form.get("namn", "").strip()
        alder = request.form.get("alder", "").strip()
        utbildning = request.form.get("utbildning", "").strip()
        erfarenheter = request.form.get("erfarenheter", "").strip()
        beskrivning = request.form.get("beskrivning", "").strip()

        if not all([namn, alder, utbildning, erfarenheter, beskrivning]):
            flash("Alla fält måste fyllas i.", "error")
            return redirect(url_for("admin_add"))

        if not age_is_valid(alder):
            flash("Ålder måste vara ett heltal mellan 16 och 100.", "error")
            return redirect(url_for("admin_add"))

        alder = str(int(alder))

        new_profile = CandidateProfile(
            id=max((profile.id for profile in profiles), default=0) + 1,
            namn=namn,
            alder=alder,
            utbildning=utbildning,
            erfarenheter=erfarenheter,
            beskrivning=beskrivning,
        )
        profiles.append(new_profile)
        save_profiles(profiles)
        flash(f"Profilen för {namn} lades till.", "success")
        return redirect(url_for("index"))

    return render_template(
        "admin_add.html",
        title="Lägg till profil",
    )


@app.post("/admin/delete/<int:profile_id>")
@login_required
def delete_profile(profile_id: int):
    global profiles

    if not csrf_is_valid():
        flash("Din session kunde inte verifieras. Försök igen.", "error")
        return redirect(url_for("index"))

    before = len(profiles)
    profiles = [profile for profile in profiles if profile.id != profile_id]

    if len(profiles) == before:
        flash("Kunde inte hitta profilen.", "error")
    else:
        save_profiles(profiles)
        flash("Profilen togs bort.", "success")

    return redirect(url_for("index"))


@app.route("/api/profiles")
def api_profiles():
    return {"profiles": [asdict(profile) for profile in profiles]}


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8080"))
    debug = os.getenv("FLASK_DEBUG", "0") == "1"
    app.run(debug=debug, port=port)
