
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from sqlalchemy import func

from models import db, User, Patient

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("auth.dashboard"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not name or len(name) > 100 or "@" not in email:
            flash("Enter a valid name and email.", "danger")
        elif len(password) < 8:
            flash("Password must contain at least 8 characters.", "danger")
        elif User.query.filter(
            func.lower(User.email) == email
        ).first():
            flash("This email is already registered.", "danger")
        else:
            user = User(name=name, email=email, role="patient")
            user.set_password(password)

            db.session.add(user)
            db.session.flush()

            db.session.add(Patient(user_id=user.id))
            db.session.commit()

            flash("Account created. Please log in.", "success")
            return redirect(url_for("auth.login"))

    return render_template("register.html")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("auth.dashboard"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        user = User.query.filter(
            func.lower(User.email) == email
        ).first()

        if user and user.is_active and user.check_password(password):
            login_user(user)
            return redirect(url_for("auth.dashboard"))

        flash("Invalid email or password.", "danger")

    return render_template("login.html")


@auth_bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    flash("You have logged out.", "success")
    return redirect(url_for("auth.login"))


@auth_bp.route("/dashboard")
@login_required
def dashboard():
    if not current_user.is_active:
        logout_user()
        flash("Your account is inactive.", "danger")
        return redirect(url_for("auth.login"))

    if current_user.role == "admin":
        return redirect(url_for("admin.dashboard"))

    if current_user.role == "doctor":
        return redirect(url_for("doctor.dashboard"))

    return redirect(url_for("patient.dashboard"))
