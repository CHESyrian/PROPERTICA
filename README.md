# PROPERTICA

Real estate listings marketplace — property owners, agents, and agencies list homes, land, and commercial properties for sale; buyers search, filter, favorite, and inquire in one place.

Built from the product & technical design docs in `../constructions-files/`.

## Stack (v1)

| Layer | Choice |
|-------|--------|
| Backend | Django 6 + Django REST Framework |
| Frontend | Server-rendered templates + htmx + Alpine.js |
| Database | **PostgreSQL** (`propertica_db`) — SQLite fallback when Postgres env vars are unset |
| Auth | Custom `Account` model with auto-generated `USRXXXXXXXXXX` usernames |
| Maps | Leaflet + Carto basemaps + Photon geocoding (language follows site locale) |
| i18n | English + Arabic (RTL), language switcher in the header menu |
| Theme | Light / dark (`data-theme`), persisted in `localStorage` |

## Quick start

```bash
cd real-estate-marketplace   # or your clone path

python -m venv .venv
source .venv/bin/activate    # Windows: .venv\Scripts\activate

pip install -r requirements.txt

# Configure environment
cp .env.example .env         # or edit existing .env
# Set SECRET_KEY (and optionally POSTGRES_* ) in .env

# Create the database (PostgreSQL)
createdb propertica_db       # or via your DB admin tool

python manage.py migrate
python manage.py seed_data
python manage.py createsuperuser   # optional
python manage.py runserver
```

Open http://127.0.0.1:8000/

**Demo account** (from `seed_data`):

| Field | Value |
|-------|--------|
| Email | `demo@example.com` |
| Password | `demo1234` |

## Environment (`.env`)

| Variable | Description |
|----------|-------------|
| `SECRET_KEY` | Django secret key (**required** in production) |
| `DEBUG` | `True` / `False` — security hardening activates when `False` |
| `ALLOWED_HOSTS` | Comma-separated hosts |
| `CSRF_TRUSTED_ORIGINS` | Comma-separated HTTPS origins (production) |
| `USE_POSTGRES` | `true` to use PostgreSQL; default SQLite |
| `POSTGRES_*` / `DATABASE_URL` | Postgres connection |
| `EMAIL_HOST` (+ port/user/password) | Real SMTP; empty → console backend |
| `USE_S3` / `AWS_*` | S3-compatible media storage |
| `USE_WHITENOISE` | Serve compressed static files from Django |
| `REDIS_URL` | Optional cache / rate-limit backend |
| `GOOGLE_OAUTH_*` | Optional OAuth scaffold |

See **`.env.example`** for the full list. **Never commit `.env`**.

## Production checklist

```bash
# 1. Environment
cp .env.example .env
# Set: SECRET_KEY, DEBUG=False, ALLOWED_HOSTS, CSRF_TRUSTED_ORIGINS
# Set: USE_POSTGRES=true + POSTGRES_* (or DATABASE_URL)
# Set: EMAIL_HOST / credentials for real mail
# Optional: USE_S3=true, USE_WHITENOISE=true, REDIS_URL

# 2. Dependencies
pip install -r requirements.txt

# 3. Database & static
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py seed_data   # optional demo data

# 4. Run (behind HTTPS reverse proxy)
gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 3
```

When `DEBUG=False`, the app enables SSL redirect, secure cookies, HSTS, and proxy SSL headers automatically.

### S3 media (live uploads)

```bash
# .env
USE_S3=true
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_STORAGE_BUCKET_NAME=propertica-media
AWS_S3_REGION_NAME=us-east-1
# Optional CDN:
# AWS_S3_CUSTOM_DOMAIN=cdn.example.com
# MinIO / R2 / Spaces — also set:
# AWS_S3_ENDPOINT_URL=https://...
```

- `ListingMedia.image` uses Django default storage → uploads go to the bucket automatically.
- `display_url` returns `image.url` (public or signed S3 URL).
- Local `MEDIA_ROOT` is **not** served when `USE_S3=true`.
- Bucket: public-read on `media/*`, **or** set `AWS_QUERYSTRING_AUTH=true` for private objects.

## Project layout

