# Database Schema
## Real Estate Listings Marketplace

**Version:** 1.0 (Draft)
**Date:** September 16, 2026
**Related:** PRD-Real-Estate-Listings-Website.md, TDD-Technical-Design-Document.md
**Engine assumed:** PostgreSQL (JSONB used for extensible attributes)

---

## 1. Entity-Relationship Overview

```
accounts ──┬─< listings >──┬─ listing_media
           │                ├─ listing_attributes (via type_attributes JSONB)
           │                └─< favorites >── accounts
           ├─< agency_agents >── accounts (self-referencing: agency ↔ agent)
           ├─< messages_threads >──< messages
           ├─< saved_searches
           ├─< reputation_events (actor & subject both reference accounts)
           ├─< reputation_summary (Agent/Agency only)
           ├─< plan_entitlements (via plans)
           └─< reports (flagged content)

property_categories ──< attribute_definitions
plans ──< plan_entitlements
```

---

## 2. Core Tables

### 2.1 `accounts`
Stores all users regardless of account type (Personal, Agent, Agency); admins may be a `role` flag or a separate `admin_users` table depending on internal-tooling needs.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID (PK) | Internal primary key (separate from the public username) |
| `username` | VARCHAR(16) UNIQUE NOT NULL | Auto-generated `USRXXXXXXXXXX`; immutable |
| `account_type` | ENUM('personal','agent','agency') NOT NULL | Selected at registration |
| `display_name` | VARCHAR(120) NULL | Editable; meaning depends on `account_type` (see TDD §4.2) |
| `email` | VARCHAR(255) UNIQUE NOT NULL | |
| `phone` | VARCHAR(30) NULL | |
| `password_hash` | VARCHAR(255) NULL | Null if OAuth-only account |
| `oauth_provider` | VARCHAR(30) NULL | e.g., 'google' |
| `email_verified_at` | TIMESTAMP NULL | |
| `phone_verified_at` | TIMESTAMP NULL | |
| `agency_id` | UUID NULL, FK → accounts.id | Set only for `account_type = 'agent'` when linked to an agency |
| `plan_id` | UUID NOT NULL, FK → plans.id | Defaults to the seeded `free` plan |
| `status` | ENUM('active','suspended','deleted') NOT NULL DEFAULT 'active' | |
| `created_at` | TIMESTAMP NOT NULL | |
| `updated_at` | TIMESTAMP NOT NULL | |

**Indexes:** unique on `username`, unique on `email`, index on `agency_id`, index on `account_type`.

**Constraint note:** `agency_id` should only be populated when `account_type = 'agent'` (enforce via check constraint or application-layer validation).

---

### 2.2 `agency_agents`
Optional join table if an agent could belong to multiple agencies over time (history) — if an agent belongs to exactly one agency at a time, `accounts.agency_id` alone is sufficient. Included here for teams/invite-flow tracking.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID (PK) | |
| `agency_id` | UUID NOT NULL, FK → accounts.id | |
| `agent_id` | UUID NOT NULL, FK → accounts.id | |
| `invited_at` | TIMESTAMP | |
| `joined_at` | TIMESTAMP NULL | Null until agent accepts invite |
| `status` | ENUM('invited','active','removed') NOT NULL | |

**Indexes:** unique on (`agency_id`, `agent_id`) where `status='active'`.

---

### 2.3 `property_categories`
Seed/reference data for property types.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID (PK) | |
| `code` | VARCHAR(40) UNIQUE | e.g., `house`, `apartment`, `land_residential`, `commercial_office` |
| `parent_group` | ENUM('residential','land','commercial','other') | Matches PRD §3 taxonomy |
| `label` | VARCHAR(100) | Display name |

---

### 2.4 `attribute_definitions`
Defines the type-specific fields per category, enabling the extensible schema described in the TDD.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID (PK) | |
| `category_id` | UUID NOT NULL, FK → property_categories.id | |
| `attribute_key` | VARCHAR(60) | e.g., `bedrooms`, `zoning_type`, `ceiling_height` |
| `data_type` | ENUM('string','number','boolean','enum') | |
| `enum_options` | JSONB NULL | If `data_type = 'enum'` |
| `is_required` | BOOLEAN DEFAULT false | |
| `display_order` | INT | |

