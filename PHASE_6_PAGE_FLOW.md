# Phase 6: Dashboard Page Flow

## Visual Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         FIRST-RUN FLOW                          │
└─────────────────────────────────────────────────────────────────┘

User visits / (no users exist)
    │
    ├─> GET / → 302 Redirect to /setup
    │
    ├─> GET /setup (Welcome Page)
    │   ├─ Display: Welcome message, feature overview
    │   └─ Action: Click "Get Started"
    │
    ├─> GET /setup/admin (Admin Account Creation)
    │   ├─ Display: Username + password form
    │   ├─ Validation: Password strength indicator
    │   └─ Action: Submit form
    │
    ├─> POST /setup/admin
    │   ├─ Create: Admin user in database
    │   ├─ Auth: Set access_token + refresh_token cookies
    │   └─ Redirect: 302 to /setup/instance
    │
    ├─> GET /setup/instance (First Instance Config)
    │   ├─ Display: Instance type, name, URL, API key form
    │   ├─ Validation: Connection test button
    │   └─ Action: Submit form
    │
    ├─> POST /setup/instance
    │   ├─ Create: Instance in database
    │   ├─ Test: Connection to Sonarr/Radarr
    │   └─ Redirect: 302 to /setup/complete
    │
    ├─> GET /setup/complete (Setup Complete)
    │   ├─ Display: Success message, next steps
    │   └─ Action: Click "Go to Dashboard"
    │
    └─> 302 Redirect to /dashboard


┌─────────────────────────────────────────────────────────────────┐
│                          LOGIN FLOW                             │
└─────────────────────────────────────────────────────────────────┘

User visits / (not authenticated)
    │
    ├─> GET / → 302 Redirect to /login
    │
    ├─> GET /login (Login Page)
    │   ├─ Display: Username + password form
    │   └─ Action: Submit form
    │
    ├─> POST /api/auth/login (JSON)
    │   ├─ Validate: Username + password
    │   ├─ Auth: Set access_token + refresh_token cookies
    │   └─ Response: 200 OK with user info
    │
    └─> JavaScript redirects to /dashboard


┌─────────────────────────────────────────────────────────────────┐
│                      AUTHENTICATED FLOW                         │
└─────────────────────────────────────────────────────────────────┘

User visits / (authenticated)
    │
    ├─> GET / → 302 Redirect to /dashboard
    │
    └─> GET /dashboard (Main Dashboard)
        │
        ├─ Header:
        │  ├─ Navigation: Dashboard | Instances | Queues | History
        │  └─ User Menu: Settings | Logout
        │
        ├─ Body:
        │  ├─ Statistics Cards:
        │  │  ├─ Instances (total, active, inactive)
        │  │  ├─ Search Queues (total, active, paused)
        │  │  └─ Searches (today, this week, success rate)
        │  │
        │  ├─ Recent Activity Table:
        │  │  └─ Last 10 searches with status
        │  │
        │  └─ Quick Actions:
        │     ├─ Create Search Queue
        │     ├─ Add Instance
        │     └─ View History
        │
        └─ Auto-refresh: GET /api/dashboard/stats every 30s


┌─────────────────────────────────────────────────────────────────┐
│                        DASHBOARD PAGES                          │
└─────────────────────────────────────────────────────────────────┘

┌──────────────────────┐
│  INSTANCE MANAGEMENT │
│  /dashboard/instances│
└──────────────────────┘
│
├─ Display:
│  ├─ Grid of instance cards
│  ├─ Each card shows:
│  │  ├─ Name + Type (Sonarr/Radarr)
│  │  ├─ URL
│  │  ├─ Health status (●/✗/?)
│  │  ├─ Last checked time
│  │  └─ Actions: Test | Edit | Delete
│  │
│  └─ Add Instance button
│
└─ Actions:
   ├─ Test: POST /api/instances/{id}/test
   ├─ Delete: DELETE /api/instances/{id}
   └─ Add: Modal form → POST /api/instances


