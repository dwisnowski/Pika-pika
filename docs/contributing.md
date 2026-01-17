# Contributing to Pika-pika

Thank you for your interest in contributing to Pika-pika!

## Development Setup

### Local Machine (No Hardware)
You can develop the UI and logic on your local machine using the demo mode.

1. **Install uv**: If you don't have it, install [uv](https://github.com/astral-sh/uv).
2. **Setup**:
   ```bash
   make sync
   ```
3. **Run Dev Server**:
   ```bash
   make dev
   ```
4. **Access Demo**: Open `http://localhost:8000/demo`

## Project Structure

- `pika/`: Main Python package.
  - `app.py`: FastAPI application.
  - `datalogger.py`: Core sampling and logging logic.
  - `mini_display.py`: LCD display logic.
  - `static/`: Frontend assets (JS, CSS, Images).
  - `templates/`: HTML templates.
- `docs/`: Documentation (MkDocs).
- `scripts/`: Utility and installation scripts.

## Standards

- **Code Style**: We use `ruff` for linting and formatting. 
- **Type Hints**: Please use Python type hints where possible.
- **Tests**: (Coming soon) We aim for high coverage on core logic.

## Pull Request Process

1. Fork the repository.
2. Create a feature branch.
3. Commit your changes with descriptive messages.
4. Submit a Pull Request to the `main` branch.

## Documentation
When adding features, please update the relevant files in `docs/` and verify with `make docs-serve`.
