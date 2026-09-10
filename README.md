# SiteAegis

### Security Intelligence Platform

**Observe. Detect. Respond.**

SiteAegis is a self-directed full-stack engineering project built for personal learning and technical exploration.

It combines **web security monitoring** with **construction-site safety intelligence** into one unified platform.

The system monitors registered websites, analyzes their security posture, tracks changes over time, generates alerts, and provides real-time monitoring updates.

It also includes an AI-assisted construction safety module using **YOLO-based computer vision** for PPE detection and evidence-aware safety analysis.

---

## Overview

Modern digital and physical environments require continuous monitoring instead of one-time checks.

SiteAegis explores how security signals can be collected, analyzed, stored, and presented through a full-stack application.

The platform currently focuses on two areas:

- Web Security Intelligence
- Construction Safety Intelligence

The main workflow is:

**Observe → Detect → Analyze → Alert → Respond**

---

## Core Features

### Web Security Monitoring

SiteAegis can monitor registered websites and collect:

- Website availability
- HTTP status code
- Response time
- IP address
- SSL/TLS status
- SSL/TLS certificate information
- Certificate issuer
- Certificate validity
- HTTP security headers
- Missing security headers
- Security findings
- Security score
- Risk classification
- Scan history
- Security trends

### Security Headers

The platform checks important security headers including:

- Strict-Transport-Security
- Content-Security-Policy
- X-Content-Type-Options
- X-Frame-Options
- Referrer-Policy
- Permissions-Policy

---

## Security Scoring

SiteAegis calculates a security score based on collected security signals.

The analysis considers factors such as:

- Website availability
- SSL/TLS configuration
- Security headers
- Security findings
- Overall security posture

Historical results can be compared to identify changes in the monitored website's security condition.

---

## Automated Monitoring

SiteAegis uses **APScheduler** for automated monitoring.

The monitoring process can:

1. Retrieve registered websites.
2. Check website availability.
3. Analyze SSL/TLS.
4. Inspect security headers.
5. Calculate security score.
6. Compare results with previous scans.
7. Generate monitoring events.
8. Create alerts when relevant changes occur.
9. Broadcast updates through WebSockets.

---

## Real-Time WebSocket Monitoring

SiteAegis uses **WebSockets** for real-time communication between the backend and frontend.

This allows monitoring events to be delivered to connected dashboard clients without manually refreshing the page.

WebSocket endpoint:

