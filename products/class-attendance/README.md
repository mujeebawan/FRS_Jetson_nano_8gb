# Class Attendance System - Advanced Educational

**Branch:** `product/class-attendance`

## Overview

Advanced attendance tracking system specifically designed for educational institutions - schools, colleges, universities, and training centers. Built on the FRS Base System V2.

## Features (To Implement)

### Student Management
- [ ] Student database with photos and student ID
- [ ] Class/Section/Batch organization
- [ ] Parent/Guardian contact information
- [ ] Student profile with attendance history

### Class & Schedule Management
- [ ] Course/Subject management
- [ ] Teacher assignment to classes
- [ ] Timetable/Schedule configuration
- [ ] Multiple periods per day support
- [ ] Holiday and vacation calendar

### Automatic Attendance
- [ ] Face recognition at classroom entry
- [ ] Period-wise attendance tracking
- [ ] Late arrival detection with grace period
- [ ] Early departure tracking
- [ ] Proxy attendance prevention

### Notifications & Alerts
- [ ] Real-time absence notification to parents (SMS/Email/WhatsApp)
- [ ] Low attendance warnings (below threshold)
- [ ] Daily attendance summary to parents
- [ ] Teacher notifications for chronic absentees

### Reports & Analytics
- [ ] Daily/Weekly/Monthly attendance reports
- [ ] Subject-wise attendance analysis
- [ ] Student attendance trends
- [ ] Class-wise comparison
- [ ] Export to Excel/CSV/PDF
- [ ] Attendance percentage calculations

### Integration
- [ ] School ERP/Management system integration
- [ ] Student Information System (SIS) sync
- [ ] LMS (Learning Management System) integration
- [ ] Government education portal reporting

## Target Use Cases

- Schools (K-12)
- Colleges and Universities
- Coaching centers and Tuition classes
- Vocational training institutes
- Professional certification programs
- Online + Offline hybrid classes

## Technical Requirements

- Cameras at classroom entrances
- Fast recognition (<500ms)
- High accuracy for young faces
- Offline capability for network issues
- Batch report generation
- Multi-campus support

## API Additions (Beyond Base)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/students/` | CRUD | Student management |
| `/api/students/{id}/attendance` | GET | Student attendance history |
| `/api/students/{id}/photo` | GET/POST | Student photo |
| `/api/classes/` | CRUD | Class/Section management |
| `/api/subjects/` | CRUD | Subject/Course management |
| `/api/teachers/` | CRUD | Teacher management |
| `/api/schedules/` | CRUD | Timetable management |
| `/api/periods/` | CRUD | Period configuration |
| `/api/attendance/` | GET/POST | Attendance records |
| `/api/attendance/mark` | POST | Manual attendance marking |
| `/api/attendance/bulk` | POST | Bulk attendance entry |
| `/api/parents/` | CRUD | Parent contact management |
| `/api/notifications/absence` | POST | Send absence notification |
| `/api/notifications/daily-summary` | POST | Send daily summary |
| `/api/reports/daily` | GET | Daily attendance report |
| `/api/reports/monthly` | GET | Monthly attendance report |
| `/api/reports/student/{id}` | GET | Individual student report |
| `/api/reports/class/{id}` | GET | Class-wise report |
| `/api/holidays/` | CRUD | Holiday calendar |

## Database Additions

### Core Tables
- **Student** - name, student_id, class, section, photo, enrollment_date
- **Class** - name, section, academic_year, class_teacher
- **Subject** - name, code, class, teacher
- **Teacher** - name, employee_id, subjects, contact

### Schedule Tables
- **Period** - name, start_time, end_time, order
- **Schedule** - class, subject, period, day_of_week, teacher
- **Holiday** - date, name, type (holiday/vacation)

### Attendance Tables
- **AttendanceRecord** - student, date, period, subject, status, marked_at
- **AttendanceStatus** - present, absent, late, excused, half_day

### Contact Tables
- **Parent** - name, relation, phone, email, whatsapp
- **StudentParent** - student, parent, is_primary

### Notification Tables
- **NotificationLog** - student, parent, type, message, sent_at, status

## Frontend Additions

### Dashboard
- Real-time attendance overview
- Today's absent students list
- Low attendance alerts
- Quick stats (present %, absent %, late %)

### Student Management
- Student roster with photos
- Student profile page
- Attendance calendar view
- Individual attendance report

### Class Management
- Class list with student count
- Class timetable view
- Subject-wise attendance
- Class attendance report

### Attendance Interface
- Period-wise attendance grid
- Manual marking interface
- Bulk attendance entry
- Late arrival marking with reason

### Reports
- Report generation interface
- Date range selection
- Export options (Excel, CSV, PDF)
- Graphical analytics (charts)

### Parent Portal (Optional)
- Parent login
- Child attendance view
- Notification preferences
- Leave application

## Attendance Status Types

| Status | Description |
|--------|-------------|
| `present` | Student attended the class |
| `absent` | Student did not attend |
| `late` | Arrived after grace period |
| `excused` | Absent with valid reason |
| `half_day` | Attended partial day |
| `on_leave` | Pre-approved leave |

## Notification Templates

- **Immediate Absence**: "Dear Parent, your ward {name} is absent for {subject} class today."
- **Daily Summary**: "Attendance Summary for {date}: Present: {periods}, Absent: {periods}"
- **Low Attendance Warning**: "Warning: {name}'s attendance is {percent}%, below required {threshold}%"
- **Monthly Report**: "Monthly attendance report for {month}: {percent}% attendance"
