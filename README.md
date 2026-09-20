# SiteAegis

## Real-Time Web Security & Construction Safety Intelligence

SiteAegis is a full-stack monitoring and intelligence platform that combines **automated web security monitoring** with **AI-powered construction safety analysis**.

The platform monitors registered websites for availability, HTTP behavior, SSL/TLS validity, security headers, security findings, and risk changes. At the same time, its computer-vision pipeline analyzes construction-site images and video to identify safety conditions including PPE violations, restricted-zone entry, worker-machine proximity, crowding, falls, and unsafe movement.

Detected conditions are converted into structured events, risk assessments, alerts, and incidents. The platform provides REST APIs, real-time WebSocket communication, PostgreSQL persistence, Redis/Memurai integration, and a unified monitoring dashboard.

> **Safety note:** Computer-vision detections are automated indicators intended to support monitoring and response. They do not replace qualified safety personnel, established safety procedures, or professional site assessments.

---

# Platform Overview

SiteAegis operates across two connected intelligence domains.

### Web Security Intelligence

The web-security engine provides:

* Website availability monitoring
* HTTP status monitoring
* Response-time measurement
* SSL/TLS validation
* Security-header analysis
* Security finding detection
* Risk scoring
* Risk-level classification
* Historical scan records
* Scheduled monitoring
* Monitoring alerts
* Real-time monitoring updates

### Construction Safety Intelligence

The safety engine provides:

* PPE detection
* Restricted-zone entry detection
* Worker-machine proximity analysis
* Crowding detection
* Fall detection
* Unsafe movement detection
* Image analysis
* Video analysis
* Background camera analysis
* Safety-event generation
* Incident management
* Real-time safety updates

---

# Architecture

```text
                         SITEAEGIS
                            │
             ┌──────────────┴──────────────┐
             │                             │
             ▼                             ▼
      WEB SECURITY                 CONSTRUCTION SAFETY
       MONITORING                     INTELLIGENCE
             │                             │
             ▼                             ▼
     Registered Websites             Camera / Image / Video
             │                             │
             ▼                             ▼
    Website Security Engine          OpenCV + YOLO
             │                             │
     ┌───────┼────────┐                    ▼
     │       │        │             Safety Detection
     ▼       ▼        ▼                    │
    SSL   Headers  Findings                ▼
     │       │        │              Safety Analysis
     └───────┼────────┘                    │
             ▼                             │
      Security Risk                        │
         Engine                            │
             │                             │
             └──────────────┬──────────────┘
                            ▼
                    Risk & Event Engine
                            │
              ┌─────────────┼─────────────┐
              ▼             ▼             ▼
          Monitoring     Safety Events   Incidents
            Events            │             │
              │               ▼             │
              └──────────► Alerts ◄────────┘
                            │
                 ┌──────────┴──────────┐
                 ▼                     ▼
             PostgreSQL          Redis / Memurai
                 │                     │
                 └──────────┬──────────┘
                            ▼
                    FastAPI REST API
                            │
                      WebSocket Layer
                            │
                            ▼
                     Next.js Dashboard
```

---

# Safety Intelligence Pipeline

Construction-site analysis follows an end-to-end computer-vision pipeline:

```text
Camera / Image / Video
          ↓
OpenCV Frame Processing
          ↓
YOLO Object Detection
          ↓
Person / PPE / Machine Detection
          ↓
Safety Rule Analysis
          ↓
Risk & Severity Classification
          ↓
Safety Event
          ↓
Alert / Incident
          ↓
PostgreSQL
          ↓
REST API + WebSocket
          ↓
Dashboard
```

This architecture allows detection results to move from raw visual input through analysis, persistence, real-time communication, and dashboard presentation.

---

# Computer Vision

SiteAegis uses **Ultralytics YOLO** and **OpenCV** for construction-site visual analysis.

The vision layer processes images and video frames and evaluates detected objects against configurable safety rules.

## PPE Detection

The configured computer-vision models support construction PPE-related detections including:

* Person
* Hardhat
* No hardhat
* Safety vest

PPE detections can be used as safety indicators and incorporated into the safety-event workflow.

## Restricted-Zone Entry

Construction areas can be configured as restricted safety zones.

When a detected person enters a restricted area, SiteAegis can generate a safety event containing information such as:

* Zone
* Camera
* Event type
* Severity
* Confidence
* Risk score
* Timestamp
* Description

## Worker-Machine Proximity

The system analyzes the spatial relationship between detected workers and machinery.

Bounding-box separation and configurable proximity thresholds are used to identify potentially unsafe worker-machine distances.

## Crowding Detection

Crowding detection evaluates the number of detected people against a configurable threshold.