```text
ws://127.0.0.1:8000/ws
````

The WebSocket system supports:

* Live monitoring updates
* Event broadcasting
* Connected-client management
* Real-time dashboard updates

---

## Alert Intelligence

SiteAegis maintains alerts generated from monitoring changes.

Alert types can include:

* Security risk changes
* Security findings
* Website status changes
* Finding resolution
* Monitoring events

Available endpoints:

```text
GET    /api/alerts
GET    /api/alerts/unread
GET    /api/alerts/count
PATCH  /api/alerts/{alert_id}/read
PATCH  /api/alerts/read-all
```

---

# Construction Safety Intelligence

SiteAegis also includes a construction-site safety subsystem.

It combines:

* Camera management
* Safety zones
* PPE detection
* Safety events
* Risk classification
* Incident management
* Evidence-aware analysis

---

## YOLO-Based PPE Detection

The construction safety module uses **Ultralytics YOLO** for computer vision.

Supported detection classes include:

* Person
* Hardhat
* No-hardhat
* Safety vest
* No-safety vest
* Safety shoes
* Gloves
* Mask
* No-mask
* Safety net
* Barricade
* Dumpster
* Excavator
* Dump truck
* Mini-van
* Truck
* Wheel loader

PPE endpoint:

```text
POST /api/scan/ppe
```

Example:

```bash
curl.exe -X POST "http://127.0.0.1:8000/api/scan/ppe" -F "file=@construction_test.jpg"
```

---

## Evidence-Aware Safety Logic

SiteAegis is designed to avoid making unsafe assumptions when visual evidence is insufficient.

For example, if an image does not contain enough worker evidence, the system can return:

```text
INSUFFICIENT_EVIDENCE
```

instead of incorrectly reporting:

```text
SAFE
```

This is important because:

> No detected violation does not always mean that the scene is safe.

The system therefore considers whether sufficient evidence exists before making strong safety conclusions.

---

## Camera Management

SiteAegis supports construction camera management.

Available endpoints:

```text
GET    /api/cameras
POST   /api/cameras
GET    /api/cameras/{camera_id}
PUT    /api/cameras/{camera_id}
DELETE /api/cameras/{camera_id}
```

Camera information can include:

* Camera name
* Location
* Source type
* Active state
* Camera status

---

## Safety Zones

The platform supports configurable construction safety zones.

Examples include:

* Main entrance
* Crane area
* Restricted areas
* Equipment areas
* Other monitored site sections

Endpoints:

```text
GET    /api/zones
POST   /api/zones
GET    /api/zones/{zone_id}
PUT    /api/zones/{zone_id}
DELETE /api/zones/{zone_id}
```

---

## Safety Events

Detected or manually recorded safety conditions are stored as safety events.

Examples include:

* Helmet violations
* No safety vest
* Fire hazards
* Other safety conditions

Endpoints:

```text
GET    /api/safety/events
POST   /api/safety/events
GET    /api/safety/events/{event_id}
PUT    /api/safety/events/{event_id}
DELETE /api/safety/events/{event_id}
```

Safety events can contain:

* Event type
* Severity
* Risk score
* Confidence
* Active state
* Camera/source
* Site information

---

## Incident Management

High-risk safety events can be represented through the incident management system.

Endpoints:

```text
GET    /api/incidents
POST   /api/incidents
GET    /api/incidents/{incident_id}
PUT    /api/incidents/{incident_id}
DELETE /api/incidents/{incident_id}
```

The incident service also includes risk-based handling and duplicate-prevention logic.

---

## Dashboard

The SiteAegis dashboard provides a centralized view of the system.

It can display:

* Monitored websites
* Online websites
* Current security score
* Alerts
* Monitoring activity
* Latest monitored target
* WebSocket connection status
* Security events

The dashboard is designed to quickly answer:

**What is being monitored?**

**What changed?**

**What needs attention?**

---

# Architecture

```text
                  +----------------------+
                  |   Next.js Frontend   |
                  |      Dashboard       |
                  +----------+-----------+
                             |
                     REST + WebSocket
                             |
                  +----------v-----------+
                  |    FastAPI Backend   |
                  |                      |
                  | API Routes           |
                  | Monitoring Services  |
                  | Security Analysis    |
                  | Alert System         |
                  | Safety Services      |
                  | Vision Service       |
                  +----------+-----------+
                             |
              +--------------+--------------+
              |              |              |
       +------v------+ +-----v------+ +-----v------+
       |   SQLite   | |    YOLO    | | WebSocket  |
       |  Database  | |   Vision   | |   Manager  |
       +-------------+ +------------+ +------------+
```

---

# Backend Architecture

```text
backend/
└── app/
    ├── api/
    │   ├── alerts.py
    │   ├── cameras.py
    │   ├── dashboard.py
    │   ├── health.py
    │   ├── incidents.py
    │   ├── routes.py
    │   ├── safety.py
    │   ├── sites.py
    │   └── zones.py
    │
    ├── core/
    │   ├── config.py
    │   ├── database.py
    │   └── security.py
    │
    ├── models/
    │
    ├── schemas/
    │
    ├── services/
    │   ├── alert_service.py
    │   ├── incident_service.py
    │   ├── monitoring_events.py
    │   ├── monitoring_scheduler.py
    │   ├── monitoring_service.py
    │   ├── safety_service.py
    │   ├── site_service.py
    │   └── vision_service.py
    │
    ├── websocket/
    │   └── manager.py
    │
    └── main.py
```

---

# Technology Stack

## Frontend

* Next.js
* React
* TypeScript
* CSS
* Responsive UI
* WebSocket Client

## Backend

* Python
* FastAPI
* Uvicorn
* Pydantic
* SQLAlchemy
* SQLite
* APScheduler

## Computer Vision

* Ultralytics YOLO
* Pillow

## Communication

* REST APIs
* WebSockets

---

# API Reference

## Website Scanning

```text
POST /api/scan
GET  /api/scan/history
GET  /api/scan/{scan_id}
```

## Dashboard

```text
GET /api/dashboard/stats
```

## Sites

```text
GET    /api/sites
POST   /api/sites
GET    /api/sites/{site_id}
PUT    /api/sites/{site_id}
DELETE /api/sites/{site_id}

