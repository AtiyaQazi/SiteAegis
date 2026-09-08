# SiteAegis

## Real-Time Web Security Monitoring Platform

SiteAegis is a real-time web security monitoring platform designed to continuously monitor registered websites, analyze their security posture, detect security changes, calculate security risk, and deliver actionable alerts through a live monitoring dashboard.

The platform combines automated website scanning, security analysis, scheduled monitoring, change detection, monitoring events, alert management, and WebSocket-based real-time updates.

---

## Features

### Website Monitoring

- Register and monitor multiple websites
- Automatic scheduled website scanning
- Website availability monitoring
- HTTP status code detection
- Response time monitoring
- IP address detection
- SSL/TLS availability checking
- SSL/TLS certificate validation

### Security Analysis

- Security header analysis
- SSL/TLS analysis
- Security findings detection
- Risk score calculation
- Risk-level classification
- Severity-based security findings

### Change Detection

SiteAegis compares consecutive website scans and detects:

- New security findings
- Resolved security findings
- Increased security risk
- Decreased security risk
- Website status changes
- Website offline events

### Monitoring Events

The system generates monitoring events when meaningful changes are detected.

Supported event types:

- `NEW_FINDING`
- `RESOLVED_FINDING`
- `RISK_INCREASED`
- `RISK_DECREASED`
- `SITE_OFFLINE`
- `SITE_STATUS_CHANGED`

### Alert Management

- Automatic alert generation from monitoring events
- Severity classification
- Alert history
- Unread alert counter
- Mark individual alerts as read
- Mark all alerts as read
- Event-to-alert relationship tracking
- Real-time alert updates

### Real-Time Monitoring

SiteAegis uses WebSockets to provide live monitoring updates.

- Real-time scan updates
- Live monitoring activity
- WebSocket connection status
- Real-time dashboard updates
- Live security event notifications

### Dashboard

The dashboard provides:

- System status
- WebSocket connection status
- Number of monitored websites
- Number of online websites
- Current security risk score
- Unread security alerts
- Latest monitored target
- Latest scan information
- Live monitoring activity
- Security Alert Center

---

## Architecture

```text
                    +-------------------------+
                    |     Next.js Frontend    |
                    |        Dashboard        |
                    +------------+------------+
                                 |
                         REST API + WebSocket
                                 |
                                 v
                    +-------------------------+
                    |     FastAPI Backend      |
                    +------------+------------+
                                 |
              +------------------+------------------+
              |                  |                  |
              v                  v                  v
       +-------------+   +---------------+   +---------------+
       | Site Scanner|   |  Monitoring   |   |  WebSocket    |
       |             |   |   Scheduler   |   |    Manager    |
       +------+------+   +-------+-------+   +---------------+
              |                  |
              +------------------+
                       |
                       v
              +-------------------------+
              |    Change Detection     |
              |   & Monitoring Events    |
              +------------+------------+
                           |
                           v
              +-------------------------+
              |      Alert Service      |
              +------------+------------+
                           |
                           v
              +-------------------------+
              |     SQLite Database     |
              |  SQLAlchemy + Alembic  |
              +-------------------------+
````

---

## Monitoring Workflow

```text
Scheduled Monitoring
        |
        v
Website Scan
        |
        v
Persist Scan
        |
        v
Compare With Previous Scan
        |
        v
Detect Security Changes
        |
        v
Create Monitoring Events
        |
        v
Create Alerts
        |
        v
Broadcast WebSocket Update
        |
        v
Update Dashboard in Real Time
```

---

## Risk Scoring

SiteAegis uses a security score from **0 to 100**.

|    Score | Risk Level |
| -------: | ---------- |
| 80 - 100 | Low        |
|  60 - 79 | Medium     |
|  40 - 59 | High       |
|   0 - 39 | Critical   |

A higher score represents a better security posture.

Example:

```text
Previous Score: 70
Current Score: 50

Result:
Security risk increased
```

Another example:

```text
Previous Score: 50
Current Score: 70

Result:
Security risk decreased
```

---

## Alert System

Monitoring events are automatically converted into user-facing security alerts.

Each alert contains:

* Alert ID
* Site ID
* Event ID
* Alert type
* Severity
* Title
* Message
* Read/unread status
* Creation timestamp

The relationship between monitoring events and alerts allows every alert to be traced back to the event that generated it.

```text
Security Change
       |
       v
Monitoring Event
       |
       v
Alert
       |
       v