The live analysis system uses temporal state handling to avoid repeatedly generating identical events while a crowd condition remains continuously active.

## Fall Detection

Fall analysis evaluates person-detection geometry to identify fall-like body orientation.

The current implementation provides frame/image-level fall detection. More advanced temporal fall recognition can be added as a future enhancement.

## Unsafe Movement

Unsafe movement analysis compares person positions between frames.

Detected workers are matched between frames and their displacement is calculated. Significant movement can be classified as an unsafe movement event according to the configured analysis rules.

---

# Video Intelligence

SiteAegis supports video analysis through the camera analysis API.

Video is processed using OpenCV frame extraction and the computer-vision safety pipeline.

The analysis can evaluate:

* People
* PPE
* Crowding
* Falls
* Worker-machine proximity
* Restricted zones
* Unsafe movement

Processed results are integrated with the safety-event and incident-management layers.

---

# Live Camera Monitoring

SiteAegis supports background camera analysis.

The live lifecycle is:

```text
START
  ↓
RUNNING
  ↓
FRAME PROCESSING
  ↓
SAFETY ANALYSIS
  ↓
EVENT GENERATION
  ↓
WEBSOCKET BROADCAST
  ↓
STATUS MONITORING
  ↓
STOP
  ↓
OFFLINE
```

Live camera processing tracks:

* Camera status
* Frames read
* Frames processed
* Generated events
* Last processed frame
* Worker state
* Processing errors

Uploaded video can also be used as a controlled source for live-analysis testing.

---

# Real-Time WebSocket Monitoring

SiteAegis provides a WebSocket endpoint:

```text
WS /ws
```

The WebSocket layer delivers real-time monitoring information to connected dashboard clients.

Camera analysis messages can include:

* Camera ID
* Frame information
* Person detections
* PPE detections
* Crowding analysis
* Fall analysis
* Proximity analysis
* Unsafe movement analysis
* Restricted-zone analysis

Safety events can also be broadcast in real time.

This allows the dashboard to receive live activity without relying exclusively on repeated polling requests.

---

# Risk Intelligence

SiteAegis uses numerical risk scores and severity levels to communicate detected conditions.

For web-security monitoring, the current risk classification is:

|  Score | Risk Level |
| -----: | ---------- |
| 80–100 | Low        |
|  60–79 | Medium     |
|  40–59 | High       |
|   0–39 | Critical   |

Construction-safety events use event-specific severity and risk rules.

High-risk conditions can be escalated into incidents, allowing the system to distinguish routine monitoring activity from conditions requiring attention.

---

# Safety Events

Safety events provide structured records for construction-site conditions detected by the vision and safety engines.

A safety event can contain:

* Event type
* Camera
* Zone
* Severity
* Confidence
* Risk score
* Description
* Timestamp
* Active state

Supported event categories include:

```text
restricted_zone_entry
worker_machine_proximity
crowding_detected
fall_detected
unsafe_movement
```

---

# Incident Management

High-risk safety conditions can be escalated into incidents.

The incident-management layer provides structured tracking of safety conditions requiring attention.

Incident information can include:

* Safety event
* Severity
* Risk score
* Description
* Status
* Timestamp

This creates a response workflow from automated detection to operational follow-up.

---

# Alerts

The alert layer provides centralized notification records for important monitoring conditions.

Alerts can represent:

* Security findings
* Risk changes
* Safety events
* High-severity conditions
* Incident-related activity

The dashboard provides a centralized alert view with read/unread management.

---

# Dashboard

The SiteAegis dashboard provides a unified operational view of both monitoring domains.

## Web Security

The dashboard presents:

* Monitored websites
* Online/offline status
* Current risk
* Security scans
* SSL statistics
* Security findings
* Risk distribution
* Monitoring activity
* Alerts

## Construction Safety

The dashboard presents:

* Cameras
* Safety events
* PPE activity
* Restricted-zone activity
* Worker-machine proximity
* Crowding
* Falls
* Unsafe movement
* Open incidents
* Video intelligence

## System Health

The dashboard also exposes:

* API health
* Database status
* Redis connectivity
* WebSocket activity

---

# Data & Infrastructure

## PostgreSQL

PostgreSQL is the primary application database.

Persistent application data includes:

* Sites
* Scans
* Monitoring events
* Alerts
* Cameras
* Zones
* Safety events
* Incidents

The application was migrated from its earlier SQLite development configuration to PostgreSQL while preserving existing application data.

## Redis / Memurai

SiteAegis integrates Redis-compatible services through Memurai.

Redis/Memurai is used for runtime caching and service-state support.

The verified local configuration uses port `6380`.

