
import os

import click
from flask import Flask, render_template
from flask_login import LoginManager, current_user
from flask_wtf.csrf import CSRFProtect

from config import Config
from models import db, User, Doctor

from routes.auth_routes import auth_bp
from routes.admin_routes import admin_bp
from routes.doctor_routes import doctor_bp
from routes.patient_routes import patient_bp
from routes.appointment_routes import appointment_bp


# =========================
# EXTENSIONS
# =========================
login_manager = LoginManager()
csrf = CSRFProtect()


# =========================
# APPLICATION FACTORY
# =========================
def create_app():
    app = Flask(__name__)

    # Load application configuration
    app.config.from_object(Config)

    # Ensure the instance directory exists
    os.makedirs(app.instance_path, exist_ok=True)

    # Initialize extensions
    db.init_app(app)

    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Please log in to access this page."
    login_manager.login_message_category = "warning"

    csrf.init_app(app)

    # Register application blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(doctor_bp)
    app.register_blueprint(patient_bp)
    app.register_blueprint(appointment_bp)

    # =========================
    # HOMEPAGE
    # =========================
    @app.route("/")
    def index():
        doctors = (
            Doctor.query
            .filter_by(is_active=True)
            .all()
        )

        return render_template(
            "index.html",
            doctors=doctors
        )

    # =========================
    # ERROR HANDLERS
    # =========================
    @app.errorhandler(403)
    def forbidden(error):
        return render_template(
            "error.html",
            code=403,
            message="You do not have permission to access this page."
        ), 403

    @app.errorhandler(404)
    def not_found(error):
        return render_template(
            "error.html",
            code=404,
            message="The page you are looking for was not found."
        ), 404

    @app.errorhandler(500)
    def internal_server_error(error):
        db.session.rollback()

        return render_template(
            "error.html",
            code=500,
            message="An unexpected server error occurred. Please try again."
        ), 500

    # =========================
    # DATABASE INITIALIZATION
    # =========================
    @app.cli.command("init-db")
    def init_db():
        """Create all database tables."""
        db.create_all()
        click.echo("Database tables created successfully.")

    # =========================
    # CREATE ADMIN ACCOUNT
    # =========================
    @app.cli.command("create-admin")
    def create_admin():
        """Create an administrator account."""
        name = click.prompt("Admin name").strip()
        email = click.prompt("Admin email").strip().lower()
        password = click.prompt(
            "Admin password",
            hide_input=True,
            confirmation_prompt=True
        )

        if not name or not email or not password:
            raise click.ClickException(
                "Name, email, and password are required."
            )

        existing_user = User.query.filter_by(email=email).first()

        if existing_user:
            raise click.ClickException(
                "An account with this email already exists."
            )

        admin = User(
            name=name,
            email=email,
            role="admin",
            is_active=True
        )
        admin.set_password(password)

        db.session.add(admin)
        db.session.commit()

        click.echo("Admin account created successfully.")

    return app


# =========================
# FLASK-LOGIN USER LOADER
# =========================
@login_manager.user_loader
def load_user(user_id):
    try:
        return db.session.get(User, int(user_id))
    except (TypeError, ValueError):
        return None


# =========================
# RUN APPLICATION
# =========================
app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