---

### 2.5 `listings`

| Column | Type | Notes |
|---|---|---|
| `id` | UUID (PK) | |
| `owner_account_id` | UUID NOT NULL, FK → accounts.id | The Personal/Agent/Agency account that owns the listing |
| `category_id` | UUID NOT NULL, FK → property_categories.id | |
| `title` | VARCHAR(200) NOT NULL | |
| `description` | TEXT | |
| `price` | NUMERIC(14,2) NOT NULL | |
| `currency` | CHAR(3) NOT NULL | ISO 4217 |
| `negotiable` | BOOLEAN DEFAULT false | |
| `address_line` | VARCHAR(255) | |
| `city` | VARCHAR(100) | |
| `region` | VARCHAR(100) | |
| `country` | VARCHAR(100) | |
| `latitude` | DECIMAL(9,6) | |
| `longitude` | DECIMAL(9,6) | |
| `area_value` | NUMERIC(12,2) NULL | Common searchable field (m²), duplicated from type_attributes for indexing |
| `type_attributes` | JSONB | Category-specific fields per `attribute_definitions` |
| `status` | ENUM('draft','pending_review','active','under_offer','sold','expired','removed') NOT NULL | |
| `featured_until` | TIMESTAMP NULL | Set when a paid "featured" boost is active (future) |
| `published_at` | TIMESTAMP NULL | |
| `expires_at` | TIMESTAMP NULL | |
| `created_at` | TIMESTAMP NOT NULL | |
| `updated_at` | TIMESTAMP NOT NULL | |

**Indexes:** index on `owner_account_id`, index on `category_id`, index on `status`, geo index on (`latitude`,`longitude`), GIN index on `type_attributes` for filtered JSONB queries (search engine is primary discovery path; DB indexes support direct/admin queries).

---

### 2.6 `listing_media`

| Column | Type | Notes |
|---|---|---|
| `id` | UUID (PK) | |
| `listing_id` | UUID NOT NULL, FK → listings.id | |
| `url` | TEXT NOT NULL | CDN URL |
| `sort_order` | INT DEFAULT 0 | |
| `is_cover` | BOOLEAN DEFAULT false | |
| `created_at` | TIMESTAMP | |

---

### 2.7 `favorites`

| Column | Type | Notes |
|---|---|---|
| `id` | UUID (PK) | |
| `account_id` | UUID NOT NULL, FK → accounts.id | |
| `listing_id` | UUID NOT NULL, FK → listings.id | |
| `created_at` | TIMESTAMP | |

**Indexes:** unique on (`account_id`, `listing_id`).

---

### 2.8 `saved_searches`

| Column | Type | Notes |
|---|---|---|
| `id` | UUID (PK) | |
| `account_id` | UUID NOT NULL, FK → accounts.id | |
| `filters` | JSONB NOT NULL | Serialized search filter state |
| `notify_by_email` | BOOLEAN DEFAULT true | |
| `last_notified_at` | TIMESTAMP NULL | |
| `created_at` | TIMESTAMP | |

---

### 2.9 `message_threads` / `messages`

**`message_threads`**

| Column | Type | Notes |
|---|---|---|
| `id` | UUID (PK) | |
| `listing_id` | UUID NOT NULL, FK → listings.id | |
| `buyer_account_id` | UUID NOT NULL, FK → accounts.id | |
| `seller_account_id` | UUID NOT NULL, FK → accounts.id | Owner of the listing at thread creation time |
| `created_at` | TIMESTAMP | |

**`messages`**

| Column | Type | Notes |
|---|---|---|
| `id` | UUID (PK) | |
| `thread_id` | UUID NOT NULL, FK → message_threads.id | |
| `sender_account_id` | UUID NOT NULL, FK → accounts.id | |
| `body` | TEXT NOT NULL | |
| `read_at` | TIMESTAMP NULL | |
| `created_at` | TIMESTAMP | |

---

### 2.10 `reports`

