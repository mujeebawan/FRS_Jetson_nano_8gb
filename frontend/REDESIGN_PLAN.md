# Frontend UI Redesign Plan

## Overview

Major UI revamp of the Face Recognition Security System frontend to create a professional, modern interface using shadcn/ui component library.

---

## Design Decisions

| Decision | Choice |
|----------|--------|
| Component Library | shadcn/ui |
| Sidebar Style | Collapsible (expand/collapse with icons-only mode) |
| Pages | Keep current 4 sections (Dashboard, Persons, Alerts, Settings) |
| Theme | Dark/Light mode with toggle |
| Routing | React Router with URL-based navigation |

---

## Phase 1: Setup & Infrastructure

### 1.1 Install Dependencies

```bash
# shadcn/ui requires Tailwind CSS
npm install -D tailwindcss postcss autoprefixer
npm install tailwindcss-animate class-variance-authority clsx tailwind-merge

# Radix UI primitives (shadcn foundation)
npm install @radix-ui/react-slot @radix-ui/react-icons

# React Router for page routing
npm install react-router-dom

# Theme support
npm install next-themes
```

### 1.2 Configure Tailwind CSS

- Initialize Tailwind: `npx tailwindcss init -p`
- Configure `tailwind.config.js` with shadcn preset
- Set up CSS variables for theming in `src/index.css`
- Configure dark mode: `darkMode: ["class"]`

### 1.3 Initialize shadcn/ui

```bash
npx shadcn@latest init
```

Configuration choices:
- Style: Default
- Base color: Slate (professional look)
- CSS variables: Yes
- Tailwind config: tailwind.config.js
- Components location: src/components/ui
- Utils location: src/lib/utils.ts

### 1.4 Install Required shadcn Components

```bash
npx shadcn@latest add button
npx shadcn@latest add card
npx shadcn@latest add input
npx shadcn@latest add label
npx shadcn@latest add select
npx shadcn@latest add slider
npx shadcn@latest add switch
npx shadcn@latest add tabs
npx shadcn@latest add table
npx shadcn@latest add badge
npx shadcn@latest add avatar
npx shadcn@latest add dialog
npx shadcn@latest add dropdown-menu
npx shadcn@latest add sheet
npx shadcn@latest add tooltip
npx shadcn@latest add separator
npx shadcn@latest add scroll-area
npx shadcn@latest add skeleton
npx shadcn@latest add alert
npx shadcn@latest add progress
npx shadcn@latest add sidebar
npx shadcn@latest add breadcrumb
npx shadcn@latest add collapsible
```

---

## Phase 2: Project Structure Reorganization

### 2.1 New Directory Structure

```
frontend/src/
├── components/
│   ├── ui/                    # shadcn components (auto-generated)
│   │   ├── button.tsx
│   │   ├── card.tsx
│   │   ├── sidebar.tsx
│   │   └── ...
│   ├── layout/                # Layout components
│   │   ├── AppSidebar.tsx     # Main collapsible sidebar
│   │   ├── Header.tsx         # Top header with breadcrumbs
│   │   ├── ThemeToggle.tsx    # Dark/light mode toggle
│   │   └── MainLayout.tsx     # Main layout wrapper
│   ├── dashboard/             # Dashboard-specific components
│   │   ├── LiveStreamCard.tsx
│   │   ├── SystemStatusCard.tsx
│   │   ├── RecentAlertsCard.tsx
│   │   └── StatsOverview.tsx
│   ├── persons/               # Person management components
│   │   ├── PersonsTable.tsx
│   │   ├── PersonDetailsDialog.tsx
│   │   ├── EnrollPersonDialog.tsx
│   │   └── PersonCard.tsx
│   ├── alerts/                # Alert components
│   │   ├── AlertsTable.tsx
│   │   ├── AlertFilters.tsx
│   │   ├── AlertDetailsDialog.tsx
│   │   └── AlertVideoPlayer.tsx
│   └── settings/              # Settings components
│       ├── DetectionSettings.tsx
│       ├── RecognitionSettings.tsx
│       ├── CameraSettings.tsx
│       ├── StorageSettings.tsx
│       └── SystemInfo.tsx
├── pages/                     # Route pages
│   ├── DashboardPage.tsx
│   ├── PersonsPage.tsx
│   ├── AlertsPage.tsx
│   └── SettingsPage.tsx
├── hooks/                     # Custom hooks
│   ├── useStreamStatus.ts
│   ├── useSystemStatus.ts
│   ├── usePersons.ts
│   ├── useAlerts.ts
│   └── useSettings.ts
├── lib/                       # Utilities
│   └── utils.ts               # shadcn utility functions (cn)
├── services/
│   └── api.ts                 # Keep existing API service
├── providers/                 # Context providers
│   └── ThemeProvider.tsx
├── App.tsx                    # Router setup
├── main.tsx                   # Entry point with providers
└── index.css                  # Tailwind + shadcn styles
```

