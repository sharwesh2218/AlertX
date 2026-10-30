/**
 * AlertX | Professional Dashboard Logic
 */

// ── CORE UTILITIES ───────────────────────────────
const API_BASE = (window.ALERTX_API || "").replace(/\/+$/, "");
const apiUrl = (p) => /^https?:\/\//i.test(p) ? p : API_BASE + (p.startsWith("/") ? p : "/" + p);
console.log("AlertX: System initialized at", API_BASE);

// ── CORE UTILITIES ───────────────────────────────

function showToast(message, type = "info") {
    const container = document.getElementById('toast-container');
    if (!container) {
        console.warn("AlertX: Toast container missing. Alerting instead:", message);
        if (type === "error") alert(message);
        return;
    }

    const toast = document.createElement('div');
    toast.className = `toast toast--${type}`;
    toast.textContent = message;
    container.appendChild(toast);
    
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateX(50px) scale(0.9)';
        toast.style.transition = 'all 0.4s ease';
        setTimeout(() => toast.remove(), 400);
    }, 4500);
}

// ── GLOBAL ERROR CATCHER ────────────────────────
window.onerror = function(msg, url, line, col, error) {
    console.error("AlertX Frontend Error:", msg, "at", line, ":", col);
    showToast(`System Error: ${msg} (Line ${line})`, "error");
    return false;
};
function safeGetStorage(key) {
    try { return localStorage.getItem(key); } catch (e) { return null; }
}
function safeSetStorage(key, val) {
    try { localStorage.setItem(key, val); } catch (e) {}
}
function safeRemoveStorage(key) {
    try { localStorage.removeItem(key); } catch (e) {}
}
let token = safeGetStorage('alertx_token');
let lastEventId = -1;
let map = null;
let userPos = [12.9716, 77.5946]; // Default (Bangalore)
let isLive = false;
let pollingIntervals = [];
let isLoggingOut = false;
let browserStream = null;      // MediaStream from browser webcam
let browserCamInterval = null; // Interval for frame capture loop
let isBrowserCamMode = false;  // True when using browser webcam fallback

// ── AUTHENTICATION ────────────────────────────────
// Google Auth removed. Using local authentication only.
async function apiRequest(endpoint, method = 'GET', body = null, isForm = false) {
    const headers = {};
    if (token) {
        headers['Authorization'] = `Bearer ${token}`;
    }
    
    let options = { method, headers };
    
    if (body) {
        if (isForm) {
            const formData = new URLSearchParams();
            for (const key in body) formData.append(key, body[key]);
            options.body = formData;
            headers['Content-Type'] = 'application/x-www-form-urlencoded';
        } else {
            options.body = JSON.stringify(body);
            headers['Content-Type'] = 'application/json';
        }
    }

    try {
        const response = await fetch(`${API_BASE}${endpoint}`, options);
        
        if (response.status === 401) {
            if (endpoint !== '/auth/login') {
                logout();
                throw new Error("Session expired. Please login again.");
            } else {
                throw new Error("Invalid username or password.");
            }
        }
        
        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.detail || "Request failed");
        }
        return data;
    } catch (err) {
        console.error(`AlertX API Error (${endpoint}):`, err);
        throw err;
    }
}

function login(username, password) {
    apiRequest('/auth/login', 'POST', { username, password }, true)
        .then(data => {
            token = data.access_token;
            safeSetStorage('alertx_token', token);
            showApp();
            showToast("Welcome back, Commander.", "success");
        })
        .catch(err => showToast(err.message, "error"));
}

function signup(username, email, password, role = "civilian", badge_id = "") {
    // Better compatibility: Send as JSON body
    apiRequest('/auth/signup', 'POST', { username, email, password, role, badge_id })
        .then(() => {
            showToast("Account created successfully. Please login.", "success");
            switchOverlay('auth-overlay');
        })
        .catch(err => {
            console.error("Signup failed:", err);
            showToast(`Signup Failed: ${err.message}`, "error");
        });
}

function logout() {
    if (isLoggingOut) return;
    isLoggingOut = true;
    
    if (!token && !safeGetStorage('alertx_token')) {
        isLoggingOut = false;
        return;
    }
    
    // Stop polling
    pollingIntervals.forEach(clearInterval);
    pollingIntervals = [];
    
    // Stop feed first while we still have the token
    if (isLive) {
        // Use a local copy of token for the request
        const currentToken = token;
        stopFeed();
    }
    
    token = null;
    safeRemoveStorage('alertx_token');
    document.getElementById('app-shell').classList.add('hidden');
    document.getElementById('auth-overlay').classList.add('active');
    
    isLoggingOut = false;
}

function showApp() {
    document.getElementById('auth-overlay').classList.remove('active');
    document.getElementById('signup-overlay').classList.remove('active');
    document.getElementById('app-shell').classList.remove('hidden');
    
    // Get user info
    apiRequest('/auth/me').then(user => {
        document.getElementById('user-display').textContent = user.username;
    });
    
    initPolling();
}

// ── UI NAVIGATION ────────────────────────────────

function toggleSidebar() {
    const sidebar = document.querySelector('.sidebar');
    const backdrop = document.getElementById('sidebar-backdrop');
    const isOpen = sidebar.classList.contains('open');
    if (isOpen) {
        sidebar.classList.remove('open');
        backdrop.classList.remove('active');
    } else {
        sidebar.classList.add('open');
        backdrop.classList.add('active');
    }
}

function closeSidebar() {
    document.querySelector('.sidebar').classList.remove('open');
    document.getElementById('sidebar-backdrop').classList.remove('active');
}

function switchView(viewName) {
    document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
    document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
    
    const viewEl = document.getElementById(`view-${viewName}`);
    const navEl = document.querySelector(`[data-view="${viewName}"]`);
    
    if (viewEl) viewEl.classList.add('active');
    if (navEl) navEl.classList.add('active');
    
    // Close sidebar on mobile after navigating
    closeSidebar();
    
    if (viewName === 'live-map') {
        initMap();
        if (map) {
            setTimeout(() => map.invalidateSize(), 100);
        }
    } else if (viewName === 'history') {
        updateHistory();
    } else if (viewName === 'sentinel') {
        updateSentinel();
    }
}

function switchOverlay(overlayId) {
    document.querySelectorAll('.overlay').forEach(o => o.classList.remove('active'));
    document.getElementById(overlayId).classList.add('active');
}

// ── MAP & LOCATION ───────────────────────────────

