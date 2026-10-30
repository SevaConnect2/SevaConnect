import os
import sqlite3
from datetime import datetime

import pandas as pd
import psycopg2
from psycopg2.extras import RealDictCursor

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash
)

from matching import rank_opportunities


# ============================================================
# FLASK CONFIGURATION
# ============================================================

app = Flask(__name__)

app.secret_key = os.environ.get(
    "SECRET_KEY",
    "sevaconnect-local-secret-key"
)

# IMPORTANT:
# This must be the NAME of the environment variable.
#
# Render:
# DATABASE_URL = PostgreSQL Internal Database URL
#
# Local:
# DATABASE_URL can be absent and SQLite will be used.
DATABASE_URL = os.environ.get("DATABASE_URL")

SQLITE_DATABASE = "database.db"

IS_RENDER = os.environ.get(
    "RENDER",
    ""
).lower() == "true"


# ============================================================
# DATABASE CONNECTION CLASS
# ============================================================

class DatabaseConnection:

    def __init__(self):

        # PostgreSQL when DATABASE_URL exists.
        # Otherwise use local SQLite.
        self.is_postgres = bool(DATABASE_URL)

        if self.is_postgres:

            database_url = DATABASE_URL

            # Support old postgres:// URLs
            if database_url.startswith("postgres://"):
                database_url = database_url.replace(
                    "postgres://",
                    "postgresql://",
                    1
                )

            self.connection = psycopg2.connect(
                database_url
            )

            self.connection.autocommit = False

        else:

            self.connection = sqlite3.connect(
                SQLITE_DATABASE
            )

            self.connection.row_factory = sqlite3.Row

    def execute(self, query, params=()):

        if self.is_postgres:

            # Convert SQLite placeholders ? to PostgreSQL %s
            query = query.replace(
                "?",
                "%s"
            )

            cursor = self.connection.cursor(
                cursor_factory=RealDictCursor
            )

            cursor.execute(
                query,
                params
            )

            return cursor

        else:

            return self.connection.execute(
                query,
                params
            )

    def commit(self):

        self.connection.commit()

    def rollback(self):

        self.connection.rollback()

    def close(self):

        self.connection.close()


def get_db_connection():

    return DatabaseConnection()


# ============================================================
# DATABASE INITIALIZATION
# ============================================================