---

## Phase 3: Layout & Navigation Implementation

### 3.1 Collapsible Sidebar Design

```
┌─────────────────────────────────────────────────────────┐
│  [Logo]  FRS Security        [<<]  │    Header / Breadcrumb    │
├─────────────────────────────────────┼─────────────────────────────┤
│                                     │                             │
│  📊 Dashboard                       │                             │
│  👥 Persons                         │      Page Content           │
│  🔔 Alerts (badge: 5)               │                             │
│  ⚙️  Settings                        │                             │
│                                     │                             │
│                                     │                             │
│  ─────────────                      │                             │
│  System Status                      │                             │
│  ● Stream: Active                   │                             │
│  ● Camera: Connected                │                             │
│                                     │                             │
├─────────────────────────────────────┤                             │
│  [🌙/☀️] Theme    [User]            │                             │
└─────────────────────────────────────┴─────────────────────────────┘

Collapsed State:
┌────┬──────────────────────────────────────────────────────────────┐
│ 📊 │  Header / Breadcrumb                                         │
│ 👥 ├──────────────────────────────────────────────────────────────┤
│ 🔔 │                                                              │
│ ⚙️  │                    Page Content                              │
│    │                                                              │
│    │                                                              │
└────┴──────────────────────────────────────────────────────────────┘
```

### 3.2 Sidebar Features

- **Collapsible**: Click toggle button or use keyboard shortcut (Ctrl+B)
- **Icons + Labels**: Full mode shows both, collapsed shows icons only
- **Active State**: Highlight current page
- **Badge Support**: Show alert count on Alerts menu item
- **System Status Footer**: Quick status indicators at bottom
- **Theme Toggle**: Dark/light mode switch in footer
- **Tooltips**: Show page name on hover when collapsed

### 3.3 React Router Setup

```typescript
// Routes configuration
const routes = [
  { path: "/", element: <Navigate to="/dashboard" /> },
  { path: "/dashboard", element: <DashboardPage /> },
  { path: "/persons", element: <PersonsPage /> },
  { path: "/persons/:id", element: <PersonDetailsPage /> },
  { path: "/alerts", element: <AlertsPage /> },
  { path: "/alerts/:id", element: <AlertDetailsPage /> },
  { path: "/settings", element: <SettingsPage /> },
  { path: "/settings/:section", element: <SettingsPage /> },
];
```

---

## Phase 4: Page Designs

### 4.1 Dashboard Page

```
┌─────────────────────────────────────────────────────────────────┐
│  Dashboard                                    [🔄 Refresh]      │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐           │
│  │ 👥 12    │ │ 🔔 5     │ │ 📹 30fps │ │ 🖥️ 45%   │           │
│  │ Persons  │ │ Alerts   │ │ Stream   │ │ GPU      │           │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘           │
│                                                                 │
│  ┌─────────────────────────────────┐ ┌─────────────────────────┐│
│  │        Live Stream              │ │     Recent Alerts       ││
│  │   ┌─────────────────────────┐   │ │  ┌───────────────────┐  ││
│  │   │                         │   │ │  │ John Doe - 2m ago │  ││
│  │   │      Video Feed         │   │ │  │ Unknown - 5m ago  │  ││
│  │   │                         │   │ │  │ Jane Doe - 10m ago│  ││
│  │   └─────────────────────────┘   │ │  └───────────────────┘  ││
│  │   [▶️] [⏸️] [🔍+] [🔍-] [⛶]    │ │  [View All Alerts →]    ││
│  └─────────────────────────────────┘ └─────────────────────────┘│
│                                                                 │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │                    System Status                            ││
│  │  CPU: ████████░░ 78%   GPU: ██████░░░░ 60%   Temp: 52°C    ││
│  │  Memory: 4.2/8 GB      Storage: 12/64 GB                   ││
│  └─────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
```

**Components:**
- Stats cards (4 top cards with key metrics)
- Live stream card with controls
- Recent alerts card with quick list
- System status card with progress bars

