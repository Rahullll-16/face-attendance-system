# 🎭 FaceAttend v2.0 – AI Attendance System

Full-featured face recognition attendance system with Admin Login, Liveness Detection, Email Notifications, and GenAI Assistant.

---

## 🆕 What's New in v2.0

| Feature | Description |
|---|---|
| 🔐 Admin Login | Session-based login with hashed password |
| 🛡 Liveness Detection | Blink-based anti-spoofing (3-step check) |
| 📧 Email Notifications | Auto-email on attendance via Gmail |
| 🤖 GenAI Assistant | Ask questions about attendance in natural language |
| 📋 Roll No + Reg No | Full student profile in registration |
| 📊 Enhanced Reports | Confidence score, roll/reg no in table |

---

## 📁 Project Structure

```
attendance-system-v2/
├── app.py                  ← Flask backend (all APIs)
├── requirements.txt
├── README.md
├── face_data/              ← Auto-created
│   └── encodings.pkl       ← Face encodings + roll/reg nos
├── database/               ← Auto-created
│   └── attendance.db       ← SQLite (attendance + users tables)
└── templates/
    ├── login.html          ← Admin login page
    ├── index.html          ← Mark attendance + liveness + AI chat
    ├── register.html       ← Register face with full profile
    └── report.html         ← Reports with export
```

---

## ⚙️ Setup

### Step 1: Install Prerequisites
```bash
# Windows: install CMake + Visual Studio Build Tools first
# Mac:
brew install cmake
# Linux:
sudo apt install cmake build-essential
```

### Step 2: Create Virtual Environment
```bash
python -m venv venv
# Windows:
venv\Scripts\activate
# Mac/Linux:
source venv/bin/activate
```

### Step 3: Install Dependencies
```bash
pip install -r requirements.txt
```
> ⚠️ `face_recognition` compiles dlib — takes 5–15 minutes

### Step 4: Configure Email (Optional)
Edit `app.py` and update:
```python
EMAIL_CONFIG = {
    "sender": "your_gmail@gmail.com",
    "password": "your_16_char_app_password",
    "enabled": True
}
```
To get Gmail App Password: Google Account → Security → 2-Step Verification → App Passwords

### Step 5: Change Admin Password (Recommended)
In `app.py`:
```python
import hashlib
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD_HASH = hashlib.sha256("your_new_password".encode()).hexdigest()
```

### Step 6: Run
```bash
python app.py
```

Open: **http://localhost:5000**
Login with: `admin` / `admin123`

---

## 🛡 Liveness Detection (Anti-Spoofing)

The system requires a 3-step check before marking attendance:

1. **Face Detected** – System confirms a face is visible
2. **Blink Twice** – User must blink 2 times (EAR < 0.22 threshold)
3. **Hold Still** – Hold steady for 1.5 seconds

This prevents someone from showing a photo/printed image to spoof the system.

**EAR** = Eye Aspect Ratio (calculated from 6 eye landmark points via dlib)

---

## 🤖 AI Assistant

The built-in assistant answers attendance questions using Claude AI (falls back to local logic if API unavailable).

Example queries:
- "Who is absent today?"
- "Top 5 most regular students this week"
- "How many students are present today?"
- "Summarize today's attendance"
- "Attendance percentage for Rahul in April"

---

## 📊 Registration Fields

| Field | Required | Purpose |
|---|---|---|
| Full Name | ✅ | Face label |
| Roll No | ✅ | Student ID |
| Registration No | Optional | University ID |
| Email | Optional | Notification email |

---

## 🔒 Security Notes

- Passwords are SHA-256 hashed (upgrade to bcrypt for production)
- Flask sessions expire on browser close
- Change default credentials before deploying
- Use HTTPS in production

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.9+ + Flask |
| Face Recognition | face_recognition + dlib + OpenCV |
| Liveness | Eye Aspect Ratio via face_recognition landmarks |
| Database | SQLite |
| Email | smtplib + Gmail SMTP |
| AI Assistant | Anthropic Claude API (with local fallback) |
| Frontend | HTML5 + CSS3 + Vanilla JS + WebRTC |
