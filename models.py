"""
urban_cleaning_app/models.py
SQLAlchemy ORM models that reproduce your ER‑diagram.
"""

from datetime import datetime, time, date
from flask_login import UserMixin
from sqlalchemy.sql import func
from app import db   # imported after db singleton is created in app.py


# -------------------------------------------------------------------------
class User(UserMixin, db.Model):
    __tablename__ = "users"

    id          = db.Column(db.Integer, primary_key=True)
    name        = db.Column(db.String(100), nullable=False)
    email       = db.Column(db.String(120), unique=True, nullable=False)
    phone       = db.Column(db.String(20), nullable=False)
    password    = db.Column(db.String(255), nullable=False)
    is_verified = db.Column(db.Boolean, default=False)

    # relationships
    bookings = db.relationship("Booking", backref="customer", cascade="all,delete")

    def __repr__(self):
        return f"<User {self.email}>"


# -------------------------------------------------------------------------
class Task(db.Model):
    __tablename__ = "tasks"

    id        = db.Column(db.Integer, primary_key=True)
    task_name = db.Column(db.String(100), unique=True, nullable=False)

    specializations = db.relationship("EmployeeSpecialization", backref="task", cascade="all,delete")

    def __repr__(self):
        return f"<Task {self.task_name}>"


# -------------------------------------------------------------------------
class Employee(db.Model):
    __tablename__ = "employees"

    id       = db.Column(db.Integer, primary_key=True)
    name     = db.Column(db.String(100), nullable=False)
    gender   = db.Column(db.Enum("Male", "Female", "Other"))
    phone    = db.Column(db.String(20), nullable=False)
    email    = db.Column(db.String(100), unique=True, nullable=False)
    age      = db.Column(db.Integer)

    specs  = db.relationship("EmployeeSpecialization", backref="employee", cascade="all,delete")
    blocks = db.relationship("EmployeeBlockedSlot", backref="employee", cascade="all,delete")

    def __repr__(self):
        return f"<Employee {self.name}>"


# -------------------------------------------------------------------------
class EmployeeSpecialization(db.Model):
    __tablename__ = "employee_specializations"

    id          = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey("employees.id"), nullable=False)
    task_id     = db.Column(db.Integer, db.ForeignKey("tasks.id"),     nullable=False)


# -------------------------------------------------------------------------
class EmployeeBlockedSlot(db.Model):
    __tablename__ = "employee_blocked_slots"

    id          = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey("employees.id"), nullable=False)
    user_id     = db.Column(db.Integer, db.ForeignKey("users.id"),     nullable=False)
    blocked_from= db.Column(db.DateTime, nullable=False)
    blocked_to  = db.Column(db.DateTime, nullable=False)
    status      = db.Column(db.Enum("confirmed", "cancelled", "pending"), default="pending")

    tasks = db.relationship("BlockedTask", backref="block", cascade="all,delete")


# -------------------------------------------------------------------------
class BlockedTask(db.Model):
    __tablename__ = "blocked_tasks"

    id       = db.Column(db.Integer, primary_key=True)
    block_id = db.Column(db.Integer, db.ForeignKey("employee_blocked_slots.id"), nullable=False)
    task_id  = db.Column(db.Integer, db.ForeignKey("tasks.id"),            nullable=False)


# -------------------------------------------------------------------------
class Booking(db.Model):
    __tablename__ = "bookings"

    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    services   = db.Column(db.String(255))   # comma‑separated list of task names
    date       = db.Column(db.Date,  nullable=False)
    start_time = db.Column(db.Time,  nullable=False)
    end_time   = db.Column(db.Time,  nullable=False)
    created_at = db.Column(db.DateTime, default=func.now())

    def __repr__(self):
        return f"<Booking {self.id} ({self.date})>"