Sensitive credentials are maintained through environment configuration and are not stored in the repository.

---

# Technology Stack

| Layer                   | Technology                 |
| ----------------------- | -------------------------- |
| Frontend                | Next.js, React, TypeScript |
| Backend                 | Python, FastAPI            |
| Database                | PostgreSQL                 |
| Runtime Cache           | Redis / Memurai            |
| ORM                     | SQLAlchemy                 |
| Computer Vision         | OpenCV                     |
| Object Detection        | Ultralytics YOLO           |
| Image Processing        | Pillow                     |
| Real-Time Communication | WebSockets                 |
| Scheduling              | APScheduler                |
| Application Server      | Uvicorn                    |

---

# API

SiteAegis provides REST APIs for web monitoring, safety analysis, cameras, zones, incidents, alerts, and dashboard data.

## Web Security

```text
POST /api/scan
GET  /api/scan/history
GET  /api/scan/{scan_id}
POST /api/scan/ppe
```

## Dashboard

```text
GET /api/dashboard/stats
```

## Cameras

```text
GET  /api/cameras
POST /api/cameras

POST /api/cameras/{camera_id}/analyze

POST /api/cameras/{camera_id}/live/start
POST /api/cameras/{camera_id}/live/stop
GET  /api/cameras/{camera_id}/live/status
```

## Zones

```text
GET    /api/zones
POST   /api/zones
GET    /api/zones/{zone_id}
PUT    /api/zones/{zone_id}
DELETE /api/zones/{zone_id}
```

## Safety

```text
GET  /api/safety
POST /api/safety

GET    /api/safety/{event_id}
PUT    /api/safety/{event_id}
DELETE /api/safety/{event_id}

POST /api/safety/proximity/analyze
POST /api/safety/crowding/analyze
POST /api/safety/fall/analyze
POST /api/safety/unsafe-movement/analyze

GET /api/safety/events
```

## Incidents

```text
GET  /api/incidents
POST /api/incidents
```

## Alerts

```text
GET   /api/alerts
PATCH /api/alerts/read-all
```

## Health

```text
GET /api/health
```

## WebSocket

```text
WS /ws
```

---

# Verification & Testing

SiteAegis was validated through direct functional and integration testing.

Testing covered computer-vision detection, video processing, live camera operation, WebSocket communication, database persistence, dashboard integration, infrastructure services, scheduler behavior, frontend builds, and web-security regression.

## Construction Safety Verification

| Capability               | Evidence                            | Result |
| ------------------------ | ----------------------------------- | ------ |
| PPE Detection            | YOLO object detection               | PASS   |
| Restricted-Zone Entry    | Safety Event #1167                  | PASS   |
| Worker-Machine Proximity | Safety Event #1158                  | PASS   |
| Crowding Detection       | Safety Event #1287                  | PASS   |
| Fall Detection           | Safety Event #1160                  | PASS   |
| Unsafe Movement          | Safety Events #1164 / #1166         | PASS   |
| Video Analysis           | 10-frame video test                 | PASS   |
| Live Camera Analysis     | Continuous background processing    | PASS   |
| WebSocket Camera Stream  | `camera_analysis_frame` messages    | PASS   |
| WebSocket Safety Event   | Safety Event #1250                  | PASS   |
| PostgreSQL Persistence   | Safety events retrieved through API | PASS   |
| Incident Management      | High-risk safety events             | PASS   |

---

# Selected Test Evidence

## Restricted-Zone Entry

```text
Safety Event #1167

Event Type:  restricted_zone_entry
Zone:        Crane Area
Camera:      1
Severity:    Critical
Confidence:  0.815
Risk Score:  95
```

The event was successfully created and persisted through the safety-event pipeline.

## Worker-Machine Proximity

```text
Safety Event #1158

Event Type:  worker_machine_proximity
Machine:     Excavators
Severity:    Medium
Risk Score:  60
Gap:         86.03 pixels
Threshold:   120 pixels
```

The detection demonstrated that the configured spatial threshold can identify a worker-machine proximity condition.

## Fall Detection

```text
Safety Event #1160

Event Type:  fall_detected
Severity:    Critical
Risk Score:  95
```

The dedicated fall test successfully produced a critical safety event.

## Crowding Detection

The final live looping-video test produced:

```text
Frames Read:       980
Frames Processed:  980
Events Created:    1
Worker Shutdown:   Clean
Last Error:        None
```

This test verified continuous crowd-state handling and duplicate-event suppression.

## Unsafe Movement

```text
Safety Event #1164

Unsafe Movements: 2
Displacements:     approximately 511 px and 642 px
Severity:          Critical
Risk Score:        95
```

