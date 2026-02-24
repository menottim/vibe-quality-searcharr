# Phase 6: Web Dashboard - Verification Checklist

## Pre-Deployment Verification

Use this checklist to verify Phase 6 implementation before release.

### 1. File Structure ✓

```bash
# Verify all template files exist
ls -1 src/vibe_quality_searcharr/templates/**/*.html

# Expected output:
# src/vibe_quality_searcharr/templates/base.html
# src/vibe_quality_searcharr/templates/auth/login.html
# src/vibe_quality_searcharr/templates/components/flash.html
# src/vibe_quality_searcharr/templates/components/instance_card.html
# src/vibe_quality_searcharr/templates/components/queue_card.html
# src/vibe_quality_searcharr/templates/dashboard/index.html
# src/vibe_quality_searcharr/templates/dashboard/instances.html
# src/vibe_quality_searcharr/templates/dashboard/search_history.html
# src/vibe_quality_searcharr/templates/dashboard/search_queues.html
# src/vibe_quality_searcharr/templates/dashboard/settings.html
# src/vibe_quality_searcharr/templates/setup/admin.html
# src/vibe_quality_searcharr/templates/setup/complete.html
# src/vibe_quality_searcharr/templates/setup/instance.html
# src/vibe_quality_searcharr/templates/setup/welcome.html
```

### 2. Syntax Validation ✓

```bash
# Check Python syntax
python -m py_compile src/vibe_quality_searcharr/api/dashboard.py
python -m py_compile src/vibe_quality_searcharr/api/instances.py
python -m py_compile src/vibe_quality_searcharr/main.py

# Expected: No output = success
```

### 3. Run Tests ✓

```bash
# Run dashboard integration tests
pytest tests/integration/test_dashboard_routes.py -v

# Expected: All tests pass
```

### 4. Manual Testing Checklist

#### Setup Wizard Flow
- [ ] Navigate to `/` on fresh install → redirects to `/setup`
- [ ] `/setup` displays welcome page with "Get Started" button
- [ ] Click "Get Started" → redirects to `/setup/admin`
- [ ] `/setup/admin` displays admin creation form
- [ ] Enter valid admin credentials → redirects to `/setup/instance`
- [ ] `/setup/instance` displays instance form with "Skip" option
- [ ] Test "Skip" button → redirects to `/setup/complete`
- [ ] Test "Test Connection" button with invalid credentials → shows error
- [ ] Test "Test Connection" button with valid credentials → shows success
- [ ] Submit valid instance → redirects to `/setup/complete`
- [ ] `/setup/complete` displays success message
- [ ] Click "Go to Dashboard" → redirects to `/dashboard`
- [ ] Try to access `/setup` again → redirects to `/` (setup is complete)

#### Authentication Flow
- [ ] Navigate to `/` when not authenticated → redirects to `/login`
- [ ] `/login` displays login form
- [ ] Submit invalid credentials → shows error message
- [ ] Submit valid credentials → redirects to `/dashboard`
- [ ] Try to access `/login` when authenticated → redirects to `/dashboard`
- [ ] Click "Logout" in navigation → logs out and redirects to `/login`

#### Dashboard
- [ ] `/dashboard` displays statistics cards
- [ ] Statistics show correct counts (instances, queues, searches)
- [ ] Recent activity table displays (or shows empty state)
- [ ] Auto-refresh indicator works (check console for updates every 30s)
- [ ] Navigation menu is visible and functional
- [ ] User dropdown shows username and logout option
- [ ] Quick actions section displays

#### Instances Management
- [ ] Navigate to `/dashboard/instances`
- [ ] Empty state message shows if no instances
- [ ] Click "Add Instance" button → shows modal/form
- [ ] Add instance with invalid URL → shows error
- [ ] Add instance with valid details → instance appears in list
- [ ] Instance card shows: name, type, URL, status, last checked
- [ ] Click "Test" button → shows connection result
- [ ] Click "Edit" button → (placeholder alert for now)
- [ ] Click "Delete" button → shows confirmation dialog
- [ ] Confirm delete → instance is removed