┌──────────────────────┐
│   QUEUE MANAGEMENT   │
│/dashboard/search-queue│
└──────────────────────┘
│
├─ Display:
│  ├─ Grid of queue cards
│  ├─ Each card shows:
│  │  ├─ Name + Status (●/⏸/✓/✗)
│  │  ├─ Instance
│  │  ├─ Strategy (recent/popular/oldest/random)
│  │  ├─ Type (one-time/recurring)
│  │  ├─ Next run time
│  │  ├─ Progress (X/Y items)
│  │  └─ Actions: Pause/Resume | View | Delete
│  │
│  └─ Create Queue button
│
└─ Actions:
   ├─ Pause: POST /api/search-queues/{id}/pause
   ├─ Resume: POST /api/search-queues/{id}/resume
   ├─ Delete: DELETE /api/search-queues/{id}
   └─ Create: Modal form → POST /api/search-queues


┌──────────────────────┐
│   SEARCH HISTORY     │
│/dashboard/search-history│
└──────────────────────┘
│
├─ Display:
│  ├─ Table with columns:
│  │  ├─ Instance
│  │  ├─ Queue
│  │  ├─ Strategy
│  │  ├─ Status (✓/⟳/✗)
│  │  ├─ Items (searched / found)
│  │  ├─ Started
│  │  └─ Duration
│  │
│  └─ Pagination controls
│
└─ Pagination:
   ├─ 20 items per page
   ├─ Previous button (if page > 1)
   ├─ Page X of Y indicator
   └─ Next button (if page < total)


┌──────────────────────┐
│      SETTINGS        │
│  /dashboard/settings │
└──────────────────────┘
│
├─ Account Information:
│  ├─ Username
│  ├─ Role (Admin/User)
│  ├─ Account created
│  └─ Last login
│
├─ Change Password:
│  ├─ Current password
│  ├─ New password (with strength indicator)
│  ├─ Confirm password
│  └─ Submit → POST /api/auth/password/change
│
├─ Two-Factor Authentication:
│  ├─ Enable/Disable toggle
│  └─ QR code (if enabling)
│
└─ Danger Zone:
   └─ Logout All Sessions → POST /api/auth/logout


┌─────────────────────────────────────────────────────────────────┐
│                         API ENDPOINTS                           │
└─────────────────────────────────────────────────────────────────┘

Dashboard UI (HTML):
├─ GET  /                          → Redirect to appropriate page
├─ GET  /login                     → Login page
├─ GET  /setup                     → Setup wizard welcome
├─ GET  /setup/admin               → Admin account creation
├─ POST /setup/admin               → Create admin account
├─ GET  /setup/instance            → First instance config
├─ POST /setup/instance            → Create first instance
├─ GET  /setup/complete            → Setup complete page
├─ GET  /dashboard                 → Main dashboard
├─ GET  /dashboard/instances       → Instance management
├─ GET  /dashboard/search-queues   → Queue management
├─ GET  /dashboard/search-history  → Search history (paginated)
└─ GET  /dashboard/settings        → User settings

Dashboard API (JSON):
├─ GET  /api/dashboard/stats       → Statistics aggregation
└─ GET  /api/dashboard/activity    → Recent activity feed

Existing API (used by dashboard):
├─ POST /api/auth/login            → Authenticate user
├─ POST /api/auth/logout           → Logout user
├─ POST /api/auth/password/change  → Change password
├─ GET  /api/instances             → List instances
├─ POST /api/instances             → Create instance
├─ POST /api/instances/{id}/test   → Test instance connection
├─ DELETE /api/instances/{id}      → Delete instance
├─ GET  /api/search-queues         → List queues
├─ POST /api/search-queues         → Create queue
├─ POST /api/search-queues/{id}/pause  → Pause queue
├─ POST /api/search-queues/{id}/resume → Resume queue
├─ DELETE /api/search-queues/{id}  → Delete queue
└─ GET  /api/search-history        → List search history


┌─────────────────────────────────────────────────────────────────┐
│                      AUTHENTICATION FLOW                        │
└─────────────────────────────────────────────────────────────────┘

