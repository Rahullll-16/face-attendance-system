# 🎭 FaceAttend v2 – AI Attendance System (Full Edition)

## ✨ Features
- ✅ Face Recognition Attendance
- 🛡 Liveness Detection (Anti-Spoofing via Eye Blink)
- 🔐 Admin Login (password protected)
- 📧 Email Notifications (student + admin)
- 🤖 GenAI Assistant (Claude-powered, ask anything about attendance)
- 📋 Student Registration with Roll No + Reg No
- 📊 Reports with CSV export
- 🔒 Change Password from Settings

---

## 📁 Project Structure
```
attendance-system/
├── app.py                  ← Flask backend (all APIs)
├── requirements.txt
├── README.md
├── face_data/              ← Auto-created: face encodings
│   └── encodings.pkl
├── database/               ← Auto-created: SQLite DB
│   └── attendance.db
└── templates/
    ├── login.html          ← Admin login
    ├── index.html          ← Mark Attendance + Liveness + AI
    ├── register.html       ← Register students
    └── report.html         ← Reports + Settings
```

---

## ⚙️ Setup

### Step 1: Install Python 3.9+
https://python.org

### Step 2: Install CMake
- **Windows:** https://cmake.org/download/
- **Mac:** `brew install cmake`
- **Linux:** `sudo apt install cmake`

### Step 3: Install Visual C++ Build Tools (Windows only)
https://visualstudio.microsoft.com/visual-cpp-build-tools/

### Step 4: Create Virtual Environment
```bash
python -m venv venv
# Windows:
venv\Scripts\activate
# Mac/Linux:
source venv/bin/activate
```

### Step 5: Install Dependencies
```bash
pip install -r requirements.txt
```
> ⚠️ `face_recognition` compiles dlib — takes 5–10 min first time

### Step 6: Run
```bash
python app.py
```

### Step 7: Open Browser
```
http://localhost:5000
```

---

## 🔐 Default Login
```
Username: admin
Password: admin123
```
> Change password: Reports → Settings → Password tab

---

## 📧 Email Setup (Gmail)

1. Go to Google Account → Security → 2-Step Verification → ON
2. Search "App Passwords" → Generate for "Mail"
3. Copy the 16-char password
4. In Reports → Settings → Email tab:
   - Enable toggle ON
   - Enter your Gmail address
   - Paste App Password
   - Enter admin email to receive alerts
5. Save

---

## 🤖 AI Assistant Setup

The AI assistant uses Claude (claude-sonnet-4-20250514).

**For the assistant to work in the browser**, the Anthropic API must be accessible from your browser (no auth header is sent from frontend—API auth is handled by your deployment).

**Recommended setup for local use:**
Add your Anthropic API key in `index.html` in the fetch headers:
```javascript
headers: {
  'Content-Type': 'application/json',
  'x-api-key': 'YOUR_ANTHROPIC_API_KEY',   // Add this line
  'anthropic-version': '2023-06-01'
}
```

---

## 🛡 Liveness Detection
- Uses Eye Aspect Ratio (EAR) algorithm
- Detects 2 blinks via facial landmarks
- Shows overlay prompt: "Blink twice"
- Progress bar fills as blinks detected
- Prevents photo/video spoofing attacks

---

## 📌 Tips
- Good lighting = better accuracy
- Register 2–3 photos per person for best results
- Tolerance is 50% (adjustable in `app.py` line: `tolerance=0.5`)
