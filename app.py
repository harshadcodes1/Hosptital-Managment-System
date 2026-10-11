"""Smart Hospital Management System - Flask + SQLite."""
import os
import secrets
import sqlite3
from datetime import date, datetime, timedelta
from functools import wraps

from flask import (Flask, abort, flash, g, redirect, render_template, request,
                   session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "hospital.db")
DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
STATUSES = ["Scheduled", "Completed", "Cancelled"]
PAY_METHODS = ["Cash", "Card", "UPI", "Insurance", "Bank transfer"]

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-change-me")

SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS patients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    age INTEGER NOT NULL,
    gender TEXT NOT NULL,
    phone TEXT NOT NULL,
    email TEXT,
    address TEXT,
    blood_group TEXT,
    medical_history TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS doctors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    specialization TEXT NOT NULL,
    phone TEXT,
    email TEXT,
    available_days TEXT NOT NULL,
    start_time TEXT NOT NULL,
    end_time TEXT NOT NULL,
    fee REAL NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS appointments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id INTEGER NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    doctor_id INTEGER NOT NULL REFERENCES doctors(id) ON DELETE CASCADE,
    date TEXT NOT NULL,
    time TEXT NOT NULL,
    reason TEXT,
    status TEXT NOT NULL DEFAULT 'Scheduled'
);
CREATE TABLE IF NOT EXISTS bills (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id INTEGER NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    description TEXT NOT NULL,
    amount REAL NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bill_id INTEGER NOT NULL REFERENCES bills(id) ON DELETE CASCADE,
    amount REAL NOT NULL,
    method TEXT NOT NULL,
    paid_on TEXT DEFAULT CURRENT_TIMESTAMP
);
"""


# ----------------------------------------------------------------- database
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(_exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    """Create tables; on first run add the admin user and demo data."""
    db = sqlite3.connect(DB_PATH)
    db.executescript(SCHEMA)
    if db.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
        db.execute("INSERT INTO users (username, password_hash) VALUES (?, ?)",
                   ("admin", generate_password_hash("admin123")))
        seed_demo_data(db)
    db.commit()
    db.close()


def seed_demo_data(db):
    doctors = [
        ("Dr. Meera Kulkarni", "Cardiology", "9800000001", "meera@example.com", "Mon,Tue,Thu,Fri", "09:00", "15:00", 800),
        ("Dr. Arjun Rao", "Orthopedics", "9800000002", "arjun@example.com", "Mon,Wed,Fri", "10:00", "16:00", 700),
        ("Dr. Sana Sheikh", "Pediatrics", "9800000003", "sana@example.com", "Mon,Tue,Wed,Thu,Fri,Sat", "09:00", "13:00", 500),
        ("Dr. Rohan Patil", "General medicine", "9800000004", "rohan@example.com", "Mon,Tue,Wed,Thu,Fri,Sat,Sun", "08:00", "20:00", 400),
    ]
    db.executemany("INSERT INTO doctors (name, specialization, phone, email, available_days, start_time, end_time, fee) VALUES (?,?,?,?,?,?,?,?)", doctors)
    patients = [
        ("Anita Deshmukh", 34, "Female", "9811111111", "anita@example.com", "Kothrud, Pune", "B+", "Mild asthma"),
        ("Vikram Joshi", 58, "Male", "9822222222", "", "Baner, Pune", "O+", "Hypertension"),
        ("Priya Nair", 7, "Female", "9833333333", "", "Aundh, Pune", "A+", ""),
        ("Imran Khan", 45, "Male", "9844444444", "imran@example.com", "Viman Nagar, Pune", "AB-", "Knee pain since 2024"),
        ("Neha Gupta", 29, "Female", "9855555555", "", "Hadapsar, Pune", "O-", ""),
    ]
    db.executemany("INSERT INTO patients (name, age, gender, phone, email, address, blood_group, medical_history) VALUES (?,?,?,?,?,?,?,?)", patients)
    today = date.today()

    def next_weekday(days_ahead, doc_days):
        d = today + timedelta(days=days_ahead)
        while DAYS[d.weekday()] not in doc_days:
            d += timedelta(days=1)
        return d.isoformat()

    d_days = [x[4] for x in doctors]
    appts = [
        (2, 1, next_weekday(0, d_days[1]), "10:30", "Knee pain follow-up", "Scheduled"),
        (1, 0, next_weekday(1, d_days[0]), "11:00", "BP check", "Scheduled"),
        (0, 3, next_weekday(0, d_days[3]), "09:00", "Cough and wheeze", "Scheduled"),
        (2, 2, next_weekday(2, d_days[2]), "10:00", "Vaccination", "Scheduled"),
        (4, 3, (today - timedelta(days=3)).isoformat(), "12:00", "Fever", "Completed"),
    ]
    db.executemany("INSERT INTO appointments (patient_id, doctor_id, date, time, reason, status) VALUES (?,?,?,?,?,?)",
                   [(p + 1, d + 1, dt, t, r, s) for p, d, dt, t, r, s in appts])
    db.executemany("INSERT INTO bills (patient_id, description, amount) VALUES (?,?,?)", [
        (5, "General consultation", 400), (1, "Cardiology consultation + ECG", 1500), (4, "X-ray and consultation", 1200)])
    db.executemany("INSERT INTO payments (bill_id, amount, method) VALUES (?,?,?)", [
        (1, 400, "UPI"), (2, 700, "Card")])


# ------------------------------------------------------------ auth & safety
def login_required(view):
    @wraps(view)
    def wrapped(*a, **kw):
        if not session.get("user"):
            return redirect(url_for("login", next=request.path))
        return view(*a, **kw)
    return wrapped


@app.before_request
def csrf_protect():
    if request.method == "POST":
        token = session.get("csrf_token")
        if not token or token != request.form.get("csrf_token"):
            abort(400, "Invalid or missing form token. Go back and reload the page.")


@app.context_processor
def inject_globals():
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_hex(16)
    return {"csrf_token": session["csrf_token"], "today": date.today().isoformat(),
            "DAYS": DAYS, "STATUSES": STATUSES, "PAY_METHODS": PAY_METHODS}


@app.template_filter("money")
def money(v):
    return f"₹{(v or 0):,.2f}"


@app.template_filter("pid")
def pid(v):
    return f"P{int(v):04d}"


@app.template_filter("nice_date")
def nice_date(v):
    try:
        return datetime.strptime(v[:10], "%Y-%m-%d").strftime("%d %b %Y")
    except (ValueError, TypeError):
        return v or ""


@app.template_filter("nice_time")
def nice_time(v):
    try:
        return datetime.strptime(v, "%H:%M").strftime("%I:%M %p").lstrip("0")
    except (ValueError, TypeError):
        return v or ""


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = get_db().execute("SELECT * FROM users WHERE username = ?",
                                (request.form.get("username", "").strip(),)).fetchone()
        if user and check_password_hash(user["password_hash"], request.form.get("password", "")):
            session.clear()
            session["user"] = user["username"]
            nxt = request.args.get("next", "")
            return redirect(nxt if nxt.startswith("/") and not nxt.startswith("//") else url_for("dashboard"))
        flash("Wrong username or password.", "error")
    return render_template("login.html")


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/password", methods=["GET", "POST"])
@login_required
def change_password():
    if request.method == "POST":
        db = get_db()
        user = db.execute("SELECT * FROM users WHERE username = ?", (session["user"],)).fetchone()
        new = request.form.get("new_password", "")
        if not check_password_hash(user["password_hash"], request.form.get("old_password", "")):
            flash("Current password is incorrect.", "error")
        elif len(new) < 6:
            flash("New password must be at least 6 characters.", "error")
        else:
            db.execute("UPDATE users SET password_hash = ? WHERE id = ?", (generate_password_hash(new), user["id"]))
            db.commit()
            flash("Password updated.", "success")
            return redirect(url_for("dashboard"))
    return render_template("password.html")


# ---------------------------------------------------------------- dashboard
@app.route("/")
@login_required
def dashboard():
    db = get_db()
    one = lambda sql, *a: db.execute(sql, a).fetchone()[0]
    today_s = date.today().isoformat()
    stats = {
        "patients": one("SELECT COUNT(*) FROM patients"),
        "doctors": one("SELECT COUNT(*) FROM doctors"),
        "today": one("SELECT COUNT(*) FROM appointments WHERE date = ? AND status != 'Cancelled'", today_s),
        "billed": one("SELECT COALESCE(SUM(amount),0) FROM bills"),
        "collected": one("SELECT COALESCE(SUM(amount),0) FROM payments"),
    }
    stats["outstanding"] = stats["billed"] - stats["collected"]
    upcoming = db.execute("""SELECT a.*, p.name AS patient, d.name AS doctor FROM appointments a
        JOIN patients p ON p.id = a.patient_id JOIN doctors d ON d.id = a.doctor_id
        WHERE a.status = 'Scheduled' AND a.date >= ? ORDER BY a.date, a.time LIMIT 8""", (today_s,)).fetchall()
    by_status = {s: one("SELECT COUNT(*) FROM appointments WHERE status = ?", s) for s in STATUSES}
    by_doctor = db.execute("""SELECT d.name, d.specialization, COUNT(a.id) AS n FROM doctors d
        LEFT JOIN appointments a ON a.doctor_id = d.id AND a.status != 'Cancelled'
        GROUP BY d.id ORDER BY n DESC""").fetchall()
    recent_payments = db.execute("""SELECT pay.*, p.name AS patient FROM payments pay
        JOIN bills b ON b.id = pay.bill_id JOIN patients p ON p.id = b.patient_id
        ORDER BY pay.id DESC LIMIT 5""").fetchall()
    return render_template("dashboard.html", stats=stats, upcoming=upcoming, by_status=by_status,
                           by_doctor=by_doctor, recent_payments=recent_payments,
                           max_status=max(by_status.values() or [1]) or 1,
                           max_doc=max([r["n"] for r in by_doctor] or [1]) or 1)


# ----------------------------------------------------------------- patients
def read_patient_form():
    f = request.form
    data = {k: f.get(k, "").strip() for k in
            ("name", "age", "gender", "phone", "email", "address", "blood_group", "medical_history")}
    error = None
    if not data["name"]:
        error = "Name is required."
    elif not data["age"].isdigit() or not 0 <= int(data["age"]) <= 130:
        error = "Enter an age between 0 and 130."
    elif data["gender"] not in ("Male", "Female", "Other"):
        error = "Choose a gender."
    elif len(data["phone"]) < 7:
        error = "Enter a valid phone number."
    return data, error


@app.route("/patients")
@login_required
def patients():
    q = request.args.get("q", "").strip()
    rows = get_db().execute(
        """SELECT * FROM patients WHERE name LIKE ? OR phone LIKE ? OR ('P' || printf('%04d', id)) = upper(?)
           ORDER BY id DESC""", (f"%{q}%", f"%{q}%", q)).fetchall()
    return render_template("patients.html", rows=rows, q=q)


@app.route("/patients/add", methods=["GET", "POST"])
@login_required
def patient_add():
    if request.method == "POST":
        data, error = read_patient_form()
        if error:
            flash(error, "error")
            return render_template("patient_form.html", p=data, edit=False)
        db = get_db()
        cur = db.execute("""INSERT INTO patients (name, age, gender, phone, email, address, blood_group, medical_history)
            VALUES (:name, :age, :gender, :phone, :email, :address, :blood_group, :medical_history)""", data)
        db.commit()
        flash("Patient registered.", "success")
        return redirect(url_for("patient_detail", pid=cur.lastrowid))
    return render_template("patient_form.html", p=None, edit=False)


@app.route("/patients/<int:pid>")
@login_required
def patient_detail(pid):
    db = get_db()
    p = db.execute("SELECT * FROM patients WHERE id = ?", (pid,)).fetchone() or abort(404)
    appts = db.execute("""SELECT a.*, d.name AS doctor, d.specialization FROM appointments a
        JOIN doctors d ON d.id = a.doctor_id WHERE a.patient_id = ? ORDER BY a.date DESC, a.time DESC""", (pid,)).fetchall()
    bills = db.execute(BILL_SQL + " WHERE b.patient_id = ? ORDER BY b.id DESC", (pid,)).fetchall()
    return render_template("patient_detail.html", p=p, appts=appts, bills=bills)


@app.route("/patients/<int:pid>/edit", methods=["GET", "POST"])
@login_required
def patient_edit(pid):
    db = get_db()
    p = db.execute("SELECT * FROM patients WHERE id = ?", (pid,)).fetchone() or abort(404)
    if request.method == "POST":
        data, error = read_patient_form()
        if error:
            flash(error, "error")
            return render_template("patient_form.html", p=data, edit=True, pid=pid)
        data["id"] = pid
        db.execute("""UPDATE patients SET name=:name, age=:age, gender=:gender, phone=:phone, email=:email,
            address=:address, blood_group=:blood_group, medical_history=:medical_history WHERE id=:id""", data)
        db.commit()
        flash("Patient details saved.", "success")
        return redirect(url_for("patient_detail", pid=pid))
    return render_template("patient_form.html", p=p, edit=True, pid=pid)


@app.route("/patients/<int:pid>/delete", methods=["POST"])
@login_required
def patient_delete(pid):
    db = get_db()
    db.execute("DELETE FROM patients WHERE id = ?", (pid,))
    db.commit()
    flash("Patient and related records deleted.", "success")
    return redirect(url_for("patients"))


# ------------------------------------------------------------------ doctors
def read_doctor_form():
    f = request.form
    data = {k: f.get(k, "").strip() for k in ("name", "specialization", "phone", "email", "start_time", "end_time", "fee")}
    data["available_days"] = ",".join(d for d in DAYS if d in f.getlist("days"))
    error = None
    if not data["name"] or not data["specialization"]:
        error = "Name and specialization are required."
    elif not data["available_days"]:
        error = "Pick at least one working day."
    elif not data["start_time"] or not data["end_time"] or data["start_time"] >= data["end_time"]:
        error = "End time must be after start time."
    else:
        try:
            data["fee"] = float(data["fee"] or 0)
            if data["fee"] < 0:
                raise ValueError
        except ValueError:
            error = "Enter a valid consultation fee."
    return data, error


@app.route("/doctors")
@login_required
def doctors():
    rows = get_db().execute("""SELECT d.*, (SELECT COUNT(*) FROM appointments a WHERE a.doctor_id = d.id
        AND a.status = 'Scheduled' AND a.date >= date('now')) AS upcoming FROM doctors d ORDER BY d.name""").fetchall()
    return render_template("doctors.html", rows=rows)


@app.route("/doctors/add", methods=["GET", "POST"])
@login_required
def doctor_add():
    if request.method == "POST":
        data, error = read_doctor_form()
        if error:
            flash(error, "error")
            return render_template("doctor_form.html", d=data, edit=False, sel=request.form.getlist("days"))
        db = get_db()
        db.execute("""INSERT INTO doctors (name, specialization, phone, email, available_days, start_time, end_time, fee)
            VALUES (:name, :specialization, :phone, :email, :available_days, :start_time, :end_time, :fee)""", data)
        db.commit()
        flash("Doctor added.", "success")
        return redirect(url_for("doctors"))
    return render_template("doctor_form.html", d=None, edit=False, sel=["Mon", "Tue", "Wed", "Thu", "Fri"])


@app.route("/doctors/<int:did>/edit", methods=["GET", "POST"])
@login_required
def doctor_edit(did):
    db = get_db()
    d = db.execute("SELECT * FROM doctors WHERE id = ?", (did,)).fetchone() or abort(404)
    if request.method == "POST":
        data, error = read_doctor_form()
        if error:
            flash(error, "error")
            return render_template("doctor_form.html", d=data, edit=True, did=did, sel=request.form.getlist("days"))
        data["id"] = did
        db.execute("""UPDATE doctors SET name=:name, specialization=:specialization, phone=:phone, email=:email,
            available_days=:available_days, start_time=:start_time, end_time=:end_time, fee=:fee WHERE id=:id""", data)
        db.commit()
        flash("Doctor profile saved.", "success")
        return redirect(url_for("doctors"))
    return render_template("doctor_form.html", d=d, edit=True, did=did, sel=d["available_days"].split(","))


@app.route("/doctors/<int:did>/delete", methods=["POST"])
@login_required
def doctor_delete(did):
    db = get_db()
    db.execute("DELETE FROM doctors WHERE id = ?", (did,))
    db.commit()
    flash("Doctor and their appointments deleted.", "success")
    return redirect(url_for("doctors"))


# ------------------------------------------------------------- appointments
def check_slot(doctor_id, day, time, exclude_id=None):
    """Return an error message if the slot cannot be booked, else None."""
    doc = get_db().execute("SELECT * FROM doctors WHERE id = ?", (doctor_id,)).fetchone()
    if not doc:
        return "Choose a doctor."
    try:
        weekday = DAYS[datetime.strptime(day, "%Y-%m-%d").weekday()]
        datetime.strptime(time, "%H:%M")
    except ValueError:
        return "Choose a valid date and time."
    if weekday not in doc["available_days"].split(","):
        return f"{doc['name']} does not work on {weekday}. Working days: {doc['available_days'].replace(',', ', ')}."
    if not doc["start_time"] <= time < doc["end_time"]:
        return f"{doc['name']} sees patients {nice_time(doc['start_time'])} to {nice_time(doc['end_time'])}."
    clash = get_db().execute("""SELECT id FROM appointments WHERE doctor_id = ? AND date = ? AND time = ?
        AND status != 'Cancelled' AND id != ?""", (doctor_id, day, time, exclude_id or 0)).fetchone()
    if clash:
        return "That slot is already booked. Pick another time."
    return None


def appointment_lookups():
    db = get_db()
    return (db.execute("SELECT id, name FROM patients ORDER BY name").fetchall(),
            db.execute("SELECT * FROM doctors ORDER BY name").fetchall())


@app.route("/appointments")
@login_required
def appointments():
    status = request.args.get("status", "")
    day = request.args.get("date", "")
    sql = """SELECT a.*, p.name AS patient, d.name AS doctor, d.specialization FROM appointments a
        JOIN patients p ON p.id = a.patient_id JOIN doctors d ON d.id = a.doctor_id WHERE 1=1"""
    args = []
    if status in STATUSES:
        sql += " AND a.status = ?"
        args.append(status)
    if day:
        sql += " AND a.date = ?"
        args.append(day)
    rows = get_db().execute(sql + " ORDER BY a.date DESC, a.time DESC", args).fetchall()
    return render_template("appointments.html", rows=rows, status=status, day=day)


def appointment_form_view(a, edit, aid=None):
    patients_, doctors_ = appointment_lookups()
    return render_template("appointment_form.html", a=a, edit=edit, aid=aid, patients=patients_, doctors=doctors_)


@app.route("/appointments/add", methods=["GET", "POST"])
@login_required
def appointment_add():
    if request.method == "POST":
        f = request.form
        data = {"patient_id": f.get("patient_id", type=int), "doctor_id": f.get("doctor_id", type=int),
                "date": f.get("date", ""), "time": f.get("time", ""), "reason": f.get("reason", "").strip()}
        error = None if data["patient_id"] else "Choose a patient."
        error = error or check_slot(data["doctor_id"], data["date"], data["time"])
        if not error and data["date"] < date.today().isoformat():
            error = "Appointments cannot be booked in the past."
        if error:
            flash(error, "error")
            return appointment_form_view(data, False)
        db = get_db()
        db.execute("""INSERT INTO appointments (patient_id, doctor_id, date, time, reason)
            VALUES (:patient_id, :doctor_id, :date, :time, :reason)""", data)
        db.commit()
        flash("Appointment booked.", "success")
        return redirect(url_for("appointments"))
    preset = {"patient_id": request.args.get("patient_id", type=int)}
    return appointment_form_view(preset, False)


@app.route("/appointments/<int:aid>/edit", methods=["GET", "POST"])
@login_required
def appointment_edit(aid):
    db = get_db()
    a = db.execute("SELECT * FROM appointments WHERE id = ?", (aid,)).fetchone() or abort(404)
    if request.method == "POST":
        f = request.form
        data = {"id": aid, "patient_id": f.get("patient_id", type=int), "doctor_id": f.get("doctor_id", type=int),
                "date": f.get("date", ""), "time": f.get("time", ""), "reason": f.get("reason", "").strip()}
        error = None if data["patient_id"] else "Choose a patient."
        error = error or check_slot(data["doctor_id"], data["date"], data["time"], exclude_id=aid)
        if error:
            flash(error, "error")
            return appointment_form_view(data, True, aid)
        db.execute("""UPDATE appointments SET patient_id=:patient_id, doctor_id=:doctor_id, date=:date,
            time=:time, reason=:reason WHERE id=:id""", data)
        db.commit()
        flash("Appointment updated.", "success")
        return redirect(url_for("appointments"))
    return appointment_form_view(a, True, aid)


@app.route("/appointments/<int:aid>/status", methods=["POST"])
@login_required
def appointment_status(aid):
    status = request.form.get("status")
    if status not in STATUSES:
        abort(400)
    db = get_db()
    db.execute("UPDATE appointments SET status = ? WHERE id = ?", (status, aid))
    db.commit()
    flash(f"Appointment marked {status.lower()}.", "success")
    return redirect(request.referrer or url_for("appointments"))


@app.route("/appointments/<int:aid>/delete", methods=["POST"])
@login_required
def appointment_delete(aid):
    db = get_db()
    db.execute("DELETE FROM appointments WHERE id = ?", (aid,))
    db.commit()
    flash("Appointment deleted.", "success")
    return redirect(url_for("appointments"))


# ------------------------------------------------------------------ billing
BILL_SQL = """SELECT b.*, p.name AS patient,
    COALESCE((SELECT SUM(amount) FROM payments WHERE bill_id = b.id), 0) AS paid
    FROM bills b JOIN patients p ON p.id = b.patient_id"""


@app.route("/billing")
@login_required
def billing():
    state = request.args.get("state", "")
    rows = get_db().execute(BILL_SQL + " ORDER BY b.id DESC").fetchall()
    if state == "unpaid":
        rows = [r for r in rows if r["paid"] < r["amount"]]
    elif state == "paid":
        rows = [r for r in rows if r["paid"] >= r["amount"]]
    totals = {"billed": sum(r["amount"] for r in rows), "paid": sum(r["paid"] for r in rows)}
    return render_template("billing.html", rows=rows, state=state, totals=totals)


@app.route("/billing/add", methods=["GET", "POST"])
@login_required
def bill_add():
    db = get_db()
    if request.method == "POST":
        patient_id = request.form.get("patient_id", type=int)
        desc = request.form.get("description", "").strip()
        try:
            amount = float(request.form.get("amount", ""))
        except ValueError:
            amount = 0
        if not patient_id or not desc or amount <= 0:
            flash("Choose a patient, add a description and enter an amount above zero.", "error")
        else:
            cur = db.execute("INSERT INTO bills (patient_id, description, amount) VALUES (?,?,?)", (patient_id, desc, amount))
            db.commit()
            flash("Bill created.", "success")
            return redirect(url_for("bill_detail", bid=cur.lastrowid))
    patients_ = db.execute("SELECT id, name FROM patients ORDER BY name").fetchall()
    doctors_ = db.execute("SELECT name, fee FROM doctors ORDER BY name").fetchall()
    return render_template("bill_form.html", patients=patients_, doctors=doctors_,
                           f=request.form or {"patient_id": request.args.get("patient_id", type=int)})


@app.route("/billing/<int:bid>")
@login_required
def bill_detail(bid):
    db = get_db()
    b = db.execute(BILL_SQL + " WHERE b.id = ?", (bid,)).fetchone() or abort(404)
    pays = db.execute("SELECT * FROM payments WHERE bill_id = ? ORDER BY id", (bid,)).fetchall()
    patient = db.execute("SELECT * FROM patients WHERE id = ?", (b["patient_id"],)).fetchone()
    return render_template("bill_detail.html", b=b, pays=pays, patient=patient)


@app.route("/billing/<int:bid>/pay", methods=["POST"])
@login_required
def bill_pay(bid):
    db = get_db()
    b = db.execute(BILL_SQL + " WHERE b.id = ?", (bid,)).fetchone() or abort(404)
    method = request.form.get("method")
    try:
        amount = round(float(request.form.get("amount", "")), 2)
    except ValueError:
        amount = 0
    balance = round(b["amount"] - b["paid"], 2)
    if method not in PAY_METHODS or amount <= 0:
        flash("Enter an amount above zero and choose a payment method.", "error")
    elif amount > balance:
        flash(f"Payment is more than the balance due ({money(balance)}).", "error")
    else:
        db.execute("INSERT INTO payments (bill_id, amount, method) VALUES (?,?,?)", (bid, amount, method))
        db.commit()
        flash("Payment recorded.", "success")
    return redirect(url_for("bill_detail", bid=bid))


@app.route("/billing/<int:bid>/delete", methods=["POST"])
@login_required
def bill_delete(bid):
    db = get_db()
    db.execute("DELETE FROM bills WHERE id = ?", (bid,))
    db.commit()
    flash("Bill deleted.", "success")
    return redirect(url_for("billing"))


init_db()

if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG", "1") == "1", port=5000)
