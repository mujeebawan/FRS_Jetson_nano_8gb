# FRS Authentication & UI Updates

## Authentication System

### Backend
- **User Model**: Username, email, hashed password, role (admin/user), active status
- **JWT Tokens**: Access token (30 min), Refresh token (7 days)
- **Password Security**: bcrypt hashing via passlib

### API Endpoints
| Endpoint | Method | Access | Description |
|----------|--------|--------|-------------|
| `/api/auth/login` | POST | Public | Login with username/password |
| `/api/auth/refresh` | POST | Public | Refresh access token |
| `/api/auth/logout` | POST | Auth | Logout user |
| `/api/auth/me` | GET | Auth | Get current user info |
| `/api/auth/change-password` | POST | Auth | Change own password |
| `/api/users` | GET/POST | Admin | List/Create users |
| `/api/users/{id}` | GET/PUT/DELETE | Admin | Manage specific user |
| `/api/users/{id}/reset-password` | POST | Admin | Reset user password |

### Route Protection
- **View-only routes**: Require authentication (any role)
- **Modify routes**: Require admin role (enroll persons, delete, acknowledge alerts, change settings)
- **Stream/WebSocket**: Token passed via query parameter `?token=<access_token>`

### Environment Variables
```bash
JWT_SECRET_KEY=your-secret-key    # Required for production
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7
ADMIN_USERNAME=admin              # Seeded on first startup
ADMIN_PASSWORD=admin123
ADMIN_EMAIL=admin@frs.local
```

## Frontend

### New Components
- `LoginPage` - Authentication form
- `AuthContext` - Auth state management
- `ProtectedRoute` - Route guard with optional admin requirement
- `UserManagement` - Admin user CRUD in Settings

### Role-Based UI
| Feature | Admin | User |
|---------|-------|------|
| View Dashboard | Yes | Yes |
| View Alerts | Yes | Yes |
| View Persons | Yes | Yes |
| Enroll/Delete Persons | Yes | No |
| Acknowledge Alerts | Yes | No |
| Settings Page | Yes | No |
| User Management | Yes | No |

## UI Theme Update

Updated dark theme to **Slate Dark** (Linear/Vercel style):
- Neutral slate grays instead of harsh dark blue
- Subtle blue-gray undertones
- Better card/background contrast
- Professional SaaS aesthetic

## Default Credentials
```
Username: admin
Password: admin123
```

## New Dependencies

### Backend
- `python-jose[cryptography]` - JWT encoding/decoding
- `passlib[bcrypt]` - Password hashing
- `email-validator` - Email validation for Pydantic

### Frontend
- `@radix-ui/react-alert-dialog` - Confirmation dialogs