### 4.2 Persons Page

```
┌─────────────────────────────────────────────────────────────────┐
│  Persons                               [🔍 Search] [+ Enroll]   │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ Photo │ Name        │ ID Card    │ Status    │ Last Seen   ││
│  ├───────┼─────────────┼────────────┼───────────┼─────────────┤│
│  │ [img] │ John Doe    │ ABC123     │ 🟢 Active │ 2 hours ago ││
│  │ [img] │ Jane Smith  │ XYZ789     │ 🔴 Watchlist│ 1 day ago  ││
│  │ [img] │ Bob Wilson  │ DEF456     │ 🟢 Active │ 5 mins ago  ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                 │
│  Showing 1-10 of 45                    [< Prev] [1] [2] [Next >]│
└─────────────────────────────────────────────────────────────────┘
```

**Components:**
- Search input with debounce
- Enroll button (opens dialog)
- Data table with sorting
- Person row with avatar, details, status badge
- Pagination
- Click row → Opens person details dialog

### 4.3 Alerts Page

```
┌─────────────────────────────────────────────────────────────────┐
│  Alerts                                          [📥 Export]    │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ Filters: [Time ▾] [Threat Level ▾] [Status ▾] [🔍 Search]   ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                 │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ Snapshot│ Person     │ Threat │ Time       │ Status │Action ││
│  ├─────────┼────────────┼────────┼────────────┼────────┼───────┤│
│  │ [img]   │ John Doe   │ 🟡 Med │ 2:30 PM    │ New    │ [👁️]  ││
│  │ [img]   │ Unknown    │ 🔴 High│ 2:25 PM    │ Ack    │ [👁️]  ││
│  │ [img]   │ Jane Smith │ 🟢 Low │ 2:20 PM    │ Verified│[👁️]  ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                 │
│  Showing 1-20 of 156                   [< Prev] [1] [2] [Next >]│
└─────────────────────────────────────────────────────────────────┘
```

**Components:**
- Filter bar with dropdowns
- Search input
- Export button
- Data table with thumbnails
- Threat level badges (color-coded)
- Status badges
- Action buttons
- Click row → Alert details dialog with video

### 4.4 Settings Page

```
┌─────────────────────────────────────────────────────────────────┐
│  Settings                                                       │
├─────────────────────────────────────────────────────────────────┤
│  ┌────────────────┐ ┌──────────────────────────────────────────┐│
│  │                │ │                                          ││
│  │ 📹 Detection   │ │  Detection Settings                      ││
│  │ 🎯 Recognition │ │  ────────────────────────────────────    ││
│  │ 🎥 Camera      │ │                                          ││
│  │ 💾 Storage     │ │  Confidence Threshold                    ││
│  │ 📊 System      │ │  [━━━━━━━━━●━━] 0.65                     ││
│  │                │ │                                          ││
│  │                │ │  Frame Skip                              ││
│  │                │ │  [━━●━━━━━━━━━] 2                        ││
│  │                │ │                                          ││
│  │                │ │  Motion Detection [🔘 On]                ││
│  │                │ │                                          ││
│  │                │ │  [Save Changes]                          ││
│  └────────────────┘ └──────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
```

**Components:**
- Vertical tabs for settings sections
- Detection: Thresholds, frame skip, motion toggle
- Recognition: Model selection, FP16/FP32, similarity threshold
- Camera: PTZ controls, zoom, connection settings
- Storage: Usage display, cleanup actions, retention settings
- System: Resource monitoring, temperature, power

---

## Phase 5: Theme System

### 5.1 Color Palette

**Light Mode:**
```css
--background: 0 0% 100%;
--foreground: 222.2 84% 4.9%;
--card: 0 0% 100%;
--card-foreground: 222.2 84% 4.9%;
--primary: 221.2 83.2% 53.3%;      /* Blue */
--primary-foreground: 210 40% 98%;
--secondary: 210 40% 96.1%;
--muted: 210 40% 96.1%;
--accent: 210 40% 96.1%;
--destructive: 0 84.2% 60.2%;      /* Red */
--success: 142.1 76.2% 36.3%;      /* Green */
--warning: 38 92% 50%;             /* Orange */
```