def init_database():

    connection = get_db_connection()

    # --------------------------------------------------------
    # USERS
    # --------------------------------------------------------

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            user_id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL
        )
        """
        if connection.is_postgres
        else
        """
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL
        )
        """
    )

    # --------------------------------------------------------
    # VOLUNTEERS
    # --------------------------------------------------------

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS volunteers (
            volunteer_id SERIAL PRIMARY KEY,
            skills TEXT,
            interests TEXT,
            location TEXT,
            availability TEXT,
            experience TEXT,
            preferred_mode TEXT,
            hours_per_week INTEGER
        )
        """
        if connection.is_postgres
        else
        """
        CREATE TABLE IF NOT EXISTS volunteers (
            volunteer_id INTEGER PRIMARY KEY AUTOINCREMENT,
            skills TEXT,
            interests TEXT,
            location TEXT,
            availability TEXT,
            experience TEXT,
            preferred_mode TEXT,
            hours_per_week INTEGER
        )
        """
    )

    # --------------------------------------------------------
    # NGOS
    # --------------------------------------------------------

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS ngos (
            ngo_id SERIAL PRIMARY KEY,
            user_id INTEGER,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            cause TEXT,
            location TEXT,
            description TEXT
        )
        """
        if connection.is_postgres
        else
        """
        CREATE TABLE IF NOT EXISTS ngos (
            ngo_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            cause TEXT,
            location TEXT,
            description TEXT
        )
        """
    )

    # --------------------------------------------------------
    # VOLUNTEER PROFILES
    # --------------------------------------------------------

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS volunteer_profiles (
            profile_id SERIAL PRIMARY KEY,
            user_id INTEGER UNIQUE,
            skills TEXT,
            interests TEXT,
            location TEXT,
            availability TEXT,
            experience TEXT,
            preferred_mode TEXT,
            hours_per_week INTEGER
        )
        """
        if connection.is_postgres
        else
        """
        CREATE TABLE IF NOT EXISTS volunteer_profiles (
            profile_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE,
            skills TEXT,
            interests TEXT,
            location TEXT,
            availability TEXT,
            experience TEXT,
            preferred_mode TEXT,
            hours_per_week INTEGER
        )
        """
    )

    # --------------------------------------------------------
    # OPPORTUNITIES
    # --------------------------------------------------------

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS opportunities (
            opportunity_id SERIAL PRIMARY KEY,
            ngo_id INTEGER,
            title TEXT,
            description TEXT,
            cause TEXT,
            required_skills TEXT,
            location TEXT,
            availability TEXT,
            hours_required INTEGER,
            mode TEXT,
            experience_required TEXT
        )
        """
        if connection.is_postgres
        else
        """
        CREATE TABLE IF NOT EXISTS opportunities (
            opportunity_id INTEGER PRIMARY KEY AUTOINCREMENT,
            ngo_id INTEGER,
            title TEXT,
            description TEXT,
            cause TEXT,
            required_skills TEXT,
            location TEXT,
            availability TEXT,
            hours_required INTEGER,
            mode TEXT,
            experience_required TEXT
        )
        """
    )

    # --------------------------------------------------------
    # APPLICATIONS
    # --------------------------------------------------------

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS applications (
            application_id SERIAL PRIMARY KEY,
            user_id INTEGER,
            opportunity_id INTEGER,
            status TEXT DEFAULT 'Pending',
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
        if connection.is_postgres
        else
        """
        CREATE TABLE IF NOT EXISTS applications (
            application_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            opportunity_id INTEGER,
            status TEXT DEFAULT 'Pending',
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    # --------------------------------------------------------
    # FEEDBACK
    # --------------------------------------------------------

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS feedback (
            feedback_id SERIAL PRIMARY KEY,
            user_id INTEGER,
            opportunity_id INTEGER,
            rating INTEGER,
            comments TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
        if connection.is_postgres
        else
        """
        CREATE TABLE IF NOT EXISTS feedback (
            feedback_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            opportunity_id INTEGER,
            rating INTEGER,
            comments TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    # --------------------------------------------------------
    # NGO INVITATIONS / TWO-WAY MATCHING
    # --------------------------------------------------------

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS ngo_invitations (
            invitation_id SERIAL PRIMARY KEY,
            ngo_id INTEGER NOT NULL,
            volunteer_user_id INTEGER NOT NULL,
            opportunity_id INTEGER NOT NULL,
            message TEXT,
            status TEXT DEFAULT 'Pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
        if connection.is_postgres
        else
        """
        CREATE TABLE IF NOT EXISTS ngo_invitations (
            invitation_id INTEGER PRIMARY KEY AUTOINCREMENT,
            ngo_id INTEGER NOT NULL,
            volunteer_user_id INTEGER NOT NULL,
            opportunity_id INTEGER NOT NULL,
            message TEXT,
            status TEXT DEFAULT 'Pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    # --------------------------------------------------------
    # CONFIRMED VOLUNTEER ACTIVITY HISTORY
    # A record is created only when the responsible NGO marks
    # an accepted application as Completed.
    # --------------------------------------------------------
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS volunteer_activity_history (
            history_id SERIAL PRIMARY KEY,
            application_id INTEGER UNIQUE NOT NULL,
            volunteer_user_id INTEGER NOT NULL,
            ngo_id INTEGER NOT NULL,
            opportunity_id INTEGER NOT NULL,
            hours_completed INTEGER NOT NULL DEFAULT 0,
            completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            confirmed_by_user_id INTEGER NOT NULL
        )
        """
        if connection.is_postgres
        else
        """
        CREATE TABLE IF NOT EXISTS volunteer_activity_history (
            history_id INTEGER PRIMARY KEY AUTOINCREMENT,
            application_id INTEGER UNIQUE NOT NULL,
            volunteer_user_id INTEGER NOT NULL,
            ngo_id INTEGER NOT NULL,
            opportunity_id INTEGER NOT NULL,
            hours_completed INTEGER NOT NULL DEFAULT 0,
            completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            confirmed_by_user_id INTEGER NOT NULL
        )
        """
    )

    connection.commit()
    connection.close()

    print(
        "Database tables initialized successfully."
    )


# ============================================================
# CSV DATA LOADING
# ============================================================

def load_csv_data():

    connection = get_db_connection()

    try:

        # ----------------------------------------------------
        # LOAD VOLUNTEERS
        # ----------------------------------------------------

        if os.path.exists("volunteers_100.csv"):

            existing = connection.execute(
                "SELECT COUNT(*) AS count FROM volunteers"
            ).fetchone()

            count = (
                existing["count"]
                if existing
                else 0
            )

            if count == 0:

                df = pd.read_csv(
                    "volunteers_100.csv"
                )

                for _, row in df.iterrows():

                    connection.execute(
                        """
                        INSERT INTO volunteers
                        (
                            skills,
                            interests,
                            location,
                            availability,
                            experience,
                            preferred_mode,
                            hours_per_week
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            str(row.get("skills", "")),
                            str(row.get("interests", "")),
                            str(row.get("location", "")),
                            str(row.get("availability", "")),
                            str(row.get("experience", "")),
                            str(row.get("preferred_mode", "")),
                            int(row.get("hours_per_week", 0))
                        )
                    )

        # ----------------------------------------------------
        # LOAD NGOS
        # ----------------------------------------------------

        if os.path.exists("ngos_30.csv"):

            existing = connection.execute(
                "SELECT COUNT(*) AS count FROM ngos"
            ).fetchone()

            count = (
                existing["count"]
                if existing
                else 0
            )

            if count == 0:

                df = pd.read_csv(
                    "ngos_30.csv"
                )

                for _, row in df.iterrows():

                    connection.execute(
                        """
                        INSERT INTO ngos
                        (
                            name,
                            email,
                            cause,
                            location,
                            description
                        )
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (
                            str(row.get("ngo_name", row.get("name", ""))),
                            str(row.get("email", "")),
                            str(row.get("cause", "")),
                            str(row.get("location", "")),
                            str(row.get("description", ""))
                        )
                    )

        # ----------------------------------------------------
        # LOAD OPPORTUNITIES
        # ----------------------------------------------------

        if os.path.exists("opportunities_100.csv"):

            existing = connection.execute(
                "SELECT COUNT(*) AS count FROM opportunities"
            ).fetchone()

            count = (
                existing["count"]
                if existing
                else 0
            )

            if count == 0:

                df = pd.read_csv(
                    "opportunities_100.csv"
                )

                for _, row in df.iterrows():

                    connection.execute(
                        """
                        INSERT INTO opportunities
                        (
                            ngo_id,
                            title,
                            description,
                            cause,
                            required_skills,
                            location,
                            availability,
                            hours_required,
                            mode,
                            experience_required
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            row.get("ngo_id"),
                            str(row.get("opportunity_title", row.get("title", ""))),
                            str(row.get("description", "")),
                            str(row.get("cause", "")),
                            str(row.get("required_skills", "")),
                            str(row.get("location", "")),
                            str(row.get("availability", "")),
                            int(row.get("hours_required", 0)),
                            str(row.get("mode", "")),
                            str(row.get("experience_required", ""))
                        )
                    )

        connection.commit()

        print(
            "CSV data loaded successfully."
        )

    except Exception as error:

        connection.rollback()

        print(
            "CSV loading skipped/error:",
            error
        )

    finally:

        connection.close()


# ============================================================
# NGO HELPER
# ============================================================

def get_ngo_for_user(
    connection,
    user_id
):

    ngo = connection.execute(
        """
        SELECT *
        FROM ngos
        WHERE user_id = ?
        """,
        (user_id,)
    ).fetchone()

    if ngo:
        return ngo

    # --------------------------------------------------------
    # Try matching NGO with logged-in user's email
    # --------------------------------------------------------

    user = connection.execute(
        """
        SELECT *
        FROM users
        WHERE user_id = ?
        """,
        (user_id,)
    ).fetchone()

    if not user:
        return None

    ngo = connection.execute(
        """
        SELECT *
        FROM ngos
        WHERE LOWER(email) = LOWER(?)
        """,
        (user["email"],)
    ).fetchone()

    if ngo:

        connection.execute(
            """
            UPDATE ngos
            SET user_id = ?
            WHERE ngo_id = ?
            """,
            (
                user_id,
                ngo["ngo_id"]
            )
        )

        connection.commit()

        return connection.execute(
            """
            SELECT *
            FROM ngos
            WHERE ngo_id = ?
            """,
            (ngo["ngo_id"],)
        ).fetchone()

    return None


# ============================================================
# HOME PAGE
# ============================================================

@app.route("/")
def home():

    return render_template(
        "index.html"
    )


# ============================================================
# REGISTER
# ============================================================

@app.route(
    "/register",
    methods=["GET", "POST"]
)
def register():

    if request.method == "POST":

        name = request.form.get(
            "name",
            ""
        ).strip()

        email = request.form.get(
            "email",
            ""
        ).strip()

        password = request.form.get(
            "password",
            ""
        )

        role = request.form.get(
            "role",
            ""
        ).strip().lower()

        if not name or not email or not password:

            flash(
                "Please fill all required fields.",
                "error"
            )

            return redirect(
                url_for("register")
            )

        if role not in ["volunteer", "ngo"]:

            flash(
                "Invalid role selected.",
                "error"
            )

            return redirect(
                url_for("register")
            )

        connection = get_db_connection()

        try:

            connection.execute(
                """
                INSERT INTO users
                (
                    name,
                    email,
                    password,
                    role
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    name,
                    email,
                    password,
                    role
                )
            )

            connection.commit()

            flash(
                "Registration successful. Please login.",
                "success"
            )

            return redirect(
                url_for("login")
            )

        except Exception:

            connection.rollback()

            flash(
                "Email already exists or registration failed.",
                "error"
            )

            return redirect(
                url_for("register")
            )

        finally:

            connection.close()

    return render_template(
        "register.html"
    )


# ============================================================
# LOGIN
# ============================================================

@app.route(
    "/login",
    methods=["GET", "POST"]
)
def login():

    if request.method == "POST":

        email = request.form.get(
            "email",
            ""
        ).strip()

        password = request.form.get(
            "password",
            ""
        )

        connection = get_db_connection()

        user = connection.execute(
            """
            SELECT *
            FROM users
            WHERE LOWER(email) = LOWER(?)
            AND password = ?
            """,
            (
                email,
                password
            )
        ).fetchone()

        connection.close()

        if not user:

            flash(
                "Invalid email or password.",
                "error"
            )

            return redirect(
                url_for("login")
            )

        session["user_id"] = user["user_id"]
        session["name"] = user["name"]
        session["email"] = user["email"]
        session["role"] = user["role"]

        if user["role"] == "volunteer":

            return redirect(
                url_for("volunteer_dashboard")
            )

        return redirect(
            url_for("ngo_dashboard")
        )

    return render_template(
        "login.html"
    )


# ============================================================
# VOLUNTEER PROFILE
# ============================================================

@app.route(
    "/volunteer-profile",
    methods=["GET", "POST"]
)
def volunteer_profile():

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )

    if session.get("role") != "volunteer":

        return redirect(
            url_for("login")
        )

    connection = get_db_connection()

    if request.method == "POST":

        name = request.form.get(
            "name",
            ""
        ).strip()

        skills = request.form.get(
            "skills",
            ""
        ).strip()

        interests = request.form.get(
            "interests",
            ""
        ).strip()

        location = request.form.get(
            "location",
            ""
        ).strip()

        availability = request.form.get(
            "availability",
            ""
        ).strip()

        experience = request.form.get(
            "experience",
            ""
        ).strip()

        preferred_mode = request.form.get(
            "preferred_mode",
            ""
        ).strip()

        hours_per_week = request.form.get(
            "hours_per_week",
            "0"
        ).strip()

        try:
            hours_per_week = int(
                hours_per_week
            )
        except:
            hours_per_week = 0

        connection.execute(
            """
            UPDATE users
            SET name = ?
            WHERE user_id = ?
            """,
            (
                name,
                session["user_id"]
            )
        )

        existing = connection.execute(
            """
            SELECT *
            FROM volunteer_profiles
            WHERE user_id = ?
            """,
            (
                session["user_id"],
            )
        ).fetchone()

        if existing:

            connection.execute(
                """
                UPDATE volunteer_profiles
                SET
                    skills = ?,
                    interests = ?,
                    location = ?,
                    availability = ?,
                    experience = ?,
                    preferred_mode = ?,
                    hours_per_week = ?
                WHERE user_id = ?
                """,
                (
                    skills,
                    interests,
                    location,
                    availability,
                    experience,
                    preferred_mode,
                    hours_per_week,
                    session["user_id"]
                )
            )

        else:

            connection.execute(
                """
                INSERT INTO volunteer_profiles
                (
                    user_id,
                    skills,
                    interests,
                    location,
                    availability,
                    experience,
                    preferred_mode,
                    hours_per_week
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session["user_id"],
                    skills,
                    interests,
                    location,
                    availability,
                    experience,
                    preferred_mode,
                    hours_per_week
                )
            )

        connection.commit()

        session["name"] = name

        flash(
            "Profile saved successfully.",
            "success"
        )

        connection.close()

        return redirect(
            url_for("volunteer_dashboard")
        )

    profile = connection.execute(
        """
        SELECT *
        FROM volunteer_profiles
        WHERE user_id = ?
        """,
        (
            session["user_id"],
        )
    ).fetchone()

    user = connection.execute(
        """
        SELECT *
        FROM users
        WHERE user_id = ?
        """,
        (
            session["user_id"],
        )
    ).fetchone()

    connection.close()

    return render_template(
        "volunteer_profile.html",
        profile=profile,
        user=user
    )


# ============================================================
# VOLUNTEER DASHBOARD
# ============================================================

@app.route("/volunteer-dashboard")
def volunteer_dashboard():

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )

    if session.get("role") != "volunteer":

        return redirect(
            url_for("login")
        )

    connection = get_db_connection()

    profile = connection.execute(
        """
        SELECT *
        FROM volunteer_profiles
        WHERE user_id = ?
        """,
        (
            session["user_id"],
        )
    ).fetchone()

    opportunities = connection.execute(
        """
        SELECT *
        FROM opportunities
        ORDER BY opportunity_id DESC
        """
    ).fetchall()

    applications = connection.execute(
        """
        SELECT
            applications.*,
            opportunities.title AS opportunity_title,
            opportunities.cause,
            opportunities.location,
            opportunities.mode
        FROM applications

        INNER JOIN opportunities
            ON applications.opportunity_id =
               opportunities.opportunity_id

        WHERE applications.user_id = ?

        ORDER BY applications.application_id DESC
        """,
        (
            session["user_id"],
        )
    ).fetchall()

    applied_ids = set(
        application["opportunity_id"]
        for application in applications
    )

    # --------------------------------------------------------
    # HYBRID RECOMMENDATIONS
    # --------------------------------------------------------

    recommendations = []

    # Do not recommend opportunities for which this volunteer
    # has already submitted an application.
    available_opportunities = [
        opportunity
        for opportunity in opportunities
        if str(opportunity["opportunity_id"]) not in {
            str(applied_id) for applied_id in applied_ids
        }
    ]

    if profile:

        volunteer_data = {
            "skills": profile["skills"] or "",
            "interests": profile["interests"] or "",
            "location": profile["location"] or "",
            "availability": profile["availability"] or "",
            "experience": profile["experience"] or "",
            "preferred_mode": profile["preferred_mode"] or ""
        }

        try:

            # matching.py returns flat opportunity dictionaries
            # with the original database fields plus a match score.
            recommendations = rank_opportunities(
                volunteer_data,
                available_opportunities,
                top_n=5
            )

        except Exception as error:

            print(
                "Recommendation error:",
                error
            )

            recommendations = []

    # TEMPORARY DEBUGGING: inspect recommendation scores in the terminal.
    print("\n========== SEVACONNECT RECOMMENDATION DEBUG ==========")
    print("Volunteer profile found:", bool(profile))
    print("Unapplied opportunities:", len(available_opportunities))
    print("Recommendations before fallback:", len(recommendations))
    for item in recommendations:
        print(
            "Opportunity ID:", item.get("opportunity_id"),
            "| Title:", item.get("title"),
            "| Score:", item.get("score"),
            "| Match score:", item.get("match_score"),
            "| Keys:", list(item.keys())
        )
    print("======================================================\n")

    # If the profile is incomplete or the recommendation engine
    # cannot produce results, show the latest unapplied opportunities.
    if not recommendations:

        recommendations = list(
            available_opportunities
        )[:5]

    recommendations = recommendations[:5]

    print("Final dashboard recommendation scores:", [
        item.get("score") for item in recommendations
    ])

    connection.close()

    return render_template(
        "volunteer_dashboard.html",
        profile=profile,
        opportunities=opportunities,
        recommendations=recommendations,
        applications=applications,
        applied_ids=applied_ids
    )


# ============================================================
# APPLY FOR OPPORTUNITY
# ============================================================

@app.route(
    "/apply/<int:opportunity_id>",
    methods=["POST"]
)
def apply_opportunity(
    opportunity_id
):

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )

    if session.get("role") != "volunteer":

        return redirect(
            url_for("login")
        )

    connection = get_db_connection()

    opportunity = connection.execute(
        """
        SELECT *
        FROM opportunities
        WHERE opportunity_id = ?
        """,
        (
            opportunity_id,
        )
    ).fetchone()

    if not opportunity:

        connection.close()

        flash(
            "Opportunity not found.",
            "error"
        )

        return redirect(
            url_for("volunteer_dashboard")
        )

    existing = connection.execute(
        """
        SELECT *
        FROM applications
        WHERE user_id = ?
        AND opportunity_id = ?
        """,
        (
            session["user_id"],
            opportunity_id
        )
    ).fetchone()

    if existing:

        connection.close()

        flash(
            "You have already applied for this opportunity.",
            "info"
        )

        return redirect(
            url_for("volunteer_dashboard")
        )

    connection.execute(
        """
        INSERT INTO applications
        (
            user_id,
            opportunity_id,
            status
        )
        VALUES (?, ?, 'Pending')
        """,
        (
            session["user_id"],
            opportunity_id
        )
    )

    connection.commit()
    connection.close()

    flash(
        "Application submitted successfully.",
        "success"
    )

    return redirect(
        url_for("volunteer_dashboard")
    )


