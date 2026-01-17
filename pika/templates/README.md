# Templates Package

This package contains Jinja2 templates for the Pika-pika web application, providing clean separation between HTML structure, styling, and JavaScript functionality.

## Package Structure

```
templates/
├── base.html              # Base template with common head/body structure
├── index.html             # Main live monitoring page
├── components/             # Reusable template components
│   ├── header.html         # Page header and navigation
│   ├── chart.html          # Chart controls and canvas
│   ├── qr_code.html        # QR code display
│   └── highlights.html     # Highlights panel
└── README.md              # This file
```

## Template Architecture

### Base Template (`base.html`)
- **Common HTML structure**: DOCTYPE, head, body tags
- **Shared assets**: Chart.js, CSS, favicons, meta tags
- **Template blocks**: `{% block title %}`, `{% block content %}`, `{% block scripts %}`
- **Asset references**: Uses `{{ url_for('static', path='...') }}`

### Component Templates
- **Reusable components**: Header, chart, QR code, highlights
- **Self-contained**: Each component handles its own HTML structure
- **Consistent styling**: Uses same CSS classes and patterns

### Page Templates
- **Extend base**: `{% extends "base.html" %}`
- **Include components**: `{% include 'components/header.html' %}`
- **Block composition**: `{% block content %}` for page-specific content

## Benefits of This Structure

### 1. **Separation of Concerns**
- **HTML Structure**: Templates handle layout and markup
- **Styling**: CSS remains in separate files
- **JavaScript**: Extracted to dedicated modules
- **Business Logic**: Handled by FastAPI handlers

### 2. **Maintainability**
- **Reusable components**: Use header/chart/QR across multiple pages
- **Single source of truth**: Change component once, updates everywhere
- **Clear inheritance**: Base template ensures consistency

### 3. **Developer Experience**
- **IDE support**: Better syntax highlighting for templates
- **Component thinking**: Break UI into logical pieces
- **Easier testing**: Each component can be tested independently

## Migration Path

### Phase 1: Template Structure (Current)
```python
# Current approach - serve static HTML
def index(static_dir):
    return HTMLResponse(content=open(os.path.join(static_dir, "index.html")).read())
```

### Phase 2: Jinja2 Integration (Recommended)
```python
# Add to app.py
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="pika/templates")

@app.get("/")
async def index(request: Request):
    return templates.TemplateResponse("index.html", {
        "request": request,
        "page_title": "Pika-pika Live Monitor",
        "page_description": "Real-time voltage monitoring"
    })
```

### Phase 3: Component-Based Architecture
```html
<!-- templates/index.html -->
{% extends "base.html" %}

{% block content %}
{% include 'components/header.html' %}
{% include 'components/chart.html' %}
{% include 'components/qr_code.html' %}
{% include 'components/highlights.html' %}
{% endblock %}

{% block scripts %}
<script src="{{ url_for('static', path='/js/live_chart.js') }}"></script>
{% endblock %}
```

## Template Variables

### Base Template Variables
- `{{ url_for('static', path='...') }}`: Static asset URLs
- `{% block title %}`: Page title
- `{% block content %}`: Main page content
- `{% block extra_head %}`: Additional head content
- `{% block scripts %}`: Page-specific scripts

### Component Variables
- `{{ page_title }}`: Custom page title (optional)
- `{{ page_description }}`: Custom page description (optional)

## JavaScript Integration

### Modular JavaScript
- **Separated files**: `static/js/live_chart.js`
- **Class-based**: `LiveChartManager` class
- **Event-driven**: Clean event handling and WebSocket management
- **Testable**: Can be unit tested independently

### Benefits
- **Cacheable**: JavaScript files can be cached by browsers
- **Debuggable**: Separate files make debugging easier
- **Maintainable**: Logic organized into classes and methods

## Styling Strategy

### Current Approach
- **Material CSS**: External stylesheet for consistent theming
- **Inline styles**: Minimal, only for dynamic values
- **CSS variables**: Use `var(--muted)` for theming

### Future Improvements
- **CSS Modules**: Component-scoped styles
- **Tailwind CSS**: Utility-first styling approach
- **CSS-in-JS**: Styled-components for dynamic styling

## Performance Considerations

### Template Caching
```python
# FastAPI automatically caches templates
# For production, consider pre-compiling templates
templates = Jinja2Templates(
    directory="pika/templates",
    cache_size=100  # Enable template caching
)
```

### Asset Optimization
- **Minified CSS**: Use production CSS builds
- **JavaScript bundling**: Combine JS files
- **CDN assets**: Chart.js and other libraries from CDN

## Development Workflow

### 1. Local Development
```bash
# Run with auto-reload
uvicorn pika.app:app --reload
```

### 2. Template Testing
```python
# Test template rendering
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="pika/templates")
rendered = templates.get_template("index.html").render({"title": "Test"})
```

### 3. Component Development
- Create new component in `templates/components/`
- Include in page templates: `{% include 'components/new_component.html' %}`
- Test component independently

This template structure provides a solid foundation for scaling the Pika-pika web interface while maintaining clean separation of concerns and excellent developer experience.
