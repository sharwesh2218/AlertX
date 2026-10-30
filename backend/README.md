---
title: AlertX
emoji: 🎥
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
pinned: false
---
# AlertX — Autonomous AI Surveillance & Voice Dispatch 🛡️🤖

**AlertX** is a professional-grade, enterprise-ready AI surveillance platform designed for real-time threat detection and autonomous emergency response. It combines state-of-the-art computer vision (YOLOv8) with advanced Voice AI (Vapi) to create a system that doesn't just watch—it acts.

---

## 🌟 Key Features

### 1. Real-Time AI Monitoring
*   **Intelligent Detection**: Recognizes weapons (knives, guns), physical violence (fights), fire, smoke, and unauthorized intrusions.
*   **Multi-Source Support**: Seamlessly connects to local webcams, IP cameras, or RTSP security streams.
*   **Privacy First**: Secure, token-authenticated video streams with local-first processing.

### 2. Autonomous Voice AI Dispatch (Vapi)
*   **Self-Dispatching**: When a high-priority incident (e.g., a fight or fire) is confirmed, the system autonomously calls emergency services.
*   **Context-Aware AI**: Powered by GPT-4o, the AI dispatcher provides specific details of the incident (location, type of threat, severity) during the call.
*   **Two-Way Interaction**: The AI can communicate with emergency dispatchers to provide live updates.

### 3. Enterprise Security Dashboard
*   **Premium Dark UI**: A sleek, high-performance monitoring console built with Vanilla JS and CSS.
*   **Digital Evidence Console**: Drag-and-drop video files for post-incident AI analysis and forensic logging.
*   **Live Event Logs**: A real-time, deduplicated history of all detected incidents with priority tagging.
*   **Interactive Maps**: integrated Leaflet.js maps for node location tracking and nearby service identification.

### 4. Advanced Security
*   **JWT Authentication**: Secure session management for all administrative actions.
*   **Bcrypt Hashing**: Industry-standard protection for user credentials.
*   **Persistent Configuration**: Saves alert recipients and system settings across reboots.

---

## 🏗️ Technical Architecture

*   **Backend**: FastAPI (Python 3.12+)
*   **AI Engine**: YOLOv8 (Computer Vision) & OpenAI GPT-4o (Reasoning)
*   **Voice Engine**: Vapi (Voice AI Gateway)
*   **Frontend**: Professional HTML5/CSS3 Dashboard (No frameworks required)
*   **Database**: Firebase Firestore (cloud), with an automatic local SQLite fallback for user accounts when Firebase credentials are not configured
*   **Security**: PyJWT & Direct Bcrypt implementation

---

## 🚀 Quick Start

### 1. Prerequisites
*   Python 3.12+
*   A Vapi.ai account (for Voice Dispatch)
*   An SMTP-enabled email (for Email Alerts)

### 2. Installation
```bash
# Clone the repository
git clone https://github.com/your-username/AlertX.git
cd AlertX

# Set up virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\\Scripts\\activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Configuration
Create a `.env` file in the root directory and add your keys:
```env
# API Keys
VAPI_API_KEY=your_vapi_key
VAPI_ASSISTANT_ID=your_assistant_id
VAPI_PHONE_NUMBER_ID=your_random_secret_string
DISPATCH_PHONE_NUMBER=+91XXXXXXXXXX

# Mail Settings
# 📧 Email Alert Configuration (SMTP)
# For Gmail: Use an "App Password" (https://myaccount.google.com/apppasswords)
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=your-app-password

# Deployment
PUBLIC_URL=http://localhost:8000
```

### 4. Launch
```bash
cd backend
python run.py
```
*   **API Docs**: `http://localhost:8000/docs`
*   **Frontend Application**: Lives separately in `../frontend`. Open `../frontend/index.html` via a static local web server (e.g. `cd ../frontend && python -m http.server 5500`) or deploy it to Vercel/Netlify. See `../DEPLOY.md` for full instructions.

---

## 🌐 Public Deployment
AlertX can be deployed publicly for 24/7 monitoring using the included `Dockerfile` and `render.yaml`.

---

## ⚖️ Disclaimer
*AlertX is an AI-assisted tool designed to support security operations. It should not be used as the sole method for emergency dispatch without human overwatch. Use responsibly and in accordance with local regulations.*

---
**Developed with ❤️ by the AlertX Team.**