# ============================================================
# NGO PROFILE
# ============================================================

@app.route(
    "/ngo-profile",
    methods=["GET", "POST"]
)
def ngo_profile():

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )

    if session.get("role") != "ngo":

        return redirect(
            url_for("login")
        )

    connection = get_db_connection()

    if request.method == "POST":

        name = request.form.get(
            "name",
            ""
        ).strip()

        email = request.form.get(
            "email",
            ""
        ).strip()

        cause = request.form.get(
            "cause",
            ""
        ).strip()

        location = request.form.get(
            "location",
            ""
        ).strip()

        description = request.form.get(
            "description",
            ""
        ).strip()

        existing = get_ngo_for_user(
            connection,
            session["user_id"]
        )

        try:

            if existing:

                connection.execute(
                    """
                    UPDATE ngos
                    SET
                        name = ?,
                        email = ?,
                        cause = ?,
                        location = ?,
                        description = ?
                    WHERE ngo_id = ?
                    """,
                    (
                        name,
                        email,
                        cause,
                        location,
                        description,
                        existing["ngo_id"]
                    )
                )

            else:

                connection.execute(
                    """
                    INSERT INTO ngos
                    (
                        user_id,
                        name,
                        email,
                        cause,
                        location,
                        description
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        session["user_id"],
                        name,
                        email,
                        cause,
                        location,
                        description
                    )
                )

            connection.execute(
                """
                UPDATE users
                SET
                    name = ?,
                    email = ?
                WHERE user_id = ?
                """,
                (
                    name,
                    email,
                    session["user_id"]
                )
            )

            connection.commit()

            session["name"] = name
            session["email"] = email

            flash(
                "NGO profile saved successfully.",
                "success"
            )

            connection.close()

            return redirect(
                url_for("ngo_dashboard")
            )

        except Exception as error:

            connection.rollback()

            print(
                "NGO profile error:",
                error
            )

            flash(
                "Could not save NGO profile. Check the email.",
                "error"
            )

    ngo = get_ngo_for_user(
        connection,
        session["user_id"]
    )

    connection.close()

    return render_template(
        "ngo_profile.html",
        ngo=ngo
    )


# ============================================================
# CREATE OPPORTUNITY
# ============================================================

@app.route(
    "/create-opportunity",
    methods=["GET", "POST"]
)
def create_opportunity():

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )

    if session.get("role") != "ngo":

        return redirect(
            url_for("login")
        )

    connection = get_db_connection()

    ngo = get_ngo_for_user(
        connection,
        session["user_id"]
    )

    if ngo is None:

        connection.close()

        flash(
            "Please complete your NGO profile first.",
            "error"
        )

        return redirect(
            url_for("ngo_profile")
        )

    if request.method == "POST":

        title = request.form.get(
            "title",
            ""
        ).strip()

        description = request.form.get(
            "description",
            ""
        ).strip()

        cause = request.form.get(
            "cause",
            ""
        ).strip()

        required_skills = request.form.get(
            "required_skills",
            ""
        ).strip()

        location = request.form.get(
            "location",
            ""
        ).strip()

        availability = request.form.get(
            "availability",
            ""
        ).strip()

        hours_required = request.form.get(
            "hours_required",
            "0"
        ).strip()

        mode = request.form.get(
            "mode",
            ""
        ).strip()

        experience_required = request.form.get(
            "experience_required",
            ""
        ).strip()

        try:

            hours_required = int(
                hours_required
            )

        except:

            hours_required = 0

        connection.execute(
            """
            INSERT INTO opportunities
            (
                ngo_id,
                title,
                description,
                cause,
                required_skills,
                location,
                availability,
                hours_required,
                mode,
                experience_required
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                ngo["ngo_id"],
                title,
                description,
                cause,
                required_skills,
                location,
                availability,
                hours_required,
                mode,
                experience_required
            )
        )

        connection.commit()
        connection.close()

        flash(
            "Opportunity created successfully.",
            "success"
        )

        return redirect(
            url_for("ngo_dashboard")
        )

    connection.close()

    return render_template(
        "create_opportunity.html"
    )


