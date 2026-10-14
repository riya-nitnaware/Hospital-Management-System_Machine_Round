
from functools import wraps

from flask import Blueprint, render_template, request, abort
from flask_login import login_required, current_user
from sqlalchemy import or_

from models import db, User, Doctor, Department, Patient, Appointment, ConsultationNote

patient_bp = Blueprint("patient", __name__, url_prefix="/patient")


def patient_required(view):
    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if not current_user.is_active or current_user.role != "patient":
            abort(403)
        return view(*args, **kwargs)
    return wrapped


@patient_bp.route("/dashboard")
@patient_required
def dashboard():
    patient = Patient.query.filter_by(user_id=current_user.id).first_or_404()

    appointments = Appointment.query.filter_by(
        patient_id=patient.id
    ).order_by(Appointment.start_time.desc()).all()

    return render_template(
        "patient_dashboard.html",
        patient=patient,
        appointments=appointments
    )


@patient_bp.route("/doctors")
@patient_required
def doctors():
    query = request.args.get("q", "").strip()
    department_id = request.args.get("department", type=int)

    doctors_query = Doctor.query.join(User).filter(
        User.is_active.is_(True)
    )

    if query:
        doctors_query = doctors_query.filter(
            or_(
                User.name.ilike(f"%{query}%"),
                Doctor.specialization.ilike(f"%{query}%")
            )
        )

    if department_id:
        doctors_query = doctors_query.filter(
            Doctor.department_id == department_id
        )

    return render_template(
        "doctors.html",
        doctors=doctors_query.order_by(User.name).all(),
        departments=Department.query.order_by(Department.name).all(),
        query=query,
        department_id=department_id
    )


@patient_bp.route("/appointments/<int:appointment_id>/notes")
@patient_required
def view_notes(appointment_id):
    patient = Patient.query.filter_by(user_id=current_user.id).first_or_404()
    appointment = db.get_or_404(Appointment, appointment_id)

    if appointment.patient_id != patient.id:
        abort(403)

    if appointment.status != "Completed":
        abort(403)

    note = ConsultationNote.query.filter_by(
        appointment_id=appointment.id
    ).first()

    return {
        "appointment_id": appointment.id,
        "notes": note.notes if note else None
    }
