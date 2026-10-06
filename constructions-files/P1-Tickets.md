# P1 Tickets — User value & trust

**Project:** PROPERTICA  
**Date:** 2026-09-17  
**Depends on:** P0 complete  

---

## P1-1 — SEO foundations (schema.org + meta) ✅ DONE (2026-09-17)

**Priority:** P1 · **Estimate:** S

### Scope
- JSON-LD `schema.org/RealEstateListing` (or Product/Offer fallback) on listing detail.
- Ensure Open Graph / Twitter cards on detail (partially done in P0-4).
- Canonical URL meta where useful.

### Acceptance
- [x] Detail page includes valid JSON-LD with name, price, geo, image when available.
- [x] OG tags present for title, description, image, url.

---

## P1-2 — Public Agency profile page ✅ DONE (2026-09-17)

**Priority:** P1 · **Estimate:** M

### Scope
- Public page at `/accounts/agency/<username>/` (or display-name slug) showing agency brand, bio fields if any, linked agents, active listings.
- Link from listing owner card when owner is agency or agent-linked-to-agency.

### Acceptance
- [x] Agency page loads for `account_type=agency`.
- [x] Lists active agents and active listings.
- [x] Linked from listing detail when applicable.

---

## P1-3 — In-app notification center ✅ DONE (2026-09-17)

**Priority:** P1 · **Estimate:** M

### Scope
- `Notification` model: recipient, type, title, body, link, read_at, created_at.
- List page + mark read; unread badge in nav (replace disabled “Notifications” item).
- Create notifications for: new message/lead, agency invite (optional).

### Acceptance
- [x] Authenticated user sees notifications list and unread count.
- [x] Mark one / mark all read.
- [x] New lead creates a notification for the seller.

---

## P1-4 — Email notifications for new leads ✅ DONE (2026-09-17)

**Priority:** P1 · **Estimate:** S–M

### Scope
- On new inquiry message to seller: send email (console backend OK in dev).
- Prefer shared helper used by contact + reply paths.
- Do not block request if email fails.

### Acceptance
- [x] Seller receives email when a buyer contacts them on a listing.
- [x] Failures are silent (logged), user flow still succeeds.

---

## P1-5 — Geo search (radius + map bounds) ✅ DONE (2026-09-17)

**Priority:** P1 · **Estimate:** M

### Scope
- Search params: `lat`, `lng`, `radius_km` and/or `bbox` (min_lat, min_lng, max_lat, max_lng).
- Filter active listings with coordinates in range (Haversine approx or bbox for Postgres/SQLite).
- Expose radius control on search UI (simple select).

### Acceptance
- [x] Radius filter returns only listings within distance of a center point.
- [x] Bbox filter works for map-viewport style queries.
- [x] UI can apply a radius from current filters.

---

## P1-6 — Phone verification (lightweight) ✅ DONE (2026-09-17)

**Priority:** P1 · **Estimate:** M

### Scope
- Soft flow: user enters phone, requests code (store hashed code + expiry on account or side table), confirms.
- Dev: log/code to console instead of SMS provider.
- Set `phone_verified_at` on success.

### Acceptance
- [x] Profile can request and confirm a phone code.
- [x] Verified state visible on profile.
- [x] Invalid/expired codes rejected.

---

## Suggested order

1. P1-1 SEO  
2. P1-2 Agency profile  
3. P1-3 Notifications model + UI  
4. P1-4 Lead emails (uses notification helper)  
5. P1-5 Geo search  
6. P1-6 Phone verification  
