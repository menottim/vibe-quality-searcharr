# Dashboard Developer Guide

Quick reference for working with the Vibe-Quality-Searcharr web dashboard.

## Quick Start

```bash
# Start the development server
uvicorn vibe_quality_searcharr.main:app --reload --port 8000

# Open browser
http://localhost:8000

# First run: setup wizard at /setup
# After setup: login at /login
# Dashboard at /dashboard
```

## Project Structure

```
src/vibe_quality_searcharr/
├── api/
│   ├── dashboard.py       # Dashboard web UI routes
│   ├── auth.py            # Authentication API
│   ├── instances.py       # Instance management API
│   ├── search_queue.py    # Queue management API
│   └── search_history.py  # History API
├── templates/
│   ├── base.html          # Base template with navigation
│   ├── components/        # Reusable components
│   ├── auth/              # Login page
│   ├── setup/             # Setup wizard (4 steps)
│   └── dashboard/         # Dashboard pages
└── static/
    ├── css/
    │   ├── pico.min.css   # CSS framework
    │   └── custom.css     # Custom styles
    └── js/
        └── app.js         # Dashboard JavaScript
```

## Adding a New Dashboard Page

### 1. Create Route in `api/dashboard.py`

```python
@router.get("/dashboard/my-page", response_class=HTMLResponse, include_in_schema=False)
async def my_page(
    request: Request,
    current_user: User = Depends(get_current_user_from_cookie),
    db: Session = Depends(get_db),
) -> Response:
    """
    My new dashboard page.
    """
    # Fetch data
    data = db.query(MyModel).filter(MyModel.user_id == current_user.id).all()

    # Render template
    return templates.TemplateResponse(
        "dashboard/my_page.html",
        {
            "request": request,
            "user": current_user,
            "data": data,
        },
    )
```

### 2. Create Template in `templates/dashboard/`

```html
{% extends "base.html" %}

{% block title %}My Page - Vibe-Quality-Searcharr{% endblock %}

{% block content %}
<hgroup>
    <h1>My Page</h1>
    <p>Description of what this page does</p>
</hgroup>

<article>
    <!-- Your content here -->
</article>
{% endblock %}
```

### 3. Add to Navigation in `templates/base.html`

```html
<li><a href="/dashboard/my-page">My Page</a></li>
```

## Working with Templates

### Template Inheritance

All pages extend `base.html`:

```html
{% extends "base.html" %}

{% block title %}Page Title{% endblock %}

{% block content %}
    <!-- Your page content -->
{% endblock %}

{% block extra_scripts %}
    <!-- Optional: page-specific JavaScript -->
{% endblock %}
```

### Using Components

Include reusable components:

```html
<!-- Flash messages -->
{% include "components/flash.html" %}

<!-- Instance card -->
{% include "components/instance_card.html" with instance=instance %}

<!-- Queue card -->
{% include "components/queue_card.html" with queue=queue %}
```

### Available Template Filters

```html
<!-- Format datetime -->
{{ user.created_at|datetime }}
Output: 2025-01-15 14:30:00

<!-- Time ago -->
{{ instance.last_health_check|timeago }}
Output: 2 hours ago
```

### Template Variables

All authenticated pages receive:
- `request` - FastAPI request object
- `user` - Current user object
- Custom data passed from route

## Styling Guide

### Pico CSS Classes

```html
<!-- Containers -->
<div class="container">...</div>
<div class="container-fluid">...</div>

<!-- Grid layout -->
<div class="grid">
    <article>Card 1</article>
    <article>Card 2</article>
    <article>Card 3</article>
</div>

<!-- Buttons -->
<button>Primary Button</button>
<button class="secondary">Secondary</button>
<button class="contrast">Contrast</button>

<!-- Forms -->
<label for="name">
    Name
    <input type="text" id="name" name="name" required>
    <small>Helper text</small>
</label>

<!-- Tables -->
<table role="grid">
    <thead>...</thead>
    <tbody>...</tbody>
</table>

<!-- Loading state -->
<button aria-busy="true">Loading...</button>
```

### Custom Status Colors