# ============================================================
# DELETE OPPORTUNITY
# ============================================================

@app.route(
    "/delete-opportunity/<int:opportunity_id>",
    methods=["POST"]
)
def delete_opportunity(
    opportunity_id
):

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )

    if session.get("role") != "ngo":

        return redirect(
            url_for("login")
        )

    connection = get_db_connection()

    ngo = get_ngo_for_user(
        connection,
        session["user_id"]
    )

    if ngo is None:

        connection.close()

        return redirect(
            url_for("ngo_dashboard")
        )

    opportunity = connection.execute(
        """
        SELECT *
        FROM opportunities
        WHERE opportunity_id = ?
        AND ngo_id = ?
        """,
        (
            opportunity_id,
            ngo["ngo_id"]
        )
    ).fetchone()

    if opportunity:

        connection.execute(
            """
            DELETE FROM applications
            WHERE opportunity_id = ?
            """,
            (
                opportunity_id,
            )
        )

        connection.execute(
            """
            DELETE FROM feedback
            WHERE opportunity_id = ?
            """,
            (
                opportunity_id,
            )
        )

        connection.execute(
            """
            DELETE FROM opportunities
            WHERE opportunity_id = ?
            """,
            (
                opportunity_id,
            )
        )

        connection.commit()

    connection.close()

    flash(
        "Opportunity deleted.",
        "success"
    )

    return redirect(
        url_for("ngo_dashboard")
    )


