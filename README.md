# AlertX — Autonomous AI Surveillance & Voice Dispatch 🛡️🤖

**AlertX** is an enterprise-grade AI surveillance platform designed for real-time threat detection and autonomous emergency response. It combines computer vision (YOLOv8 + CLIP zero-shot classification + deep learning violence detection) with advanced Voice AI (Vapi.ai) to detect high-priority physical threats and autonomously dispatch emergency services.

---

## 🏛️ System Architecture

```text
┌────────────────────────────────────────────────────────┐
│                   Client Browser                       │
│    (Webcam capture via WebRTC / Canvas Frame Sync)     │
└───────────────▲────────────────────────▲───────────────┘
                │                        │
       Static Assets (HTTPS)       REST API / Token Auth
                │                        │
┌───────────────┴────────┐       ┌───────┴────────────────────────────────────────┐
│     Frontend App       │       │                Backend Server                  │
│  (Vercel / Netlify /   │       │          (Hugging Face Docker Space)           │
│   Cloudflare Pages)    │       │                                                │
│  • index.html          │       │  • FastAPI Application (Python 3.12)          │
│  • app.js              │       │  • YOLOv8 Ensemble (Object / Weapon Detection) │
│  • style.css           │       │  • CLIP Zero-Shot Vision Model                 │
│  • config.js           │       │  • Keras Violence Detection Classifier        │
└────────────────────────┘       └───────┬──────────────┬──────────────┬──────────┘
                                         │              │              │
                                    SMTP Alerts    Voice Calls   Cloud Storage
                                         │              │              │
                                  ┌──────▼──────┐ ┌─────▼────┐ ┌───────▼───────┐
                                  │ Email Alert │ │ Vapi.ai  │ │ Firebase /    │
                                  │ (STARTTLS)  │ │ Voice AI │ │ Local SQLite  │
                                  └─────────────┘ └──────────┘ └───────────────┘
```

---

## 📁 Repository Structure

```text
repo-root/
├── README.md                           # Root project documentation (this file)
├── DEPLOY.md                           # Comprehensive, zero-surprise deployment guide
├── render.yaml                         # Optional Render deployment specification
├── .gitignore                          # Root ignore rules (.DS_Store, .env, *.db)
├── .github/workflows/sync_to_hub.yml   # GitHub Actions automated sync to HF Spaces
├── frontend/                           # Client static application
│   ├── index.html                      # Tactical monitoring dashboard UI
│   ├── style.css                       # Dark-mode dashboard stylesheet
│   ├── app.js                          # Frontend client logic & camera synchronizer
│   └── config.js                       # API endpoint configuration
└── backend/                            # Core API & AI intelligence pipeline
    ├── run.py                          # Application entry point
    ├── requirements.txt                # Python package dependencies
    ├── Dockerfile                      # Non-root container spec for Hugging Face Spaces
    ├── .dockerignore                   # Build exclusion patterns
    ├── .env.example                    # Environment configuration template
    ├── .gitattributes                  # Git LFS tracking rules (*.pt, *.h5)
    ├── .gitignore                      # Backend-specific ignore rules
    ├── README.md                       # Backend documentation with HF front-matter
    ├── backend/                        # FastAPI server package (main, auth, config, models)
    ├── agents/                         # Multi-agent analysis pipeline
    ├── pipeline/                       # Video frame ingestion & YOLO ensemble detector
    ├── utils/                          # Dispatch, email, and cloud integrations
    ├── AI-model/                       # Neural network weight checkpoints
    └── tests/                          # Automated pipeline smoke tests
```

---

## 🌟 Key Features

### 1. Multi-Agent Threat Analysis
*   **Pipeline Flow**: `DetectionAgent` ➔ `ThreatAnalysisAgent` ➔ `ViolenceAgent` (CLIP) ➔ `DecisionAgent` ➔ `AlertAgent` ➔ `LearningAgent`.
*   **Ensemble Intelligence**: Combines real-time object detection with zero-shot scene understanding to drastically reduce false alarms.
*   **Intelligent De-duplication**: Context-aware cooldown logic ensures emergency responders and administrators receive concise notifications without spam.

### 2. Autonomous Emergency Dispatch
*   **AI Voice Agent**: Dispatches real-time automated phone calls via Vapi.ai with situational awareness (incident type, confidence, and timestamp).
*   **Signed Action Links**: Automated alert emails include secure, expiring HMAC-SHA256 tokens allowing one-click emergency dispatch directly from any email client.
*   **STARTTLS Email Dispatch**: Real-time incident alert delivery with attached evidence frames.

### 3. Decoupled Deployment
*   **Static Frontend**: Zero build step; deployable directly to Netlify, Vercel, or Cloudflare Pages.
*   **Containerized Backend**: Configured for direct deployment to Hugging Face Spaces Docker SDK (port 7860) or cloud containers.

---

## 🚀 Deployment

For step-by-step production setup, environment variable requirements, and troubleshooting, read **[DEPLOY.md](./DEPLOY.md)**.