Dashboard Notification
```

---

## WebSocket

SiteAegis provides a real-time WebSocket endpoint:

```text
ws://127.0.0.1:8000/ws
```

The WebSocket stream provides:

* Connection confirmation
* Monitoring updates
* Scan completion updates
* Live activity
* Real-time dashboard synchronization

---

## API Endpoints

### Sites

```text
GET    /api/sites
POST   /api/sites
GET    /api/sites/{site_id}
PATCH  /api/sites/{site_id}
DELETE /api/sites/{site_id}
```

### Alerts

```text
GET   /api/alerts
GET   /api/alerts/unread
GET   /api/alerts/count
PATCH /api/alerts/{alert_id}/read
PATCH /api/alerts/read-all
```

### Dashboard

```text
GET /api/dashboard
```

### Health

```text
GET /api/health
```

### WebSocket

```text
WS /ws
```

---

## Technology Stack

### Frontend

* Next.js
* React
* TypeScript
* Tailwind CSS
* Lucide React

### Backend

* Python
* FastAPI
* SQLAlchemy
* Pydantic
* APScheduler
* WebSockets

### Database

* SQLite
* SQLAlchemy ORM
* Alembic

### Development Tools

* Git
* GitHub
* Visual Studio Code
* Uvicorn
* npm

---

## Project Structure

```text
SiteAegis/
|
+-- backend/
|   |
|   +-- alembic/
|   |   +-- versions/
|   |
|   +-- app/
|   |   |
|   |   +-- api/
|   |   |   +-- alerts.py
|   |   |   +-- dashboard.py
|   |   |   +-- health.py
|   |   |   +-- routes.py
|   |   |   +-- sites.py
|   |   |
|   |   +-- core/
|   |   |   +-- config.py
|   |   |   +-- database.py
|   |   |   +-- security.py
|   |   |
|   |   +-- models/
|   |   |   +-- alert.py
|   |   |   +-- monitoring_event.py
|   |   |   +-- scan.py
|   |   |   +-- site.py
|   |   |
|   |   +-- schemas/
|   |   |   +-- common.py
|   |   |   +-- monitoring_event.py
|   |   |   +-- site.py
|   |   |
|   |   +-- services/
|   |   |   +-- alert_service.py
|   |   |   +-- monitoring_events.py
|   |   |   +-- monitoring_scheduler.py
|   |   |   +-- monitoring_service.py
|   |   |   +-- site_service.py
|   |   |
|   |   +-- websocket/
|   |   |   +-- manager.py
|   |   |
|   |   +-- main.py
|   |
|   +-- requirements.txt
|   +-- alembic.ini
|
+-- frontend/
|   |
|   +-- app/
|   |   +-- globals.css
|   |   +-- layout.tsx
|   |   +-- page.tsx
|   |
|   +-- public/
|   +-- package.json
|   +-- package-lock.json
|   +-- next.config.ts
|
+-- .gitignore
+-- README.md
```

---

## Installation

### Clone the Repository

```bash
git clone https://github.com/AtiyaQazi/SiteAegis.git
cd SiteAegis
```

---

## Backend Setup

Navigate to the backend:

```bash
cd backend
```

Create a virtual environment:

```bash
python -m venv .venv
```

### Windows

Activate the virtual environment:

```powershell
.venv\Scripts\activate
```

### Linux / macOS

```bash
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Run the backend:

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Backend will run at:

```text
http://127.0.0.1:8000
```

FastAPI documentation:

```text
http://127.0.0.1:8000/docs
```

---

## Frontend Setup

Open a second terminal.

Navigate to the frontend:

```bash
cd frontend
```

Install dependencies:

```bash
npm install
```

Start the development server:

```bash
npm run dev
```

Frontend will run at:

```text
http://localhost:3000
```

---

## Database

SiteAegis currently uses SQLite for local development.

The database stores:

* Registered websites
* Website scans
* Monitoring events
* Security alerts

SQLAlchemy is used as the ORM and Alembic is used for database migrations.

Apply migrations with:

```bash
alembic upgrade head
```

---

## Monitoring Scheduler

The monitoring scheduler automatically scans enabled websites at the configured monitoring interval.

The scheduler:

1. Finds enabled monitoring targets
2. Checks whether a scan is due
3. Runs the website scanner
4. Saves the scan
5. Compares the scan with the previous scan
6. Detects security changes
7. Creates monitoring events
8. Generates alerts
9. Broadcasts updates through WebSocket

---

## Security Checks

SiteAegis performs defensive security analysis including:

* Website availability
* HTTP status
* Response time
* IP address
* SSL/TLS availability
* SSL/TLS certificate information
* Security headers
* Security findings
* Risk scoring

Only websites that the user is authorized to monitor should be registered in SiteAegis.

---

## Testing

The monitoring pipeline has been tested for:

* Website scanning
* Scan persistence
* Risk calculation
* Security finding detection
* Finding resolution detection
* Risk change detection
* Website status change detection
* Monitoring event creation
* Alert generation
* Event-to-alert relationship
* WebSocket broadcasting
* Real-time dashboard updates

The core event pipeline is:

```text
Website Scan
     |
     v
Change Detection
     |
     v
Monitoring Event
     |
     v
Alert
     |
     v
WebSocket
     |
     v
Dashboard
```

---

## Dashboard

The SiteAegis dashboard provides a centralized security monitoring interface.

It displays:

* System online status
* Live WebSocket status
* Monitored sites
* Online sites
* Current risk score
* Unread alerts
* Latest monitored target
* Latest scan
* Response time
* HTTP status code
* IP address
* Live monitoring activity
* Security Alert Center

---

## Future Improvements

Possible future enhancements include:

* User authentication and authorization
* Multiple user accounts
* Role-based access control
* PostgreSQL production database
* Email notifications
* SMS notifications
* Advanced historical analytics
* Security trend charts
* Custom monitoring intervals
* Docker support
* CI/CD pipeline
* Production deployment
* Expanded automated test coverage
* Additional security checks

---

## Project Goal

The goal of SiteAegis is to provide an automated and real-time security monitoring platform that helps users:

* Monitor website availability
* Analyze website security
* Identify security weaknesses
* Detect changes between scans
* Track security risk
* Receive actionable alerts
* Monitor website security activity in real time

---

## Author

**Attia Qamar-un-nisa**

BS Computer Science

---

## Repository

GitHub Repository:

[https://github.com/AtiyaQazi/SiteAegis](https://github.com/AtiyaQazi/SiteAegis)

---

## License

This project is intended for educational, research, and portfolio purposes.


