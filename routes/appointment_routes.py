
from datetime import datetime, date, timedelta
from functools import wraps

from flask import (
    Blueprint,
    request,
    jsonify,
    render_template,
    redirect,
    url_for,
    flash,
    abort,
)
from flask_login import login_required, current_user

from models import db, User, Doctor, Patient, DoctorSchedule, Appointment


# Keep this blueprint name as "appointment" because app.py
# and the templates use appointment.* endpoint names.
appointment_bp = Blueprint("appointment", __name__)


# =====================================================
# HELPERS
# =====================================================

def role_required(*roles):
    """Restrict a route to specified user roles."""

    def decorator(view_function):
        @wraps(view_function)
        @login_required
        def wrapped(*args, **kwargs):
            if current_user.role not in roles:
                abort(403)

            return view_function(*args, **kwargs)

        return wrapped

    return decorator


def get_patient():
    """Return the patient profile for the logged-in user."""
    return Patient.query.filter_by(user_id=current_user.id).first()


def wants_json():
    return (
        request.is_json
        or request.headers.get("X-Requested-With") == "XMLHttpRequest"
    )


def response_error(message, status=400):
    if wants_json():
        return jsonify({"success": False, "message": message}), status

    flash(message, "danger")
    return redirect(request.referrer or url_for("index"))


def parse_datetime(value):
    """Parse a datetime-local value or ISO datetime string."""
    if not value:
        return None

    try:
        parsed = datetime.fromisoformat(
            str(value).strip().replace("Z", "+00:00")
        )

        # This application stores appointment times as naive datetimes.
        if parsed.tzinfo is not None:
            parsed = parsed.replace(tzinfo=None)

        return parsed.replace(second=0, microsecond=0)

    except (ValueError, TypeError):
        return None


def get_request_data():
    """Support JSON requests and normal HTML form submissions."""
    if request.is_json:
        return request.get_json(silent=True) or {}

    return request.form


# =====================================================
# APPOINTMENT VALIDATION
# =====================================================

def check_slot(
    doctor_id,
    start_time,
    end_time,
    exclude_appointment_id=None,
):
    """
    Check that a requested appointment:
    1. Fits the doctor's schedule.
    2. Starts on a valid slot boundary.
    3. Does not overlap another active appointment.
    """

    if end_time <= start_time:
        return False, "The appointment end time must be after its start time."

    doctor = db.session.get(Doctor, doctor_id)

    if not doctor or not doctor.is_active:
        return False, "This doctor is unavailable."

    schedules = DoctorSchedule.query.filter_by(
        doctor_id=doctor_id,
        weekday=start_time.weekday(),
    ).all()

    matching_schedule = None

    for schedule in schedules:
        schedule_start = datetime.combine(
            start_time.date(), schedule.start_time
        )
        schedule_end = datetime.combine(
            start_time.date(), schedule.end_time
        )

        if (
            schedule_start <= start_time
            and end_time <= schedule_end
            and schedule.slot_minutes > 0
        ):
            elapsed = int((start_time - schedule_start).total_seconds())

            if elapsed % (schedule.slot_minutes * 60) == 0:
                matching_schedule = schedule
                break

    if matching_schedule is None:
        return False, "This time is outside the doctor's available schedule."

    overlapping = Appointment.query.filter(
        Appointment.doctor_id == doctor_id,
        Appointment.start_time < end_time,
        Appointment.end_time > start_time,
        Appointment.status.notin_(
            ["Cancelled", "Rejected", "cancelled", "rejected"]
        ),
    )

    if exclude_appointment_id is not None:
        overlapping = overlapping.filter(
            Appointment.id != exclude_appointment_id
        )

    if overlapping.first():
        return False, "This time slot is already booked."

    return True, "Time slot is available."


