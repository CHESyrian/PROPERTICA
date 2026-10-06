# API Specification
## Real Estate Listings Marketplace

**Version:** 1.0 (Draft)
**Date:** September 16, 2026
**Related:** PRD-Real-Estate-Listings-Website.md, TDD-Technical-Design-Document.md, Database-Schema.md
**Style:** REST, JSON over HTTPS (confirmed — via Django REST Framework)
**Base URL (example):** `https://api.example.com/v1`
**Auth:** Bearer JWT in `Authorization` header, unless noted as public.

---

## 1. Conventions

- All timestamps: ISO 8601 UTC.
- All IDs in URLs/bodies refer to internal UUIDs, **except** where `username` (`USRXXXXXXXXXX`) is explicitly used for public-facing lookups.
- Standard error shape:
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "price is required",
    "fields": { "price": "required" }
  }
}
```
- Standard list response shape:
```json
{
  "data": [ ... ],
  "pagination": { "page": 1, "per_page": 20, "total": 134 }
}
```
- HTTP status codes used: `200`, `201`, `204`, `400`, `401`, `403`, `404`, `409`, `422`, `429`, `500`.

---

## 2. Auth & Registration

### `POST /auth/register`
Registers a new account. **Public.**

Request:
```json
{
  "account_type": "personal | agent | agency",
  "email": "user@example.com",
  "password": "••••••••",
  "agency_invite_token": "optional, for agent joining via invite"
}
```
Response `201`:
```json
{
  "id": "uuid",
  "username": "USR0000001234",
  "account_type": "personal",
  "display_name": null,
  "email": "user@example.com",
  "plan": "free",
  "email_verified": false
}
```
Notes: `username` is generated server-side; the client never supplies or edits it (see TDD §4.1). `display_name` is null by default for Personal accounts (username is shown publicly per PRD FR-33b).

### `POST /auth/login`
Public. Returns JWT/session token.

### `POST /auth/oauth/google`
Public. OAuth login/registration.

### `POST /auth/verify-email`
Authenticated. Confirms email verification token.

### `POST /auth/logout`
Authenticated.

---

## 3. Accounts / Profile

### `GET /accounts/me`
Authenticated. Returns the current account's full profile, including `username`, `display_name`, `account_type`, `agency_id` (if agent), `plan`, verification status.

### `PATCH /accounts/me`
Authenticated. Editable fields only: `display_name` (subject to account-type rules below), `phone`, profile photo, contact preferences. **`username` is never editable via this or any endpoint.**

- If `account_type = personal`: `display_name` updates are rejected or ignored — public display always resolves to `username` (per PRD FR-33b / TDD §4.2). *(Open decision: allow Personal accounts to set an optional display_name for future use, but keep default behavior as username-only — flag for product decision.)*
- If `account_type = agent` and `agency_id` is set: `display_name` is not directly editable by the agent; it resolves from the parent agency's `display_name`.
- If `account_type = agency`: `display_name` is fully editable (this is the agency's public brand name).

### `GET /accounts/{username}`
Public. Returns the public profile view (resolved `display_name`, account type, verification badge, and — once built — reputation summary for Agent/Agency accounts). Looked up by the public `username`, not the internal ID.

### `POST /accounts/agency/invite-agent`
Authenticated, Agency accounts only. Body: `{ "email": "agent@example.com" }`. Creates an `agency_agents` invite row.

### `POST /accounts/agency/agents/{agentId}/remove`
Authenticated, Agency accounts only. Unlinks an agent from the agency.

---

## 4. Listings

### `POST /listings`
Authenticated (Personal/Agent/Agency). Creates a listing.

Request:
```json
{
  "category_code": "house",
  "title": "Modern 3BR House with Garden",
  "description": "...",
  "price": 250000,
  "currency": "USD",
  "negotiable": true,
  "address_line": "123 Main St",
  "city": "Rotterdam",
  "region": "South Holland",
  "country": "Netherlands",
  "latitude": 51.9225,
  "longitude": 4.4792,
  "type_attributes": {
    "bedrooms": 3,
    "bathrooms": 2,
    "living_area_m2": 140,
    "year_built": 2005
  }
}
```
Server-side: validates `type_attributes` against `attribute_definitions` for `category_code`; checks `EntitlementService` for `max_active_listings` before allowing a new **active** listing (drafts may be exempt).

Response `201`: full listing object with `id`, `status: "draft"` (or `pending_review`/`active` depending on moderation policy).

### `GET /listings/{id}`
Public. Full listing detail, including resolved owner `display_name` (not raw username, unless owner is Personal).

### `PATCH /listings/{id}`
Authenticated, owner (or agency admin on behalf of a linked agent) only.

### `DELETE /listings/{id}`
Authenticated, owner only. Soft-delete (`status = removed`).

### `POST /listings/{id}/publish`
Authenticated, owner only. Transitions `draft` → `pending_review` or `active`.

### `POST /listings/{id}/status`
Authenticated, owner only. Body: `{ "status": "under_offer" | "sold" | "active" }`.

### `GET /listings` (mine)
Authenticated. `?owner=me&status=active`. Powers the seller/agent dashboard listing table.

### `POST /listings/{id}/media`
Authenticated, owner only. Multipart upload; returns media object(s) with CDN URL.

### `DELETE /listings/{id}/media/{mediaId}`
Authenticated, owner only.

---

## 5. Search & Discovery

### `GET /search/listings`
Public. Query parameters:

| Param | Type | Notes |
|---|---|---|
| `q` | string | Free-text keyword |
| `category` | string | e.g., `house`, `land_residential` |
| `parent_group` | string | `residential`/`land`/`commercial`/`other` |
| `price_min`, `price_max` | number | |
| `area_min`, `area_max` | number | m² |
| `city`, `region`, `country` | string | |
| `lat`, `lng`, `radius_km` | number | Geo-radius search |
| `bbox` | string | Map viewport bounding box, alt. to radius |
| `attributes[bedrooms]` etc. | dynamic | Category-specific filters, keyed by `attribute_key` |
| `sort` | enum | `price_asc`, `price_desc`, `newest`, `area_asc/desc` |
| `page`, `per_page` | number | |

Response: paginated list of listing summaries (cover photo, price, title, key attributes) plus facet counts for the applied filters.

### `POST /search/saved-searches`
Authenticated. Persists current filter set; `notify_by_email` flag.

### `GET /search/saved-searches`
Authenticated. Lists the user's saved searches.

### `DELETE /search/saved-searches/{id}`
Authenticated.

---

## 6. Favorites

### `POST /favorites` — body `{ "listing_id": "uuid" }` — Authenticated.
### `DELETE /favorites/{listingId}` — Authenticated.
### `GET /favorites` — Authenticated, paginated list of favorited listings.

---

## 7. Messaging & Leads

### `POST /listings/{id}/messages`
Authenticated. Creates (or appends to) a thread with the listing owner.
```json
{ "body": "Is this still available?" }
```

### `GET /messages/threads`
Authenticated. Lists the user's threads (as buyer or as seller), most recent first.

### `GET /messages/threads/{threadId}`
Authenticated, participant only. Full message history.

### `POST /messages/threads/{threadId}`
Authenticated, participant only. Adds a message to an existing thread.

### `POST /messages/threads/{threadId}/read`
Authenticated. Marks thread as read.

---

## 8. Reports & Moderation (User-Facing)

### `POST /reports`
Authenticated. Body: `{ "listing_id": "uuid" (optional), "reported_account_username": "USRXXXXXXXXXX" (optional), "reason": "fraud", "details": "..." }`

---

## 9. Admin API (Internal, requires admin role)

### `GET /admin/reports?status=open`
### `POST /admin/listings/{id}/moderate` — body `{ "action": "approve"|"reject"|"remove", "notes": "..." }`
### `POST /admin/accounts/{id}/suspend`
### `GET /admin/analytics/overview` — total listings, active users, top searches, etc.

---

## 10. Plans & Entitlements (Future — Stub for v1)

### `GET /plans`
Public. Lists available plans (v1: returns only `free`).

### `GET /accounts/me/entitlements`
Authenticated. Returns resolved entitlement values for the caller's current plan (e.g., `{ "max_active_listings": 10, "can_feature_listing": false }`), consumed by the frontend to gate UI (e.g., disable "Feature this listing" button).

*(Billing/subscription endpoints — create/cancel/upgrade — are out of scope for v1 and intentionally not specified here; to be added when paid plans are built, per TDD §4.3.)*

---

## 11. Reputation (Future — Stub for v1)

### `GET /accounts/{username}/reputation`
Public. Returns `null`/`not_applicable` for Personal accounts; returns `{ total_points, experience_level, reputation_score, badges }` for Agent/Agency accounts.

### `POST /accounts/{username}/ratings` (Future, not built in v1)
Authenticated. Submits a rating tied to a completed interaction; only valid when the target account is Agent or Agency. Writes a `reputation_events` row (per Database Schema §4.1); the rater's own account (which may be Personal) never accrues points from this action.

---

## 12. Rate Limits (Recommended Defaults)

| Endpoint group | Limit |
|---|---|
| `/auth/*` | 10 requests / minute / IP |
| `/listings/{id}/messages` (contact seller) | 20 requests / hour / account |
| `/reports` | 10 requests / hour / account |
| `/search/*` | 60 requests / minute / IP |