# ============================================================
# NGO: FIND AND APPROACH VOLUNTEERS
# ============================================================

@app.route("/ngo/find-volunteers")
def find_volunteers():

    if "user_id" not in session or session.get("role") != "ngo":
        return redirect(url_for("login"))

    connection = get_db_connection()
    ngo = get_ngo_for_user(connection, session["user_id"])

    if ngo is None:
        connection.close()
        return redirect(url_for("ngo_profile"))

    volunteers = connection.execute(
        """
        SELECT
            users.user_id,
            users.name,
            users.email,
            volunteer_profiles.skills,
            volunteer_profiles.interests,
            volunteer_profiles.location,
            volunteer_profiles.availability,
            volunteer_profiles.experience,
            volunteer_profiles.preferred_mode,
            volunteer_profiles.hours_per_week
        FROM users
        INNER JOIN volunteer_profiles
            ON users.user_id = volunteer_profiles.user_id
        WHERE users.role = 'volunteer'
        ORDER BY users.name ASC
        """
    ).fetchall()

    opportunities = connection.execute(
        """
        SELECT *
        FROM opportunities
        WHERE ngo_id = ?
        ORDER BY opportunity_id DESC
        """,
        (ngo["ngo_id"],)
    ).fetchall()

    connection.close()

    return render_template(
        "find_volunteers.html",
        ngo=ngo,
        volunteers=volunteers,
        opportunities=opportunities
    )


