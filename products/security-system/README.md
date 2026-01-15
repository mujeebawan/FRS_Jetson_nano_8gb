# Security System Product

**Branch:** `product/security-system`

## Overview

Criminal detection and security monitoring system built on the FRS Base System V2.

## Features (To Implement)

- [ ] Watchlist management (criminal, suspect, banned, VIP)
- [ ] Real-time alerts with threat levels
- [ ] Video clip recording on alerts
- [ ] Multi-camera surveillance
- [ ] Guard action prompts
- [ ] Alert history and statistics
- [ ] Email/SMS notifications
- [ ] Integration with law enforcement databases

## Target Use Cases

- Banks and financial institutions
- Government buildings
- Shopping malls
- Public transportation hubs
- Hotels and resorts

## Technical Requirements

- Multiple IP cameras (4-8)
- 24/7 operation
- Low false positive rate
- Quick alert response time (<1s)
- Video evidence storage

## API Additions (Beyond Base)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/watchlist/` | CRUD | Manage watchlist entries |
| `/api/alerts/` | GET/POST | Alert management |
| `/api/alerts/{id}/video` | GET | Get video clip |
| `/api/notifications/` | POST | Send notifications |
| `/api/reports/` | GET | Generate reports |

## Database Additions

- Alert table (threat level, guard actions, video path)
- Notification log
- Guard verification records

## Frontend Additions

- Alert dashboard with priority sorting
- Threat level indicators
- Video playback for alerts
- Guard action interface
- Statistics dashboard
