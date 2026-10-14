
from datetime import datetime
from functools import wraps

from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user

from models import db, User, Doctor, DoctorSchedule, Appointment, ConsultationNote

doctor_bp = Blueprint("doctor", __name__, url_prefix="/doctor")


def doctor_required(view):
    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if not current_user.is_active or current_user.role != "doctor":
            abort(403)
        return view(*args, **kwargs)
    return wrapped


@doctor_bp.route("/dashboard")
@doctor_required
def dashboard():
    doctor = Doctor.query.filter_by(user_id=current_user.id).first_or_404()
    appointments = Appointment.query.filter_by(
        doctor_id=doctor.id
    ).order_by(Appointment.start_time.desc()).all()

    return render_template(
        "doctor_dashboard.html",
        doctor=doctor,
        appointments=appointments,
        schedules=doctor.schedules,
        now=datetime.now()
    )


@doctor_bp.route("/schedule", methods=["POST"])
@doctor_required
def save_schedule():
    doctor = Doctor.query.filter_by(user_id=current_user.id).first_or_404()

    days = request.form.getlist("weekday")
    start = request.form.get("start_time", "")
    end = request.form.get("end_time", "")

    try:
        start_time = datetime.strptime(start, "%H:%M").time()
        end_time = datetime.strptime(end, "%H:%M").time()
        weekdays = {int(day) for day in days}
    except (ValueError, TypeError):
        flash("Enter valid working days and hours.", "danger")
        return redirect(url_for("doctor.dashboard"))

    if not weekdays or not weekdays.issubset(set(range(7))) or start_time >= end_time:
        flash("Choose valid days and working hours.", "danger")
        return redirect(url_for("doctor.dashboard"))

    DoctorSchedule.query.filter_by(doctor_id=doctor.id).delete()

    for weekday in weekdays:
        db.session.add(DoctorSchedule(
            doctor_id=doctor.id,
            weekday=weekday,
            start_time=start_time,
            end_time=end_time,
            slot_minutes=30
        ))

    db.session.commit()
    flash("Availability saved successfully.", "success")
    return redirect(url_for("doctor.dashboard"))


@doctor_bp.route("/appointments/<int:appointment_id>/status", methods=["POST"])
@doctor_required
def update_status(appointment_id):
    doctor = Doctor.query.filter_by(user_id=current_user.id).first_or_404()
    appointment = db.get_or_404(Appointment, appointment_id)

    if appointment.doctor_id != doctor.id:
        abort(403)

    status = request.form.get("status", "")
    if status not in {"Confirmed", "Completed", "Cancelled"}:
        abort(400)

    if appointment.status not in {"Pending", "Confirmed"}:
        flash("This appointment is already closed.", "danger")
    elif status == "Completed" and appointment.end_time > datetime.now():
        flash("This appointment has not finished yet.", "danger")
    else:
        appointment.status = status
        db.session.commit()
        flash("Appointment status updated.", "success")

    return redirect(url_for("doctor.dashboard"))


@doctor_bp.route("/appointments/<int:appointment_id>/notes", methods=["POST"])
@doctor_required
def save_notes(appointment_id):
    doctor = Doctor.query.filter_by(user_id=current_user.id).first_or_404()
    appointment = db.get_or_404(Appointment, appointment_id)

    if appointment.doctor_id != doctor.id:
        abort(403)

    notes_text = request.form.get("notes", "").strip()

    if appointment.status != "Completed":
        flash("Only completed appointments can have consultation notes.", "danger")
    elif not notes_text or len(notes_text) > 5000:
        flash("Enter consultation notes (maximum 5000 characters).", "danger")
    else:
        note = ConsultationNote.query.filter_by(
            appointment_id=appointment.id
        ).first()

        if note:
            note.notes = notes_text
            note.doctor_id = doctor.id
        else:
            db.session.add(ConsultationNote(
                appointment_id=appointment.id,
                doctor_id=doctor.id,
                notes=notes_text
            ))

        db.session.commit()
        flash("Consultation notes saved.", "success")

    return redirect(url_for("doctor.dashboard"))