```
accounts/     # Custom user (Account), plans, agency linking, reputation, verification
listings/     # Categories, attributes, listings, media, favorites, wizard, geo search
messaging/    # Inquiry threads, inbox, contact seller, notifications, reports
search_app/   # Search service abstraction (DB backend + OpenSearch stub)
api/          # DRF v1 endpoints
core/         # Home, static pages, rate limits, context processors
config/       # Django settings, URLs, WSGI/ASGI
templates/    # Server-rendered pages
static/       # CSS / brand assets (img/)
```

## Features (current)

### Accounts & trust
- Personal / Agent / Agency accounts with immutable `USR…` usernames
- Email verification via signed, URL-safe tokens (`/accounts/verify-email/?token=…`)
- Lightweight phone verification (console/dev code flow)
- Profile, public profile, public agency page
- GDPR-lite data export (JSON) and account soft-delete
- Reputation events / summary foundation (agent/agency)

### Listings
- Multi-step wizard: type → basics → location (map + geocode) → details → photos → review
- Multi-photo upload, cover selection, drag-reorder, remove
- Publish gates: plan `max_active_listings`, ≥1 photo, required type attributes
- Status flow: draft / active / under_offer / sold / expired / removed
- Featured listing path (entitlement-gated; homepage prioritizes featured)
- Full-width **hero image carousel** on detail (auto-advance 2s, dots, arrows)
- Similar listings, share, Open Graph + JSON-LD SEO
- Favorites with neon-red active/hover state (including homepage)

### Search & discovery
- Filters: keyword, category, city, price, area, currency, sort
- Geo search: radius + bounding box
- Sticky filter sidebar with internal scrollbar
- Search map with listing pins
- Saved searches CRUD + email digest management command

### Messaging & moderation
- Contact seller → inquiry threads + inbox
- In-app notification center + lead email notifications
- Report listing; staff ReportAdmin moderation actions
- Rate limits on contact, report, auth, phone-code, geocode

### Plans & ops
- Free + starter plan seeds; pricing page; entitlement checks
- View analytics (`ListingViewEvent` + dashboard counters)
- `run_maintenance_tasks` (expire listings / featured flags)
- `send_saved_search_digests` command
- Bulk status actions on dashboard

### UI / UX
- Fixed navbar, brand assets (horizontal / vertical / icon)
- Dark / light theme toggle
- EN / AR language switch (RTL for Arabic)
- Dismissible neon toasts (success / danger / warning / info)
- Map + geocode language follows active site language

## Management commands

```bash
python manage.py seed_data
python manage.py run_maintenance_tasks
python manage.py send_saved_search_digests
python manage.py send_test_email you@example.com
```

## Docs

See `../constructions-files/` for the full PRD, TDD, Database Schema, API Spec, UI/UX Spec, and ticket history (P0–P3 foundations complete).

## REST API (v1)

Base path: `/api/v1/`

Auth uses **Token** authentication (`Authorization: Token <key>`). Register and login return a `token` field.

| Area | Endpoints |
|------|-----------|
| Auth | `POST /auth/register/`, `/auth/login/`, `/auth/logout/` |
| Accounts | `GET\|PATCH /accounts/me/`, `GET /accounts/{username}/`, agency invite/remove |
| Listings | `GET\|POST /listings/`, `GET\|PATCH\|DELETE /listings/{id}/`, publish, status |
| Search | `GET /search/listings/` |
| Favorites | `GET\|POST /favorites/`, `DELETE /favorites/{listing_id}/` |
| Messaging | `POST /listings/{id}/messages/`, `GET /messages/threads/`, thread detail |
| Reports | `POST /reports/` |
| Categories | `GET /categories/` |

List responses use `{ "data": [...], "pagination": { "page", "per_page", "total" } }`.

## Brand assets

Located under `static/img/`:

| File | Use |
|------|-----|
| `propertica-brand-h.png` | Navbar, footer |
| `propertica-brand-v.png` | Login / register cards |
| `propertica-icon.png` | Favicon, mobile mark |

## Notes

- Geocoding uses the free Photon API (no key required in development). Production map providers (Google, Mapbox, etc.) need an API key if you switch tile sources.
- Email uses Django’s configured backend (console in dev). Verification links are query-string based to avoid MIME line-wrap corruption.
- Media defaults to local `MEDIA_ROOT`; S3 hooks are settings-ready via `USE_S3`.
