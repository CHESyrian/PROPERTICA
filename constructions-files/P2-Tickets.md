# P2 Tickets — Scale & monetization readiness

**Project:** PROPERTICA  
**Date:** 2026-09-17  
**Depends on:** P0 + P1  

---

## P2-1 — Rate limiting ✅ DONE (2026-09-17)

**Priority:** P2 · **Estimate:** S–M

### Scope
- Rate-limit contact, report, auth register/login, phone-code, and geocode endpoints.
- Use cache-backed counters (LocMem/Redis-ready).
- Clear 429 responses for API; messages + redirect for web.

### Acceptance
- [x] Exceeding limit returns 429 (API) or friendly error (web).
- [x] Limits configurable via settings.

---

## P2-2 — Featured listing activation path ✅ DONE (2026-09-17)

**Priority:** P2 · **Estimate:** S–M

### Scope
- Owner can request/activate feature if `can_feature_listing` entitlement is true.
- Staff/admin can set `featured_until` manually (free plan remains false).
- Homepage already shows featured; ensure query uses `featured_until >= now`.

### Acceptance
- [x] Entitlement gate on feature action.
- [x] Featured listings appear on home when `featured_until` is future.
- [x] Free plan users see clear “not available on free plan” message.

---

## P2-3 — Listing view analytics (seller + admin basics) ✅ DONE (2026-09-17)

**Priority:** P2 · **Estimate:** M

### Scope
- `ListingViewEvent` (or daily counter) recorded on detail page views.
- Seller dashboard: views count + leads count per listing (or totals).
- Admin: simple totals (listings, users, views, open reports).

### Acceptance
- [x] Detail view increments view counter (authenticated unique soft-dedupe optional).
- [x] Dashboard shows view/lead stats.
- [x] Admin index or custom page shows platform KPIs.

---

## P2-4 — Background task runner (foundation) ✅ DONE (2026-09-17)

**Priority:** P2 · **Estimate:** M

### Scope
- Introduce a pluggable task interface + management command runner for:
  - expire listings past `expires_at`
  - clear expired featured flags
  - (stub) saved-search digest, image optimize
- Prefer Django management command in v1; document Celery hook for later.

### Acceptance
- [x] `python manage.py run_maintenance_tasks` runs safely.
- [x] Expired listings transition to `expired`.
- [x] Featured flags past `featured_until` no longer treated as featured.

---

## P2-5 — Search abstraction (OpenSearch-ready) ✅ DONE (2026-09-17)

**Priority:** P2 · **Estimate:** M

### Scope
- `search_app` service interface: `search_listings(filters) -> queryset or result page`.
- Default backend: current DB implementation.
- Optional OpenSearch backend stub (settings flag) without requiring a live cluster.

### Acceptance
- [x] Listing search view uses search service.
- [x] DB backend preserves existing filters (incl. geo).
- [x] Settings switch for future OpenSearch backend.

---

## P2-6 — Media storage abstraction (S3-ready) ✅ DONE (2026-09-17)

**Priority:** P2 · **Estimate:** S–M

### Scope
- Settings for `USE_S3` + django-storages placeholders.
- Default remains local filesystem.
- Document env vars for S3-compatible endpoint.

### Acceptance
- [x] Local media still works when S3 disabled.
- [x] `.env.example` documents S3 variables.
- [x] No hard dependency on boto3 unless S3 enabled.

---

## Suggested order

1. P2-1 Rate limiting  
2. P2-2 Featured path  
3. P2-3 Analytics  
4. P2-4 Maintenance tasks  
5. P2-5 Search service  
6. P2-6 Storage settings  