def get_available_slots(doctor_id, selected_date):
    """Generate available start times from the doctor's schedule."""

    doctor = db.session.get(Doctor, doctor_id)

    if not doctor or not doctor.is_active:
        return []

    schedules = DoctorSchedule.query.filter_by(
        doctor_id=doctor_id,
        weekday=selected_date.weekday(),
    ).order_by(DoctorSchedule.start_time).all()

    available = []
    now = datetime.now()

    for schedule in schedules:
        if schedule.slot_minutes <= 0:
            continue

        current = datetime.combine(
            selected_date, schedule.start_time
        )
        schedule_end = datetime.combine(
            selected_date, schedule.end_time
        )
        duration = timedelta(minutes=schedule.slot_minutes)

        while current + duration <= schedule_end:
            end_time = current + duration

            if current > now:
                valid, _ = check_slot(
                    doctor_id,
                    current,
                    end_time,
                )

                if valid:
                    available.append(current.isoformat(timespec="minutes"))

            current = end_time

    return available


# =====================================================
# BOOKING PAGE
# URL: /appointments/book/<doctor_id>
# Endpoint: appointment.booking_page
# =====================================================

@appointment_bp.route(
    "/appointments/book/<int:doctor_id>",
    methods=["GET"],
)
@role_required("patient")
def booking_page(doctor_id):
    doctor = db.session.get(Doctor, doctor_id)

    if not doctor or not doctor.is_active:
        abort(404)

    patient = get_patient()

    if not patient:
        return response_error(
            "Your patient profile was not found. Please contact the administrator.",
            403,
        )

    return render_template(
        "appointment_booking.html",
        doctor=doctor,
        patient=patient,
    )


# =====================================================
# AVAILABLE SLOTS API
# URL: /appointments/slots
# Endpoint: appointment.slots
# =====================================================

@appointment_bp.route(
    "/appointments/slots",
    methods=["GET"],
)
@role_required("patient")
def slots():
    doctor_id = request.args.get("doctor_id", type=int)
    date_string = request.args.get("date", "")

    if not doctor_id or not date_string:
        return jsonify({
            "success": False,
            "message": "Doctor and date are required.",
            "slots": [],
        }), 400

    try:
        selected_date = date.fromisoformat(date_string)
    except ValueError:
        return jsonify({
            "success": False,
            "message": "Invalid date format. Use YYYY-MM-DD.",
            "slots": [],
        }), 400

    if selected_date < date.today():
        return jsonify({
            "success": True,
            "slots": [],
            "message": "Past dates are not available.",
        })

    doctor = db.session.get(Doctor, doctor_id)

    if not doctor or not doctor.is_active:
        return jsonify({
            "success": False,
            "message": "Doctor not found or unavailable.",
            "slots": [],
        }), 404

    available_slots = get_available_slots(
        doctor_id,
        selected_date,
    )

    return jsonify({
        "success": True,
        "slots": available_slots,
    })


# =====================================================
# CREATE APPOINTMENT
# URL: POST /appointments
# Endpoint: appointment.book
# =====================================================

@appointment_bp.route(
    "/appointments",
    methods=["POST"],
)
@role_required("patient")
def book():
    data = get_request_data()
    patient = get_patient()

    if not patient:
        return response_error(
            "Patient profile not found.",
            403,
        )

    doctor_id = data.get("doctor_id", type=int)
    start_time = parse_datetime(data.get("start_time"))
    reason = str(data.get("reason", "")).strip()

    if not doctor_id or not start_time:
        return response_error(
            "Please select a doctor and appointment time.",
        )

    if start_time <= datetime.now():
        return response_error(
            "Please select a future appointment time.",
        )

    doctor = db.session.get(Doctor, doctor_id)

    if not doctor or not doctor.is_active:
        return response_error(
            "The selected doctor is unavailable.",
            404,
        )

    schedule = DoctorSchedule.query.filter_by(
        doctor_id=doctor_id,
        weekday=start_time.weekday(),
    ).all()

    matching_schedule = None

    for item in schedule:
        schedule_start = datetime.combine(
            start_time.date(), item.start_time
        )
        schedule_end = datetime.combine(
            start_time.date(), item.end_time
        )

        if (
            item.slot_minutes > 0
            and schedule_start <= start_time < schedule_end
        ):
            matching_schedule = item
            break

    if not matching_schedule:
        return response_error(
            "The doctor has no schedule for this time.",
        )

    end_time = start_time + timedelta(
        minutes=matching_schedule.slot_minutes
    )

    valid, message = check_slot(
        doctor_id,
        start_time,
        end_time,
    )

    if not valid:
        return response_error(message, 409)

    appointment = Appointment(
        patient_id=patient.id,
        doctor_id=doctor.id,
        start_time=start_time,
        end_time=end_time,
        reason=reason,
        status="Pending",
    )

    try:
        db.session.add(appointment)
        db.session.commit()
    except Exception:
        db.session.rollback()
        app_logger_message = (
            "The appointment could not be saved. Please try again."
        )
        return response_error(app_logger_message, 500)

    if wants_json():
        return jsonify({
            "success": True,
            "message": "Appointment booked successfully.",
            "appointment_id": appointment.id,
            "redirect_url": url_for("patient.dashboard"),
        }), 201

    flash("Appointment booked successfully.", "success")
    return redirect(url_for("patient.dashboard"))