A separate video integration test generated Safety Event **#1166** for unsafe movement.

---

# Video Integration Verification

A construction video containing 10 frames was processed through the camera analysis API.

```text
FPS:              5
Total Frames:     10
Frames Processed: 2
Frame Interval:   5
Resolution:       902 × 1536
```

The sampled frames were processed through the safety-analysis pipeline.

Verified results included:

* Person detection
* Crowding detection
* Unsafe movement detection
* Restricted-zone evaluation

Generated events included:

```text
#1165 — crowding_detected
#1166 — unsafe_movement
```

This verified the flow from video input through safety analysis and event persistence.

---

# Live Camera Verification

The live camera pipeline was tested from startup through shutdown.

Verified behavior included:

* Camera successfully entered running state
* Background processing worker started
* Frames were continuously processed
* Safety analysis was executed
* Events were generated
* WebSocket messages were delivered
* Camera status was queryable
* No processing error occurred
* Worker stopped cleanly

The final lifecycle verification was:

```text
START → PROCESS → ANALYZE → BROADCAST → STATUS → STOP
```

---

# WebSocket Verification

An independent WebSocket client connected successfully to:

```text
ws://127.0.0.1:8000/ws
```

The test received `camera_analysis_frame` messages containing live analysis information.

Verified information included:

* 5 detected persons
* 2 hardhat detections
* Crowding analysis
* Fall analysis
* Proximity analysis
* Unsafe movement analysis
* Restricted-zone analysis

A `camera_safety_event` message was also captured for Safety Event **#1250**.

---

# Web Security Regression

The existing web-security monitoring functionality was regression-tested after construction-safety integration.

Final scan:

```text
Scan ID:       2468
Target:        https://example.com
Availability:  Online
HTTP Status:   200
SSL:           Valid
Risk Score:    65
Risk Level:    Medium
Findings:      6
```

This verified that the construction-safety additions did not break the original web-security monitoring pipeline.

---

# Scheduler Verification

The automated monitoring scheduler was tested with registered websites.

A successful monitoring cycle produced:

```text
Google
Risk Score: 70
Risk Level: medium

Test Monitoring
Risk Score: 65
Risk Level: medium
```

The scheduler completed successfully and persisted the correct risk-level values.

---

# Reliability & Integration Validation

The major processing chain was verified end-to-end:

```text
Input
  ↓
Detection
  ↓
Analysis
  ↓
Risk Classification
  ↓
Event Creation
  ↓
PostgreSQL Persistence
  ↓
REST API
  ↓
WebSocket
  ↓
Dashboard
```

This confirms that the construction-safety modules are integrated into the application's analysis, persistence, API, real-time communication, and dashboard layers.

---

# Application Health

The final health verification returned:

```text
Application: SiteAegis
Version:     1.0.0
Status:      healthy
Redis:       connected
```

The application version was also verified against OpenAPI metadata:

```text
Health Version:  1.0.0
OpenAPI Version: 1.0.0
```

---

# Frontend Validation

The Next.js frontend was successfully validated using:

```text
npm run build
```

The production build completed successfully through:

* Compilation
* TypeScript validation
* Page data collection
* Static generation
* Final optimization

---

# Repository Verification

The final implementation was committed and synchronized with GitHub.

```text
Branch:         main
Latest Commit:  aa969a2
Commit:         Complete SiteAegis safety and monitoring platform
Remote:         origin/main
Working Tree:   Clean
```

The repository was checked to ensure that sensitive and generated files were excluded from version control.

Excluded categories include:

* Environment files
* Local databases
* Virtual environments
* Node modules
* Model weights
* Generated uploads
* Test media
* Python cache files

---

# Future Enhancements

Potential future extensions include:

* RTSP/IP camera sources
* Multi-camera distributed processing
* Advanced worker and object tracking
* Temporal fall detection
* Improved model evaluation and calibration
* Site-specific computer-vision models
* Authentication and role-based access control
* Email, SMS, and push notifications
* Cloud deployment
* Distributed processing
* Advanced safety analytics
* Historical safety trends
* Automated compliance reporting
* Explainable AI safety reports

These represent potential future extensions to the current implementation.

---

# Project Summary

SiteAegis combines:

```text
Web Security
      +
Computer Vision
      +
Construction Safety
      +
Risk Intelligence
      +
Event Management
      +
PostgreSQL
      +
Redis
      +
WebSockets
      +
Real-Time Dashboard
```

The platform provides a unified approach to monitoring digital assets and construction-site safety conditions through automated analysis, structured events, risk assessment, alerts, incidents, persistent records, and real-time visualization.

**SiteAegis — Observe. Detect. Assess. Respond.**
