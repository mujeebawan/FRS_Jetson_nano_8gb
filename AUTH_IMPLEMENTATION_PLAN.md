# Authentication & Authorization Implementation Plan

## Overview

Implement JWT-based authentication with role-based access control (RBAC) for the FRS application.

## Requirements Summary

- **Auth Method**: JWT Tokens (access + refresh tokens)
- **Admin Seeding**: Environment variables
- **Roles**:
  - `admin` - Full access to all features
  - `user` - View-only access (dashboard, alerts, persons list)
- **User Management**: Admin creates users via settings page

---

## Backend Implementation

### 1. Database Models

**File**: `backend/app/models/user.py`

```python
class User(Base):
    __tablename__ = "users"

    id: int (primary key)
    username: str (unique, indexed)
    email: str (unique, optional)
    hashed_password: str
    role: str ("admin" | "user")
    is_active: bool (default True)
    created_at: datetime
    updated_at: datetime
    last_login: datetime (optional)
```

### 2. Authentication Endpoints

**File**: `backend/app/api/routes/auth.py`

| Endpoint | Method | Auth Required | Description |
|----------|--------|---------------|-------------|
| `/api/auth/login` | POST | No | Login with username/password, returns tokens |
| `/api/auth/refresh` | POST | No | Refresh access token using refresh token |
| `/api/auth/logout` | POST | Yes | Invalidate refresh token |
| `/api/auth/me` | GET | Yes | Get current user info |
| `/api/auth/change-password` | POST | Yes | Change own password |

### 3. User Management Endpoints (Admin Only)

**File**: `backend/app/api/routes/users.py`

| Endpoint | Method | Role | Description |
|----------|--------|------|-------------|
| `/api/users` | GET | Admin | List all users |
| `/api/users` | POST | Admin | Create new user |
| `/api/users/{id}` | GET | Admin | Get user details |
| `/api/users/{id}` | PUT | Admin | Update user (role, active status) |
| `/api/users/{id}` | DELETE | Admin | Delete user |
| `/api/users/{id}/reset-password` | POST | Admin | Reset user password |

### 4. JWT Token Structure

**Access Token** (short-lived: 15-30 minutes):
```json
{
  "sub": "user_id",
  "username": "admin",
  "role": "admin",
  "type": "access",
  "exp": 1234567890,
  "iat": 1234567890
}
```

**Refresh Token** (long-lived: 7 days):
```json
{
  "sub": "user_id",
  "type": "refresh",
  "exp": 1234567890,
  "iat": 1234567890
}
```

### 5. Auth Middleware & Dependencies

**File**: `backend/app/api/deps.py`

```python
# Dependencies for route protection
async def get_current_user(token: str = Depends(oauth2_scheme)) -> User
async def get_current_active_user(user: User = Depends(get_current_user)) -> User
async def require_admin(user: User = Depends(get_current_active_user)) -> User
```

### 6. Role-Based Permissions Matrix

| Feature | Admin | User |
|---------|-------|------|
| View Dashboard | ✓ | ✓ |
| View Live Stream | ✓ | ✓ |
| View Alerts List | ✓ | ✓ |
| View Alert Details | ✓ | ✓ |
| Acknowledge Alerts | ✓ | ✗ |
| Verify Alerts | ✓ | ✗ |
| View Persons List | ✓ | ✓ |
| View Person Details | ✓ | ✓ |
| Enroll Person | ✓ | ✗ |
| Edit Person | ✓ | ✗ |
| Delete Person | ✓ | ✗ |
| View Settings | ✓ | ✗ |
| Modify Settings | ✓ | ✗ |
| Manage Users | ✓ | ✗ |
| Control Stream | ✓ | ✗ |
| Camera PTZ Control | ✓ | ✗ |
| Storage Cleanup | ✓ | ✗ |

### 7. Protect Existing Endpoints

Update all existing routes with appropriate dependencies:

**Public (No Auth)**:
- None (all routes require authentication)

**Any Authenticated User**:
- `GET /api/persons` - List persons
- `GET /api/persons/{id}` - Get person details
- `GET /api/persons/{id}/image` - Get person image
- `GET /api/alerts` - List alerts
- `GET /api/alerts/{id}` - Get alert details
- `GET /api/alerts/{id}/snapshot` - Get alert snapshot
- `GET /api/alerts/{id}/video` - Get alert video
- `GET /api/stream/status` - Get stream status
- `GET /api/stream/mjpeg` - View MJPEG stream
- `WS /api/alerts/ws` - WebSocket alerts (with token query param)
- `GET /api/system/health` - Health check
- `GET /api/system/storage` - Storage info

**Admin Only**:
- `POST /api/persons/enroll` - Enroll person
- `PUT /api/persons/{id}` - Update person
- `DELETE /api/persons/{id}` - Delete person
- `POST /api/alerts/{id}/acknowledge` - Acknowledge alert
- `POST /api/alerts/{id}/verify` - Verify alert
- `POST /api/stream/start` - Start stream
- `POST /api/stream/stop` - Stop stream
- `POST /api/system/zoom/*` - Camera zoom controls
- `GET /api/system/settings` - Get settings
- `PUT /api/system/settings` - Update settings
- `POST /api/system/cleanup` - Cleanup storage
- All `/api/users/*` endpoints

