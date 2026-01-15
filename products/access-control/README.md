# Access Control System Product

**Branch:** `product/access-control`

## Overview

Door access control system with face recognition authentication built on the FRS Base System V2.

## Features (To Implement)

- [ ] Door/Zone management
- [ ] Access group permissions
- [ ] Time-based access rules (working hours, holidays)
- [ ] Anti-passback detection
- [ ] Tailgating prevention alerts
- [ ] Visitor pre-registration
- [ ] Temporary access codes
- [ ] Access logs and audit trail
- [ ] Integration with existing access control systems

## Target Use Cases

- Corporate offices
- Data centers
- Research facilities
- Secure government buildings
- Residential complexes
- Hospitals (restricted areas)

## Technical Requirements

- Entry cameras at each door
- Door lock relay integration
- Fast recognition (<300ms)
- Very low false positive rate
- Failsafe mode (manual override)
- Network resilience

## API Additions (Beyond Base)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/doors/` | CRUD | Door management |
| `/api/zones/` | CRUD | Zone/Area management |
| `/api/access-groups/` | CRUD | Access group permissions |
| `/api/access-rules/` | CRUD | Time-based rules |
| `/api/visitors/` | CRUD | Visitor management |
| `/api/visitors/{id}/qr` | GET | Generate visitor QR code |
| `/api/access-logs/` | GET | Access history |
| `/api/doors/{id}/unlock` | POST | Manual door unlock |
| `/api/doors/{id}/lock` | POST | Manual door lock |

## Database Additions

- Door table (name, location, camera, relay GPIO)
- Zone table (doors, security level)
- Access group table (members, allowed zones/doors)
- Access rule table (group, schedule, doors)
- Visitor table (host, purpose, valid period)
- Access log table (person, door, result, timestamp)

## Frontend Additions

- Door status dashboard (locked/unlocked)
- Floor plan view with door indicators
- Access group management
- Visitor registration form
- Visitor QR code generator
- Real-time access log
- Manual unlock controls
- Access denied alerts

## Hardware Integration

- GPIO relay control for door locks
- Magnetic door sensors
- Emergency unlock button input
- Audible alerts/buzzers