@app.route("/ngo/approach-volunteer/<int:volunteer_user_id>", methods=["POST"])
def approach_volunteer(volunteer_user_id):

    if "user_id" not in session or session.get("role") != "ngo":
        return redirect(url_for("login"))

    connection = get_db_connection()
    ngo = get_ngo_for_user(connection, session["user_id"])

    if ngo is None:
        connection.close()
        return redirect(url_for("ngo_profile"))

    opportunity_id = request.form.get("opportunity_id", "").strip()
    message = request.form.get("message", "").strip()

    try:
        opportunity_id = int(opportunity_id)
    except (TypeError, ValueError):
        connection.close()
        flash("Please select an opportunity.", "error")
        return redirect(url_for("find_volunteers"))

    volunteer = connection.execute(
        """
        SELECT user_id
        FROM users
        WHERE user_id = ? AND role = 'volunteer'
        """,
        (volunteer_user_id,)
    ).fetchone()

    opportunity = connection.execute(
        """
        SELECT opportunity_id
        FROM opportunities
        WHERE opportunity_id = ? AND ngo_id = ?
        """,
        (opportunity_id, ngo["ngo_id"])
    ).fetchone()

    if not volunteer or not opportunity:
        connection.close()
        flash("Invalid volunteer or opportunity.", "error")
        return redirect(url_for("find_volunteers"))

    existing = connection.execute(
        """
        SELECT invitation_id, status
        FROM ngo_invitations
        WHERE ngo_id = ?
          AND volunteer_user_id = ?
          AND opportunity_id = ?
        """,
        (ngo["ngo_id"], volunteer_user_id, opportunity_id)
    ).fetchone()

    if existing:
        connection.close()
        flash("You have already approached this volunteer for this opportunity.", "info")
        return redirect(url_for("find_volunteers"))

    connection.execute(
        """
        INSERT INTO ngo_invitations
        (ngo_id, volunteer_user_id, opportunity_id, message, status)
        VALUES (?, ?, ?, ?, 'Pending')
        """,
        (ngo["ngo_id"], volunteer_user_id, opportunity_id, message)
    )

    connection.commit()
    connection.close()

    flash("Volunteer approached successfully.", "success")
    return redirect(url_for("find_volunteers"))


# ============================================================
# VOLUNTEER: VIEW AND RESPOND TO NGO INVITATIONS
# ============================================================

@app.route("/volunteer/invitations")
def volunteer_invitations():

    if "user_id" not in session or session.get("role") != "volunteer":
        return redirect(url_for("login"))

    connection = get_db_connection()

    invitations = connection.execute(
        """
        SELECT
            ngo_invitations.invitation_id,
            ngo_invitations.message,
            ngo_invitations.status,
            ngo_invitations.created_at,
            ngos.ngo_id,
            ngos.name AS ngo_name,
            ngos.cause AS ngo_cause,
            ngos.location AS ngo_location,
            opportunities.opportunity_id,
            opportunities.title AS opportunity_title,
            opportunities.hours_required,
            opportunities.cause,
            opportunities.required_skills,
            opportunities.location,
            opportunities.availability,
            opportunities.hours_required,
            opportunities.mode,
            opportunities.experience_required
        FROM ngo_invitations
        INNER JOIN ngos
            ON ngo_invitations.ngo_id = ngos.ngo_id
        INNER JOIN opportunities
            ON ngo_invitations.opportunity_id = opportunities.opportunity_id
        WHERE ngo_invitations.volunteer_user_id = ?
        ORDER BY ngo_invitations.created_at DESC
        """,
        (session["user_id"],)
    ).fetchall()

    connection.close()

    return render_template(
        "volunteer_invitations.html",
        invitations=invitations
    )


