# Technical Design Document (TDD)
## Real Estate Listings Marketplace

**Version:** 1.0 (Draft)
**Date:** September 16, 2026
**Related:** PRD-Real-Estate-Listings-Website.md
**Status:** Draft for review

---

## 1. Purpose & Scope

This document translates the PRD's functional and non-functional requirements into a concrete technical architecture: system components, technology choices, data flow, and key design decisions (auto-generated usernames, account-type behavior, plan/entitlement system, and the future points/reputation layer).

---

## 2. Architecture Overview

### 2.1 High-Level Architecture Style
A **modular monolith** is recommended for v1 rather than microservices: the domain is cohesive (listings, users, search, messaging), team size is presumably small at launch, and a monolith is faster to build and simpler to operate — while still being organized into clear internal modules (Users, Listings, Search, Messaging, Reputation, Billing) so it can be split into services later if scale demands it.

### 2.2 Core Components

```
┌─────────────────────────────────────────────────────────────┐
│                        Client Layer                          │
│   Server-rendered HTML (Django templates) + CSS + vanilla JS │
│   htmx (partial page updates/AJAX) · Alpine.js (small client │
│   interactivity: toggles, form widgets, gallery, map bindings)│
└───────────────────────────┬───────────────────────────────────┘
                             │ HTTPS / REST
┌───────────────────────────▼───────────────────────────────────┐
│                    Django Application Server                  │
│   Django views (render templates & htmx partials) +           │
│   Django REST Framework (JSON REST API) · Auth middleware ·   │
│   Rate limiting · Request routing                              │
└───────────────────────────┬───────────────────────────────────┘
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                     │
┌───────▼──────┐   ┌─────────▼─────────┐   ┌───────▼────────┐
│  Application  │   │   Application     │   │  Application    │
│  Module:      │   │   Module:         │   │  Module:        │
│  Users/Auth   │   │   Listings        │   │  Search/Discov. │
└───────┬──────┘   └─────────┬─────────┘   └───────┬────────┘
        │                    │                     │
┌───────▼──────┐   ┌─────────▼─────────┐   ┌───────▼────────┐
│  Module:      │   │   Module:         │   │  Module:        │
│  Messaging    │   │   Reputation/     │   │  Billing/Plans  │
│  & Leads      │   │   Points (future) │   │  (future)       │
└───────┬──────┘   └─────────┬─────────┘   └───────┬────────┘
        │                    │                     │
┌───────▼─────────────────────▼─────────────────────▼────────┐
│                     Shared Data Layer                        │
│   Primary DB (PostgreSQL) · Search Index (OpenSearch/ES)     │
│   Object Storage (images) · Cache (Redis)                    │
└────────────────────────────────────────────────────────────┘
```

### 2.3 Module Responsibilities

| Module | Responsibility |
|---|---|
| **Users/Auth** | Registration (3 account types), auto-generated username (`USRXXXXXXXXXX`), display-name resolution, login/session, email/phone verification, agency↔agent linking |
| **Listings** | CRUD for listings, property-type-specific schema validation, media upload, listing lifecycle (draft/active/under offer/sold/expired) |
| **Search/Discovery** | Query parsing, filtering, geo/map search, sorting, saved searches |
| **Messaging & Leads** | Inquiry threads, notifications, inbox |
| **Reputation/Points (future)** | Tracks points/XP/reputation for Agent & Agency accounts; records rating events where Personal accounts are participants but non-accruing |
| **Billing/Plans (future)** | Plan/tier assignment, entitlement checks, subscription lifecycle, payment provider integration |
| **Admin** | Moderation queue, user/listing suspension, platform analytics |

---

## 3. Technology Stack

