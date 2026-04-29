from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import cv2
import face_recognition
import numpy as np
import os
import pickle
import sqlite3
from datetime import datetime, date
import base64
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from functools import wraps
import hashlib
import secrets

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)

# ─── Config ─────────────────────────────────────────────────────────────────
FACE_DATA_PATH = "face_data/encodings.pkl"
DB_PATH        = "database/attendance.db"

# EMAIL CONFIG — fill these in
EMAIL_CONFIG = {
    "enabled":   False,          # Set True after filling credentials
    "sender":    "your_email@gmail.com",
    "password":  "your_app_password",   # Gmail App Password
    "smtp_host": "smtp.gmail.com",
    "smtp_port": 587,
    "notify_to": "admin@example.com",   # Where to send alerts
}

# ADMIN CONFIG
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD_HASH = hashlib.sha256("admin123".encode()).hexdigest()  # default: admin123

# ─── Database ────────────────────────────────────────────────────────────────
def init_db():
    os.makedirs("database", exist_ok=True)
    os.makedirs("face_data", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        name            TEXT NOT NULL,
        roll_no         TEXT UNIQUE NOT NULL,
        reg_no          TEXT UNIQUE NOT NULL,
        email           TEXT,
        registered_at   TEXT DEFAULT CURRENT_TIMESTAMP
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS attendance (
        id      INTEGER PRIMARY KEY AUTOINCREMENT,
        roll_no TEXT NOT NULL,
        name    TEXT NOT NULL,
        date    TEXT NOT NULL,
        time    TEXT NOT NULL,
        status  TEXT DEFAULT 'Present',
        liveness_verified INTEGER DEFAULT 0
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS admin_settings (
        key   TEXT PRIMARY KEY,
        value TEXT
    )''')

    conn.commit()
    conn.close()

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# ─── Auth helpers ────────────────────────────────────────────────────────────
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("admin_logged_in"):
            return redirect(url_for("admin_login"))
        return f(*args, **kwargs)
    return decorated

def api_login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("admin_logged_in"):
            return jsonify({"success": False, "message": "Unauthorized"}), 401
        return f(*args, **kwargs)
    return decorated

# ─── Face data helpers ───────────────────────────────────────────────────────
def load_face_data():
    if os.path.exists(FACE_DATA_PATH):
        with open(FACE_DATA_PATH, "rb") as f:
            return pickle.load(f)
    return {"roll_nos": [], "encodings": []}

def save_face_data(data):
    with open(FACE_DATA_PATH, "wb") as f:
        pickle.dump(data, f)

# ─── Email helper ─────────────────────────────────────────────────────────────
def send_email(subject, body, to_email=None):
    if not EMAIL_CONFIG["enabled"]:
        return
    try:
        to = to_email or EMAIL_CONFIG["notify_to"]
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = EMAIL_CONFIG["sender"]
        msg["To"]      = to
        msg.attach(MIMEText(body, "html"))
        with smtplib.SMTP(EMAIL_CONFIG["smtp_host"], EMAIL_CONFIG["smtp_port"]) as s:
            s.starttls()
            s.login(EMAIL_CONFIG["sender"], EMAIL_CONFIG["password"])
            s.sendmail(EMAIL_CONFIG["sender"], to, msg.as_string())
    except Exception as e:
        print(f"Email error: {e}")

def send_attendance_email(user, time_str):
    subject = f"✅ Attendance Marked – {user['name']}"
    body = f"""
    <div style="font-family:sans-serif;background:#0a0a0f;color:#e8e8f0;padding:32px;border-radius:12px">
      <h2 style="color:#00e5a0;margin:0 0 16px">Attendance Confirmed</h2>
      <table style="width:100%;border-collapse:collapse">
        <tr><td style="padding:8px 0;color:#6b6b80">Name</td><td style="font-weight:700">{user['name']}</td></tr>
        <tr><td style="padding:8px 0;color:#6b6b80">Roll No</td><td>{user['roll_no']}</td></tr>
        <tr><td style="padding:8px 0;color:#6b6b80">Reg No</td><td>{user['reg_no']}</td></tr>
        <tr><td style="padding:8px 0;color:#6b6b80">Date</td><td>{date.today().strftime('%d %B %Y')}</td></tr>
        <tr><td style="padding:8px 0;color:#6b6b80">Time</td><td>{time_str}</td></tr>
        <tr><td style="padding:8px 0;color:#6b6b80">Status</td><td style="color:#00e5a0">✅ Present</td></tr>
      </table>
    </div>"""
    # Email the student if they have an email
    if user.get("email"):
        send_email(subject, body, user["email"])
    # Also notify admin
    send_email(f"[FaceAttend] {user['name']} marked attendance", body)

# ─── Routes: Pages ───────────────────────────────────────────────────────────
@app.route("/")
def index():
    if not session.get("admin_logged_in"):
        return redirect(url_for("admin_login"))
    return render_template("index.html")

@app.route("/register")
@login_required
def register():
    return render_template("register.html")

@app.route("/report")
@login_required
def report():
    return render_template("report.html")

@app.route("/login", methods=["GET"])
def admin_login():
    if session.get("admin_logged_in"):
        return redirect(url_for("index"))
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("admin_login"))

# ─── API: Auth ────────────────────────────────────────────────────────────────
@app.route("/api/login", methods=["POST"])
def api_login():
    data     = request.json
    username = data.get("username", "")
    password = data.get("password", "")
    pwd_hash = hashlib.sha256(password.encode()).hexdigest()
    if username == ADMIN_USERNAME and pwd_hash == ADMIN_PASSWORD_HASH:
        session["admin_logged_in"] = True
        session["admin_username"]  = username
        return jsonify({"success": True})
    return jsonify({"success": False, "message": "Invalid username or password."})

# ─── API: Register Face ───────────────────────────────────────────────────────
@app.route("/api/register", methods=["POST"])
@api_login_required
def api_register():
    data    = request.json
    name    = data.get("name", "").strip()
    roll_no = data.get("roll_no", "").strip()
    reg_no  = data.get("reg_no", "").strip()
    email   = data.get("email", "").strip()
    img_b64 = data.get("image", "")

    if not all([name, roll_no, reg_no, img_b64]):
        return jsonify({"success": False, "message": "Name, Roll No, Reg No and photo are required."})

    # Decode image
    try:
        _, encoded = img_b64.split(",", 1)
        img = cv2.imdecode(np.frombuffer(base64.b64decode(encoded), np.uint8), cv2.IMREAD_COLOR)
        rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    except Exception as e:
        return jsonify({"success": False, "message": f"Image error: {e}"})

    encodings = face_recognition.face_encodings(rgb)
    if len(encodings) == 0:
        return jsonify({"success": False, "message": "No face detected. Use clearer lighting."})
    if len(encodings) > 1:
        return jsonify({"success": False, "message": "Multiple faces detected. Only one person should be visible."})

    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO users (name, roll_no, reg_no, email) VALUES (?,?,?,?)",
            (name, roll_no, reg_no, email)
        )
        conn.commit()
    except sqlite3.IntegrityError as e:
        conn.close()
        if "roll_no" in str(e):
            return jsonify({"success": False, "message": f"Roll No '{roll_no}' already exists."})
        return jsonify({"success": False, "message": f"Reg No '{reg_no}' already exists."})
    conn.close()

    fd = load_face_data()
    fd["roll_nos"].append(roll_no)
    fd["encodings"].append(encodings[0])
    save_face_data(fd)

    return jsonify({"success": True, "message": f"✅ {name} registered successfully!"})

# ─── API: Recognize & Mark Attendance ────────────────────────────────────────
@app.route("/api/recognize", methods=["POST"])
def api_recognize():
    data    = request.json
    img_b64 = data.get("image", "")
    liveness_ok = data.get("liveness_verified", False)

    if not img_b64:
        return jsonify({"success": False, "message": "No image received."})

    try:
        _, encoded = img_b64.split(",", 1)
        img = cv2.imdecode(np.frombuffer(base64.b64decode(encoded), np.uint8), cv2.IMREAD_COLOR)
        rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    except Exception as e:
        return jsonify({"success": False, "message": f"Image error: {e}"})

    fd = load_face_data()
    if not fd["encodings"]:
        return jsonify({"success": False, "message": "No registered faces. Please register first."})

    locations = face_recognition.face_locations(rgb)
    encodings = face_recognition.face_encodings(rgb, locations)
    if not encodings:
        return jsonify({"success": False, "message": "No face detected."})

    results = []
    for enc in encodings:
        matches   = face_recognition.compare_faces(fd["encodings"], enc, tolerance=0.5)
        distances = face_recognition.face_distance(fd["encodings"], enc)

        if True in matches:
            idx      = int(np.argmin(distances))
            roll_no  = fd["roll_nos"][idx]
            conf     = round((1 - distances[idx]) * 100, 1)

            conn  = get_db()
            user  = conn.execute("SELECT * FROM users WHERE roll_no=?", (roll_no,)).fetchone()
            today = date.today().isoformat()
            existing = conn.execute(
                "SELECT id FROM attendance WHERE roll_no=? AND date=?", (roll_no, today)
            ).fetchone()

            if existing:
                results.append({"name": user["name"], "roll_no": roll_no,
                                 "reg_no": user["reg_no"], "confidence": conf,
                                 "status": "already_marked"})
            else:
                now = datetime.now()
                conn.execute(
                    "INSERT INTO attendance (roll_no,name,date,time,liveness_verified) VALUES (?,?,?,?,?)",
                    (roll_no, user["name"], now.strftime("%Y-%m-%d"),
                     now.strftime("%H:%M:%S"), int(liveness_ok))
                )
                conn.commit()
                send_attendance_email(dict(user), now.strftime("%H:%M:%S"))
                results.append({"name": user["name"], "roll_no": roll_no,
                                 "reg_no": user["reg_no"], "confidence": conf,
                                 "status": "marked"})
            conn.close()
        else:
            results.append({"name": "Unknown", "confidence": 0, "status": "unknown"})

    return jsonify({"success": True, "results": results})

# ─── API: Liveness check (eye-blink via landmarks) ───────────────────────────
@app.route("/api/liveness_check", methods=["POST"])
def api_liveness_check():
    """
    Receives a frame + landmarks. Computes Eye Aspect Ratio (EAR).
    Frontend sends multiple frames; server returns EAR so frontend can
    detect blink (EAR drops below 0.25).
    """
    data    = request.json
    img_b64 = data.get("image", "")
    if not img_b64:
        return jsonify({"success": False})

    try:
        _, encoded = img_b64.split(",", 1)
        img = cv2.imdecode(np.frombuffer(base64.b64decode(encoded), np.uint8), cv2.IMREAD_COLOR)
        rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    except:
        return jsonify({"success": False, "ear": 0.3, "face_detected": False})

    locations = face_recognition.face_locations(rgb)
    if not locations:
        return jsonify({"success": True, "ear": 0.3, "face_detected": False})

    landmarks_list = face_recognition.face_landmarks(rgb, locations)
    if not landmarks_list:
        return jsonify({"success": True, "ear": 0.3, "face_detected": False})

    lm = landmarks_list[0]

    def ear(eye):
        # Eye Aspect Ratio: vertical / horizontal distances
        A = np.linalg.norm(np.array(eye[1]) - np.array(eye[5]))
        B = np.linalg.norm(np.array(eye[2]) - np.array(eye[4]))
        C = np.linalg.norm(np.array(eye[0]) - np.array(eye[3]))
        return (A + B) / (2.0 * C) if C else 0.3

    left_ear  = ear(lm.get("left_eye",  []))
    right_ear = ear(lm.get("right_eye", []))
    avg_ear   = (left_ear + right_ear) / 2.0 if (lm.get("left_eye") and lm.get("right_eye")) else 0.3

    return jsonify({"success": True, "ear": round(avg_ear, 4), "face_detected": True})

# ─── API: Attendance records ──────────────────────────────────────────────────
@app.route("/api/attendance", methods=["GET"])
@api_login_required
def api_attendance():
    d    = request.args.get("date", "")
    name = request.args.get("name", "")
    conn = get_db()
    q    = "SELECT a.*, u.reg_no FROM attendance a LEFT JOIN users u ON a.roll_no=u.roll_no WHERE 1=1"
    params = []
    if d:
        q += " AND a.date=?"; params.append(d)
    if name:
        q += " AND a.name LIKE ?"; params.append(f"%{name}%")
    q += " ORDER BY a.date DESC, a.time DESC"
    rows = conn.execute(q, params).fetchall()
    conn.close()
    return jsonify({"success": True, "records": [dict(r) for r in rows]})

# ─── API: User list ────────────────────────────────────────────────────────────
@app.route("/api/users", methods=["GET"])
@api_login_required
def api_users():
    conn  = get_db()
    users = conn.execute("SELECT * FROM users ORDER BY name").fetchall()
    conn.close()
    return jsonify({"success": True, "users": [dict(u) for u in users], "count": len(users)})

# ─── API: Delete user ──────────────────────────────────────────────────────────
@app.route("/api/delete_user", methods=["POST"])
@api_login_required
def api_delete_user():
    roll_no = request.json.get("roll_no", "")
    conn    = get_db()
    user    = conn.execute("SELECT * FROM users WHERE roll_no=?", (roll_no,)).fetchone()
    if not user:
        conn.close()
        return jsonify({"success": False, "message": "User not found."})
    conn.execute("DELETE FROM users WHERE roll_no=?", (roll_no,))
    conn.commit()
    conn.close()
    # Remove from face data
    fd = load_face_data()
    if roll_no in fd["roll_nos"]:
        idx = fd["roll_nos"].index(roll_no)
        fd["roll_nos"].pop(idx)
        fd["encodings"].pop(idx)
        save_face_data(fd)
    return jsonify({"success": True, "message": f"'{user['name']}' removed."})

# ─── API: GenAI Assistant ─────────────────────────────────────────────────────
@app.route("/api/ai_query", methods=["POST"])
@api_login_required
def api_ai_query():
    """
    Passes the user query + relevant attendance data to the frontend
    which calls the Anthropic API directly (Claude-in-Claude).
    This endpoint prepares and returns the filtered data + system prompt.
    """
    user_query = request.json.get("query", "")
    today      = date.today().isoformat()

    conn = get_db()
    # Gather relevant data
    today_att   = conn.execute(
        "SELECT a.name, a.roll_no, u.reg_no, a.time, a.status FROM attendance a LEFT JOIN users u ON a.roll_no=u.roll_no WHERE a.date=?", (today,)
    ).fetchall()
    week_att = conn.execute(
        "SELECT a.name, a.roll_no, a.date, a.time FROM attendance a WHERE a.date >= date('now','-7 days') ORDER BY a.date DESC"
    ).fetchall()
    all_users = conn.execute("SELECT name, roll_no, reg_no FROM users").fetchall()
    conn.close()

    data_context = {
        "today": today,
        "today_attendance": [dict(r) for r in today_att],
        "week_attendance":  [dict(r) for r in week_att],
        "all_registered":   [dict(u) for u in all_users],
        "total_registered": len(all_users),
        "today_present_count": len(today_att),
    }

    system_prompt = f"""You are an intelligent attendance assistant for FaceAttend, an AI-powered attendance management system.

Answer questions strictly based on the attendance data provided below. Be concise, helpful, and use emojis where appropriate.

If information is not in the data, respond with "No record found for that query."

Today's date: {today}

ATTENDANCE DATA:
{json.dumps(data_context, indent=2)}

Rules:
- Answer ONLY from the data above
- For absent students: compare all_registered vs today_attendance
- For percentages: use week_attendance data
- Be friendly and professional
- Use tables or lists for multi-item answers
- Keep responses under 200 words unless listing many records"""

    return jsonify({
        "success":       True,
        "system_prompt": system_prompt,
        "user_query":    user_query,
        "data_summary":  {
            "today_present":   len(today_att),
            "total_registered": len(all_users),
            "today":           today,
        }
    })

# ─── API: Email config update ─────────────────────────────────────────────────
@app.route("/api/update_email_config", methods=["POST"])
@api_login_required
def api_update_email():
    global EMAIL_CONFIG
    d = request.json
    EMAIL_CONFIG.update({
        "enabled":  d.get("enabled", False),
        "sender":   d.get("sender", ""),
        "password": d.get("password", ""),
        "notify_to":d.get("notify_to", ""),
    })
    return jsonify({"success": True, "message": "Email config updated."})

# ─── API: Change password ─────────────────────────────────────────────────────
@app.route("/api/change_password", methods=["POST"])
@api_login_required
def api_change_password():
    global ADMIN_PASSWORD_HASH
    d           = request.json
    current     = d.get("current", "")
    new_pwd     = d.get("new_password", "")
    if hashlib.sha256(current.encode()).hexdigest() != ADMIN_PASSWORD_HASH:
        return jsonify({"success": False, "message": "Current password is incorrect."})
    if len(new_pwd) < 6:
        return jsonify({"success": False, "message": "New password must be at least 6 characters."})
    ADMIN_PASSWORD_HASH = hashlib.sha256(new_pwd.encode()).hexdigest()
    return jsonify({"success": True, "message": "Password updated successfully."})

if __name__ == "__main__":
    init_db()
    print("🚀 FaceAttend running at http://localhost:5000")
    print("📋 Default login → username: admin | password: admin123")
    app.run(debug=True, host="0.0.0.0", port=5000)
