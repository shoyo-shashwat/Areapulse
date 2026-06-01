<div align="center">

# 🛰️ AreaPulse

**AI-powered civic infrastructure reporting & resolution platform.**
One live map. Three stakeholders: citizens, government, NGOs.

[![Live Demo](https://img.shields.io/badge/Live-areapulse.onrender.com-22d3ee?style=for-the-badge)](https://areapulse.onrender.com/)
[![AR Scanner](https://img.shields.io/badge/AR-Scanner-22c55e?style=for-the-badge)](https://areapulse-cam.onrender.com/)
[![Built by](https://img.shields.io/badge/Built_by-Team_Nexons-f8c023?style=for-the-badge)](#-team)



</div>

---

## 🔥 The Problem

India files **40+ million civic complaints a year**. The system is broken at every layer.

| Stakeholder | Pain point |
|---|---|
| **Citizens** | Long forms (name, address, ward, captcha, OTP). Most abandon. Those who submit wait 2 months and hear nothing. |
| **Government** | Thousands of unsorted, unprioritised complaints. No intelligent routing. No duplicate detection. No SLA tracking. Critical issues get buried. |
| **NGOs** | Want to help. Have zero access to ground-level civic data showing where to deploy. |

**AreaPulse fixes all three simultaneously.**

---

## ✨ What AreaPulse Does

### One live civic map. Three personas. Zero friction.

```
   ┌──────────────────────────────────────────────────────────┐
   │           AreaPulse Live Map (Delhi · 141 issues)         │
   │   🔴 high  🟠 medium  🟢 low                               │
   │   (color = severity · pulse = SLA breach)                 │
   ├──────────────────────────────────────────────────────────┤
   │  CITIZEN              GOVERNMENT          NGO            │
   │  • AR scan            • Priority queue    • Heatmap      │
   │  • WhatsApp           • SLA timers        • Filter by    │
   │  • Map tap            • Auto-routing       focus area    │
   │  • One tap            • One-click status  • Impact data  │
   └──────────────────────────────────────────────────────────┘
```

---

## 🚀 Three Citizen Reporting Channels

### 1. AR Camera Scanner — *Under 5 seconds*
Open camera → point at pothole/garbage/broken streetlight → AI vision classifies + scores severity + grabs GPS → submitted. **No form.**

### 2. WhatsApp Bot — *No app install, works on any phone*
Send a photo to the AreaPulse WhatsApp number. AI reads the image, classifies, extracts EXIF location, files the report. Built for rural users with low internet literacy. Powered by Twilio.

### 3. Map Tap — *Under 30 seconds*
Tap location on the map → take photo → submit. AI handles categorisation, severity, area detection, and routing.

> **Core principle:** the citizen does almost nothing. AI does the rest.

---

## 🧠 AI Processing Pipeline

Every report passes through this pipeline, powered by **Groq's `llama-4-scout-17b-16e-instruct`**:

```
  ┌────────────────────────────────────────────────────────────┐
  │  📷 Image + 📝 Description + 📍 GPS                          │
  └────────────────────────────────────────────────────────────┘
                            ↓
  ┌────────────────────────────────────────────────────────────┐
  │  STAGE 1 · Tag classification                              │
  │  → pothole | water | sewage | electricity | streetlight    │
  │  → garbage | traffic | noise | tree | other                │
  ├────────────────────────────────────────────────────────────┤
  │  STAGE 2 · Severity scoring  (high / medium / low)         │
  ├────────────────────────────────────────────────────────────┤
  │  STAGE 3 · Spam + abuse filter                             │
  ├────────────────────────────────────────────────────────────┤
  │  STAGE 4 · Duplicate detection                             │
  │           (50 m radius, 7-day window — upvotes merged)     │
  ├────────────────────────────────────────────────────────────┤
  │  STAGE 5 · Auto-routing to correct department              │
  │           water board · MCD · DISCOM · traffic police …    │
  └────────────────────────────────────────────────────────────┘
                            ↓
                    📤 Live on map
```

---

## ⏱️ SLA Engine (Indian Municipal Norms)

Every issue ships with a live countdown timer. SLA breach → automatic escalation.

| Category    | SLA       |
|-------------|-----------|
| Sewage      | **24 h**  |
| Electricity | **24 h**  |
| Traffic     | **24 h**  |
| Noise       | **24 h**  |
| Water       | **48 h**  |
| Streetlight | **48 h**  |
| Garbage     | **72 h**  |
| Other       | **120 h** |
| Pothole     | **168 h** (7 d) |
| Tree        | **168 h** (7 d) |

Plus **crowd escalation**: any issue with **25+ citizen upvotes** auto-escalates regardless of SLA state.

---

## 🏛️ Government Dashboard

Department-specific login (`gov_rmc`, `gov_water`, `gov_electricity`, `gov_traffic` · PIN `0000`):

- Issue queue sorted by SLA urgency
- Live countdown timers per issue
- Auto-escalation flags
- One-click status: `open` → `acknowledged` → `in_progress` → `resolved` / `escalated`
- Full status history with timestamps
- KPI cards (Total · Overdue · Due Soon · Open · In Progress · Resolved)

## 🤝 NGO Hub

Filtered civic data by focus area + operational geography. NGOs see:
- Which neighbourhoods have the most unresolved issues
- Which issue types government is ignoring
- Where their intervention will create the highest impact

## 📱 WhatsApp Status Notifications

Citizens receive WhatsApp updates whenever their issue is acknowledged, escalated, or resolved. Powered by Twilio WhatsApp Business API.

```
Sandbox code:  feet-cheese
Number:        +1 415 523 8886
Send:          "join feet-cheese" to activate
```

---

## 🏗️ Technical Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  Frontend                                                        │
│  • Leaflet.js (full-screen interactive map)                      │
│  • MapTiler satellite hybrid tiles (Flightradar24-style dark)    │
│  • Vanilla JS — no framework, fast paint, mobile-scalable        │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │  REST + JSON
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│  Backend  (Python 3.12+ · Flask 3.0)                             │
│  • Groq Llama-4-Scout for classification & complaint drafting    │
│  • Google OAuth + email/password auth                            │
│  • Firebase Admin SDK · Twilio WhatsApp API                      │
└─────────────────────────────────────────────────────────────────┘
                  │                      │
                  ↓                      ↓
        ┌──────────────────┐   ┌─────────────────────┐
        │  Neon Postgres   │   │  Firebase Firestore  │
        │  (persistent)    │   │  (real-time sync)    │
        └──────────────────┘   └─────────────────────┘
                  │
                  └─► In-memory fallback (141 seed issues)
                      activates when both DBs quota-blocked
```

### Resilience
- **5-minute read cache** → reduces Firebase reads from 2880/day → 288/day
- **Triple-fallback** → Firebase → Postgres → in-memory seed (site never goes empty)
- **Per-issue error handling** on `/issues` → one bad record can't break the feed
- **UptimeRobot** pings both services every 5 min → no Render free-tier cold starts

---

## 🗂️ Project Structure

```
Areapulse/
├── app.py                  # Flask app — all routes, AI pipeline, auth
├── ai_engine.py            # Groq integration · classify · severity · draft
├── classifier.py           # Tag classification + severity scoring
├── database.py             # Firebase + Postgres + in-memory fallback
├── email_sender.py         # SMTP for complaint emails to authorities
├── templates/
│   ├── base.html           # Shared layout (mobile-responsive chrome)
│   ├── index.html          # Live map · the home page
│   ├── issues.html         # All Issues feed
│   ├── my_issues.html      # User's reports + detail modal
│   ├── community.html      # Channel-based community feed
│   ├── ngos.html           # NGO directory + performance
│   ├── gov.html            # Government dashboard
│   ├── stats.html          # Public stats page
│   ├── login.html          # Auth (Google OAuth + email)
│   └── complaint_print.html # Printable AI-drafted complaint
└── requirements.txt
```

---

## 📊 Database Schema

**`issues`** table:
```
id · description · area · severity · tag · lat · lng
user_name · landmark · contact · status · upvotes · image
timestamp · verified · escalated · resolved
status_history · escalation_reason · escalated_at · resolved_at
```

**`ngos`** table:
```
id · name · focus · tag · rating · area · phone · email · lat · lng
```

### Seed Data
- **141 seed issues** across **36 Delhi neighbourhoods**, all 10 categories
- **16 seed NGOs** with focus areas, ratings, contact info
- Loaded automatically on first run · always available as fallback

### Areas Covered
Connaught Place · Karol Bagh · Rohini · Saket · Lajpat Nagar · Hauz Khas · Dwarka · Janakpuri · Chandni Chowk · Paharganj · Mehrauli · Malviya Nagar · Greater Kailash · Vasant Kunj · Pitampura · Model Town · Civil Lines · Mukherjee Nagar · Rajouri Garden · Punjabi Bagh · Mayur Vihar · Preet Vihar · Shahdara · Laxmi Nagar · Okhla · Kalkaji · Nehru Place · Lodhi Colony · Kashmere Gate · Nizamuddin · Sarojini Nagar · INA · Patel Nagar · RK Puram · Vasant Vihar · Defence Colony

---

## 🛠️ Local Development

### Prerequisites
- Python 3.12+
- A Groq API key ([free at console.groq.com](https://console.groq.com))
- *(Optional)* Firebase service account JSON
- *(Optional)* Neon Postgres connection string
- *(Optional)* MapTiler API key

### Setup
```bash
git clone https://github.com/shash-shukla06/Areapulse.git
cd Areapulse
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### Configure `.env`
```env
GROQ_API_KEY=gsk_your_key_here
SECRET_KEY=any-random-string-for-flask-sessions
MAPTILER_KEY=optional_for_satellite_tiles
FIREBASE_KEY_JSON=optional_service_account_json_as_string
DATABASE_URL=optional_neon_postgres_url
GOOGLE_CLIENT_ID=optional_for_google_oauth
GOOGLE_CLIENT_SECRET=optional_for_google_oauth
TWILIO_WHATSAPP_NUMBER=optional_for_whatsapp_notifications
```

> **Works with zero env vars.** App falls back to in-memory mode with 141 seed issues + Esri satellite tiles.

### Run
```bash
python app.py
```
Visit **`http://localhost:5000`**.

---

## 🌐 Deployment (Render)

Already configured for continuous deployment from `main`.

| Service | URL |
|---------|-----|
| Main app | https://areapulse.onrender.com |
| AR Scanner | https://areapulse-cam.onrender.com |
| GitHub | https://github.com/shash-shukla06/Areapulse |

### Required Render Environment Variables
```
GROQ_API_KEY            ← classification + complaint drafting
FIREBASE_KEY_JSON       ← full service-account JSON
DATABASE_URL            ← Neon Postgres connection string
MAPTILER_KEY            ← satellite map tiles
SECRET_KEY              ← Flask session secret
GOOGLE_CLIENT_ID        ← Google OAuth
GOOGLE_CLIENT_SECRET    ← Google OAuth
TWILIO_WHATSAPP_NUMBER  ← Twilio sandbox number
```

UptimeRobot keeps both services warm by pinging every 5 minutes.

---

## 🔌 Public API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/issues` | GET | List all issues (with SLA + auto-escalation) |
| `/issue/<id>/detail` | GET | Full issue detail (timeline, NGOs, authority) |
| `/report` | POST | Citizen report submission |
| `/ngo/nearby` | GET | NGOs near a coordinate (`?lat=&lng=&tag=`) |
| `/api/authority/<tag>` | GET | AI-matched government authority |
| `/areas` | GET | List all 36 Delhi areas |
| `/user/stats` | GET | Citizen impact stats (`?name=`) |
| `/my-issues-data` | GET | User's reports (`?user=`) |
| `/issue/<id>/upvote` | POST | Upvote (crowd escalation at 25+) |
| `/issue/<id>/verify` | POST | Verify an issue |
| `/issue/<id>/status` | POST | Government status update |
| `/ai/draft-complaint` | POST | AI-drafted formal complaint letter |

---

## 🎯 Key Features

- ⚡ **One-tap / 5-second reporting** via AR camera
- 📲 **WhatsApp reporting** for users with no internet literacy
- 🤖 **AI classification** across 10 categories with severity scoring
- 🚫 **Spam filtering** + duplicate merging
- 🎯 **Auto-routing** to the correct government department
- ⏰ **Live SLA countdowns** per issue
- 🚨 **Auto-escalation** on SLA breach
- 👥 **Crowd escalation** at 25+ upvotes
- 📊 **Government dashboard** with prioritised queue + one-click updates
- 🤝 **NGO dashboard** with filtered civic intelligence
- 🔍 **Public issue tracking** for transparency
- 📩 **WhatsApp notifications** via Twilio
- 🗺️ **Full-screen heatmap** with severity-coded pins
- 🔐 **Google OAuth** + anonymous reporting
- 📱 **Mobile-first responsive UI** (Flightradar24/Zoom Earth aesthetic)

---

## 👥 Team

**Built by Team Nexons**

| | |
|---|---|
| **Garv Chopra** | Co-Founder, Engineering |
| **Shashwat Shukla** | Co-Founder, Engineering |

### Recognition
- 🏆 **QuantCraft 2026** — Top 10 Finalists
- 🎓 **Microsoft Build AI** — Selected

---

## 📜 License

MIT — free to study, learn from, and adapt. If you ship something similar, a credit is appreciated, not required.

---

<div align="center">

**Built for India. Built fast. Built to scale.**

⭐ Star the repo if you find it useful · 🐛 [Report a bug](https://github.com/shash-shukla06/Areapulse/issues) · 💡 [Suggest a feature](https://github.com/shash-shukla06/Areapulse/issues/new)

</div>