@app.route("/volunteer/invitation/<int:invitation_id>/<string:new_status>", methods=["POST"])
def update_invitation_status(invitation_id, new_status):

    if "user_id" not in session or session.get("role") != "volunteer":
        return redirect(url_for("login"))

    if new_status not in ["Accepted", "Rejected"]:
        return redirect(url_for("volunteer_invitations"))

    connection = get_db_connection()

    invitation = connection.execute(
        """
        SELECT invitation_id, opportunity_id, status
        FROM ngo_invitations
        WHERE invitation_id = ?
          AND volunteer_user_id = ?
        """,
        (invitation_id, session["user_id"])
    ).fetchone()

    if invitation is None:
        connection.close()
        return redirect(url_for("volunteer_invitations"))

    connection.execute(
        """
        UPDATE ngo_invitations
        SET status = ?
        WHERE invitation_id = ?
          AND volunteer_user_id = ?
        """,
        (new_status, invitation_id, session["user_id"])
    )

    if new_status == "Accepted":
        existing_application = connection.execute(
            """
            SELECT application_id
            FROM applications
            WHERE user_id = ? AND opportunity_id = ?
            """,
            (session["user_id"], invitation["opportunity_id"])
        ).fetchone()

        if existing_application:
            connection.execute(
                """
                UPDATE applications
                SET status = 'Accepted'
                WHERE application_id = ?
                """,
                (existing_application["application_id"],)
            )
        else:
            connection.execute(
                """
                INSERT INTO applications
                (user_id, opportunity_id, status)
                VALUES (?, ?, 'Accepted')
                """,
                (session["user_id"], invitation["opportunity_id"])
            )

    connection.commit()
    connection.close()

    flash(
        "Invitation accepted." if new_status == "Accepted" else "Invitation rejected.",
        "success"
    )

    return redirect(url_for("volunteer_invitations"))


# ============================================================
# NGO DASHBOARD
# ============================================================

@app.route("/ngo-dashboard")
def ngo_dashboard():

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )

    if session.get("role") != "ngo":

        return redirect(
            url_for("login")
        )

    connection = get_db_connection()

    # --------------------------------------------------------
    # GET NGO PROFILE
    # --------------------------------------------------------

    ngo = get_ngo_for_user(
        connection,
        session["user_id"]
    )

    if ngo is None:

        connection.close()

        return redirect(
            url_for("ngo_profile")
        )

    # --------------------------------------------------------
    # GET OPPORTUNITIES CREATED BY THIS NGO
    # --------------------------------------------------------

    opportunities = connection.execute(
        """
        SELECT *
        FROM opportunities
        WHERE ngo_id = ?
        ORDER BY opportunity_id DESC
        """,
        (
            ngo["ngo_id"],
        )
    ).fetchall()

    # --------------------------------------------------------
    # GET ALL VOLUNTEERS WHO APPLIED
    # TO THIS NGO'S OPPORTUNITIES
    # --------------------------------------------------------

    applicants = connection.execute(
        """
        SELECT

            applications.application_id,
            applications.status,
            applications.applied_at,

            users.user_id,
            users.name AS volunteer_name,
            users.email AS volunteer_email,

            volunteer_profiles.skills,
            volunteer_profiles.interests,
            volunteer_profiles.location,
            volunteer_profiles.availability,
            volunteer_profiles.experience,
            volunteer_profiles.preferred_mode,
            volunteer_profiles.hours_per_week,

            opportunities.opportunity_id,
            opportunities.title AS opportunity_title

        FROM applications

        INNER JOIN users
            ON applications.user_id =
               users.user_id

        LEFT JOIN volunteer_profiles
            ON applications.user_id =
               volunteer_profiles.user_id

        INNER JOIN opportunities
            ON applications.opportunity_id =
               opportunities.opportunity_id

        WHERE opportunities.ngo_id = ?

        ORDER BY applications.applied_at DESC
        """,
        (
            ngo["ngo_id"],
        )
    ).fetchall()

    # --------------------------------------------------------
    # APPLICATION COUNTS
    # --------------------------------------------------------

    total_applications = len(
        applicants
    )

    pending_applications = sum(
        1
        for applicant in applicants
        if applicant["status"] == "Pending"
    )

    accepted_applications = sum(
        1
        for applicant in applicants
        if applicant["status"] == "Accepted"
    )

    completed_applications = sum(
        1
        for applicant in applicants
        if applicant["status"] == "Completed"
    )

    connection.close()

    return render_template(
        "ngo_dashboard.html",

        ngo=ngo,

        opportunities=opportunities,

        applicants=applicants,

        total_applications=total_applications,

        pending_applications=pending_applications,

        accepted_applications=accepted_applications,

        completed_applications=completed_applications
    )


# ============================================================
# UPDATE APPLICATION STATUS
# ============================================================

