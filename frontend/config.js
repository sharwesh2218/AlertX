// Optional override if hosting frontend separately (e.g. Vercel) from backend; leave empty for full-stack Railway / HF Spaces / local dev.
const CUSTOM_BACKEND_URL = "";

window.ALERTX_API = CUSTOM_BACKEND_URL || (
    (typeof window !== "undefined" &&
     window.location &&
     (!(window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1") ||
      window.location.port === "8000" ||
      window.location.port === "8080" ||
      window.location.port === "7860"))
        ? window.location.origin
        : "http://localhost:8000"
);

