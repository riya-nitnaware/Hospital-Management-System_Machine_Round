
from functools import wraps

from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from sqlalchemy import func

from models import db, User, Doctor, Patient, Department, Appointment

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


def admin_required(view):
    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if not current_user.is_active:
            abort(403)
        if current_user.role != "admin":
            abort(403)
        return view(*args, **kwargs)
    return wrapped


@admin_bp.route("/dashboard")
@admin_required
def dashboard():
    stats = {
        "doctors": Doctor.query.join(User).filter(User.is_active.is_(True)).count(),
        "patients": Patient.query.join(User).filter(User.is_active.is_(True)).count(),
        "appointments": Appointment.query.count(),
        "pending": Appointment.query.filter_by(status="Pending").count(),
        "completed": Appointment.query.filter_by(status="Completed").count()
    }

    doctors = Doctor.query.join(User).order_by(User.name).all()
    patients = Patient.query.join(User).order_by(User.name).all()
    appointments = Appointment.query.order_by(
        Appointment.start_time.desc()
    ).all()
    departments = Department.query.order_by(Department.name).all()

    return render_template(
        "admin_dashboard.html",
        stats=stats,
        doctors=doctors,
        patients=patients,
        appointments=appointments,
        departments=departments
    )


@admin_bp.route("/doctors/add", methods=["POST"])
@admin_required
def add_doctor():
    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")
    specialization = request.form.get("specialization", "").strip()
    department_id = request.form.get("department_id", type=int)
    qualification = request.form.get("qualification", "").strip()

    try:
        fee = float(request.form.get("consultation_fee", "500"))
        experience = int(request.form.get("experience", "0"))
    except ValueError:
        flash("Enter valid fee and experience values.", "danger")
        return redirect(url_for("admin.dashboard"))

    department = db.session.get(Department, department_id)

    if (
        not name or len(name) > 100 or "@" not in email
        or len(password) < 8 or not specialization
        or not department or fee < 0 or fee > 100000
        or experience < 0 or experience > 80
    ):
        flash("Please check all doctor details.", "danger")
        return redirect(url_for("admin.dashboard"))

    if User.query.filter(func.lower(User.email) == email).first():
        flash("Email is already registered.", "danger")
        return redirect(url_for("admin.dashboard"))

    user = User(name=name, email=email, role="doctor")
    user.set_password(password)

    db.session.add(user)
    db.session.flush()

    doctor = Doctor(
        user_id=user.id,
        department_id=department.id,
        specialization=specialization,
        qualification=qualification,
        experience=experience,
        consultation_fee=fee
    )

    db.session.add(doctor)
    db.session.commit()

    flash("Doctor profile created successfully.", "success")
    return redirect(url_for("admin.dashboard"))


@admin_bp.route("/doctors/<int:doctor_id>/edit", methods=["POST"])
@admin_required
def edit_doctor(doctor_id):
    doctor = db.get_or_404(Doctor, doctor_id)

    specialization = request.form.get("specialization", "").strip()
    department_id = request.form.get("department_id", type=int)
    department = db.session.get(Department, department_id)

    try:
        fee = float(request.form.get("consultation_fee", "500"))
        experience = int(request.form.get("experience", "0"))
    except ValueError:
        flash("Invalid fee or experience.", "danger")
        return redirect(url_for("admin.dashboard"))

    if not specialization or not department or fee < 0 or experience < 0:
        flash("Enter valid doctor details.", "danger")
        return redirect(url_for("admin.dashboard"))

    doctor.specialization = specialization
    doctor.department_id = department.id
    doctor.consultation_fee = fee
    doctor.experience = experience
    doctor.qualification = request.form.get("qualification", "").strip()

    db.session.commit()
    flash("Doctor profile updated.", "success")
    return redirect(url_for("admin.dashboard"))


@admin_bp.route("/doctors/<int:doctor_id>/toggle", methods=["POST"])
@admin_required
def toggle_doctor(doctor_id):
    doctor = db.get_or_404(Doctor, doctor_id)
    doctor.user.is_active = not doctor.user.is_active
    db.session.commit()

    flash("Doctor account status updated.", "success")
    return redirect(url_for("admin.dashboard"))


@admin_bp.route("/departments/add", methods=["POST"])
@admin_required
def add_department():
    name = request.form.get("name", "").strip()
    description = request.form.get("description", "").strip()

    if not name or len(name) > 100:
        flash("Enter a valid department name.", "danger")
    elif Department.query.filter(
        func.lower(Department.name) == name.lower()
    ).first():
        flash("Department already exists.", "danger")
    else:
        db.session.add(Department(name=name, description=description[:300]))
        db.session.commit()
        flash("Department added.", "success")

    return redirect(url_for("admin.dashboard"))


@admin_bp.route("/appointments/<int:appointment_id>/status", methods=["POST"])
@admin_required
def update_appointment(appointment_id):
    appointment = db.get_or_404(Appointment, appointment_id)
    status = request.form.get("status", "")

    if status not in {"Pending", "Confirmed", "Completed", "Cancelled"}:
        abort(400)

    if appointment.status in {"Completed", "Cancelled"}:
        flash("Closed appointments cannot be changed.", "danger")
    elif status == "Completed":
        flash("Only the assigned doctor can complete an appointment.", "danger")
    else:
        appointment.status = status
        db.session.commit()
        flash("Appointment status updated.", "success")

    return redirect(url_for("admin.dashboard"))
