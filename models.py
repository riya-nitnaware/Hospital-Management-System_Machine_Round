from flask_login import UserMixin

from datetime import datetime, date, time

from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


# =========================
# USER MODEL
# =========================
class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="patient")
    phone = db.Column(db.String(20))
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    doctor_profile = db.relationship(
        "Doctor",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan"
    )

    patient_profile = db.relationship(
        "Patient",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan"
    )

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def active(self):
        return self.is_active

    def get_id(self):
     return str(self.id)

    def __repr__(self):
        return f"<User {self.email}>"


# =========================
# DEPARTMENT MODEL
# =========================
class Department(db.Model):
    __tablename__ = "departments"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.Text)

    doctors = db.relationship(
        "Doctor",
        back_populates="department"
    )

    def __repr__(self):
        return f"<Department {self.name}>"


# =========================
# DOCTOR MODEL
# =========================
class Doctor(db.Model):
    __tablename__ = "doctors"

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        unique=True,
        nullable=False
    )

    department_id = db.Column(
        db.Integer,
        db.ForeignKey("departments.id"),
        nullable=True
    )

    specialization = db.Column(db.String(120), nullable=False)
    qualification = db.Column(db.String(200))
    experience = db.Column(db.Integer, default=0)
    consultation_fee = db.Column(db.Float, default=0.0)
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    user = db.relationship(
        "User",
        back_populates="doctor_profile"
    )

    department = db.relationship(
        "Department",
        back_populates="doctors"
    )

    schedules = db.relationship(
        "DoctorSchedule",
        back_populates="doctor",
        cascade="all, delete-orphan"
    )

    appointments = db.relationship(
        "Appointment",
        back_populates="doctor",
        foreign_keys="Appointment.doctor_id"
    )

    def __repr__(self):
        return f"<Doctor {self.id}>"


# =========================
# PATIENT MODEL
# =========================
class Patient(db.Model):
    __tablename__ = "patients"

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        unique=True,
        nullable=False
    )

    date_of_birth = db.Column(db.Date)
    gender = db.Column(db.String(20))
    phone = db.Column(db.String(20))
    address = db.Column(db.Text)

    user = db.relationship(
        "User",
        back_populates="patient_profile"
    )

    appointments = db.relationship(
        "Appointment",
        back_populates="patient",
        foreign_keys="Appointment.patient_id"
    )

    def __repr__(self):
        return f"<Patient {self.id}>"


# =========================
# DOCTOR SCHEDULE MODEL
# =========================
class DoctorSchedule(db.Model):
    __tablename__ = "doctor_schedules"

    id = db.Column(db.Integer, primary_key=True)

    doctor_id = db.Column(
        db.Integer,
        db.ForeignKey("doctors.id"),
        nullable=False
    )

    weekday = db.Column(db.Integer, nullable=False)
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    slot_minutes = db.Column(db.Integer, default=30, nullable=False)

    doctor = db.relationship(
        "Doctor",
        back_populates="schedules"
    )

    def __repr__(self):
        return f"<DoctorSchedule {self.id}>"


# =========================
# APPOINTMENT MODEL
# =========================
class Appointment(db.Model):
    __tablename__ = "appointments"

    id = db.Column(db.Integer, primary_key=True)

    patient_id = db.Column(
        db.Integer,
        db.ForeignKey("patients.id"),
        nullable=False
    )

    doctor_id = db.Column(
        db.Integer,
        db.ForeignKey("doctors.id"),
        nullable=False
    )

    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime, nullable=False)

    status = db.Column(
        db.String(20),
        nullable=False,
        default="Pending"
    )

    reason = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    patient = db.relationship(
        "Patient",
        back_populates="appointments",
        foreign_keys=[patient_id]
    )

    doctor = db.relationship(
        "Doctor",
        back_populates="appointments",
        foreign_keys=[doctor_id]
    )

    notes = db.relationship(
        "ConsultationNote",
        back_populates="appointment",
        cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Appointment {self.id}>"


# =========================
# CONSULTATION NOTES MODEL
# =========================
class ConsultationNote(db.Model):
    __tablename__ = "consultation_notes"

    id = db.Column(db.Integer, primary_key=True)

    appointment_id = db.Column(
        db.Integer,
        db.ForeignKey("appointments.id"),
        nullable=False
    )

    doctor_id = db.Column(
        db.Integer,
        db.ForeignKey("doctors.id"),
        nullable=False
    )

    notes = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    appointment = db.relationship(
        "Appointment",
        back_populates="notes"
    )

    doctor = db.relationship(
        "Doctor",
        foreign_keys=[doctor_id]
    )

    def __repr__(self):
        return f"<ConsultationNote {self.id}>"