```html
<!-- Status indicators -->
<span style="color: var(--ins-color);">✓ Healthy</span>
<span style="color: var(--del-color);">✗ Failed</span>
<span style="color: var(--primary);">⟳ Running</span>
<span style="color: var(--muted-color);">● Unknown</span>
```

### Custom Classes (from `custom.css`)

```html
<!-- Status classes -->
<span class="status-healthy">Healthy</span>
<span class="status-unhealthy">Unhealthy</span>
<span class="status-warning">Warning</span>
<span class="status-unknown">Unknown</span>

<!-- Utility classes -->
<div class="text-center">Centered text</div>
<div class="text-right">Right-aligned</div>
<div class="text-muted">Muted text</div>
<div class="text-success">Success text</div>
<div class="text-error">Error text</div>

<!-- Empty state -->
<div class="empty-state">
    <p>No items yet</p>
</div>
```

## JavaScript Guide

### Using the API Helper

```javascript
// Available globally as window.QualitySearcharr

// Make API call
const result = await QualitySearcharr.apiCall('/api/instances', {
    method: 'POST',
    body: JSON.stringify({...})
});

if (result.success) {
    console.log(result.data);
} else {
    console.error(result.error);
}
```

### Form Validation

```javascript
// Validate password
const errors = QualitySearcharr.validatePassword('mypassword');
if (errors.length > 0) {
    alert('Password errors: ' + errors.join(', '));
}

// Validate username
const errors = QualitySearcharr.validateUsername('myuser');
if (errors.length > 0) {
    alert('Username errors: ' + errors.join(', '));
}
```

### Auto-Refresh

```javascript
// Create auto-refresh
const refresh = new QualitySearcharr.AutoRefresh(async () => {
    const result = await QualitySearcharr.apiCall('/api/dashboard/stats');
    if (result.success) {
        // Update UI with result.data
    }
}, 30000); // 30 seconds

// Start refreshing
refresh.start();

// Stop refreshing
refresh.stop();
```

### Format Dates

```javascript
// Format datetime
const formatted = QualitySearcharr.formatDateTime('2025-01-15T14:30:00');
console.log(formatted); // "1/15/2025, 2:30:00 PM"

// Format time ago
const ago = QualitySearcharr.formatTimeAgo('2025-01-15T14:30:00');
console.log(ago); // "2 hours ago"
```

## Common Patterns

### Confirming Destructive Actions

```javascript
async function deleteItem(id, name) {
    if (!confirm(`Are you sure you want to delete "${name}"?`)) {
        return;
    }

    try {
        const response = await fetch(`/api/items/${id}`, {
            method: 'DELETE'
        });

        if (response.ok) {
            location.reload();
        } else {
            const data = await response.json();
            alert('Delete failed: ' + (data.detail || 'Unknown error'));
        }
    } catch (error) {
        alert('Delete failed: ' + error.message);
    }
}
```

### Form Submission with AJAX

```html
<form id="myForm">
    <input type="text" name="name" required>
    <button type="submit" id="submitBtn">Submit</button>
</form>

<script>
document.getElementById('myForm').addEventListener('submit', async (e) => {
    e.preventDefault();

    const submitBtn = document.getElementById('submitBtn');
    submitBtn.disabled = true;
    submitBtn.setAttribute('aria-busy', 'true');

    const formData = {
        name: document.querySelector('input[name="name"]').value
    };

    try {
        const response = await fetch('/api/endpoint', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(formData)
        });

        if (response.ok) {
            window.location.href = '/success-page';
        } else {
            const data = await response.json();
            alert('Error: ' + (data.detail || 'Unknown error'));
            submitBtn.disabled = false;
            submitBtn.setAttribute('aria-busy', 'false');
        }
    } catch (error) {
        alert('Error: ' + error.message);
        submitBtn.disabled = false;
        submitBtn.setAttribute('aria-busy', 'false');
    }
});
</script>
```

### Displaying Flash Messages