#### Search Queues Management
- [ ] Navigate to `/dashboard/search-queues`
- [ ] Empty state message shows if no queues
- [ ] Click "Create Queue" button → shows modal with form
- [ ] Create queue form has: instance selector, name, strategy, recurring option
- [ ] Toggle recurring → interval field appears/hides
- [ ] Submit valid queue → queue appears in list
- [ ] Queue card shows: name, status, strategy, type, progress
- [ ] Click "Pause" button on running queue → queue pauses
- [ ] Click "Resume" button on paused queue → queue resumes
- [ ] Click "View" button → (redirects to queue list for now)
- [ ] Click "Delete" button → shows confirmation and deletes

#### Search History
- [ ] Navigate to `/dashboard/search-history`
- [ ] Empty state message shows if no history
- [ ] History table displays with correct columns
- [ ] Pagination works (if >20 items)
- [ ] "Previous" and "Next" buttons work
- [ ] Summary statistics show correct counts

#### Settings
- [ ] Navigate to `/dashboard/settings`
- [ ] Account information displays correctly
- [ ] Change password form is present
- [ ] Submit password change with wrong current password → shows error
- [ ] Submit password change with mismatched new passwords → shows error
- [ ] Submit valid password change → success (logs out all sessions)
- [ ] 2FA section displays (enable/disable button based on status)
- [ ] "Logout All Sessions" button works

### 5. Security Verification

#### XSS Protection
```bash
# Test XSS prevention by creating instance with malicious name
# The <script> tag should be HTML-escaped in the output
```
- [ ] Create instance with name: `<script>alert('xss')</script>`
- [ ] View instances page
- [ ] Verify script does not execute (check page source for HTML entities)

#### Authentication Required
- [ ] Try to access `/dashboard` without authentication → redirects to `/login`
- [ ] Try to access `/api/dashboard/stats` without auth → returns 401
- [ ] Try to access dashboard pages without auth → redirects or returns 401

#### Security Headers
```bash
# Check security headers
curl -I http://localhost:8000/dashboard

# Expected headers:
# X-Content-Type-Options: nosniff
# X-Frame-Options: DENY
# X-XSS-Protection: 1; mode=block
# Content-Security-Policy: (CSP directive)
# Strict-Transport-Security: (if HTTPS and production)
```

### 6. Responsive Design

#### Desktop (1920x1080)
- [ ] Navigation menu displays horizontally
- [ ] Statistics cards display in grid (3 columns)
- [ ] Tables are readable
- [ ] Forms are appropriately sized

#### Tablet (768x1024)
- [ ] Navigation menu still functional
- [ ] Statistics cards stack appropriately
- [ ] Tables are scrollable
- [ ] Forms are appropriately sized

#### Mobile (375x667)
- [ ] Navigation collapses or stacks
- [ ] Statistics cards display vertically
- [ ] Tables are scrollable
- [ ] Forms are touch-friendly
- [ ] Buttons are appropriately sized

### 7. Browser Compatibility

Test on:
- [ ] Chrome (latest)
- [ ] Firefox (latest)
- [ ] Safari (latest)
- [ ] Edge (latest)
- [ ] Mobile Safari (iOS)
- [ ] Chrome Mobile (Android)

### 8. Performance Checks

#### Page Load Times
- [ ] `/dashboard` loads in < 1 second (without external API calls)
- [ ] `/dashboard/instances` loads in < 1 second
- [ ] `/dashboard/search-queues` loads in < 1 second
- [ ] `/dashboard/search-history` loads in < 1 second

#### Auto-Refresh
- [ ] Dashboard stats refresh every 30 seconds (check Network tab)
- [ ] Auto-refresh pauses when tab is hidden
- [ ] Auto-refresh resumes when tab is visible

#### Form Submission
- [ ] Form submissions show loading state (aria-busy)
- [ ] Form submissions don't cause full page reload (AJAX)
- [ ] Error messages display inline
- [ ] Success messages redirect appropriately

### 9. Accessibility Checks

#### Keyboard Navigation
- [ ] Tab through all form fields
- [ ] Tab through navigation menu
- [ ] Tab through buttons and links
- [ ] Enter key submits forms
- [ ] Escape key closes modals