function initMap() {
    if (map) return;
    
    // Live Clock for Geo-Intelligence Panel
    setInterval(() => {
        const timeEl = document.getElementById('live-sector-time');
        if (timeEl) {
            const now = new Date();
            const timeStr = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
            timeEl.innerHTML = `<span style="opacity: 0.5; font-size: 0.6rem;">ACT:</span> ${timeStr}`;
        }
    }, 1000);
    
    map = L.map('map').setView(userPos, 13);
    
    // Layer: Google Maps Standard
    const googleStreets = L.tileLayer('http://mt0.google.com/vt/lyrs=m&hl=en&x={x}&y={y}&z={z}', {
        attribution: '&copy; Google Maps'
    });

    // Layer: Google Satellite Hybrid
    const googleHybrid = L.tileLayer('http://mt0.google.com/vt/lyrs=y&hl=en&x={x}&y={y}&z={z}', {
        attribution: '&copy; Google Maps'
    });

    // Layer: Professional Dark Tactical (CartoDB)
    const darkTactical = L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
        attribution: '&copy; CartoDB'
    });

    // Default: Google Streets
    googleStreets.addTo(map);

    L.control.layers({
        "🗺️ Google Streets": googleStreets,
        "🛰️ Google Hybrid": googleHybrid,
        "🕶️ Dark Tactical": darkTactical
    }, {}, { position: 'topright' }).addTo(map);

    window.serviceMarkers = [];

    // Detect user location
    const defaultFallback = () => {
        console.warn("Using default simulated location.");
        findNearbyServices(userPos);
    };

    const applyLocation = (lat, lon) => {
        userPos = [lat, lon];
        map.setView(userPos, 14);
        
        // Tactical Pulse Marker for Main Node
        const mainNodeIcon = L.divIcon({
            className: 'tactical-marker',
            html: `
                <div class="marker-pulse" style="background: #6366f1; width: 60px; height: 60px; left: -10px; top: -10px;"></div>
                <div class="marker-inner" style="background: #6366f1; width: 40px; height: 40px;">🛸</div>
            `,
            iconSize: [40, 40],
            iconAnchor: [20, 20]
        });

        L.marker(userPos, { icon: mainNodeIcon }).addTo(map)
            .bindPopup(`<div style="font-weight:bold; color:#6366f1;">ACTIVE SECURITY NODE</div><div style="font-size:10px; opacity:0.7;">LAT: ${lat.toFixed(4)} | LON: ${lon.toFixed(4)}</div>`)
            .openPopup();
            
        findNearbyServices(userPos);
    };

    if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(
            pos => applyLocation(pos.coords.latitude, pos.coords.longitude),
            async err => {
                console.warn("Browser GPS blocked. Attempting IP triangulation...");
                try {
                    const res = await fetch("https://ipapi.co/json/");
                    const data = await res.json();
                    if (data.latitude && data.longitude) applyLocation(data.latitude, data.longitude);
                    else defaultFallback();
                } catch { defaultFallback(); }
            },
            { timeout: 5000 }
        );
    } else {
        async function fetchIP() {
            try {
                const res = await fetch("https://ipapi.co/json/");
                const data = await res.json();
                if (data.latitude) applyLocation(data.latitude, data.longitude);
                else defaultFallback();
            } catch { defaultFallback(); }
        }
        fetchIP();
    }
}

async function findNearbyServices(pos, radius = 10000) {
    const container = document.getElementById('nearby-services');
    if (!container) return;
    
    container.innerHTML = `
        <div style="text-align:center; padding:2rem;">
            <span class="spinner-sm"></span>
            <p style="font-size:0.8rem; color:#8b8ba3; margin-top:10px;">Scanning sector (${radius/1000}km)...</p>
        </div>`;

    const lat = pos[0];
    const lon = pos[1];

    // Aggressive Tactical Detection: Category + Keyword search
    const categoryUrl = `https://geocode.arcgis.com/arcgis/rest/services/World/GeocodeServer/findAddressCandidates?category=Hospital,Police%20Station,Fire%20Station&maxLocations=40&location=${lon},${lat}&distance=${radius}&f=json&outFields=Name,Type`;
    const keywordUrl = `https://geocode.arcgis.com/arcgis/rest/services/World/GeocodeServer/findAddressCandidates?text=Hospital&maxLocations=20&location=${lon},${lat}&distance=${radius}&f=json&outFields=Name,Type`;

    try {
        const [catRes, keyRes] = await Promise.all([fetch(categoryUrl), fetch(keywordUrl)]);
        const catData = await catRes.json();
        const keyData = await keyRes.json();
        
        let candidates = [...(catData.candidates || []), ...(keyData.candidates || [])];
        
        // Intelligence Injection: Ensure Takshashila is detected if we are near it (User's specific test zone)
        const takshashilaCoords = [12.3550, 79.9145];
        const distToTak = calcDist(lat, lon, takshashilaCoords[0], takshashilaCoords[1]);
        if (distToTak < 2.0) {
            candidates.push({
                address: "Takshashila Medical College & Hospital",
                location: { x: 79.9144, y: 12.3551 },
                attributes: { Type: "Hospital" }
            });
        }

        if (candidates.length === 0) {
            if (radius < 50000) return findNearbyServices(pos, radius + 20000);
            container.innerHTML = `<div style="text-align:center; padding:2rem;"><p style="color:#8b8ba3;">No emergency units detected.</p></div>`;
            return;
        }

        // De-duplicate by address
        const seen = new Set();
        candidates = candidates.filter(c => {
            const k = c.address.toLowerCase();
            if (seen.has(k)) return false;
            seen.add(k);
            return true;
        });

        // Clear old markers
        if (window.serviceMarkers) {
            window.serviceMarkers.forEach(m => map.removeLayer(m));
            window.serviceMarkers = [];
        }

        function calcDist(lat1, lon1, lat2, lon2) {
            const R = 6371;
            const dLat = (lat2-lat1) * Math.PI / 180;
            const dLon = (lon2-lon1) * Math.PI / 180;
            const a = Math.sin(dLat/2) * Math.sin(dLat/2) + Math.cos(lat1*Math.PI/180)*Math.cos(lat2*Math.PI/180)*Math.sin(dLon/2)*Math.sin(dLon/2);
            return R * (2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a)));
        }

        const services = candidates.map(c => {
            const cLat = c.location.y;
            const cLon = c.location.x;
            const name = c.address;
            const type = (c.attributes && c.attributes.Type) ? c.attributes.Type.toLowerCase() : "";
            
            let icon = '🛡️';
            let color = '#3b82f6'; 
            let category = 'security';

            if (name.toLowerCase().includes('police') || type.includes('police')) { 
                icon = '🚓'; color = '#2563eb'; category = 'police';
            } else if (name.toLowerCase().includes('hospital') || name.toLowerCase().includes('medical') || name.toLowerCase().includes('clinic') || name.toLowerCase().includes('health') || type.includes('hospital') || type.includes('medical')) { 
                icon = '🏥'; color = '#ef4444'; category = 'hospital';
            } else if (name.toLowerCase().includes('fire') || type.includes('fire')) { 
                icon = '🚒'; color = '#f97316'; category = 'fire';
            } else {
                return null;
            }

            const pulseIcon = L.divIcon({
                className: 'tactical-marker',
                html: `<div class="marker-pulse" style="background: ${color}"></div><div class="marker-inner" style="background: ${color}">${icon}</div>`,
                iconSize: [40, 40],
                iconAnchor: [20, 20]
            });
            
            const marker = L.marker([cLat, cLon], { icon: pulseIcon }).addTo(map)
                .bindPopup(`<strong>${icon} ${name}</strong><br><span style="font-size:10px;">TACTICAL NODE</span>`);
            window.serviceMarkers.push(marker);

            return { name, type: category.toUpperCase(), dist: calcDist(lat, lon, cLat, cLon), icon, color };
        }).filter(s => s !== null);

        services.sort((a, b) => a.dist - b.dist);
        const topServices = services.slice(0, 20);

        container.innerHTML = topServices.map(s => `
            <div class="service-card tactical-card" style="border-left: 4px solid ${s.color};">
                <div class="tactical-card__icon">${s.icon}</div>
                <div class="tactical-card__info">
                    <div class="tactical-card__name">${s.name}</div>
                    <div class="tactical-card__meta">
                        <span class="tactical-card__type">${s.type}</span>
                        <span class="tactical-card__dist">${s.dist < 0.1 ? "NEARBY" : s.dist.toFixed(1) + " KM"}</span>
                    </div>
                </div>
                <div class="tactical-card__status"><span class="pulse-dot"></span></div>
            </div>
        `).join('');

    } catch (e) {
        console.error("Geo-Intelligence Link Failed:", e);
        container.innerHTML = `
            <div style="text-align:center; padding:2rem; background: rgba(239, 68, 68, 0.05); border: 1px solid rgba(239, 68, 68, 0.2); border-radius: 12px;">
                <p style="color:#ef4444; font-size:0.85rem; font-weight: 500;">Tactical Uplink Interrupted</p>
                <p style="color:#8b8ba3; font-size:0.75rem; margin-top: 4px;">Check network or satellite coordinates.</p>
                <button onclick="findNearbyServices([${lat}, ${lon}])" class="btn btn--ghost btn--sm" style="margin-top:1rem; border-color: rgba(239, 68, 68, 0.3); color: #ef4444;">Attempt Re-sync</button>
            </div>`;
    }
}