**Dark Mode:**
```css
--background: 222.2 84% 4.9%;
--foreground: 210 40% 98%;
--card: 217.2 32.6% 17.5%;
--card-foreground: 210 40% 98%;
--primary: 217.2 91.2% 59.8%;      /* Blue */
--primary-foreground: 222.2 47.4% 11.2%;
--secondary: 217.2 32.6% 17.5%;
--muted: 217.2 32.6% 17.5%;
--accent: 217.2 32.6% 17.5%;
--destructive: 0 62.8% 50.6%;      /* Red */
--success: 142.1 70.6% 45.3%;      /* Green */
--warning: 38 92% 50%;             /* Orange */
```

### 5.2 Theme Provider

- Use `next-themes` for theme management
- Store preference in localStorage
- System preference detection
- Smooth transition between themes

---

## Phase 6: Migration Strategy

### 6.1 Incremental Migration Steps

1. **Setup Phase** (Phase 1)
   - Install all dependencies
   - Configure Tailwind + shadcn
   - Set up folder structure

2. **Layout First** (Phase 3)
   - Create MainLayout with sidebar
   - Set up React Router
   - Implement theme toggle
   - Keep old components working inside new layout

3. **Page by Page Migration** (Phase 4)
   - Dashboard → DashboardPage (migrate LiveStream, SystemStatus)
   - Persons → PersonsPage (migrate PersonList)
   - Alerts → AlertsPage (migrate AlertList)
   - Settings → SettingsPage (migrate SystemSettings)

4. **Component Replacement**
   - Replace custom buttons → shadcn Button
   - Replace custom inputs → shadcn Input
   - Replace custom modals → shadcn Dialog
   - Replace custom tables → shadcn Table
   - Replace custom dropdowns → shadcn Select/DropdownMenu

5. **Cleanup**
   - Remove old App.css (3000+ lines)
   - Remove unused components
   - Final testing

### 6.2 Files to Delete After Migration

- `src/App.css` (replaced by Tailwind)
- Old component files after migration complete

### 6.3 Files to Keep/Modify

- `src/services/api.ts` (keep as-is, works well)
- `src/main.tsx` (add providers)
- `src/App.tsx` (replace with router)

---

## Phase 7: Implementation Checklist

### Setup
- [ ] Install Tailwind CSS and configure
- [ ] Initialize shadcn/ui
- [ ] Install all required shadcn components
- [ ] Set up folder structure
- [ ] Configure theme system with next-themes
- [ ] Install and configure React Router

### Layout
- [ ] Create ThemeProvider
- [ ] Create AppSidebar component
- [ ] Create Header component with breadcrumbs
- [ ] Create MainLayout wrapper
- [ ] Implement collapsible sidebar logic
- [ ] Add theme toggle

### Pages
- [ ] Create DashboardPage
- [ ] Create PersonsPage
- [ ] Create AlertsPage
- [ ] Create SettingsPage
- [ ] Set up all routes

### Dashboard Components
- [ ] StatsOverview (4 metric cards)
- [ ] LiveStreamCard
- [ ] RecentAlertsCard
- [ ] SystemStatusCard

### Person Components
- [ ] PersonsTable with DataTable
- [ ] PersonDetailsDialog
- [ ] EnrollPersonDialog
- [ ] Camera capture integration

### Alert Components
- [ ] AlertsTable with DataTable
- [ ] AlertFilters component
- [ ] AlertDetailsDialog
- [ ] AlertVideoPlayer

### Settings Components
- [ ] DetectionSettings
- [ ] RecognitionSettings
- [ ] CameraSettings (PTZ)
- [ ] StorageSettings
- [ ] SystemInfo

### Custom Hooks
- [ ] useStreamStatus
- [ ] useSystemStatus
- [ ] usePersons
- [ ] useAlerts
- [ ] useSettings

### Final Steps
- [ ] Remove old CSS
- [ ] Remove old components
- [ ] Test all functionality
- [ ] Verify dark/light themes
- [ ] Test responsive behavior
- [ ] Performance testing

---

## Estimated Component Count

| Category | Count |
|----------|-------|
| shadcn/ui components | ~20 |
| Layout components | 4 |
| Page components | 4 |
| Dashboard components | 4 |
| Person components | 4 |
| Alert components | 4 |
| Settings components | 5 |
| Custom hooks | 5 |
| **Total new files** | **~50** |

---

## Notes

- Keep existing API service (`api.ts`) - it's well structured
- Maintain all current functionality during migration
- Test each page after migration before moving to next
- Use TypeScript strictly throughout
- Follow shadcn/ui patterns and conventions