#### Screen Reader Compatibility
- [ ] Form labels are associated with inputs
- [ ] Error messages are announced
- [ ] Loading states use aria-busy
- [ ] Buttons have descriptive text or aria-label

#### Color Contrast
- [ ] Text is readable on all backgrounds
- [ ] Links are distinguishable
- [ ] Error messages are visible
- [ ] Success messages are visible

### 10. Error Handling

#### Network Errors
- [ ] API call failures show error messages
- [ ] Connection timeouts are handled gracefully
- [ ] 404 errors show appropriate message
- [ ] 500 errors show appropriate message

#### Form Validation
- [ ] Required fields show error when empty
- [ ] Invalid URLs show error
- [ ] Weak passwords show error
- [ ] Mismatched passwords show error

#### Edge Cases
- [ ] Empty states display when no data
- [ ] Long names don't break layout
- [ ] Large numbers display correctly
- [ ] Special characters are handled
- [ ] Unicode characters display correctly

## Quick Test Script

```bash
#!/bin/bash
# Quick verification script

echo "🔍 Phase 6 Verification"
echo "======================="
echo ""

echo "1. Checking file structure..."
if [ -f "src/vibe_quality_searcharr/templates/base.html" ]; then
    echo "   ✓ Base template exists"
else
    echo "   ✗ Base template missing"
fi

if [ -f "src/vibe_quality_searcharr/static/css/custom.css" ]; then
    echo "   ✓ Custom CSS exists"
else
    echo "   ✗ Custom CSS missing"
fi

if [ -f "src/vibe_quality_searcharr/static/js/app.js" ]; then
    echo "   ✓ App JavaScript exists"
else
    echo "   ✗ App JavaScript missing"
fi

echo ""
echo "2. Checking Python syntax..."
python -m py_compile src/vibe_quality_searcharr/api/dashboard.py 2>/dev/null && echo "   ✓ dashboard.py syntax OK" || echo "   ✗ dashboard.py has errors"
python -m py_compile src/vibe_quality_searcharr/api/instances.py 2>/dev/null && echo "   ✓ instances.py syntax OK" || echo "   ✗ instances.py has errors"

echo ""
echo "3. Running tests..."
pytest tests/integration/test_dashboard_routes.py -q 2>/dev/null && echo "   ✓ Tests passed" || echo "   ⚠ Tests need attention"

echo ""
echo "4. Starting development server..."
echo "   Run: uvicorn vibe_quality_searcharr.main:app --reload"
echo "   Then navigate to: http://localhost:8000"
echo ""
echo "✅ Verification complete!"
```

## Post-Deployment Verification

After deploying to production:

1. **Smoke Tests**
   - [ ] Access root URL → appropriate redirect
   - [ ] Complete setup wizard (if fresh install)
   - [ ] Login works
   - [ ] Dashboard loads
   - [ ] Navigation works
   - [ ] Logout works

2. **Monitoring**
   - [ ] Check application logs for errors
   - [ ] Monitor response times
   - [ ] Check database query performance
   - [ ] Verify security headers in production

3. **User Acceptance**
   - [ ] Ask user to complete setup wizard
   - [ ] Ask user to navigate dashboard
   - [ ] Ask user to add instance
   - [ ] Ask user to create queue
   - [ ] Collect feedback

## Issues / Bugs Found

Document any issues found during verification:

| Issue | Severity | Status | Notes |
|-------|----------|--------|-------|
| (none yet) | - | - | - |

## Sign-Off

- [ ] All critical paths tested and working
- [ ] Security features verified
- [ ] Performance is acceptable
- [ ] Browser compatibility confirmed
- [ ] Accessibility checked
- [ ] Tests are passing
- [ ] Documentation reviewed

**Verified by:** _________________
**Date:** _________________
**Notes:** _________________

---

## Additional Resources

- **Implementation Summary:** `PHASE6_IMPLEMENTATION_SUMMARY.md`
- **Test Coverage:** `tests/integration/test_dashboard_routes.py`
- **API Documentation:** http://localhost:8000/api/docs (when running)
- **Templates Directory:** `src/vibe_quality_searcharr/templates/`
- **Static Assets:** `src/vibe_quality_searcharr/static/`
