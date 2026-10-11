# CareDesk - Smart Hospital Management System

A beginner-friendly hospital management web app built with **Python, Flask, SQLite, HTML, CSS and JavaScript**.

## Features
- **Patient registration and records**: register, search (name / phone / patient ID), edit, delete, and view each patient's full history
- **Doctor profiles and schedules**: specialization, working days, working hours, consultation fee
- **Appointment booking**: checks the doctor's working days and hours and blocks double-booking; reschedule, complete or cancel
- **Billing and payments**: create bills, record full or partial payments (cash, card, UPI, insurance, bank transfer), printable invoice
- **Admin dashboard**: totals, today's appointments, money collected vs outstanding, upcoming appointments, doctor workload
- Admin login, password change, CSRF protection, hashed passwords, parameterized SQL

## Run it
```bash
cd hospital_management
python -m venv venv
# Windows:   venv\Scripts\activate
# Mac/Linux: source venv/bin/activate
pip install -r requirements.txt
python app.py
```
Open http://127.0.0.1:5000 and sign in with **admin / admin123** (change it from the Password link).

The database file `hospital.db` is created on first run, with sample doctors, patients, appointments and bills so you can explore right away.

- **Reset everything:** stop the app, delete `hospital.db`, start again (sample data returns).
- **Start with no sample data:** delete the `seed_demo_data(db)` line in `init_db()` in `app.py`, then delete `hospital.db` and start again.

## Project structure
```
hospital_management/
  app.py              routes, database schema, validation
  requirements.txt
  templates/          HTML pages (Jinja2)
  static/css/style.css
  static/js/main.js   confirm dialogs, fee autofill, doctor hours hint
```

## Before real use
Set a strong secret key (`SECRET_KEY` environment variable), run with `FLASK_DEBUG=0` behind a production
server such as gunicorn or waitress, and use HTTPS. This is a learning project, not a certified medical system.