Cookie-Based Authentication:

1. User logs in:
   POST /api/auth/login
   └─> Server sets cookies:
       ├─ access_token (15 min, path=/)
       └─ refresh_token (30 days, path=/api/auth)

2. User visits dashboard page:
   GET /dashboard
   └─> Browser sends cookie: access_token=...
       ├─> Server validates token
       │   ├─ Valid? → Render page
       │   └─ Invalid? → 401 Unauthorized
       └─> Dashboard depends on get_current_user_from_cookie()

3. AJAX requests:
   GET /api/dashboard/stats
   └─> Browser sends cookie: access_token=...
       ├─> Server validates token
       │   ├─ Valid? → Return JSON
       │   └─ Invalid? → 401 Unauthorized
       └─> API depends on get_current_user_from_cookie()

4. Token expires:
   POST /api/auth/refresh
   └─> Browser sends cookie: refresh_token=...
       ├─> Server validates refresh token
       ├─> Server issues new access + refresh tokens
       └─> Browser updates cookies


┌─────────────────────────────────────────────────────────────────┐
│                        RESPONSIVE DESIGN                        │
└─────────────────────────────────────────────────────────────────┘

Desktop (>992px):
├─ Full navigation menu
├─ 3-column grid for statistics
├─ Full-width tables
└─ Side-by-side cards

Tablet (768px - 992px):
├─ Full navigation menu
├─ 2-column grid for statistics
├─ Scrollable tables
└─ Side-by-side cards

Mobile (<768px):
├─ Collapsible navigation menu
├─ 1-column grid (stacked)
├─ Scrollable tables
├─ Stacked cards
└─ Larger tap targets


┌─────────────────────────────────────────────────────────────────┐
│                          DATA FLOW                              │
└─────────────────────────────────────────────────────────────────┘

Dashboard Statistics Calculation:

1. Client requests: GET /api/dashboard/stats
   │
2. Server aggregates data:
   │
   ├─ Instances:
   │  ├─ Total: COUNT(*) FROM instances WHERE user_id=X
   │  ├─ Active: COUNT(*) WHERE user_id=X AND is_active=true
   │  └─ Inactive: Total - Active
   │
   ├─ Search Queues:
   │  ├─ Total: COUNT(*) FROM search_queues
   │  │         JOIN instances WHERE user_id=X
   │  ├─ Active: COUNT(*) WHERE is_active=true
   │  │         AND status IN ['pending', 'running']
   │  └─ Paused: Total - Active
   │
   └─ Searches:
      ├─ Today: COUNT(*) FROM search_history
      │         JOIN instances WHERE user_id=X
      │         AND started_at >= today
      ├─ This Week: COUNT(*) WHERE started_at >= week_ago
      └─ Success Rate: (completed / total) * 100
                       WHERE started_at >= week_ago

3. Server returns JSON:
   {
     "instances": {"total": 3, "active": 2, "inactive": 1},
     "search_queues": {"total": 5, "active": 2, "paused": 3},
     "searches": {"today": 45, "this_week": 312, "success_rate": 78.5}
   }

4. Client updates UI:
   ├─ Update statistics cards
   ├─ Update status indicators
   └─ Schedule next refresh (30s)


┌─────────────────────────────────────────────────────────────────┐
│                      ERROR HANDLING                             │
└─────────────────────────────────────────────────────────────────┘

Authentication Errors:
├─ 401 Unauthorized → Redirect to /login
├─ 403 Forbidden → Display error message
└─ Token expired → POST /api/auth/refresh

Validation Errors:
├─ Client-side: Display inline error (JavaScript)
├─ Server-side: Return 400 with error message
└─ Display: Flash message or inline error

Database Errors:
├─ Catch: Exception in endpoint
├─ Log: structlog.error()
├─ Return: 500 Internal Server Error
└─ Display: Generic error message (no details)

Connection Errors (Instance Test):
├─ Catch: SonarrError / RadarrError
├─ Return: 400 with specific error message
└─ Display: Error in modal or inline


