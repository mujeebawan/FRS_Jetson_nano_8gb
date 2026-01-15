# Attendance System Product

**Branch:** `product/attendance-system`

## Overview

Automated attendance tracking system for schools, offices, and organizations built on the FRS Base System V2.

## Features (To Implement)

- [ ] Student/Employee database with photos
- [ ] Class/Department management
- [ ] Automatic check-in/check-out detection
- [ ] Schedule-based attendance (class times, shifts)
- [ ] Late arrival tracking
- [ ] Absence notifications to parents/managers
- [ ] Daily/Weekly/Monthly reports
- [ ] Export to Excel/CSV
- [ ] Integration with school/HR management systems

## Target Use Cases

- Schools and universities
- Corporate offices
- Manufacturing plants
- Coworking spaces
- Training centers

## Technical Requirements

- Entry/Exit cameras
- Fast recognition (<500ms)
- High accuracy for similar faces
- Offline capability
- Batch report generation

## API Additions (Beyond Base)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/students/` | CRUD | Student/Employee management |
| `/api/classes/` | CRUD | Class/Department management |
| `/api/attendance/` | GET/POST | Attendance records |
| `/api/attendance/check-in` | POST | Manual check-in |
| `/api/attendance/check-out` | POST | Manual check-out |
| `/api/schedules/` | CRUD | Class/Shift schedules |
| `/api/reports/daily` | GET | Daily attendance report |
| `/api/reports/monthly` | GET | Monthly attendance report |
| `/api/notifications/absence` | POST | Send absence notification |

## Database Additions

- Student/Employee table (class, department, contact)
- Class/Department table
- Schedule table (days, start/end times)
- Attendance record table (check-in, check-out, status)
- Parent/Manager contact table

## Frontend Additions

- Student/Employee roster with photos
- Real-time attendance dashboard
- Class/Department view
- Calendar view of attendance
- Report generation interface
- Late/Absent highlighting
- Parent notification settings
