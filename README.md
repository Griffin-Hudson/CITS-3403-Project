# TuneFeed

**TuneFeed** is a music discovery and beat marketplace built for CITS3403 at the University of Western Australia. Producers upload beats; listeners discover them through a vertical scroll feed, like and save tracks, leave comments, and follow producers.

## Features

| Feature | Details |
|---|---|
| Scroll feed | TikTok-style vertical snap feed with auto-play and waveform visualiser |
| Beat marketplace | Per-beat pricing with Basic, Premium, and Exclusive licence tiers |
| Social layer | Likes, saves, comments with threaded replies, follow/unfollow |
| Producer profiles | Avatar, bio, beat catalogue, and engagement stats |
| Discovery page | Trending and new-drops sections with genre/BPM/key metadata |
| Search | Full-text beat and producer search |
| Wallet | In-app balance, top-up, and beat purchase flow |
| Authentication | Flask-Login sessions with CSRF protection and per-user rate limiting |

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3, Flask 3.1, SQLAlchemy, Flask-Login, Flask-WTF, Flask-Migrate |
| Database | SQLite (development) — swap `DATABASE_URL` for Postgres in production |
| Frontend | Jinja2, Bootstrap 5, Bootstrap Icons, Web Audio API |

## Group Members

| UWA ID | Name | GitHub Username |
|---|---|---|
| 24274489 | Griffin Hudson | griffhudson |
| 24527669 | Tinashe Nemacha | tinashenemacha |
| 24339064 | Saiyang Seo | seosy218-ops |

## How to Run

**1. Create and activate a virtual environment**
```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate
```

**2. Install dependencies**
```bash
pip install -r requirements.txt
```

**3. Seed the database**

Creates `instance/tunefeed.db` with demo producers, beats, likes, and comments:
```bash
python seed.py
```

**4. Start the development server**
```bash
python run.py
```

Open [http://127.0.0.1:5002](http://127.0.0.1:5002) in your browser.

**Demo accounts** (all use password `password123`):

| Role | Email |
|---|---|
| Listener | demo@tunefeed.io |
| Producer | prodbyu@tunefeed.io |

## Environment Variables

Copy `.env.example` to `.env` and set values before deploying.

| Variable | Default | Purpose |
|---|---|---|
| `SECRET_KEY` | ephemeral dev key | Flask session signing key — **must** be changed in production |
| `DATABASE_URL` | `sqlite:///tunefeed.db` | SQLAlchemy connection string |
| `FLASK_DEBUG` | `false` | Set to `true` to enable the Werkzeug debugger |
| `PORT` | `5002` | Port the dev server binds to |

## Running Tests

Three test suites cover different layers of the application.

**Unit tests** — model methods, no HTTP, fastest:
```bash
python -m unittest tests.test_models -v
```

**Integration tests** — Flask test client, in-memory SQLite:
```bash
pytest tests/test_auth.py tests/test_routes.py tests/test_api.py -v
```

**System tests** — Selenium WebDriver end-to-end (requires Google Chrome):
```bash
python -m unittest tests.test_selenium -v
```

## Project Structure

```
app/
├── __init__.py           # Application factory
├── config.py             # Config class (reads env vars)
├── models.py             # SQLAlchemy models
├── forms.py              # Flask-WTF form definitions
├── routes.py             # Main blueprint — pages and auth
├── services/
│   ├── feed_service.py   # Feed ranking algorithm
│   └── wallet_service.py # Balance and transaction logic
├── api/
│   └── routes.py         # JSON API blueprint
├── static/               # CSS, JS, audio files
└── templates/            # Jinja2 HTML templates

migrations/               # Alembic migration scripts (Flask-Migrate)

tests/
├── conftest.py           # Fixtures and helpers
├── test_models.py        # Unit tests for model methods
├── test_auth.py          # Registration, login, logout flows
├── test_routes.py        # Page route status codes
├── test_api.py           # Like, save, follow, play API endpoints
└── test_selenium.py      # End-to-end browser tests
```

## Known Limitations

- **SQLite only** — SQLite does not support concurrent writes well. Set `DATABASE_URL` to a Postgres connection string for any multi-worker deployment.
- **Audio hosted locally** — beat audio files are served from `app/static/audio/`. A production version would store audio in an object store such as S3.
- **Rate limiter uses in-memory storage** — per-user request limits reset on process restart. A multi-worker deployment would need Redis as the rate-limit backend.
- **No email verification** — accounts are activated immediately on registration without email confirmation.
- **No password reset** — there is no forgot-password route.

## Academic Integrity

All external libraries are listed in `requirements.txt`. Third-party assets (Bootstrap, Bootstrap Icons) are referenced from their respective CDNs. No code was copied from other student submissions.
