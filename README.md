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
| **Spotify OAuth** | Connect your Spotify account via Authorization Code Flow; displays a "Spotify Verified Producer" badge on your profile |

## Artist Endorsement — ProducedByKyle

TuneFeed features six unreleased original beats from **ProducedByKyle**, a professional Boom Bap producer with a verified Spotify artist profile. Kyle granted explicit personal permission for his work to be used in this project as a genuine demonstration of the platform's commercial-grade capabilities — these are not stock audio files.

- Spotify: [open.spotify.com/artist/34KLV4fA8n6XZyFrWs9iRx](https://open.spotify.com/artist/34KLV4fA8n6XZyFrWs9iRx)
- Beats: *Escargot*, *Reverse Layup*, *Unknown*, *Word Magicc*, *No Danger*, *Sandro Jova*

All other MP3 audio files in the database are used purely for demonstration purposes and were hand-selected from producers who listed their work as free to use. Proper beat licensing, royalty tracking, and secure payment infrastructure are identified as future development priorities (see Known Limitations below).

> **Note on licensing and payments:** The current implementation is a demonstration of the platform's UI, data model, and social mechanics. Beat licensing agreements and real payment processing (Stripe, royalty splits, etc.) have not been implemented — due to time constraints in this academic project, we focused on showcasing the architecture and user experience. A future iteration would integrate proper licensing workflows and payment gateways, and explore connectivity with platforms such as SoundCloud in addition to Spotify.

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3, Flask 3.1, SQLAlchemy, Flask-Login, Flask-WTF, Flask-Migrate |
| Database | SQLite (development) — swap `DATABASE_URL` for Postgres in production |
| Frontend | Jinja2, Bootstrap 5, Bootstrap Icons, Web Audio API |

## Group Members

| UWA ID | Name | GitHub Username |
|---|---|---|
| 24274489 | Griffin Hudson | Griffin-Hudson |
| 24527669 | Tinashe Nemacha | tnemz |
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
| `SPOTIFY_CLIENT_ID` | _(empty)_ | Spotify Developer Dashboard app Client ID — enables Spotify connect |
| `SPOTIFY_CLIENT_SECRET` | _(empty)_ | Spotify Developer Dashboard app Client Secret |
| `SPOTIFY_REDIRECT_URI` | `http://127.0.0.1:5002/spotify/callback` | Must match the URI registered in your Spotify app dashboard |

**Setting up Spotify OAuth:**
1. Create an app at [developer.spotify.com/dashboard](https://developer.spotify.com/dashboard)
2. Add `http://127.0.0.1:5002/spotify/callback` to the app's Redirect URIs
3. Copy Client ID and Client Secret into your `.env` file
4. If credentials are absent the feature degrades gracefully — the connect button shows a configuration notice instead of attempting OAuth

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
- **Beat licensing is demo-only** — the current purchase flow is a UI demonstration. Real beat licensing agreements, royalty splits, and secure payment processing (e.g. Stripe) are not implemented. Due to time constraints in this academic project, we focused on the architecture and UX. A production version would integrate proper licensing workflows.
- **Spotify: profile connection only** — the Spotify integration links a user's account and displays the Verified Producer badge. Importing beats from Spotify is identified as a future priority, alongside potential integrations with SoundCloud and other music production platforms.
- **Demo audio licensing** — all MP3 files in the seeder are hand-selected from producers who listed their work as free to use. No formal licensing agreements are in place; a production deployment would require a proper rights-clearance process. ProducedByKyle's WAV beats are used with explicit personal permission from the artist.

## Academic Integrity

All external libraries are listed in `requirements.txt`. Third-party assets (Bootstrap, Bootstrap Icons) are referenced from their respective CDNs. No code was copied from other student submissions.
