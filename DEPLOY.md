# AlertX — Production Deployment Guide 🚀

AlertX is partitioned into two independently deployable applications:
1. **Backend Server** (FastAPI, YOLOv8, CLIP, Keras) hosted on **Hugging Face Spaces** (Docker SDK).
2. **Frontend Dashboard** (Static HTML5/CSS3/Vanilla JS) hosted on **Vercel, Netlify, or Cloudflare Pages**.

Follow this guide sequentially to achieve a zero-surprise deployment.

---

## Part 1: Deploy Backend to Hugging Face Spaces

### 1. Create the Space
1. Log into your [Hugging Face](https://huggingface.co) account.
2. Click **New Space** (`https://huggingface.co/new-space`).
3. Set:
   - **Space Name**: e.g., `AlertX`
   - **License**: `mit` or `apache-2.0`
   - **Space SDK**: **Docker** (Blank)
   - **Visibility**: **Public** (required for client browsers to reach API)
4. Click **Create Space**.

### 2. Configure Environment Variables & Secrets
Navigate to **Settings ➔ Variables and secrets** in your Space dashboard:
* Add the variables specified in the [Environment Variables Reference](#environment-variables-reference) table below.
* **Important**:
  * Set `SECRET_KEY` to a random 64-character hexadecimal string:
    ```bash
    python3 -c "import secrets; print(secrets.token_hex(32))"
    ```
  * Note down your Space's Direct URL: `https://<owner>-<space-name>.hf.space` (you can also view this under the embed/direct link options in Space settings).
  * Set `PUBLIC_URL` to `https://<owner>-<space-name>.hf.space` (no trailing slash).

### 3. Deploy Backend Code
Push your code using GitHub Actions or direct Git push:
* **Option A (GitHub Actions)**: Add your Hugging Face write token to GitHub repository **Settings ➔ Secrets and variables ➔ Actions ➔ New repository secret** as `HF_TOKEN`. Pushing to `main` will automatically trigger `.github/workflows/sync_to_hub.yml`.
* **Option B (Direct Git)**:
  ```bash
  cd backend
  git remote add hf https://huggingface.co/spaces/<owner>/<space-name>
  git push hf main --force
  ```

### 4. Verify Backend Readiness
* **Build Time Note**: The initial Docker build compiles heavy dependencies (PyTorch, TensorFlow, OpenCV, CLIP) and pre-downloads the ViT weights. This can take 5 to 10 minutes.
* **Cold Starts**: Free-tier CPU Spaces sleep when inactive. Ping the Space URL or open the web view 2–3 minutes before live evaluations.
* **Test Endpoints**:
  * Open `https://<owner>-<space>.hf.space/health` ➔ should return `{"status":"ok","model_loaded":true}`.
  * Open `https://<owner>-<space>.hf.space/docs` ➔ should display interactive Swagger API documentation.

---

## Part 2: Deploy Frontend to Static Hosting

### 1. Configure the API Target
Open `frontend/config.js` and set `window.ALERTX_API` to your Hugging Face Space Direct URL:
```javascript
// Backend base URL. HTTPS, no trailing slash.
window.ALERTX_API = "https://<owner>-<space>.hf.space";
```

### 2. Deploy to Your Chosen Platform

#### Deploying on Vercel
1. In Vercel, click **Add New ➔ Project** and import the AlertX repository.
2. In Project Settings:
   - **Root Directory**: `frontend`
   - **Framework Preset**: `Other`
   - **Build Command**: *Leave empty* (no build step)
   - **Output Directory**: `.` (or empty)
3. Click **Deploy**. Note down your assigned domain (e.g., `https://alertx.vercel.app`).

#### Deploying on Netlify
1. In Netlify, click **Add new site ➔ Import an existing project**.
2. Select your repository and configure:
   - **Base directory**: `frontend`
   - **Build command**: *Leave empty*
   - **Publish directory**: `frontend` (or `.` if base directory is set)
3. Click **Deploy Site**.

#### Deploying on Cloudflare Pages
1. In Cloudflare Dashboard, go to **Workers & Pages ➔ Create application ➔ Pages ➔ Connect to Git**.
2. Set:
   - **Root directory**: `frontend`
   - **Build command**: *Leave empty*
   - **Build output directory**: `.`
3. Click **Save and Deploy**.

---

## Part 3: Finalize CORS & Inter-Service URLs

1. Return to your Hugging Face Space: **Settings ➔ Variables and secrets**.
2. Set:
   - `FRONTEND_URL`: Your live frontend domain, e.g., `https://alertx.vercel.app` (no trailing slash).
   - `FRONTEND_ORIGIN` *(Optional for strict CORS)*: Set to `https://alertx.vercel.app`.
3. Restart the Hugging Face Space (via **Factory restart** or **Restart this Space**).

---

## Environment Variables Reference

| Variable Name | Required? | Example Value | Target Platform | Description |
|---|:---:|---|:---:|---|
| `SECRET_KEY` | **Yes** | `8f9b3... (64 hex chars)` | Backend (HF Space) | Signs JWT tokens & HMAC dispatch links. |
| `PUBLIC_URL` | **Yes** | `https://username-alertx.hf.space` | Backend (HF Space) | Public backend URL for callbacks & email links. |
| `FRONTEND_URL` | **Yes** | `https://alertx.vercel.app` | Backend (HF Space) | Web dashboard URL embedded in notification emails. |
| `FRONTEND_ORIGIN`| No | `https://alertx.vercel.app` | Backend (HF Space) | Allowed CORS origins. Leave unset/empty to allow all (`*`). |
| `PORT` | No | `7860` | Backend (HF Space) | Internal container port (preconfigured to 7860). |
| `VAPI_API_KEY` | Optional | `vapi_live_...` | Backend (HF Space) | Vapi Voice AI integration token. |
| `VAPI_ASSISTANT_ID` | Optional | `asst_abc123` | Backend (HF Space) | Vapi Agent Assistant ID. |
| `VAPI_PHONE_NUMBER_ID` | Optional | `ph_xyz789` | Backend (HF Space) | Vapi registered phone number ID. |
| `DISPATCH_PHONE_NUMBER` | Optional | `+14155552671` | Backend (HF Space) | Destination number called during emergencies. |
| `MAIL_SERVER` | Optional | `smtp.gmail.com` | Backend (HF Space) | SMTP server hostname. |
| `MAIL_PORT` | Optional | `587` | Backend (HF Space) | SMTP server port (STARTTLS). |
| `MAIL_USERNAME` | Optional | `security@example.com` | Backend (HF Space) | Email address sending alert notifications. |
| `MAIL_PASSWORD` | Optional | `app-password-code` | Backend (HF Space) | SMTP App Password. |
| `MAIL_RECIPIENT` | Optional | `guard@example.com` | Backend (HF Space) | Default email recipient for critical alerts. |
| `FIREBASE_SERVICE_ACCOUNT` | Optional | `{"type":"service_account",...}` | Backend (HF Space) | One-line JSON service account. Unset uses SQLite. |
| `ALERTX_CAMERA` | No | *Unset on Cloud* | Backend (HF Space) | Set only for local RTSP/IP cameras. |
| `ALLOW_PUBLIC_IMAGE_HOST` | No | `false` | Backend (HF Space) | Opt-in flag to upload incident frames publicly. |
| `ALERTX_API` in `config.js` | **Yes** | `https://username-alertx.hf.space` | Frontend (`config.js`) | Direct API endpoint accessed by browser client. |

---

## 🛠️ Troubleshooting

### 1. "Backend URL not configured - edit frontend/config.js"
* **Cause**: Your frontend is running on a public domain, but `frontend/config.js` still has `http://localhost:8000` or an empty string.
* **Fix**: Edit `frontend/config.js`, set `window.ALERTX_API = "https://your-space.hf.space"`, commit, and redeploy frontend.

### 2. Mixed Content Warning / API Blocked
* **Cause**: The frontend is served over `https://`, but `window.ALERTX_API` is set to `http://` (or localhost). Modern browsers block insecure requests.
* **Fix**: Ensure your backend URL uses `https://`.

### 3. CORS Error in Browser Console (`Access-Control-Allow-Origin`)
* **Cause**: Backend `FRONTEND_ORIGIN` does not match your frontend URL (e.g. wrong protocol or trailing slash).
* **Fix**: In your Hugging Face Space settings, set `FRONTEND_ORIGIN` to empty (defaults to `*`) or provide the exact origin without a trailing slash (`https://your-frontend.vercel.app`).

### 4. 401 Unauthorized / Sessions Expire Immediately After Space Rebuild
* **Cause**: `SECRET_KEY` was not configured in Space secrets, causing the backend to generate a new ephemeral key on every startup.
* **Fix**: Generate a persistent 64-character hex string and save it as `SECRET_KEY` in your Hugging Face Space settings.

### 5. Hugging Face Space Status Shows "Building" For A Long Time
* **Cause**: The PyTorch, TensorFlow, OpenCV, and CLIP layers are large (>1GB total).
* **Fix**: Wait for the first build to complete (5–10 minutes). Subsequent builds leverage Docker caching.

### 6. Webcam Access Blocked
* **Cause**: WebRTC and media device access (`navigator.mediaDevices.getUserMedia`) require a secure context (`https://` or `localhost`).
* **Fix**: Deploy the frontend on an HTTPS provider (Vercel, Netlify, or Cloudflare Pages) or test locally on `localhost`.