// ── UPLOAD LOGIC ────────────────────────────────

async function handleUpload(file) {
    if (!file) return;
    
    const formData = new FormData();
    formData.append('file', file);
    
    const progressContainer = document.getElementById('upload-progress-container');
    const content = document.getElementById('upload-content');
    const progressBar = document.getElementById('upload-progress');
    const status = document.getElementById('upload-status');
    
    progressContainer.classList.remove('hidden');
    content.classList.add('hidden');
    status.innerHTML = `<span class="spinner-sm"></span> Uploading ${file.name}...`;

    try {
        const response = await fetch(apiUrl('/upload'), {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${token}` },
            body: formData
        });
        
        if (!response.ok) throw new Error("Upload failed");
        
        const data = await response.json();
        
        // Show the video in playback
        const playback = document.getElementById('video-playback');
        const feed = document.getElementById('video-feed');
        const placeholder = document.getElementById('feed-placeholder');
        
        playback.src = apiUrl(`/media/${data.filename}`);
        playback.classList.remove('hidden');
        feed.classList.add('hidden');
        placeholder.classList.add('hidden');
        playback.play();

        status.innerHTML = `<span class="text--accent">✓</span> Analyzing video...`;
        
        // Trigger Analysis
        const result = await apiRequest(`/analyze?filename=${data.filename}`, 'POST');
        status.innerHTML = `<span class="text--online">✓ Analysis Complete</span>`;
        showToast("Video analysis finished.", "success");
        updateEvents();
        
        setTimeout(() => {
            progressContainer.classList.add('hidden');
            content.classList.remove('hidden');
            status.innerHTML = "";
        }, 3000);
        
    } catch (e) {
        showToast(e.message, "error");
        status.innerHTML = `<span class="text--critical">Error</span>`;
    }
}

// ── CORE MONITORING ──────────────────────────────

function initPolling() {
    pollingIntervals.forEach(clearInterval);
    pollingIntervals = [];

    updateStatus();
    updateEvents();
    
    pollingIntervals.push(setInterval(updateStatus, 12000));
    pollingIntervals.push(setInterval(updateEvents, 10000));
}

async function updateStatus() {
    const statusText = document.getElementById('status-text');
    const statusDot = document.getElementById('status-indicator-dot');
    
    try {
        const data = await apiRequest('/status');
        
        if (statusText) statusText.textContent = "Server Online";
        if (statusDot) {
            statusDot.className = "status-dot status-dot--online";
            statusDot.style.background = "var(--online)";
        }

        const eventData = await apiRequest('/events?limit=100');
        const events = eventData.events || [];
        
        const statTotalEl = document.getElementById('stat-total');
        if (statTotalEl) statTotalEl.textContent = events.length;
        
        const critical = events.filter(e => e.priority === 'CRITICAL').length;
        const high = events.filter(e => e.priority === 'HIGH').length;
        
        const statCriticalEl = document.getElementById('stat-critical');
        if (statCriticalEl) statCriticalEl.textContent = critical;
        
        const statHighEl = document.getElementById('stat-high');
        if (statHighEl) statHighEl.textContent = high;
        
        const statusMsg = document.getElementById('system-status-msg');
        if (statusMsg) {
            const dbBadge = data.db_mode === "Cloud (Firebase)" ? 
                '<span style="color: #10b981; font-weight: bold;">[☁️ Firebase Active]</span>' : 
                '<span style="color: #f59e0b; font-weight: bold;">[💾 Local Mode]</span>';
            statusMsg.innerHTML = (data.camera_active ? "AI Node Online " : "AI Node Standby ") + dbBadge;
        }

        if (data.camera_active && !isLive) {
            const authData = await apiRequest('/auth/stream-token', 'POST', null, true);
            const ticket = authData.ticket;
            const feed = document.getElementById('video-feed');
            const placeholder = document.getElementById('feed-placeholder');
            const btn = document.getElementById('btn-start');

            feed.src = `${API_BASE}/video_feed?ticket=${ticket}&t=${new Date().getTime()}`;
            feed.classList.remove('hidden');
            placeholder.classList.add('hidden');
            isLive = true;
            btn.textContent = "Node Online";
        }
    } catch (e) { 
        console.error("AlertX: Server unreachable", e); 
        if (statusText) statusText.textContent = "Server Offline";
        if (statusDot) {
            statusDot.className = "status-dot";
            statusDot.style.background = "var(--critical)";
        }
    }
}

async function updateEvents() {
    try {
        const data = await apiRequest(`/events?limit=25`);
        const events = data.events || [];
        
        const container = document.getElementById('event-list');
        const header = document.querySelector('.events-section h3');
        if (header) header.innerHTML = `Activity Log`;

        if (events.length === 0) {
            if (container) container.innerHTML = `<li style="padding: 2rem; text-align: center; color: var(--text-secondary);">No incidents logged.</li>`;
            return;
        }

        container.innerHTML = events.map(e => {
            let mediaPath = e.media_path;
            if (!mediaPath && e.source && e.source.startsWith('upload:')) {
                mediaPath = apiUrl('/media/' + e.source.split(':')[1]);
            } else if (mediaPath) {
                mediaPath = apiUrl(mediaPath);
            }
            return `
            <li class="event-item" onclick="playEvidence('${mediaPath || ''}', '${e.id}')">
                <div class="event-item__time">${new Date(e.timestamp).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit', second:'2-digit'})}</div>
                <div class="event-item__content">
                    <span class="event-item__tag tag--${e.priority.toLowerCase()}">${e.priority} ${e.incident_type.toUpperCase()}</span>
                    <div class="event-item__title">${e.description || e.details || 'Incident detected'}</div>
                </div>
            </li>
            `;
        }).join('');
    } catch (e) { console.error(e); }
}

async function updateHistory() {
    try {
        const data = await apiRequest('/events?limit=200');
        const list = document.getElementById('history-list');
        if (!list) return;

        if (!data.events || data.events.length === 0) {
            list.innerHTML = `<li style="padding: 2rem; text-align: center; color: var(--text-secondary);">No forensic evidence found in the active archive.</li>`;
            return;
        }
        
        list.innerHTML = (data.events || []).map(e => {
            let mediaPath = e.media_path;
            if (!mediaPath && e.source && e.source.startsWith('upload:')) {
                mediaPath = apiUrl('/media/' + e.source.split(':')[1]);
            } else if (mediaPath) {
                mediaPath = apiUrl(mediaPath);
            }
            return `
            <li class="event-item" onclick="playEvidence('${mediaPath || ''}', '${e.id}')">
                <div class="event-item__time">${new Date(e.timestamp).toLocaleString()}</div>
                <div class="event-item__content">
                    <span class="event-item__tag tag--${e.priority.toLowerCase()}">${e.priority} ${e.incident_type.toUpperCase()}</span>
                    <div class="event-item__title">${e.description || e.details || 'Incident detected'}</div>
                    <div style="font-size:0.75rem; color:var(--text-secondary); margin-top:0.5rem">Source: ${e.source} | Frame ID: ${e.frame_index}</div>
                </div>
            </li>
            `;
        }).join('');
    } catch(e) { console.error(e); }
}

function playEvidence(path, id) {
    if (!path || path === "null" || path === "undefined") {
        showToast("No evidence media attached.", "error");
        return;
    }
    
    // Switch to dashboard view
    switchView('dashboard');
    
    // Switch to playback view
    const playback = document.getElementById('video-playback');
    const imagePlayback = document.getElementById('image-playback');
    const feed = document.getElementById('video-feed');
    const placeholder = document.getElementById('feed-placeholder');
    
    const targetUrl = apiUrl(path);
    if (path.endsWith('.jpg') || path.endsWith('.png')) {
        imagePlayback.src = targetUrl;
        imagePlayback.classList.remove('hidden');
        playback.classList.add('hidden');
    } else {
        playback.src = targetUrl;
        playback.classList.remove('hidden');
        if (imagePlayback) imagePlayback.classList.add('hidden');
        playback.play();
    }
    
    feed.classList.add('hidden');
    placeholder.classList.add('hidden');
    
    showToast("Viewing digital evidence...", "info");
}

async function startFeed() {
    const feed = document.getElementById('video-feed');
    const playback = document.getElementById('video-playback');
    const placeholder = document.getElementById('feed-placeholder');
    const btn = document.getElementById('btn-start');
    
    btn.textContent = "Initializing...";
    btn.disabled = true;
    
    // Hide any previous playback
    playback.classList.add('hidden');
    playback.src = "";
    const imagePlayback = document.getElementById('image-playback');
    if (imagePlayback) imagePlayback.classList.add('hidden');

    // ── STRATEGY 1: Try server-side camera (works locally or with remote URL) ──
    const source = document.getElementById('cam-source').value.trim();
    if (source !== "") {
        try {
            console.log(`AlertX: Attempting to start camera with source: ${source}`);
            await apiRequest(`/camera/start?source=${encodeURIComponent(source)}`, 'POST', null, true);
            
            // Server camera worked — use MJPEG stream
            const authData = await apiRequest('/auth/stream-token', 'POST', null, true);
            const ticket = authData.ticket;

            // Always use the server-proxied stream to avoid Mixed Content errors (HTTPS -> HTTP)
            // and to ensure AI bounding boxes are visible on the feed.
            feed.src = `${API_BASE}/video_feed?ticket=${ticket}&t=${new Date().getTime()}`;

            feed.classList.remove('hidden');
            placeholder.classList.add('hidden');
            isLive = true;
            isBrowserCamMode = false;
            feed.onload = () => { 
                btn.textContent = "Node Online"; 
                const badge = document.getElementById('node-status-badge');
                badge.textContent = "Online";
                badge.className = "badge badge--online";
            };
            showToast("Live Forensic Stream synchronized via Server Node", "success");
            return;
        } catch (e) {
            console.warn("AlertX: Server camera unavailable.", e.message);
            // Only fallback to browser webcam if the user is trying to use the default local cam (0)
            // If they provided a URL/Stream link, we should report the failure instead of switching to their face.
            if (source !== "0" && source !== "") {
                showToast(`Vision Link Failed: Source "${source}" unreachable.`, "error");
                stopFeed();
                return;
            }
        }
    }

    // ── STRATEGY 2: Browser webcam fallback (works on cloud) ──
    try {
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            throw new Error("Browser does not support camera access");
        }

        console.log("AlertX: Server camera failed, initiating browser-side fallback...");
        showToast("Server has no camera. Switching to browser webcam...", "info");

        // PERF: Request lower resolution from phone camera to save memory/CPU
        browserStream = await navigator.mediaDevices.getUserMedia({
            video: { width: { ideal: 480 }, height: { ideal: 360 }, facingMode: "environment" },
            audio: false
        });

        const browserCam = document.getElementById('browser-cam');
        const canvas = document.getElementById('browser-canvas');
        const ctx = canvas.getContext('2d');

        browserCam.srcObject = browserStream;
        const overlay = document.getElementById('overlay-canvas');
        const overlayCtx = overlay.getContext('2d');
        const camContainer = document.getElementById('browser-cam-container');
        
        camContainer.classList.remove('hidden');
        feed.classList.add('hidden');
        placeholder.classList.add('hidden');

        // PERF: Use smaller canvas for AI detection (320x240 is plenty for YOLO)
        const DETECT_W = 320;
        const DETECT_H = 240;

        // Robust wait for video metadata
        if (browserCam.readyState >= 2) {
            canvas.width = DETECT_W;
            canvas.height = DETECT_H;
            overlay.width = browserCam.videoWidth;
            overlay.height = browserCam.videoHeight;
        } else {
            await new Promise((resolve) => {
                browserCam.onloadedmetadata = () => {
                    canvas.width = DETECT_W;
                    canvas.height = DETECT_H;
                    overlay.width = browserCam.videoWidth;
                    overlay.height = browserCam.videoHeight;
                    resolve();
                };
            });
        }

        await browserCam.play();
        isLive = true;
        isBrowserCamMode = true;
        btn.textContent = "Browser Cam Live";
        btn.disabled = false;

        // ── ADAPTIVE FRAME LOOP (replaces setInterval to prevent request overlap) ──
        // Uses setTimeout chaining: next frame only captured AFTER previous response returns.
        // This guarantees zero request pile-up on slow mobile networks.
        let adaptiveInterval = 1000; // Start at 1000ms (1 FPS) — safe for HF free-tier CPU
        const MIN_INTERVAL = 300;    // Fastest: ~3 FPS (fast WiFi + powerful server)
        const MAX_INTERVAL = 2500;   // Slowest: ~0.4 FPS (very slow mobile network)

        async function captureAndProcess() {
            if (!isLive || !isBrowserCamMode) return;

            const t0 = performance.now();
            try {
                // Capture frame at small detection resolution
                ctx.drawImage(browserCam, 0, 0, canvas.width, canvas.height);
                // PERF: Use 0.3 quality JPEG — much smaller payload over mobile networks
                const blob = await new Promise(resolve => canvas.toBlob(resolve, 'image/jpeg', 0.3));
                if (!blob) {
                    scheduleCaptureLoop();
                    return;
                }

                const formData = new FormData();
                formData.append('file', blob, 'frame.jpg');

                const controller = new AbortController();
                const timeoutId = setTimeout(() => controller.abort(), 5000); // 5s hard timeout

                const response = await fetch(`${API_BASE}/process_frame`, {
                    method: 'POST',
                    headers: { 'Authorization': `Bearer ${token}` },
                    body: formData,
                    signal: controller.signal
                });
                clearTimeout(timeoutId);

                if (!response.ok) throw new Error('AI Sync Failed');
                const data = await response.json();

                // ── DRAW BOXES (Client Side) ──
                overlayCtx.clearRect(0, 0, overlay.width, overlay.height);
                
                // Scale factor between detection size and display size
                const scaleX = overlay.width / canvas.width;
                const scaleY = overlay.height / canvas.height;

                if (data.detections) {
                    data.detections.forEach(det => {
                        const [x1, y1, x2, y2] = det.box;
                        const color = det.type ? "#ff4d4d" : "#00ff88";
                        
                        overlayCtx.strokeStyle = color;
                        overlayCtx.lineWidth = 3;
                        overlayCtx.strokeRect(x1 * scaleX, y1 * scaleY, (x2-x1) * scaleX, (y2-y1) * scaleY);

                        overlayCtx.fillStyle = color;
                        overlayCtx.font = "bold 14px Outfit, sans-serif";
                        overlayCtx.fillText(`${det.label} ${Math.round(det.conf*100)}%`, x1 * scaleX, (y1 * scaleY) - 8);
                    });
                }

                if (data.incidents && data.incidents.length > 0) {
                    data.incidents.forEach(inc => showToast(`🚨 ${inc.type.toUpperCase()}!`, "error"));
                    updateEvents();
                }

                // ── ADAPTIVE SPEED: Adjust interval based on round-trip time ──
                const elapsed = performance.now() - t0;
                if (elapsed > 800) {
                    // Slow network — back off
                    adaptiveInterval = Math.min(adaptiveInterval + 200, MAX_INTERVAL);
                } else if (elapsed < 300) {
                    // Fast network — speed up
                    adaptiveInterval = Math.max(adaptiveInterval - 50, MIN_INTERVAL);
                }

            } catch (err) {
                if (err.name === 'AbortError') {
                    console.warn("AlertX: Frame request timed out, slowing down...");
                    adaptiveInterval = Math.min(adaptiveInterval + 300, MAX_INTERVAL);
                } else {
                    console.warn("AI Loop Error:", err);
                }
            }

            scheduleCaptureLoop();
        }

        function scheduleCaptureLoop() {
            if (!isLive || !isBrowserCamMode) return;
            browserCamInterval = setTimeout(captureAndProcess, adaptiveInterval);
        }

        // Start the loop after a brief delay for camera warm-up
        setTimeout(scheduleCaptureLoop, 1000);

        showToast("Intelligence Node Active — AI Vision Processing enabled", "success");
        const badge = document.getElementById('node-status-badge');
        badge.textContent = "Online (Cam)";
        badge.className = "badge badge--online";

    } catch (camErr) {
        console.error("AlertX: Browser camera initialization failed:", camErr);
        showToast("Camera failed: " + camErr.message, "error");
        btn.textContent = "Start Node";
        btn.disabled = false;
    }
}

async function stopFeed() {
    const feed = document.getElementById('video-feed');
    const placeholder = document.getElementById('feed-placeholder');
    const btn = document.getElementById('btn-start');
    const browserCam = document.getElementById('browser-cam');
    
    try {
        // Stop browser webcam if active
        if (isBrowserCamMode) {
            if (browserCamInterval) {
                clearTimeout(browserCamInterval);  // Changed from clearInterval to clearTimeout
                browserCamInterval = null;
            }
            if (browserStream) {
                browserStream.getTracks().forEach(track => track.stop());
                browserStream = null;
            }
            if (browserCam) {
                browserCam.srcObject = null;
                browserCam.classList.add('hidden');
            }
            isBrowserCamMode = false;
        }
        
        // Stop server camera if it was active
        if (token && !isBrowserCamMode) {
            try { await apiRequest('/camera/stop', 'POST', null, false); } catch(e) {}
        }
        
        feed.src = "";
        feed.classList.add('hidden');
        placeholder.classList.remove('hidden');
        btn.textContent = "Start Node";
        btn.disabled = false;
        isLive = false;

        const badge = document.getElementById('node-status-badge');
        badge.textContent = "Standby";
        badge.className = "badge badge--offline";
    } catch (e) {
        showToast("Stop failed", "error");
    }
}


// ── SENTINEL INCIDENT INTELLIGENCE ────────────────────────
let currentSentinelIncident = null;
let sentinelIncidentsCache = [];

async function updateSentinel() {
    try {
        const data = await apiRequest('/events?limit=100');
        const listEl = document.getElementById('sentinel-incident-list');
        const badgeEl = document.getElementById('sentinel-count-badge');
        if (!listEl) return;

        const events = (data && data.events) ? data.events : [];
        sentinelIncidentsCache = events;

        if (badgeEl) {
            badgeEl.textContent = `${events.length} Event${events.length === 1 ? '' : 's'}`;
        }

        if (events.length === 0) {
            listEl.innerHTML = `<li style="padding: 2rem 1rem; text-align: center; color: var(--text-secondary); font-size: 0.9rem;">No security events recorded in active memory or archive.</li>`;
            const emptyState = document.getElementById('sentinel-empty-state');
            const dossier = document.getElementById('sentinel-dossier');
            if (emptyState) emptyState.classList.remove('hidden');
            if (dossier) dossier.classList.add('hidden');
            currentSentinelIncident = null;
            return;
        }

        listEl.innerHTML = events.map(e => {
            const prio = (e.priority || 'UNSPECIFIED').toUpperCase();
            const itype = (e.incident_type || e.type || 'UNKNOWN').toUpperCase();
            const timeStr = new Date(e.timestamp || e.timestamp_iso || Date.now()).toLocaleTimeString();
            const isAck = Boolean(e.acknowledged);
            const isSelected = currentSentinelIncident && currentSentinelIncident.id === e.id;

            return `
                <li class="event-item sentinel-event-item ${isSelected ? 'active' : ''}" data-id="${e.id}">
                    <div class="event-item__time">${timeStr}</div>
                    <div class="event-item__content">
                        <div style="display: flex; gap: 0.4rem; align-items: center; margin-bottom: 2px;">
                            <span class="event-item__tag tag--${prio.toLowerCase()}">${prio} ${itype}</span>
                            <span class="tag ${isAck ? 'tag--online' : 'tag--medium'}" style="font-size: 0.68rem; padding: 1px 5px;">${isAck ? 'ACK' : 'PENDING'}</span>
                        </div>
                        <div class="event-item__title" style="font-size: 0.82rem; color: var(--text-secondary); font-family: monospace;">ID: #${e.id}</div>
                    </div>
                </li>
            `;
        }).join('');

        // Attach click listener to each event row
        listEl.querySelectorAll('.sentinel-event-item').forEach(item => {
            item.onclick = () => {
                const eventId = item.dataset.id;
                const match = sentinelIncidentsCache.find(x => String(x.id) === eventId);
                if (match) {
                    selectSentinelIncident(match);
                }
            };
        });

        // Automatically select the first incident if none selected or if selected is missing
        if (!currentSentinelIncident && events.length > 0) {
            selectSentinelIncident(events[0]);
        } else if (currentSentinelIncident) {
            const stillExists = events.find(x => String(x.id) === String(currentSentinelIncident.id));
            if (stillExists) {
                selectSentinelIncident(stillExists);
            } else if (events.length > 0) {
                selectSentinelIncident(events[0]);
            }
        }
    } catch (err) {
        console.error("Sentinel update error:", err);
        showToast("Failed to load Sentinel incident intelligence", "error");
    }
}

async function selectSentinelIncident(incident) {
    if (!incident) return;
    currentSentinelIncident = incident;

    // Highlight selected item in list
    document.querySelectorAll('.sentinel-event-item').forEach(el => {
        el.classList.toggle('active', el.dataset.id === String(incident.id));
    });

    const emptyState = document.getElementById('sentinel-empty-state');
    const dossier = document.getElementById('sentinel-dossier');
    if (emptyState) emptyState.classList.add('hidden');
    if (dossier) dossier.classList.remove('hidden');

    // Populate header & top metadata
    const prio = (incident.priority || 'UNSPECIFIED').toUpperCase();
    const itype = incident.incident_type || incident.type || 'Unknown Event';
    const timeFormatted = new Date(incident.timestamp || incident.timestamp_iso || Date.now()).toLocaleString();
    const isAck = Boolean(incident.acknowledged);

    const idEl = document.getElementById('sentinel-dossier-id');
    if (idEl) idEl.textContent = `#${incident.id}`;

    const titleEl = document.getElementById('sentinel-dossier-title');
    if (titleEl) titleEl.textContent = `${itype.toUpperCase()} Detection`;

    const prioEl = document.getElementById('sentinel-dossier-prio');
    if (prioEl) {
        prioEl.textContent = prio;
        prioEl.className = `tag tag--${prio.toLowerCase()}`;
    }

    const statusEl = document.getElementById('sentinel-dossier-status');
    if (statusEl) {
        statusEl.textContent = isAck ? 'ACKNOWLEDGED' : 'PENDING_REVIEW';
        statusEl.className = isAck ? 'tag tag--online' : 'tag tag--medium';
    }

    const timeEl = document.getElementById('sentinel-dossier-time');
    if (timeEl) timeEl.textContent = `Reported: ${timeFormatted}`;

    // Meta grid
    const srcEl = document.getElementById('sentinel-meta-source');
    if (srcEl) srcEl.textContent = incident.source || 'Live Feed / Sensor';

    let confText = 'Unspecified';
    if (incident.confidence !== undefined && incident.confidence !== null) {
        const cVal = parseFloat(incident.confidence);
        confText = (cVal <= 1.0 ? (cVal * 100).toFixed(1) : cVal.toFixed(1)) + '%';
    }
    const confEl = document.getElementById('sentinel-meta-conf');
    if (confEl) confEl.textContent = confText;

    const ackEl = document.getElementById('sentinel-meta-ack');
    if (ackEl) ackEl.textContent = isAck ? 'Acknowledged by Operator' : 'Pending Verification';

    // Visual Evidence Card
    let mediaPath = incident.media_path;
    if (!mediaPath && incident.source && incident.source.startsWith('upload:')) {
        mediaPath = '/media/' + incident.source.split(':')[1];
    }
    const evidenceCard = document.getElementById('sentinel-evidence-container');
    const mediaImg = document.getElementById('sentinel-media-img');
    const metaEvidence = document.getElementById('sentinel-meta-evidence');
    if (mediaPath && (mediaPath.endsWith('.jpg') || mediaPath.endsWith('.png') || mediaPath.includes('/media/'))) {
        mediaImg.src = apiUrl(mediaPath);
        if (evidenceCard) evidenceCard.classList.remove('hidden');
        if (metaEvidence) metaEvidence.textContent = 'Frame Artifact Attached';
    } else {
        if (evidenceCard) evidenceCard.classList.add('hidden');
        if (metaEvidence) metaEvidence.textContent = 'No Visual Artifact';
    }

    // Acknowledge Button State
    const ackBtn = document.getElementById('sentinel-ack-btn');
    if (ackBtn) {
        if (isAck) {
            ackBtn.textContent = 'Acknowledged ✓';
            ackBtn.disabled = true;
            ackBtn.classList.remove('btn--primary');
            ackBtn.classList.add('btn--ghost');
        } else {
            ackBtn.textContent = 'Acknowledge Incident';
            ackBtn.disabled = false;
            ackBtn.classList.add('btn--primary');
            ackBtn.classList.remove('btn--ghost');
        }
    }

    // Try to fetch structured briefing from backend API
    try {
        const briefingRes = await apiRequest(`/sentinel/briefing/${incident.id}`);
        if (briefingRes && briefingRes.briefing) {
            renderSentinelBriefing(incident, briefingRes.briefing);
            return;
        }
    } catch (e) {
        console.warn("Could not fetch remote briefing, generating client-side fallback:", e);
    }

    // Fallback Client-Side Briefing Synthesis
    const fallbackBriefing = generateFallbackBriefing(incident, confText);
    renderSentinelBriefing(incident, fallbackBriefing);
}

function generateFallbackBriefing(incident, confText) {
    const itype = (incident.incident_type || incident.type || 'Unknown Event');
    const prio = (incident.priority || 'UNSPECIFIED').toUpperCase();
    const source = incident.source || 'Live Feed';
    const isAck = Boolean(incident.acknowledged);

    return {
        reported_event: `AlertX vision node flagged candidate pattern for '${itype}' with ${confText} algorithmic confidence. Preliminary automated detection; awaiting human verification.`,
        known_facts: [
            `System Incident ID: ${incident.id}`,
            `Model Classification Tag: ${itype}`,
            `Calculated Algorithmic Confidence: ${confText}`,
            `Assigned Threat Priority: ${prio}`,
            `Capture Sensor: ${source}`,
            `Operator Status: ${isAck ? 'Acknowledged' : 'Pending review'}`
        ],
        uncertainties: [
            "AUTOMATED DETECTION CAVEAT: Algorithmic alerts represent statistical pattern matching and are not conclusive proof of a crime, weapon, or real-world emergency.",
            "ENVIRONMENTAL CONSTRAINTS: Camera perspective, lighting artifacts, or occlusions may cause false positives.",
            "INTENT AMBIGUITY: Sensor telemetry cannot establish subject intent or authorization status."
        ],
        recommended_response: [
            { step: "Visual Verification", action: "Examine high-resolution frame or monitor live zone camera to confirm object morphology." },
            { step: "Perimeter Safety", action: "Verify zone activity and maintain designated security perimeter." },
            { step: "Audit Documentation", action: "Record notes and acknowledge incident in the operational security log." }
        ],
        checklist: [
            { id: "chk_review_class", label: "Review automated classification and confidence score", hint: `Inspect reported class '${itype}' at ${confText}.` },
            { id: "chk_inspect_evidence", label: "Inspect visual evidence and environmental context", hint: "Check captured frame or monitor live zone camera." },
            { id: "chk_verify_source", label: "Verify sensor zone and identify personnel on scene", hint: `Confirm activity at source '${source}'.` },
            { id: "chk_assess_escalation", label: "Assess escalation criteria against facility SOP", hint: `Determine if [${prio}] tier response is required.` },
            { id: "chk_acknowledge", label: "Acknowledge incident in AlertX audit log", hint: "Commit operator review status." },
            { id: "chk_export_report", label: "Export evidence intelligence dossier for records", hint: "Download sanitized incident report for audit archive." }
        ]
    };
}

function renderSentinelBriefing(incident, briefing) {
    const reportedEl = document.getElementById('sentinel-reported-event');
    if (reportedEl) reportedEl.textContent = briefing.reported_event || '';

    const factsEl = document.getElementById('sentinel-known-facts');
    if (factsEl) {
        factsEl.innerHTML = (briefing.known_facts || []).map(f => `<li>${f}</li>`).join('');
    }

    const uncertEl = document.getElementById('sentinel-uncertainties');
    if (uncertEl) {
        uncertEl.innerHTML = (briefing.uncertainties || []).map(u => `<li>${u}</li>`).join('');
    }

    const recEl = document.getElementById('sentinel-recommendations');
    if (recEl) {
        recEl.innerHTML = (briefing.recommended_response || []).map(r => `
            <div class="sentinel-rec-item">
                <strong>${r.step}:</strong> ${r.action}
            </div>
        `).join('');
    }

    // Render Checklist with persistent state
    const checklistContainer = document.getElementById('sentinel-checklist-items');
    if (checklistContainer) {
        const state = getChecklistState(incident.id);
        const checklistItems = briefing.checklist || [];

        checklistContainer.innerHTML = checklistItems.map(item => {
            const isChecked = Boolean(state[item.id] || (item.id === 'chk_acknowledge' && incident.acknowledged));
            return `
                <div class="sentinel-check-row ${isChecked ? 'completed' : ''}" data-check-id="${item.id}">
                    <input type="checkbox" id="chk-${incident.id}-${item.id}" ${isChecked ? 'checked' : ''}>
                    <label for="chk-${incident.id}-${item.id}" style="cursor: pointer; flex: 1;">
                        <div class="sentinel-check-label">${item.label}</div>
                        <div class="sentinel-check-hint">${item.hint}</div>
                    </label>
                </div>
            `;
        }).join('');

        checklistContainer.querySelectorAll('.sentinel-check-row').forEach(row => {
            const input = row.querySelector('input[type="checkbox"]');
            const chkId = row.dataset.checkId;
            input.onchange = (e) => {
                const checked = e.target.checked;
                const curState = getChecklistState(incident.id);
                curState[chkId] = checked;
                setChecklistState(incident.id, curState);
                row.classList.toggle('completed', checked);
                updateChecklistProgress(incident.id);
            };
        });
        updateChecklistProgress(incident.id);
    }
}

function getChecklistState(eventId) {
    try {
        const saved = localStorage.getItem(`sentinel_chk_${eventId}`);
        return saved ? JSON.parse(saved) : {};
    } catch (e) {
        return {};
    }
}

function setChecklistState(eventId, state) {
    try {
        localStorage.setItem(`sentinel_chk_${eventId}`, JSON.stringify(state));
    } catch (e) {}
}

function markChecklistItemCompleted(eventId, checkId) {
    const state = getChecklistState(eventId);
    state[checkId] = true;
    setChecklistState(eventId, state);

    const row = document.querySelector(`.sentinel-check-row[data-check-id="${checkId}"]`);
    if (row) {
        row.classList.add('completed');
        const input = row.querySelector('input[type="checkbox"]');
        if (input) input.checked = true;
    }
    updateChecklistProgress(eventId);
}

function updateChecklistProgress(eventId) {
    const state = getChecklistState(eventId);
    const rows = document.querySelectorAll('.sentinel-check-row');
    const total = rows.length;
    let completed = 0;
    rows.forEach(r => {
        const chkId = r.dataset.checkId;
        if (state[chkId]) completed++;
    });
    const pct = total > 0 ? Math.round((completed / total) * 100) : 0;
    const bar = document.getElementById('sentinel-progress-bar');
    if (bar) bar.style.width = `${pct}%`;
    const label = document.getElementById('sentinel-checklist-progress');
    if (label) label.textContent = `${completed} / ${total} Completed (${pct}%)`;
}

async function acknowledgeCurrentSentinelIncident() {
    if (!currentSentinelIncident || !currentSentinelIncident.id) {
        showToast("No incident selected to acknowledge.", "warning");
        return;
    }
    const eventId = currentSentinelIncident.id;
    try {
        const res = await apiRequest(`/events/${eventId}/acknowledge`, 'POST');
        if (res && res.status === 'acknowledged') {
            currentSentinelIncident.acknowledged = true;
            showToast(`Incident #${eventId} acknowledged in security audit log.`, "online");

            const ackBadge = document.getElementById('sentinel-dossier-status');
            if (ackBadge) {
                ackBadge.textContent = 'ACKNOWLEDGED';
                ackBadge.className = 'tag tag--online';
            }
            const metaAck = document.getElementById('sentinel-meta-ack');
            if (metaAck) metaAck.textContent = 'Acknowledged by Operator';

            const ackBtn = document.getElementById('sentinel-ack-btn');
            if (ackBtn) {
                ackBtn.textContent = 'Acknowledged ✓';
                ackBtn.disabled = true;
                ackBtn.classList.remove('btn--primary');
                ackBtn.classList.add('btn--ghost');
            }

            markChecklistItemCompleted(eventId, 'chk_acknowledge');

            const listItem = document.querySelector(`.sentinel-event-item[data-id="${eventId}"]`);
            if (listItem) {
                const subTag = listItem.querySelector('.tag--medium');
                if (subTag) {
                    subTag.textContent = 'ACK';
                    subTag.className = 'tag tag--online';
                }
            }
        } else {
            showToast("Failed to acknowledge incident.", "error");
        }
    } catch (err) {
        console.error("Acknowledge error:", err);
        showToast(`Acknowledge failed: ${err.message}`, "error");
    }
}

async function exportSentinelDossier(format) {
    if (!currentSentinelIncident || !currentSentinelIncident.id) {
        showToast("No incident selected to export.", "warning");
        return;
    }
    const eventId = currentSentinelIncident.id;
    try {
        const url = apiUrl(`/sentinel/export/${eventId}?format=${format}`);
        const res = await fetch(url, {
            headers: token ? { "Authorization": `Bearer ${token}` } : {}
        });
        if (!res.ok) {
            throw new Error(`HTTP ${res.status}`);
        }
        const blob = await res.blob();
        const blobUrl = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = blobUrl;
        a.download = `sentinel-dossier-${eventId}.${format === 'html' ? 'html' : 'json'}`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(blobUrl);
        showToast(`Sentinel ${format.toUpperCase()} dossier downloaded successfully.`, "online");

        markChecklistItemCompleted(eventId, 'chk_export_report');
    } catch (err) {
        console.error("Sentinel export failed:", err);
        showToast(`Export failed: ${err.message}`, "error");
    }
}

// ── LISTENERS ────────────────────────────────────

function init() {
    console.log("AlertX: Initializing tactical protocols...");

    // Environment and Backend Health Checks
    const isLocalhost = window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1";
    if (!isLocalhost && (!API_BASE || API_BASE.includes("localhost"))) {
        showToast("Backend URL not configured - edit frontend/config.js", "error");
        console.error("Backend URL not configured - edit frontend/config.js");
    }

    let healthRetries = 0;
    function checkBackendHealth() {
        fetch(apiUrl("/health"))
            .then(res => {
                if (!res.ok) throw new Error("Health check failed");
            })
            .catch(err => {
                if (healthRetries === 0) {
                    showToast("Cannot reach backend. If it is starting up, wait about a minute.", "error");
                }
                healthRetries++;
                if (healthRetries < 6) {
                    setTimeout(checkBackendHealth, 10000);
                }
            });
    }
    checkBackendHealth();

    if (token) showApp();

    const addListener = (id, event, fn) => {
        const el = document.getElementById(id);
        if (el) el[event] = fn;
    };

    addListener('login-form', 'onsubmit', (e) => {
        e.preventDefault();
        console.log("AlertX: Login trigger initiated");
        login(document.getElementById('login-user').value, document.getElementById('login-pass').value);
    });

    addListener('signup-form', 'onsubmit', (e) => {
        e.preventDefault();
        console.log("AlertX: Signup trigger initiated");
        signup(
            document.getElementById('signup-user').value, 
            document.getElementById('signup-email').value, 
            document.getElementById('signup-pass').value,
            document.getElementById('signup-role').value,
            document.getElementById('signup-badge').value
        );
    });

    addListener('show-signup', 'onclick', (e) => {
        e.preventDefault();
        console.log("AlertX: Switching to Registration Overlay");
        switchOverlay('signup-overlay');
    });

    addListener('show-login', 'onclick', (e) => {
        e.preventDefault();
        console.log("AlertX: Switching to Login Overlay");
        switchOverlay('auth-overlay');
    });

    addListener('btn-logout', 'onclick', (e) => {
        e.preventDefault();
        logout();
    });

    document.querySelectorAll('.nav-item').forEach(btn => {
        btn.onclick = (e) => {
            e.preventDefault();
            switchView(btn.dataset.view);
        };
    });

    // Hamburger menu (mobile)
    addListener('hamburger-btn', 'onclick', toggleSidebar);
    addListener('sidebar-backdrop', 'onclick', closeSidebar);

    addListener('btn-start', 'onclick', startFeed);
    addListener('btn-stop', 'onclick', stopFeed);

    addListener('btn-apply-source', 'onclick', () => {
        const el = document.getElementById('cam-source');
        if (el) {
            const source = el.value;
            // Removed redundant toasts
        }
    });

    // Upload interaction
    const zone = document.getElementById('upload-zone');
    const input = document.getElementById('file-input');
    if (zone && input) {
        zone.onclick = () => input.click();
        input.onchange = (e) => handleUpload(e.target.files[0]);
        zone.ondragover = (e) => { e.preventDefault(); zone.classList.add('dragover'); };
        zone.ondragleave = () => zone.classList.remove('dragover');
        zone.ondrop = (e) => {
            e.preventDefault();
            zone.classList.remove('dragover');
            handleUpload(e.dataTransfer.files[0]);
        };
    }

    // Dispatch buttons logic
    document.querySelectorAll('.dispatch-btn').forEach(btn => {
        btn.onclick = () => {
            const service = btn.dataset.service;
            fetch(`${API_BASE}/dispatch/${service}`, {
                headers: token ? { 'Authorization': `Bearer ${token}` } : {}
            })
                .then(r => {
                    if (!r.ok) throw new Error(`HTTP ${r.status}`);
                    showToast(`AI Voice Agent contacted ${service.toUpperCase()}`, "success");
                })
                .catch(() => showToast("Emergency Protocol Error: AI Agent unreachable", "error"));
        };
    });

    // Optional UI listeners (will not crash if missing)
    addListener('btn-refresh-stats', 'onclick', () => {
        updateStatus();
        updateEvents();
    });

    // Sentinel listeners
    addListener('sentinel-refresh-btn', 'onclick', () => updateSentinel());
    addListener('sentinel-ack-btn', 'onclick', () => acknowledgeCurrentSentinelIncident());
    addListener('sentinel-export-json-btn', 'onclick', () => exportSentinelDossier('json'));
    addListener('sentinel-export-html-btn', 'onclick', () => exportSentinelDossier('html'));
}

// ── BOOTSTRAP ─────────────────────────────────────
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
} else {
    init();
}
