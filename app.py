from flask import Flask, render_template, request, jsonify, redirect, url_for, session
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
import hashlib
import secrets
from functools import wraps

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)

# ─── Config ───────────────────────────────────────────────────────
FACE_DATA_PATH = "face_data/encodings.pkl"
DB_PATH = "database/attendance.db"

# Email config – update these with your Gmail credentials
EMAIL_CONFIG = {
    "sender": "your_email@gmail.com",
    "password": "your_app_password",   # Use Gmail App Password
    "enabled": False                    # Set True after configuring email
}

# Admin credentials (change before deploying!)
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD_HASH = hashlib.sha256("admin123".encode()).hexdigest()

# ─── Database Setup ───────────────────────────────────────────────
def init_db():
    os.makedirs("database", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            reg_no TEXT,
            roll_no TEXT,
            date TEXT NOT NULL,
            time TEXT NOT NULL,
            status TEXT DEFAULT 'Present',
            confidence REAL DEFAULT 0
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            reg_no TEXT,
            roll_no TEXT,
            email TEXT,
            registered_at TEXT
        )
    ''')
    conn.commit()
    conn.close()

# ─── Face Data Helpers ────────────────────────────────────────────
def load_face_data():
    os.makedirs("face_data", exist_ok=True)
    if os.path.exists(FACE_DATA_PATH):
        with open(FACE_DATA_PATH, "rb") as f:
            return pickle.load(f)
    return {"names": [], "encodings": [], "reg_nos": [], "roll_nos": []}

def save_face_data(data):
    with open(FACE_DATA_PATH, "wb") as f:
        pickle.dump(data, f)

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# ─── Auth Decorator ───────────────────────────────────────────────
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('admin_logged_in'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

# ─── Email Helper ─────────────────────────────────────────────────
def send_attendance_email(name, email, reg_no, roll_no, time_str):
    if not EMAIL_CONFIG["enabled"] or not email:
        return False
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"✅ Attendance Marked – {name}"
        msg["From"] = EMAIL_CONFIG["sender"]
        msg["To"] = email
        html = f"""
        <html><body style="font-family: Arial, sans-serif; background:#0a0a0f; color:#e8e8f0; padding:30px;">
        <div style="max-width:500px; margin:0 auto; background:#111118; border:1px solid #2a2a3a; border-radius:16px; padding:30px;">
          <h2 style="color:#00e5a0; margin-bottom:8px;">✅ Attendance Marked</h2>
          <p style="color:#6b6b80; margin-bottom:24px; font-size:14px;">FaceAttend System Notification</p>
          <table style="width:100%; border-collapse:collapse;">
            <tr><td style="padding:10px 0; color:#6b6b80; font-size:13px; border-bottom:1px solid #2a2a3a;">Name</td><td style="padding:10px 0; font-weight:bold; border-bottom:1px solid #2a2a3a;">{name}</td></tr>
            <tr><td style="padding:10px 0; color:#6b6b80; font-size:13px; border-bottom:1px solid #2a2a3a;">Roll No</td><td style="padding:10px 0; font-weight:bold; border-bottom:1px solid #2a2a3a;">{roll_no or 'N/A'}</td></tr>
            <tr><td style="padding:10px 0; color:#6b6b80; font-size:13px; border-bottom:1px solid #2a2a3a;">Reg No</td><td style="padding:10px 0; font-weight:bold; border-bottom:1px solid #2a2a3a;">{reg_no or 'N/A'}</td></tr>
            <tr><td style="padding:10px 0; color:#6b6b80; font-size:13px; border-bottom:1px solid #2a2a3a;">Date</td><td style="padding:10px 0; font-weight:bold; border-bottom:1px solid #2a2a3a;">{datetime.now().strftime('%d %B %Y')}</td></tr>
            <tr><td style="padding:10px 0; color:#6b6b80; font-size:13px;">Time</td><td style="padding:10px 0; font-weight:bold;">{time_str}</td></tr>
          </table>
          <p style="margin-top:24px; font-size:12px; color:#6b6b80;">This is an automated notification from FaceAttend.</p>
        </div></body></html>
        """
        msg.attach(MIMEText(html, "html"))
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(EMAIL_CONFIG["sender"], EMAIL_CONFIG["password"])
            server.sendmail(EMAIL_CONFIG["sender"], email, msg.as_string())
        return True
    except Exception as e:
        print(f"Email error: {e}")
        return False

# ─── Routes ───────────────────────────────────────────────────────
@app.route("/")
@login_required
def index():
    return render_template("index.html")

@app.route("/register")
@login_required
def register():
    return render_template("register.html")

@app.route("/report")
def report():
    return render_template("report.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        data = request.json
        username = data.get("username", "")
        password = data.get("password", "")
        pw_hash = hashlib.sha256(password.encode()).hexdigest()
        if username == ADMIN_USERNAME and pw_hash == ADMIN_PASSWORD_HASH:
            session['admin_logged_in'] = True
            # Clear student session
            session.pop('student_roll', None)
            session.pop('student_name', None)
            return jsonify({"success": True})
        return jsonify({"success": False, "message": "Invalid credentials"})
    return render_template("login.html")

@app.route("/student_login", methods=["POST"])
def student_login():
    data = request.json

    roll_no = data.get("roll_no", "").strip()
    reg_no = data.get("reg_no", "").strip()
    name = data.get("name", "").strip()

    conn = get_db()
    user = conn.execute(
        "SELECT * FROM users WHERE TRIM(LOWER(name)) = TRIM(LOWER(?)) AND TRIM(roll_no) = TRIM(?) AND TRIM(reg_no) = TRIM(?)",
        (name, roll_no, reg_no)
    ).fetchone()
    conn.close()

    if user:
        session['student_name'] = user['name']
        session['student_roll'] = user['roll_no']

        return jsonify({
            "success": True,
            "message": "Login successful",
            "user": dict(user)
        })
    else:
        return jsonify({
        "success": False,
        "message": "Invalid student details"
    })
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for('login'))

# ─── Student login with face ─────────────────────────────────────
@app.route("/api/face_login", methods=["POST"])
def face_login():
    data = request.json
    image_data = data.get("image")

    if not image_data:
        return jsonify({"success": False, "message": "No image received"})

    try:
        # Base64 → image
        img_bytes = base64.b64decode(image_data.split(',')[1])
        nparr = np.frombuffer(img_bytes, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    except Exception as e:
        return jsonify({"success": False, "message": f"Image decode error: {str(e)}"})

    # Detect face
    face_locations = face_recognition.face_locations(frame)
    if not face_locations:
        return jsonify({"success": False, "message": "No face found"})

    encodings = face_recognition.face_encodings(frame, face_locations)

    # Load saved encodings
    if not os.path.exists(FACE_DATA_PATH):
        return jsonify({"success": False, "message": "No registered faces found"})

    face_data = load_face_data()
    if not face_data["encodings"]:
        return jsonify({"success": False, "message": "No registered faces found"})

    for encoding in encodings:
        matches = face_recognition.compare_faces(face_data["encodings"], encoding)

        if True in matches:
            index = matches.index(True)
            name = face_data["names"][index]
            roll_no = face_data.get("roll_nos", [""] * len(face_data["names"]))[index] if index < len(face_data.get("roll_nos", [])) else ""
            reg_no = face_data.get("reg_nos", [""] * len(face_data["names"]))[index] if index < len(face_data.get("reg_nos", [])) else ""

            # DB lookup for full user info
            conn = get_db()
            user = conn.execute(
                "SELECT * FROM users WHERE LOWER(name)=LOWER(?)",
                (name,)
            ).fetchone()
            conn.close()

            if user:
                # Use DB data (most accurate)
                session['student_name'] = user["name"]
                session['student_roll'] = user["roll_no"]
                session.pop('admin_logged_in', None)

                return jsonify({
                    "success": True,
                    "name": user["name"]
                })
            else:
                # Fallback: use data from pkl file
                session['student_name'] = name
                session['student_roll'] = roll_no
                session.pop('admin_logged_in', None)

                return jsonify({
                    "success": True,
                    "name": name
                })

    return jsonify({"success": False, "message": "Face not recognized"})
# ─── API: Register Face ───────────────────────────────────────────
@app.route("/api/register", methods=["POST"])
@login_required
def api_register():
    data = request.json
    name = data.get("name", "").strip()
    reg_no = data.get("reg_no", "").strip()
    roll_no = data.get("roll_no", "").strip()
    email = data.get("email", "").strip()
    image_data = data.get("image", "")

    if not name or not image_data:
        return jsonify({"success": False, "message": "Name and image are required."})

    try:
        header, encoded = image_data.split(",", 1)
        img_bytes = base64.b64decode(encoded)
        np_arr = np.frombuffer(img_bytes, np.uint8)
        img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        rgb_img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    except Exception as e:
        return jsonify({"success": False, "message": f"Image decode error: {str(e)}"})

    encodings = face_recognition.face_encodings(rgb_img)
    if len(encodings) == 0:
        return jsonify({"success": False, "message": "No face detected. Please try again with a clearer photo."})
    if len(encodings) > 1:
        return jsonify({"success": False, "message": "Multiple faces detected. Please ensure only one face is visible."})

    face_data = load_face_data()

    if name in face_data["names"]:
        return jsonify({"success": False, "message": f"'{name}' is already registered."})

    face_data["names"].append(name)
    face_data["encodings"].append(encodings[0])
    if "reg_nos" not in face_data: face_data["reg_nos"] = []
    if "roll_nos" not in face_data: face_data["roll_nos"] = []
    face_data["reg_nos"].append(reg_no)
    face_data["roll_nos"].append(roll_no)
    save_face_data(face_data)

    # Save to users table
    conn = get_db()
    try:
        conn.execute("INSERT OR IGNORE INTO users (name, reg_no, roll_no, email, registered_at) VALUES (?,?,?,?,?)",
                     (name, reg_no, roll_no, email, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
    except: pass
    finally: conn.close()

    return jsonify({"success": True, "message": f"✅ '{name}' registered successfully!"})

# ─── API: Liveness Check ──────────────────────────────────────────
@app.route("/api/liveness_check", methods=["POST"])
@login_required
def api_liveness_check():
    """Analyze a frame for eye aspect ratio to detect blinks"""
    data = request.json
    image_data = data.get("image", "")
    try:
        header, encoded = image_data.split(",", 1)
        img_bytes = base64.b64decode(encoded)
        np_arr = np.frombuffer(img_bytes, np.uint8)
        img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        rgb_img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    except:
        return jsonify({"success": False, "ear": 0})

    face_locations = face_recognition.face_locations(rgb_img)
    if not face_locations:
        return jsonify({"success": False, "message": "No face detected", "ear": 0})

    landmarks_list = face_recognition.face_landmarks(rgb_img, face_locations)
    if not landmarks_list:
        return jsonify({"success": False, "ear": 0})

    landmarks = landmarks_list[0]

    def eye_aspect_ratio(eye_pts):
        import math
        def dist(a, b): return math.sqrt((a[0]-b[0])**2 + (a[1]-b[1])**2)
        A = dist(eye_pts[1], eye_pts[5])
        B = dist(eye_pts[2], eye_pts[4])
        C = dist(eye_pts[0], eye_pts[3])
        return (A + B) / (2.0 * C) if C > 0 else 0

    left_eye = landmarks.get("left_eye", [])
    right_eye = landmarks.get("right_eye", [])
    ear = 0
    if left_eye and right_eye:
        ear = (eye_aspect_ratio(left_eye) + eye_aspect_ratio(right_eye)) / 2.0

    return jsonify({"success": True, "ear": round(ear, 4), "face_detected": True})

# ─── API: Recognize & Mark Attendance ────────────────────────────
@app.route("/api/recognize", methods=["POST"])
@login_required
def api_recognize():
    data = request.json
    image_data = data.get("image", "")
    if not image_data:
        return jsonify({"success": False, "message": "No image received."})

    try:
        header, encoded = image_data.split(",", 1)
        img_bytes = base64.b64decode(encoded)
        np_arr = np.frombuffer(img_bytes, np.uint8)
        img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        rgb_img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    except Exception as e:
        return jsonify({"success": False, "message": f"Image error: {str(e)}"})

    face_data = load_face_data()
    if not face_data["encodings"]:
        return jsonify({"success": False, "message": "No registered faces found. Please register first."})

    face_locations = face_recognition.face_locations(rgb_img)
    face_encodings = face_recognition.face_encodings(rgb_img, face_locations)

    if not face_encodings:
        return jsonify({"success": False, "message": "No face detected in frame."})

    results = []
    for encoding in face_encodings:
        matches = face_recognition.compare_faces(face_data["encodings"], encoding, tolerance=0.5)
        face_distances = face_recognition.face_distance(face_data["encodings"], encoding)

        if True in matches:
            best_idx = np.argmin(face_distances)
            name = face_data["names"][best_idx]
            reg_no = face_data.get("reg_nos", [""] * len(face_data["names"]))[best_idx] if best_idx < len(face_data.get("reg_nos", [])) else ""
            roll_no = face_data.get("roll_nos", [""] * len(face_data["names"]))[best_idx] if best_idx < len(face_data.get("roll_nos", [])) else ""
            confidence = round((1 - face_distances[best_idx]) * 100, 1)

            today = datetime.now().strftime("%Y-%m-%d")
            conn = get_db()
            c = conn.cursor()
            c.execute("SELECT id FROM attendance WHERE name=? AND date=?", (name, today))
            existing = c.fetchone()

            if existing:
                results.append({"name": name, "reg_no": reg_no, "roll_no": roll_no, "confidence": confidence, "status": "already_marked"})
            else:
                now = datetime.now()
                time_str = now.strftime("%H:%M:%S")
                c.execute("INSERT INTO attendance (name, reg_no, roll_no, date, time, confidence) VALUES (?,?,?,?,?,?)",
                          (name, reg_no, roll_no, now.strftime("%Y-%m-%d"), time_str, confidence))
                conn.commit()

                # Get email from users table
                user_row = conn.execute("SELECT email FROM users WHERE name=?", (name,)).fetchone()
                email = user_row["email"] if user_row else ""
                send_attendance_email(name, email, reg_no, roll_no, time_str)

                results.append({"name": name, "reg_no": reg_no, "roll_no": roll_no, "confidence": confidence, "status": "marked", "time": time_str})
            conn.close()
        else:
            results.append({"name": "Unknown", "confidence": 0, "status": "unknown"})

    return jsonify({"success": True, "results": results})

# ─── API: Get Attendance Records ──────────────────────────────────
@app.route("/api/attendance", methods=["GET"])
def api_attendance():
    date_filter = request.args.get("date", "")
    conn = get_db()

    is_admin = session.get('admin_logged_in')
    student_roll = session.get('student_roll')

    if is_admin:
        # 👉 ADMIN → full data
        if date_filter:
            rows = conn.execute("""
                SELECT name, reg_no, roll_no, date, time, status, confidence
                FROM attendance
                WHERE date=?
                ORDER BY time DESC
            """, (date_filter,)).fetchall()
        else:
            rows = conn.execute("""
                SELECT name, reg_no, roll_no, date, time, status, confidence
                FROM attendance
                ORDER BY date DESC, time DESC
            """).fetchall()

    elif student_roll:
        # 👉 STUDENT → only his data
        if date_filter:
            rows = conn.execute("""
                SELECT name, reg_no, roll_no, date, time, status, confidence
                FROM attendance
                WHERE roll_no=? AND date=?
                ORDER BY time DESC
            """, (student_roll, date_filter)).fetchall()
        else:
            rows = conn.execute("""
                SELECT name, reg_no, roll_no, date, time, status, confidence
                FROM attendance
                WHERE roll_no=?
                ORDER BY date DESC, time DESC
            """, (student_roll,)).fetchall()

    else:
        rows = []

    conn.close()
    return jsonify({"success": True, "records": [dict(r) for r in rows]})
# ─── API: Get Registered Users ────────────────────────────────────
@app.route("/api/users", methods=["GET"])
@login_required
def api_users():
    conn = get_db()
    rows = conn.execute("SELECT name, reg_no, roll_no, email, registered_at FROM users ORDER BY name").fetchall()
    conn.close()
    users = [dict(r) for r in rows]
    face_data = load_face_data()
    return jsonify({"success": True, "users": users, "count": len(face_data["names"])})

# ─── API: Delete User ─────────────────────────────────────────────
@app.route("/api/delete_user", methods=["POST"])
@login_required
def api_delete_user():
    name = request.json.get("name", "")
    face_data = load_face_data()
    if name in face_data["names"]:
        idx = face_data["names"].index(name)
        face_data["names"].pop(idx)
        face_data["encodings"].pop(idx)
        if "reg_nos" in face_data and idx < len(face_data["reg_nos"]): face_data["reg_nos"].pop(idx)
        if "roll_nos" in face_data and idx < len(face_data["roll_nos"]): face_data["roll_nos"].pop(idx)
        save_face_data(face_data)
        conn = get_db()
        conn.execute("DELETE FROM users WHERE name=?", (name,))
        conn.commit()
        conn.close()
        return jsonify({"success": True, "message": f"'{name}' removed."})
    return jsonify({"success": False, "message": "User not found."})

# ─── API: AI Assistant ────────────────────────────────────────────
@app.route("/api/ai_query", methods=["POST"])
@login_required
def api_ai_query():
    import urllib.request
    query = request.json.get("query", "")
    if not query:
        return jsonify({"success": False, "message": "No query provided."})

    today = datetime.now().strftime("%Y-%m-%d")
    conn = get_db()

    # Gather relevant data
    today_records = conn.execute(
        "SELECT name, reg_no, roll_no, time, confidence FROM attendance WHERE date=? ORDER BY time", (today,)
    ).fetchall()
    all_users = conn.execute("SELECT name, reg_no, roll_no FROM users").fetchall()
    week_records = conn.execute(
        "SELECT name, date, time FROM attendance WHERE date >= date(?, '-7 days') ORDER BY date DESC", (today,)
    ).fetchall()
    month_records = conn.execute(
        "SELECT name, COUNT(*) as count FROM attendance WHERE date >= date(?, '-30 days') GROUP BY name ORDER BY count DESC",
        (today,)
    ).fetchall()
    conn.close()

    present_today = [dict(r) for r in today_records]
    all_registered = [dict(r) for r in all_users]
    absent_today = [u for u in all_registered if u["name"] not in [p["name"] for p in present_today]]
    weekly = [dict(r) for r in week_records]
    monthly_counts = [dict(r) for r in month_records]

    context = f"""
Today's Date: {today}
Total Registered Students/Staff: {len(all_registered)}
Present Today ({len(present_today)}): {json.dumps(present_today, indent=2)}
Absent Today ({len(absent_today)}): {json.dumps(absent_today, indent=2)}
Last 7 Days Records: {json.dumps(weekly[:50], indent=2)}
Monthly Attendance Counts (last 30 days): {json.dumps(monthly_counts, indent=2)}
"""

    prompt = f"""You are an intelligent attendance assistant for an AI-powered face recognition system.
Answer the user's question strictly based on the data provided below.
If the information is not available in the data, respond with "No record found for this query."
Be concise, accurate, and helpful. Use bullet points or tables where appropriate.

=== ATTENDANCE DATA ===
{context}
======================

User Question: {query}"""

    try:
        req_data = json.dumps({
            "model": "claude-sonnet-4-20250514",
            "max_tokens": 1000,
            "messages": [{"role": "user", "content": prompt}]
        }).encode()

        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=req_data,
            headers={
                "Content-Type": "application/json",
                "anthropic-version": "2023-06-01"
            }
        )
        with urllib.request.urlopen(req, timeout=30) as response:
            result = json.loads(response.read())
            answer = result["content"][0]["text"]
            return jsonify({"success": True, "answer": answer})
    except Exception as e:
        # Fallback: Answer from data directly
        answer = generate_local_answer(query, present_today, absent_today, monthly_counts, today)
        return jsonify({"success": True, "answer": answer})

def generate_local_answer(query, present, absent, monthly, today):
    q = query.lower()
    if "absent" in q:
        if not absent: return "✅ Everyone is present today!"
        names = ", ".join([a["name"] for a in absent])
        return f"❌ **Absent today ({len(absent)}):** {names}"
    elif "present" in q and "today" in q:
        if not present: return "No attendance recorded yet today."
        names = "\n".join([f"• {p['name']} ({p['time']})" for p in present])
        return f"✅ **Present today ({len(present)}):**\n{names}"
    elif "top" in q or "regular" in q:
        if not monthly: return "No data available."
        top = monthly[:5]
        return "🏆 **Most Regular (last 30 days):**\n" + "\n".join([f"• {r['name']}: {r['count']} days" for r in top])
    elif "summarize" in q or "summary" in q:
        return f"📊 **Today's Summary ({today}):**\n• Present: {len(present)}\n• Absent: {len(absent)}"
    return "I couldn't find specific data for your query. Please ask about today's attendance, absent students, or top attendees."

# ─── API: Email Config Update ─────────────────────────────────────
@app.route("/api/email_config", methods=["POST"])
@login_required
def api_email_config():
    data = request.json
    EMAIL_CONFIG["sender"] = data.get("sender", EMAIL_CONFIG["sender"])
    EMAIL_CONFIG["password"] = data.get("password", EMAIL_CONFIG["password"])
    EMAIL_CONFIG["enabled"] = data.get("enabled", False)
    return jsonify({"success": True, "message": "Email config updated."})

# ─── API: Stats ───────────────────────────────────────────────────
@app.route("/api/stats", methods=["GET"])
@login_required
def api_stats():
    today = datetime.now().strftime("%Y-%m-%d")
    conn = get_db()
    total = conn.execute("SELECT COUNT(*) FROM attendance").fetchone()[0]
    today_count = conn.execute("SELECT COUNT(*) FROM attendance WHERE date=?", (today,)).fetchone()[0]
    users_count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    days = conn.execute("SELECT COUNT(DISTINCT date) FROM attendance").fetchone()[0]
    conn.close()
    return jsonify({"total": total, "today": today_count, "users": users_count, "days": days})

if __name__ == "__main__":
    init_db()
    print("FaceAttend running at http://localhost:5000")
    app.run(debug=True, host="0.0.0.0", port=5000)