@app.route(
    "/ngo/application/<int:application_id>/<string:new_status>",
    methods=["POST"]
)
def update_application_status(
    application_id,
    new_status
):

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )

    if session.get("role") != "ngo":

        return redirect(
            url_for("login")
        )

    allowed_statuses = [
        "Pending",
        "Accepted",
        "Rejected",
        "Completed"
    ]

    if new_status not in allowed_statuses:

        return redirect(
            url_for("ngo_dashboard")
        )

    connection = get_db_connection()

    # --------------------------------------------------------
    # GET NGO
    # --------------------------------------------------------

    ngo = get_ngo_for_user(
        connection,
        session["user_id"]
    )

    if ngo is None:

        connection.close()

        return redirect(
            url_for("ngo_dashboard")
        )

    # --------------------------------------------------------
    # VERIFY APPLICATION BELONGS TO THIS NGO
    # --------------------------------------------------------

    application = connection.execute(
        """
        SELECT
            applications.application_id,
            applications.user_id,
            applications.opportunity_id,
            applications.status AS current_status,
            opportunities.hours_required,
            opportunities.ngo_id
        FROM applications

        INNER JOIN opportunities
            ON applications.opportunity_id =
               opportunities.opportunity_id

        WHERE applications.application_id = ?

        AND opportunities.ngo_id = ?
        """,
        (
            application_id,
            ngo["ngo_id"]
        )
    ).fetchone()

    if application is None:

        connection.close()

        return redirect(
            url_for("ngo_dashboard")
        )

    # --------------------------------------------------------
    # COMPLETION CAN ONLY BE CONFIRMED BY THE RESPONSIBLE NGO.
    # Only accepted applications can be marked Completed.
    # --------------------------------------------------------
    if new_status == "Completed":
        if application["current_status"] != "Accepted":
            connection.close()
            flash("Only accepted applications can be marked completed.", "error")
            return redirect(url_for("ngo_dashboard"))

        try:
            submitted_hours = int(request.form.get("hours_completed", "") or application["hours_required"] or 0)
        except (TypeError, ValueError):
            submitted_hours = int(application["hours_required"] or 0)

        if submitted_hours < 0 or submitted_hours > 10000:
            connection.close()
            flash("Enter a valid number of completed hours.", "error")
            return redirect(url_for("ngo_dashboard"))

        connection.execute(
            """
            UPDATE applications
            SET status = ?
            WHERE application_id = ?
            """,
            (new_status, application_id)
        )

        existing_history = connection.execute(
            "SELECT history_id FROM volunteer_activity_history WHERE application_id = ?",
            (application_id,)
        ).fetchone()

        if not existing_history:
            connection.execute(
                """
                INSERT INTO volunteer_activity_history
                    (application_id, volunteer_user_id, ngo_id, opportunity_id,
                     hours_completed, confirmed_by_user_id)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (application_id, application["user_id"], ngo["ngo_id"],
                 application["opportunity_id"], submitted_hours, session["user_id"])
            )
        else:
            connection.execute(
                """
                UPDATE volunteer_activity_history
                SET hours_completed = ?, confirmed_by_user_id = ?
                WHERE application_id = ?
                """,
                (submitted_hours, session["user_id"], application_id)
            )
    else:
        connection.execute(
            """
            UPDATE applications
            SET status = ?
            WHERE application_id = ?
            """,
            (new_status, application_id)
        )

    connection.commit()
    connection.close()

    if new_status == "Completed":
        flash("Activity completion confirmed and saved to history.", "success")

    return redirect(
        url_for("ngo_dashboard")
    )


# ============================================================
# VOLUNTEER ACTIVITY HISTORY (volunteer sees only own records)
# ============================================================
@app.route("/volunteer-history")
def volunteer_history():
    if "user_id" not in session or session.get("role") != "volunteer":
        return redirect(url_for("login"))

    connection = get_db_connection()
    history = connection.execute(
        """
        SELECT h.history_id, h.hours_completed, h.completed_at,
               o.title AS opportunity_title, o.location, o.mode,
               n.name AS ngo_name, n.location AS ngo_location
        FROM volunteer_activity_history h
        JOIN opportunities o ON o.opportunity_id = h.opportunity_id
        JOIN ngos n ON n.ngo_id = h.ngo_id
        WHERE h.volunteer_user_id = ?
        ORDER BY h.completed_at DESC
        """,
        (session["user_id"],)
    ).fetchall()
    connection.close()
    return render_template("volunteer_history.html", history=history)


# ============================================================
# NGO VIEW OF A VOLUNTEER'S HISTORY WITH THIS NGO ONLY
# ============================================================
@app.route("/ngo/volunteer-history/<int:volunteer_user_id>")
def ngo_volunteer_history(volunteer_user_id):
    if "user_id" not in session or session.get("role") != "ngo":
        return redirect(url_for("login"))

    connection = get_db_connection()
    ngo = get_ngo_for_user(connection, session["user_id"])
    if not ngo:
        connection.close()
        return redirect(url_for("ngo_profile"))

    volunteer = connection.execute(
        "SELECT user_id, name, email FROM users WHERE user_id = ? AND role = 'volunteer'",
        (volunteer_user_id,)
    ).fetchone()
    if not volunteer:
        connection.close()
        flash("Volunteer not found.", "error")
        return redirect(url_for("ngo_dashboard"))

    history = connection.execute(
        """
        SELECT h.history_id, h.hours_completed, h.completed_at,
               o.title AS opportunity_title, o.location, o.mode
        FROM volunteer_activity_history h
        JOIN opportunities o ON o.opportunity_id = h.opportunity_id
        WHERE h.volunteer_user_id = ? AND h.ngo_id = ?
        ORDER BY h.completed_at DESC
        """,
        (volunteer_user_id, ngo["ngo_id"])
    ).fetchall()
    connection.close()
    return render_template("ngo_volunteer_history.html", volunteer=volunteer, history=history, ngo=ngo)


# ============================================================
# LOGOUT
# ============================================================

@app.route("/logout")
def logout():

    session.clear()

    return redirect(
        url_for("home")
    )


# ============================================================
# APPLICATION STARTUP
# ============================================================

def initialize_application():

    print()
    print("SevaConnect starting...")
    print("----------------------------------------")

    if DATABASE_URL:

        print(
            "Database mode: PostgreSQL"
        )

    else:

        print(
            "Database mode: SQLite (local development)"
        )

    init_database()

    load_csv_data()

    print("----------------------------------------")
    print(
        "SevaConnect is ready."
    )


# ============================================================
# RUN APPLICATION
# ============================================================

# Initialize database for both local Python execution and Gunicorn/Render.
try:
    initialize_application()
except Exception as startup_error:
    print("Startup database initialization error:", startup_error)

if __name__ == "__main__":

    app.run(
        debug=True,
        use_reloader=False
    )