In route handler:
```python
return templates.TemplateResponse(
    "dashboard/page.html",
    {
        "request": request,
        "user": current_user,
        "success": "Operation completed successfully!",
        # or "error": "Operation failed!"
        # or "warning": "Warning message"
        # or "info": "Information"
    },
)
```

Messages will auto-dismiss after 5 seconds.

### Creating Modals

```html
<!-- Button to open modal -->
<a href="#my-modal" role="button">Open Modal</a>

<!-- Modal dialog -->
<dialog id="my-modal">
    <article>
        <header>
            <a href="#close" aria-label="Close" class="close" onclick="closeModal()"></a>
            <h3>Modal Title</h3>
        </header>

        <p>Modal content here</p>

        <footer>
            <button class="secondary" onclick="closeModal()">Cancel</button>
            <button onclick="handleSubmit()">Submit</button>
        </footer>
    </article>
</dialog>

<script>
function closeModal() {
    document.getElementById('my-modal').close();
}

function handleSubmit() {
    // Handle submission
    closeModal();
}
</script>
```

## Testing

### Writing Dashboard Tests

```python
def test_my_page_renders(authenticated_client):
    """My page should render successfully."""
    response = authenticated_client.get("/dashboard/my-page")
    assert response.status_code == 200
    assert b"My Page Title" in response.content

def test_my_page_requires_auth(client):
    """My page should require authentication."""
    response = client.get("/dashboard/my-page", follow_redirects=False)
    assert response.status_code in [302, 401]
```

### Running Tests

```bash
# Run all dashboard tests
pytest tests/integration/test_dashboard_routes.py -v

# Run specific test
pytest tests/integration/test_dashboard_routes.py::TestClass::test_name -v

# Run with coverage
pytest tests/integration/test_dashboard_routes.py --cov=vibe_quality_searcharr.api.dashboard
```

## Debugging Tips

### Enable Debug Mode

```bash
# Set environment variable
export LOG_LEVEL=DEBUG

# Or in .env file
LOG_LEVEL=DEBUG

# Run with reload
uvicorn vibe_quality_searcharr.main:app --reload --log-level debug
```

### Check Logs

```python
# Add logging to routes
logger.info("my_page_accessed", user_id=current_user.id)
logger.warning("validation_failed", error=str(e))
logger.error("database_error", error=str(e))
```

### Browser DevTools

1. **Network Tab**: Check API calls and responses
2. **Console**: Check for JavaScript errors
3. **Elements**: Inspect rendered HTML
4. **Application**: Check cookies and storage

### Common Issues

**Templates not found:**
- Check path in `dashboard.py` line 50: should be `src/vibe_quality_searcharr/templates`
- Verify template file exists
- Check spelling/capitalization

**Static files not loading:**
- Verify `/static` mount in `main.py`
- Check file exists in `src/vibe_quality_searcharr/static/`
- Clear browser cache

**Authentication issues:**
- Check `access_token` cookie exists
- Verify token is not expired (15 min default)
- Check `get_current_user_from_cookie` dependency

**CORS errors:**
- Update `settings.cors_origins` in config
- Verify CORS middleware is configured in `main.py`

## Best Practices

1. **Always use type hints** in route handlers
2. **Add docstrings** to all routes
3. **Use template components** for reusable UI elements
4. **Validate user input** on both client and server
5. **Handle errors gracefully** with try/except
6. **Log important events** with structured logging
7. **Write tests** for new features
8. **Keep JavaScript minimal** - prefer server-side rendering
9. **Use semantic HTML** for accessibility
10. **Test on mobile** before considering complete

## Resources

- **FastAPI Docs**: https://fastapi.tiangolo.com/
- **Pico CSS Docs**: https://picocss.com/
- **Jinja2 Docs**: https://jinja.palletsprojects.com/
- **MDN Web Docs**: https://developer.mozilla.org/

## Getting Help

1. Check implementation summary: `PHASE6_IMPLEMENTATION_SUMMARY.md`
2. Review verification checklist: `PHASE6_VERIFICATION_CHECKLIST.md`
3. Look at existing templates for examples
4. Check test files for usage patterns
5. Review API documentation: http://localhost:8000/api/docs

---

**Happy Coding!** 🚀