# =====================================================
# CANCEL APPOINTMENT
# URL: POST /appointments/<id>/cancel
# Endpoint: appointment.cancel
# =====================================================

@appointment_bp.route(
    "/appointments/<int:appointment_id>/cancel",
    methods=["POST"],
)
@role_required("patient")
def cancel(appointment_id):
    patient = get_patient()

    if not patient:
        return response_error("Patient profile not found.", 403)

    appointment = Appointment.query.filter_by(
        id=appointment_id,
        patient_id=patient.id,
    ).first_or_404()

    if appointment.status in ("Completed", "Cancelled", "Rejected"):
        return response_error(
            "This appointment can no longer be cancelled.",
            400,
        )

    appointment.status = "Cancelled"

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        return response_error(
            "Unable to cancel the appointment. Please try again.",
            500,
        )

    if wants_json():
        return jsonify({
            "success": True,
            "message": "Appointment cancelled successfully.",
        })

    flash("Appointment cancelled successfully.", "success")
    return redirect(url_for("patient.dashboard"))


# =====================================================
# RESCHEDULE APPOINTMENT
# URL: POST/PATCH /appointments/<id>/reschedule
# Endpoint: appointment.reschedule
# =====================================================

@appointment_bp.route(
    "/appointments/<int:appointment_id>/reschedule",
    methods=["POST", "PATCH"],
)
@role_required("patient")
def reschedule(appointment_id):
    patient = get_patient()

    if not patient:
        return response_error("Patient profile not found.", 403)

    appointment = Appointment.query.filter_by(
        id=appointment_id,
        patient_id=patient.id,
    ).first_or_404()

    if appointment.status in ("Completed", "Cancelled", "Rejected"):
        return response_error(
            "This appointment cannot be rescheduled.",
            400,
        )

    data = get_request_data()
    new_start = parse_datetime(data.get("start_time"))

    if not new_start:
        return response_error(
            "Please provide a valid new appointment time.",
        )

    if new_start <= datetime.now():
        return response_error(
            "Please select a future appointment time.",
        )

    schedule = DoctorSchedule.query.filter_by(
        doctor_id=appointment.doctor_id,
        weekday=new_start.weekday(),
    ).all()

    matching_schedule = None

    for item in schedule:
        schedule_start = datetime.combine(
            new_start.date(), item.start_time
        )
        schedule_end = datetime.combine(
            new_start.date(), item.end_time
        )

        if (
            item.slot_minutes > 0
            and schedule_start <= new_start < schedule_end
        ):
            matching_schedule = item
            break

    if not matching_schedule:
        return response_error(
            "The doctor is not available at this time.",
        )

    new_end = new_start + timedelta(
        minutes=matching_schedule.slot_minutes
    )

    valid, message = check_slot(
        appointment.doctor_id,
        new_start,
        new_end,
        exclude_appointment_id=appointment.id,
    )

    if not valid:
        return response_error(message, 409)

    appointment.start_time = new_start
    appointment.end_time = new_end
    appointment.status = "Pending"

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        return response_error(
            "Unable to reschedule the appointment. Please try again.",
            500,
        )

    if wants_json():
        return jsonify({
            "success": True,
            "message": "Appointment rescheduled successfully.",
            "start_time": new_start.isoformat(timespec="minutes"),
        })

    flash("Appointment rescheduled successfully.", "success")
    return redirect(url_for("patient.dashboard"))
