# UI & Authentication Integration Plan

**Branch:** `feature/base-system-v2`
**Reference Branch:** `feature/ui-revamp-muaz`
**Created:** 2026-01-14
**Status:** In Progress

---

## Overview

Integrate the modern shadcn/ui components and JWT authentication system from Muaz's branch into our production DeepStream pipeline.

### Current State

| Component | base-system-v2 (Current) | ui-revamp-muaz (Reference) |
|-----------|--------------------------|----------------------------|
| **Backend Pipeline** | DeepStream + TensorRT + FAISS | Basic GStreamer |
| **Face Detection** | SCRFD via TensorRT | SCRFD via ONNX |
| **Multi-Camera** | Yes (2 cameras) | No |
| **Authentication** | None | JWT + Role-based |
| **UI Framework** | Basic CSS | shadcn/ui + Tailwind |
| **Theme** | Light only | Dark/Light toggle |
| **Routing** | Tab-based | React Router |

### Integration Strategy

**Approach: Reference-based Rebuild**
Use Muaz's branch as a reference to rebuild the UI and add auth to our working DeepStream system.

**Why not merge?**
- Our branch has critical DeepStream pipeline code
- Muaz's branch has different backend architecture
- Merge conflicts would be significant and risky
- Cleaner to integrate features one by one

---

## Phase 1: Backend Authentication

### 1.1 New Files to Create

```
backend/app/
├── api/
│   ├── deps.py              # Auth dependencies (get_current_user, require_admin)
│   ├── schemas.py           # Pydantic schemas for auth
│   └── routes/
│       ├── auth.py          # Login, refresh, logout, me
│       └── users.py         # User CRUD (admin only)
├── core/
│   ├── security.py          # JWT, password hashing
│   └── seed.py              # Admin user seeding
└── models/
    └── user.py              # User SQLAlchemy model
```

### 1.2 Environment Variables

Add to `.env`:
```bash
JWT_SECRET_KEY=your-256-bit-secret-key-change-in-production
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7
ADMIN_USERNAME=admin
ADMIN_PASSWORD=admin123
```

### 1.3 Dependencies to Add

```
# backend/requirements.txt
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
python-multipart==0.0.6
```

### 1.4 Route Protection Matrix

| Endpoint | Auth Required | Admin Only |
|----------|--------------|------------|
| `POST /api/auth/login` | No | No |
| `POST /api/auth/refresh` | No | No |
| `GET /api/auth/me` | Yes | No |
| `GET /api/persons/` | Yes | No |
| `POST /api/persons/enroll` | Yes | Yes |
| `DELETE /api/persons/{id}` | Yes | Yes |
| `GET /api/alerts/` | Yes | No |
| `POST /api/alerts/{id}/acknowledge` | Yes | Yes |
| `GET /api/stream/mjpeg` | Yes | No |
| `POST /api/stream/start` | Yes | Yes |
| `GET /api/cameras/` | Yes | No |
| `POST /api/cameras/` | Yes | Yes |
| `GET /api/system/settings` | Yes | Yes |
| `PUT /api/system/settings` | Yes | Yes |
| `GET /api/users/` | Yes | Yes |
| `POST /api/users/` | Yes | Yes |

---

## Phase 2: Frontend UI Upgrade

### 2.1 Install shadcn/ui

```bash
cd frontend

# Install dependencies
npm install @radix-ui/react-alert-dialog @radix-ui/react-avatar \
  @radix-ui/react-checkbox @radix-ui/react-dialog @radix-ui/react-dropdown-menu \
  @radix-ui/react-label @radix-ui/react-progress @radix-ui/react-scroll-area \
  @radix-ui/react-select @radix-ui/react-separator @radix-ui/react-slider \
  @radix-ui/react-slot @radix-ui/react-switch @radix-ui/react-tabs \
  @radix-ui/react-tooltip class-variance-authority clsx tailwind-merge \
  tailwindcss-animate next-themes lucide-react react-router-dom

# Install dev dependencies
npm install -D tailwindcss postcss autoprefixer @types/node
npx tailwindcss init -p
```

### 2.2 New Frontend Structure

```
frontend/src/
├── components/
│   ├── ui/                    # shadcn components
│   │   ├── button.tsx
│   │   ├── card.tsx
│   │   ├── dialog.tsx
│   │   ├── input.tsx
│   │   ├── label.tsx
│   │   ├── select.tsx
│   │   ├── table.tsx
│   │   ├── tabs.tsx
│   │   └── ...
│   ├── layout/
│   │   ├── AppSidebar.tsx
│   │   ├── Header.tsx
│   │   └── MainLayout.tsx
│   ├── auth/
│   │   └── ProtectedRoute.tsx
│   ├── dashboard/
│   │   ├── LiveStreamCard.tsx
│   │   ├── StatsOverview.tsx
│   │   └── SystemStatusCard.tsx
│   ├── persons/
│   │   ├── PersonsTable.tsx
│   │   └── EnrollPersonDialog.tsx
│   ├── alerts/
│   │   ├── AlertsTable.tsx
│   │   └── AlertDetailsDialog.tsx
│   └── settings/
│       ├── DetectionSettings.tsx
│       ├── CameraSettings.tsx
│       ├── StorageSettings.tsx
│       └── UserManagement.tsx
├── contexts/
│   └── AuthContext.tsx
├── providers/
│   └── ThemeProvider.tsx
├── pages/
│   ├── LoginPage.tsx
│   ├── DashboardPage.tsx
│   ├── PersonsPage.tsx
│   ├── AlertsPage.tsx
│   └── SettingsPage.tsx
├── services/
│   └── api.ts                 # Updated with auth headers
└── App.tsx                    # Router setup
```