┌─────────────────────────────────────────────────────────────────┐
│                       STATE MANAGEMENT                          │
└─────────────────────────────────────────────────────────────────┘

Server-Side State:
├─ Database: SQLite + SQLCipher
├─ Sessions: JWT tokens (stateless)
├─ Cookies: HTTP-only, Secure, SameSite
└─ Cache: None (always fresh data)

Client-Side State:
├─ DOM: Rendered by server (Jinja2)
├─ Forms: Native HTML forms
├─ AJAX: Fetch API for JSON endpoints
└─ Auto-refresh: setInterval (30s)

No client-side state management library needed:
├─ No React/Vue/Angular
├─ No Redux/Vuex/MobX
└─ Pure vanilla JavaScript
```

## Key Design Decisions

### 1. Server-Side Rendering
**Why**: Fast initial load, SEO-friendly, works without JavaScript
**Trade-off**: Full page reloads on navigation

### 2. Cookie-Based Authentication
**Why**: Secure (HTTP-only), simple, works across tabs
**Trade-off**: Not suitable for mobile apps (use tokens)

### 3. Progressive Enhancement
**Why**: Works without JavaScript, graceful degradation
**Trade-off**: Some features require JavaScript (auto-refresh)

### 4. Minimal JavaScript
**Why**: Fast, maintainable, no build step required
**Trade-off**: No reactive UI updates (manual refresh)

### 5. Pico CSS Framework
**Why**: Classless, semantic HTML, small size (10KB gzipped)
**Trade-off**: Less customizable than Bootstrap/Tailwind

### 6. Auto-Refresh Polling
**Why**: Simple, works with existing infrastructure
**Trade-off**: Not real-time (30-second delay)

### 7. Pagination
**Why**: Handles large datasets efficiently
**Trade-off**: Requires multiple page loads

### 8. Modal Dialogs
**Why**: Native HTML `<dialog>` element, no library needed
**Trade-off**: Limited browser support (IE11)

## Navigation Map

```
Root (/)
├─ Setup Wizard (/setup)
│  ├─ Welcome (/setup)
│  ├─ Admin Account (/setup/admin)
│  ├─ First Instance (/setup/instance)
│  └─ Complete (/setup/complete)
│
├─ Login (/login)
│
└─ Dashboard (/dashboard)
   ├─ Main (/dashboard)
   ├─ Instances (/dashboard/instances)
   ├─ Search Queues (/dashboard/search-queues)
   ├─ Search History (/dashboard/search-history)
   └─ Settings (/dashboard/settings)
      ├─ Account Info
      ├─ Change Password
      ├─ Two-Factor Auth
      └─ Logout All Sessions
```

## Component Hierarchy

```
base.html (Common Layout)
├─ <head>
│  ├─ Meta tags
│  ├─ Pico CSS
│  └─ Custom CSS
│
├─ <nav> (If authenticated)
│  ├─ Logo/App Name
│  ├─ Main Navigation
│  │  ├─ Dashboard
│  │  ├─ Instances
│  │  ├─ Queues
│  │  └─ History
│  │
│  └─ User Menu
│     ├─ Settings
│     └─ Logout
│
├─ <main>
│  ├─ Flash Messages (errors/success)
│  └─ {% block content %}
│     │
│     ├─ setup/welcome.html
│     ├─ setup/admin.html
│     ├─ setup/instance.html
│     ├─ setup/complete.html
│     ├─ auth/login.html
│     ├─ dashboard/index.html
│     ├─ dashboard/instances.html
│     ├─ dashboard/search_queues.html
│     ├─ dashboard/search_history.html
│     └─ dashboard/settings.html
│
├─ <footer>
│  └─ Version + Links
│
└─ <scripts>
   ├─ app.js (Custom JS)
   └─ {% block extra_scripts %}
```

---

**This page flow diagram provides a visual reference for understanding how users navigate through the Vibe-Quality-Searcharr dashboard and how data flows between the client and server.**
