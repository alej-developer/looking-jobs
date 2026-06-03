# ATS Job Automator

Automated job application engine that targets corporate ATS portals directly (Workday, Greenhouse, Lever, iCIMS, etc.), bypassing LinkedIn.

## Quick Start

```bash
# 1. Clone and enter the project
git clone https://github.com/<YOUR_USERNAME>/looking-jobs.git
cd looking-jobs

# 2. Create virtual environment
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS/Linux

# 3. Install dependencies
pip install -e ".[dev]"

# 4. Install Playwright browsers
playwright install chromium

# 5. Configure environment
copy .env.example .env
# Edit .env with your real values

# 6. Run
python main.py
```

## Project Structure

```
Looking Jobs/
├── config.py              # Secure env-var loader (python-dotenv)
├── main.py                # Application entry point
├── pyproject.toml         # Project metadata & dependencies
├── .env.example           # Template — copy to .env
├── .gitignore             # Strict security-first exclusions
│
├── src/
│   ├── __init__.py
│   ├── scraper/           # ATS portal scrapers
│   │   ├── __init__.py
│   │   └── base.py        # Abstract base scraper
│   ├── applicator/        # Form-filling & submission logic
│   │   ├── __init__.py
│   │   └── base.py        # Abstract base applicator
│   ├── models/            # SQLAlchemy / Pydantic models
│   │   ├── __init__.py
│   │   └── job.py         # Job listing data model
│   └── utils/             # Shared helpers (logging, retries, etc.)
│       ├── __init__.py
│       └── logger.py      # Structured logging setup
│
├── data/                  # Runtime data (DB lives here, git-ignored)
│
├── tests/
│   ├── __init__.py
│   └── test_config.py     # Smoke test for config loading
│
└── docs/                  # Documentation & notes
```

## Security

- **All secrets** live in `.env` (git-ignored).
- **`.env.example`** is committed as the safe template.
- **`config.py`** fails fast if required variables are missing.
- **`.gitignore`** blocks databases, browser state, and credentials.