POST   /api/sites/{site_id}/scan
GET    /api/sites/{site_id}/scans
GET    /api/sites/{site_id}/findings
GET    /api/sites/{site_id}/scans/{scan_id}/findings
GET    /api/sites/{site_id}/trend
GET    /api/sites/{site_id}/events
```

## PPE

```text
POST /api/scan/ppe
```

## WebSocket

```text
WS /ws
```

---

# Local Development

## Clone Repository

```bash
git clone https://github.com/AtiyaQazi/SiteAegis.git
cd SiteAegis
```

## Backend Setup

```powershell
cd backend

python -m venv venv

.\venv\Scripts\Activate.ps1

pip install -r requirements.txt
```

Run backend:

```powershell
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Backend:

```text
http://127.0.0.1:8000
```

Swagger API documentation:

```text
http://127.0.0.1:8000/docs
```

## Frontend Setup

Open another terminal:

```powershell
cd frontend

npm install

npm run dev
```

Frontend:

```text
http://localhost:3000
```

---

# Database

SiteAegis currently uses **SQLite** with SQLAlchemy.

The local database is intentionally excluded from Git version control.

```text
siteaegis.db
```

---

# Testing

The backend has been tested across the main API modules.

### Backend Smoke Tests

The following were tested successfully:

* Root endpoint
* Health endpoint
* Sites
* Dashboard
* Alerts
* Alert count
* Cameras
* Zones
* Safety events
* Incidents

Result:

```text
Passed: 10
Failed: 0

RESULT: ALL BACKEND SMOKE TESTS PASSED
```

### WebSocket Test

```text
State: Open
RESULT: PASS
```

### PPE Model Test

The YOLO PPE model was tested successfully.

Example detections:

```text
hardhat: 0.91
hardhat: 0.83
```

The system also correctly handled insufficient worker evidence instead of incorrectly classifying the scene as safe.

---

# Engineering Approach

SiteAegis was designed around several practical engineering principles.

### Separation of Responsibilities

API routes, services, database models, schemas, monitoring logic, and WebSocket management are separated into dedicated modules.

### Evidence-Aware Decisions

Safety conclusions should be based on sufficient evidence rather than assuming that an undetected condition is automatically safe.

### Continuous Monitoring

Scheduled monitoring allows the platform to detect changes over time.

### Real-Time Communication

WebSockets provide live communication between backend monitoring services and the frontend dashboard.

### Persistent History

Scan and event information is stored for historical analysis and comparison.

### Extensibility

The architecture allows additional monitoring sources, analytics, notifications, and computer-vision capabilities to be added later.

---

# Future Enhancements

Possible future improvements include:

* Live RTSP/IP camera streams
* Real-time video PPE monitoring
* Object tracking
* Zone-based detection rules
* Email notifications
* Push notifications
* Advanced security-header analysis
* DNS intelligence
* Domain intelligence
* Vulnerability intelligence
* Authentication
* Role-based access control
* Multi-user dashboards
* Cloud deployment
* Background task queues
* Advanced security analytics
* Historical safety analytics
* Explainable AI safety reports
* Improved model confidence calibration
* Automated incident workflows

---

# Why I Built SiteAegis

SiteAegis is a **self-directed personal learning and engineering project** created to explore the combination of:

* Full-stack development
* Web security
* Automation
* Real-time systems
* REST APIs
* WebSockets
* Databases
* Computer vision
* AI-assisted safety analysis

The project focuses on building a complete workflow instead of isolated features:

```text
Observe
   ↓
Collect
   ↓
Analyze
   ↓
Detect
   ↓
Evaluate
   ↓
Alert
   ↓
Respond
```

This project provided hands-on experience with backend architecture, frontend integration, monitoring systems, real-time communication, database design, scheduling, computer vision, and practical system testing.

---

# Repository Structure

```text
SiteAegis/
│
├── backend/
│   ├── app/
│   ├── requirements.txt
│   └── ...
│
├── frontend/
│   ├── app/
│   ├── package.json
│   └── ...
│
├── .gitignore
└── README.md
```

---

# Disclaimer

SiteAegis is a personal learning and engineering project.

Security scores, monitoring results, and computer-vision detections should be treated as technical indicators rather than guarantees of security or physical safety.

Real-world deployment would require additional validation, security hardening, model evaluation, infrastructure controls, and operational procedures.

---

# SiteAegis

**Observe. Detect. Respond.**

**Web Security × Real-Time Monitoring × Computer Vision × Construction Safety**

