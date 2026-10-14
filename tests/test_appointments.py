
from datetime import datetime, timedelta

import pytest

from app import create_app
from models import db, User, Doctor, Patient, Department, DoctorSchedule, Appointment


@pytest.fixture
def app():
    application = create_app()
    application.config.update(
        TESTING=True,
        WTF_CSRF_ENABLED=False,
        SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
        SECRET_KEY="test-secret"
    )

    with application.app_context():
        db.create_all()

        department = Department(name="General Medicine")
        db.session.add(department)
        db.session.flush()

        doctor_user = User(name="Test Doctor", email="doctor@example.com", role="doctor")
        doctor_user.set_password("TestPassword123")
        patient_user = User(name="Test Patient", email="patient@example.com", role="patient")
        patient_user.set_password("TestPassword123")

        db.session.add_all([doctor_user, patient_user])
        db.session.flush()

        doctor = Doctor(
            user_id=doctor_user.id,
            department_id=department.id,
            specialization="General Medicine"
        )
        patient = Patient(user_id=patient_user.id)

        db.session.add_all([doctor, patient])
        db.session.flush()

        db.session.add(DoctorSchedule(
            doctor_id=doctor.id,
            weekday=0,
            start_time=datetime.strptime("09:00", "%H:%M").time(),
            end_time=datetime.strptime("17:00", "%H:%M").time(),
            slot_minutes=30
        ))
        db.session.commit()

        yield application

        db.session.remove()
        db.drop_all()


def test_appointment_table_exists(app):
    with app.app_context():
        assert db.session.query(Appointment).count() == 0


def test_appointment_model_stores_status(app):
    with app.app_context():
        patient = Patient.query.first()
        doctor = Doctor.query.first()
        start = datetime.now() + timedelta(days=2)

        appointment = Appointment(
            patient_id=patient.id,
            doctor_id=doctor.id,
            start_time=start,
            end_time=start + timedelta(minutes=30),
            status="Pending"
        )
        db.session.add(appointment)
        db.session.commit()

        saved = db.session.get(Appointment, appointment.id)
        assert saved.status == "Pending"
        assert saved.doctor_id == doctor.id