| Column | Type | Notes |
|---|---|---|
| `id` | UUID (PK) | |
| `listing_id` | UUID NULL, FK → listings.id | Nullable if reporting a user instead of a listing |
| `reported_account_id` | UUID NULL, FK → accounts.id | |
| `reporter_account_id` | UUID NOT NULL, FK → accounts.id | |
| `reason` | VARCHAR(60) | |
| `details` | TEXT NULL | |
| `status` | ENUM('open','reviewed','dismissed','actioned') DEFAULT 'open' | |
| `created_at` | TIMESTAMP | |

---

## 3. Plans & Entitlements (Future-Proofing, Seeded Minimal for v1)

### 3.1 `plans`

| Column | Type | Notes |
|---|---|---|
| `id` | UUID (PK) | |
| `code` | VARCHAR(40) UNIQUE | v1 seeds a single row: `free` |
| `label` | VARCHAR(100) | |
| `applies_to` | ENUM('personal','agent','agency','all') | |
| `is_active` | BOOLEAN DEFAULT true | |

### 3.2 `plan_entitlements`

| Column | Type | Notes |
|---|---|---|
| `id` | UUID (PK) | |
| `plan_id` | UUID NOT NULL, FK → plans.id | |
| `entitlement_key` | VARCHAR(60) | e.g., `max_active_listings`, `can_feature_listing` |
| `entitlement_value` | VARCHAR(100) | Stored as string, cast by application (e.g., `"10"`, `"false"`) |

---

## 4. Reputation / Points System (Future — Schema Ready, Not Populated in v1)

### 4.1 `reputation_events`
Event-sourced log; append-only.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID (PK) | |
| `actor_account_id` | UUID NOT NULL, FK → accounts.id | The account performing the action (can be Personal, Agent, or Agency) |
| `subject_account_id` | UUID NOT NULL, FK → accounts.id | The account the event applies to; **must be `account_type IN ('agent','agency')`** at the application layer |
| `event_type` | VARCHAR(60) | e.g., `rating_received`, `listing_sold`, `fast_lead_response` |
| `value` | NUMERIC(10,2) | Points/weight contributed by this event |
| `metadata` | JSONB NULL | e.g., related listing_id, rating stars, free-text review |
| `created_at` | TIMESTAMP | |

### 4.2 `reputation_summary`
Aggregated/materialized per Agent or Agency account only.

| Column | Type | Notes |
|---|---|---|
| `account_id` | UUID (PK), FK → accounts.id | Only rows for `account_type IN ('agent','agency')` |
| `total_points` | NUMERIC(12,2) DEFAULT 0 | |
| `experience_level` | INT DEFAULT 1 | |
| `reputation_score` | NUMERIC(5,2) NULL | Normalized score, e.g., 0–5 |
| `badges` | JSONB DEFAULT '[]' | Array of earned badge codes |
| `updated_at` | TIMESTAMP | Recomputed by async job |

**Application-layer rule:** no row is ever created in `reputation_summary` for `account_type = 'personal'`; Personal accounts appear only as `actor_account_id` in `reputation_events`.

---

## 5. Admin / Audit

### 5.1 `admin_audit_log`

| Column | Type | Notes |
|---|---|---|
| `id` | UUID (PK) | |
| `admin_account_id` | UUID NOT NULL | |
| `action` | VARCHAR(60) | e.g., `listing_removed`, `account_suspended` |
| `target_type` | VARCHAR(40) | `listing` / `account` |
| `target_id` | UUID | |
| `notes` | TEXT NULL | |
| `created_at` | TIMESTAMP | |

---

## 6. Notes on Design Choices
- **UUID primary keys** throughout for safe distributed ID generation and to avoid leaking sequential IDs (separate from the public-facing `username`).
- **`type_attributes` JSONB** on `listings` avoids a wide sparse table or per-category table explosion, while `attribute_definitions` keeps validation data-driven.
- **Event-sourced reputation** (rather than a single mutable counter) preserves history, supports re-computation if the scoring formula changes, and makes it straightforward to enforce "Personal accounts participate but don't accrue" purely as an application/query rule.
- **Plan/entitlement separation** means adding a paid tier later is an INSERT into `plans`/`plan_entitlements`, not a schema migration.
