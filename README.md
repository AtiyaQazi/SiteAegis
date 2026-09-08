# SiteAegis

## Real-Time Web Security Monitoring Platform

SiteAegis is a web security monitoring platform that continuously monitors registered websites, analyzes their security posture, detects security changes, calculates risk levels, and provides real-time alerts.

## Features

- Website availability monitoring
- HTTP status code detection
- Response time monitoring
- IP address detection
- SSL/TLS validation
- Security header analysis
- Security findings detection
- Risk score calculation
- Risk-level classification
- New security finding detection
- Resolved finding detection
- Risk increase/decrease detection
- Website offline detection
- Automatic scheduled monitoring
- Monitoring event generation
- Automatic alert generation
- Unread alert management
- Mark alert as read
- Mark all alerts as read
- Real-time WebSocket updates
- Live monitoring activity stream
- Security Alert Center
- Dashboard with monitoring statistics

## Tech Stack

### Frontend
- Next.js
- React
- TypeScript
- Tailwind CSS
- Lucide React

### Backend
- Python
- FastAPI
- SQLAlchemy
- Pydantic
- APScheduler
- WebSockets

### Database
- SQLite
- SQLAlchemy ORM
- Alembic

## Architecture

```text
Next.js Frontend
       |
       | REST API + WebSocket
       |
       v
FastAPI Backend
       |
       +---- Site Scanner
       |
       +---- Monitoring Scheduler
       |
       +---- Change Detection
       |
       +---- Monitoring Events
       |
       +---- Alert Service
       |
       v
SQLite Database