### 2.3 Key UI Components from Reference

| Component | Purpose | Source |
|-----------|---------|--------|
| `AppSidebar` | Navigation with status indicators | ui-revamp-muaz |
| `Header` | Top bar with user menu, theme toggle | ui-revamp-muaz |
| `ThemeToggle` | Dark/Light mode switch | ui-revamp-muaz |
| `StatsOverview` | Dashboard stats cards | ui-revamp-muaz |
| `LiveStreamCard` | Stream container with controls | Adapt existing |
| `PersonsTable` | Data table with actions | ui-revamp-muaz |
| `UserManagement` | Admin user CRUD | ui-revamp-muaz |

---

## Phase 3: Settings Page Cleanup

### 3.1 Remove Model Selection

Current settings page has model selection which is not needed for production.

**Remove:**
- Model pack dropdown
- Detection model selection
- Recognition model selection

**Keep:**
- Detection confidence slider
- Recognition threshold slider
- Frame skip setting
- Alert cooldown
- Camera settings
- Storage management
- User management (new)

---

## Phase 4: Testing & Validation

### 4.1 Backend Tests

```bash
# Test auth endpoints
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin123"}'

# Test protected endpoint
curl http://localhost:8000/api/persons/ \
  -H "Authorization: Bearer <token>"

# Test admin endpoint
curl -X POST http://localhost:8000/api/users/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"username": "user1", "password": "pass123", "role": "user"}'
```

### 4.2 Frontend Tests

- [ ] Login page renders correctly
- [ ] Login with valid credentials works
- [ ] Invalid credentials show error
- [ ] Protected routes redirect to login
- [ ] Admin-only routes check role
- [ ] Theme toggle works
- [ ] Sidebar navigation works
- [ ] Dashboard shows live stream
- [ ] Persons page shows enrolled persons
- [ ] Alerts page shows alerts
- [ ] Settings page (admin only) works
- [ ] User management works

---

## Implementation Order

### Week 1: Backend Auth
1. [x] Analyze Muaz's auth implementation
2. [ ] Create User model and migration
3. [ ] Create security.py (JWT, password)
4. [ ] Create auth routes
5. [ ] Create user routes
6. [ ] Create auth dependencies
7. [ ] Add admin seeding
8. [ ] Protect existing routes
9. [ ] Test all endpoints

### Week 2: Frontend Setup
1. [ ] Install shadcn/ui dependencies
2. [ ] Configure Tailwind CSS
3. [ ] Copy UI components from reference
4. [ ] Set up React Router
5. [ ] Create AuthContext
6. [ ] Create ProtectedRoute
7. [ ] Create LoginPage

### Week 3: Frontend Pages
1. [ ] Create MainLayout with sidebar
2. [ ] Migrate Dashboard to new UI
3. [ ] Migrate Persons page
4. [ ] Migrate Alerts page
5. [ ] Create Settings page (without model selection)
6. [ ] Add User Management to Settings
7. [ ] Test full flow

### Week 4: Polish & Deploy
1. [ ] Test all features
2. [ ] Fix bugs
3. [ ] Performance optimization
4. [ ] Documentation update
5. [ ] Production deployment prep

---

## Files Changed Summary

### New Files
- `backend/app/api/deps.py`
- `backend/app/api/schemas.py`
- `backend/app/api/routes/auth.py`
- `backend/app/api/routes/users.py`
- `backend/app/core/security.py`
- `backend/app/core/seed.py`
- `backend/app/models/user.py`
- `backend/.env.example`
- `frontend/src/components/ui/*.tsx` (15+ files)
- `frontend/src/components/layout/*.tsx`
- `frontend/src/components/auth/*.tsx`
- `frontend/src/contexts/AuthContext.tsx`
- `frontend/src/providers/ThemeProvider.tsx`
- `frontend/src/pages/*.tsx`
- `frontend/tailwind.config.js`
- `frontend/postcss.config.js`

### Modified Files
- `backend/app/main.py` - Add auth routes, startup seed
- `backend/app/api/routes/__init__.py` - Include new routers
- `backend/app/api/routes/persons.py` - Add auth dependencies
- `backend/app/api/routes/alerts.py` - Add auth dependencies
- `backend/app/api/routes/stream.py` - Add auth dependencies
- `backend/app/api/routes/system.py` - Add auth dependencies
- `backend/requirements.txt` - Add auth packages
- `frontend/package.json` - Add new dependencies
- `frontend/src/App.tsx` - Router setup
- `frontend/src/services/api.ts` - Add auth headers
- `frontend/src/index.css` - Tailwind directives

### Removed/Simplified
- `frontend/src/components/SystemSettings.tsx` - Model selection removed

---

## Reference Commands

### Copy shadcn components from reference branch
```bash
# View component in reference branch
git show feature/ui-revamp-muaz:frontend/src/components/ui/button.tsx

# Copy specific file
git show feature/ui-revamp-muaz:frontend/src/components/ui/button.tsx > frontend/src/components/ui/button.tsx
```

### Copy auth files from reference branch
```bash
git show feature/ui-revamp-muaz:backend/app/api/routes/auth.py > backend/app/api/routes/auth.py
git show feature/ui-revamp-muaz:backend/app/core/security.py > backend/app/core/security.py
```

---

## Notes

- Keep DeepStream pipeline code unchanged
- Auth is stateless JWT - no session management needed
- Default admin: admin/admin123 (change in production!)
- Theme preference stored in localStorage
- Access tokens expire in 30 minutes, refresh tokens in 7 days