| Layer | Choice | Notes |
|---|---|---|
| Frontend | HTML, CSS, vanilla JS, **htmx**, **Alpine.js** | Server-rendered templates (via Django) with htmx for partial-page updates/AJAX (search filtering, favoriting, pagination without full reloads) and Alpine.js for lightweight client-side interactivity (dropdowns, multi-step form state, gallery/lightbox, map widget bindings). SEO is handled naturally since pages are server-rendered HTML by default. |
| Backend | **Django 6** | Django views render templates/htmx partials; Django REST Framework provides the JSON REST API (see API Specification doc). Module boundaries (Users, Listings, Search, Messaging, Reputation, Billing) map to Django apps. |
| Primary Database | **PostgreSQL** (all environments) | Same database engine for local dev and production — avoids environment-parity issues (e.g., JSON query/indexing behavior differs between SQLite and PostgreSQL). Strong relational integrity for users/listings/transactions; native `jsonb` support for flexible type-specific attributes. |
| Search Engine | OpenSearch / Elasticsearch | Full-text + geo-spatial + faceted filtering at scale |
| Object Storage | S3-compatible storage | Listing photos, with CDN in front |
| Cache | Redis | Session cache, rate limiting, hot search results |
| Background Jobs | Queue (e.g., Celery, or Django 6's built-in Background Tasks framework) | Image processing, email notifications, saved-search digest jobs, search-index sync |
| Email | Transactional email provider (via Django's email backend) | Verification, notifications, lead alerts |
| Auth | Django auth (sessions) for the server-rendered app; token/JWT auth via DRF for API consumers | Email/password + Google OAuth login |
| API Style | **HTTPS / REST** (via Django REST Framework) | Resolves the earlier open question in favor of REST over GraphQL |
| Hosting | Cloud provider, containerized | Horizontal scalability for the Django app + search index |

*(Search engine, object storage, cache, and hosting remain proposals — update if you have preferences for those too.)*

---

## 4. Key Design Decisions

### 4.1 Username Generation
- On account creation, the system generates a unique identifier `USR` + 10 digits (`USRXXXXXXXXXX`), checked for uniqueness against the `users` table (collision retry loop or a reserved sequence/counter to guarantee uniqueness without retries).
- This ID is **immutable** — never editable by the user or admin through normal flows.
- The ID is the internal foreign key used across the schema (listings, messages, ratings all reference it), decoupled from the mutable, user-facing **display name**.

### 4.2 Display Name Resolution Logic
Because "what name is shown publicly" varies by account type and linkage, this is implemented as a resolver function (not stored redundantly on every record):

```
resolveDisplayName(accountId):
  account = getAccount(accountId)
  if account.type == PERSONAL:
      return account.username          # USRXXXXXXXXXX
  if account.type == AGENT and account.agencyId is not null:
      agency = getAccount(account.agencyId)
      return agency.displayName        # Agency brand name
  if account.type == AGENT and account.agencyId is null:
      return account.displayName or account.username
  if account.type == AGENCY:
      return account.displayName
```
This keeps the source of truth in one place and avoids denormalized display-name copies going stale when an agency rebrands.

### 4.3 Plan / Entitlement System (Future-Proofing for v1)
- Every account has a `plan_id` (v1: single seeded `free` plan row).
- A generic `plan_entitlements` table (see Database Schema doc) maps `plan_id` → entitlement key/value pairs (e.g., `max_active_listings = 10`, `can_feature_listing = false`).
- Application code calls a single `EntitlementService.check(accountId, entitlementKey)` rather than hardcoding limits — so introducing a new paid plan later is a data change (new plan row + entitlement values), not a code change.

### 4.4 Reputation/Points System (Future-Proofing for v1)
- A `reputation_events` table records atomic events (e.g., `rating_received`, `listing_sold`, `lead_response_time`) with `actor_account_id`, `subject_account_id`, `event_type`, `value`, `created_at`.
- A `reputation_summary` table (or materialized view) aggregates events into points/XP/level/reputation score **per Agent/Agency account only**.
- Personal accounts can appear as `actor_account_id` (e.g., the one leaving a rating) but never have a `reputation_summary` row — enforced at the application layer (and optionally a DB constraint/trigger) since only Agent/Agency account types accrue.
- This event-sourced design means the actual points formula can change later without re-architecting — only the aggregation logic changes.

### 4.5 Property Type Extensibility
- A hybrid schema: common listing fields as real relational columns (price, location, status, etc.) plus a `type_attributes` JSONB column (Django `JSONField`, backed by PostgreSQL's native `jsonb`) for category-specific fields (bedrooms, zoning type, ceiling height, etc.), validated against a per-category JSON Schema stored in an `attribute_definitions` table.
- This avoids a new migration every time a new property subtype or attribute is added, while keeping common fields relational for indexing/filtering performance. PostgreSQL's `jsonb` supports GIN indexing on `type_attributes`, so category-specific filters can be indexed at the DB level in addition to the search engine.

---

## 5. Data Flow: Key Scenarios

### 5.1 Listing Creation
1. User (Agent/Agency/Personal) submits listing form → API validates against category schema (from `attribute_definitions`) and against plan entitlement (`max_active_listings`).
2. Listing stored in `listings` table (status = `draft` or `active` depending on moderation policy).
3. Background job: images processed/resized, pushed to object storage + CDN.
4. Background job: listing indexed into search engine.
5. If auto-publish: listing becomes searchable; else enters moderation queue.

### 5.2 Search Query
1. Client sends filters (location, type, price range, attributes) to Search module.
2. Search module translates to a search-engine query (geo filter + facets + full text).
3. Results returned with pagination; DB is not queried directly for search (search index is source of truth for discovery, DB is source of truth for the record itself).

### 5.3 Rating an Agent (Future)
1. Personal (or other) account submits a rating tied to a completed interaction.
2. Event written to `reputation_events` with `actor_account_id` = rater, `subject_account_id` = agent/agency being rated.
3. Async job recomputes `reputation_summary` for the subject account only (actor's summary is untouched since Personal accounts don't accrue).

---

## 6. Security Considerations
- Password hashing (bcrypt/argon2) or OAuth-only for social accounts.
- Rate limiting on registration, login, contact-seller, and report endpoints to prevent abuse/scraping.
- Phone number reveal endpoint should be rate-limited/obfuscated to deter scraping bots.
- Image upload virus/content scanning before publishing.
- Row-level authorization: a user can only edit their own listings (or listings belonging to their agency, for agency-admin roles).
- Audit log for admin moderation actions (suspend/remove).

---

## 7. Scalability & Performance
- Search-heavy read traffic is offloaded to the search engine, keeping the primary DB focused on writes/transactional integrity.
- CDN in front of all listing images.
- Read replicas for the primary DB if read load grows beyond a single instance.
- Caching layer (Redis) for popular search result pages and homepage featured listings.

---

## 8. Open Technical Questions
1. Real-time messaging (WebSocket, e.g., Django Channels) vs polling for the inbox — v1 can likely use htmx polling/email notifications and defer real-time.
2. Single-region vs multi-region deployment at launch.
3. Preferred cloud provider / hosting environment / existing infra constraints.