### 8. Environment Variables

Add to `.env` file:
```bash
# JWT Configuration
JWT_SECRET_KEY=your-256-bit-secret-key-here
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

# Admin Seed Credentials
ADMIN_USERNAME=admin
ADMIN_PASSWORD=changeme123
ADMIN_EMAIL=admin@example.com
```

### 9. Admin Seeding

**File**: `backend/app/core/seed.py`

On application startup:
1. Check if any admin user exists
2. If not, read credentials from environment variables
3. Create admin user with hashed password
4. Log warning if default password is detected

---

## Frontend Implementation

### 1. New Pages

| Page | Route | Description |
|------|-------|-------------|
| Login | `/login` | Username/password form |

### 2. Auth Context & State

**File**: `frontend/src/contexts/AuthContext.tsx`

```typescript
interface AuthState {
  user: User | null
  isAuthenticated: boolean
  isLoading: boolean
  login: (username: string, password: string) => Promise<void>
  logout: () => void
  refreshToken: () => Promise<void>
}
```

### 3. Token Storage

- Access token: Memory (React state)
- Refresh token: HttpOnly cookie (set by backend) OR localStorage with XSS mitigation

### 4. API Client Updates

**File**: `frontend/src/services/api.ts`

- Add Authorization header interceptor
- Add 401 response interceptor for token refresh
- Add automatic logout on refresh failure

### 5. Protected Routes

**File**: `frontend/src/components/ProtectedRoute.tsx`

```typescript
// Wrapper component that checks authentication
// Redirects to /login if not authenticated
// Checks role for admin-only routes
```

### 6. UI Changes by Role

**Admin View**:
- Full sidebar with all navigation items
- All action buttons visible (Enroll, Delete, Edit, etc.)
- Settings page accessible
- User management in settings

**User View**:
- Sidebar without Settings link
- No action buttons on Persons page (no Enroll, Delete, Edit)
- No action buttons on Alerts (no Acknowledge, Verify)
- No stream control buttons
- Read-only mode indicators

### 7. User Management UI (Admin Only)

**Location**: Settings page → Users tab

Features:
- List all users with role, status, last login
- Create new user form (username, password, role)
- Edit user (change role, activate/deactivate)
- Delete user (with confirmation)
- Reset password

---

## Implementation Order

### Phase 1: Backend Auth Foundation
- [ ] Create User model and migration
- [ ] Create auth utilities (password hashing, JWT functions)
- [ ] Create auth routes (login, refresh, logout, me)
- [ ] Create auth dependencies (get_current_user, require_admin)
- [ ] Add admin seeding on startup

### Phase 2: Backend Route Protection
- [ ] Update all person routes with auth
- [ ] Update all alert routes with auth
- [ ] Update all stream routes with auth
- [ ] Update all system routes with auth
- [ ] Add user management routes

### Phase 3: Frontend Auth
- [ ] Create AuthContext and provider
- [ ] Create Login page
- [ ] Update API client with token handling
- [ ] Create ProtectedRoute component
- [ ] Update App.tsx with auth routing

### Phase 4: Frontend Role-Based UI
- [ ] Update Sidebar to hide/show based on role
- [ ] Update Persons page (hide actions for users)
- [ ] Update Alerts page (hide actions for users)
- [ ] Update Dashboard (hide controls for users)
- [ ] Add User Management to Settings

### Phase 5: Testing & Polish
- [ ] Test all protected routes
- [ ] Test token refresh flow
- [ ] Test role-based access
- [ ] Add loading states
- [ ] Add error handling

---

## Security Considerations

1. **Password Requirements**: Minimum 8 characters
2. **Token Security**: Short-lived access tokens (30 min)
3. **Refresh Token Rotation**: New refresh token on each refresh
4. **Failed Login Tracking**: Consider rate limiting after failed attempts
5. **Secure Headers**: Add security headers to responses
6. **HTTPS**: Recommended for production deployment

---

## File Structure

```
backend/
├── app/
│   ├── api/
│   │   ├── deps.py          # Auth dependencies
│   │   └── routes/
│   │       ├── auth.py      # Login, refresh, logout
│   │       └── users.py     # User management
│   ├── core/
│   │   ├── security.py      # Password hashing, JWT
│   │   └── seed.py          # Admin seeding
│   ├── models/
│   │   └── user.py          # User SQLAlchemy model
│   └── schemas/
│       ├── auth.py          # Login, Token schemas
│       └── user.py          # User schemas

frontend/
├── src/
│   ├── contexts/
│   │   └── AuthContext.tsx  # Auth state management
│   ├── components/
│   │   └── auth/
│   │       ├── LoginForm.tsx
│   │       └── ProtectedRoute.tsx
│   └── pages/
│       └── LoginPage.tsx
```
