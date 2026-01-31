---
inclusion: always
---

# Python Execution Requirements

## CRITICAL: Always Use UV for Python Commands

This project uses `uv` as the Python package manager and execution environment. You MUST always use `uv run` for any Python command execution.

### Required Commands:

- ✅ **Correct**: `uv run python script.py`
- ✅ **Correct**: `uv run python -m pytest tests/`
- ✅ **Correct**: `uv run python -c "import module"`
- ❌ **Wrong**: `python script.py`
- ❌ **Wrong**: `cd directory && python script.py`
- ❌ **Wrong**: `python -m pytest tests/`

### Why This Matters:

1. **Dependency Management**: `uv` ensures the correct virtual environment and dependencies are used
2. **Consistency**: All team members and CI/CD use the same execution environment
3. **Isolation**: Prevents conflicts with system Python installations
4. **Performance**: `uv` provides faster package resolution and installation

### Testing Commands:

- Run all tests: `uv run python -m pytest tests/ -v`
- Run specific test: `uv run python -m pytest tests/test_file.py -v`
- Run with coverage: `uv run python -m pytest tests/ --cov=pika`
- Property-based tests: `uv run python -m pytest tests/test_*_property.py -v`

### Development Commands:

- Run application: `uv run python -m pika.app`
- Check syntax: `uv run python -c "import pika.module"`
- Interactive shell: `uv run python`
- Install dependencies: `uv add package_name`

### Remember:

**NEVER use bare `python` commands in this workspace. Always prefix with `uv run`.**

This is a hard requirement for this project and must be followed consistently.