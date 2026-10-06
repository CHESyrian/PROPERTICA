# Product Requirements Document (PRD)
## Real Estate Listings Marketplace

**Version:** 1.0 (Draft)
**Date:** September 16, 2026
**Status:** Draft for review

---

## 1. Overview

### 1.1 Purpose
A web platform where property owners, real estate agents, and agencies can list properties for sale — including land, houses, apartments, commercial premises, and other property types — and where buyers can search, filter, and inquire about listings.

### 1.2 Problem Statement
Buyers looking for property often have to check multiple fragmented sources (agency sites, classifieds, social media groups) to find relevant listings. Sellers and agents need an easy, low-friction way to publish listings that reach a wide, relevant audience. This platform centralizes supply and demand into one searchable marketplace.

### 1.3 Goals
- Provide a fast, intuitive way for buyers to discover properties matching their criteria.
- Provide sellers/agents with simple tools to create, manage, and promote listings.
- Build a trustworthy marketplace (verified listings, accurate data, safe contact flow).
- Support monetization through paid listing tiers/featured placements.

### 1.4 Non-Goals (v1)
- Full transaction processing (offers, contracts, escrow, payments for the property itself).
- Property management / rental listings (rental could be a future phase — v1 is sale-only).
- Mortgage/loan brokering or financial calculators beyond a simple estimator.
- Native mobile apps (responsive web only for v1).

### 1.5 Assumptions (flag if incorrect)
- Focus is **sale**, not rental, listings.
- Both private individuals and professional agents/agencies can post listings.
- Single country/region launch first, with multi-region architecture in mind.
- Monetization via paid/featured listings rather than buyer-side fees.

---

## 2. Target Users & Personas

| Persona | Description | Key Needs |
|---|---|---|
| **Buyer/Renter Prospect** | Individual or family searching for property to purchase | Powerful search/filter, accurate photos & details, easy contact with seller/agent |
| **Private Seller** | Individual selling their own property | Simple listing creation, visibility, lead management |
| **Real Estate Agent** | Professional managing listings for multiple clients | Bulk listing tools, branded profile, lead/CRM basics, analytics |
| **Agency (multi-agent)** | Company managing a team of agents | Agency dashboard, multiple agent seats, brand page |
| **Site Admin/Moderator** | Internal team | Content moderation, fraud detection, user management |

---

## 3. Property Types & Taxonomy

The platform must support multiple property categories, each with tailored attributes:

- **Residential:** houses, apartments/condos, townhouses, villas
- **Land:** residential land, agricultural land, industrial land
- **Commercial:** offices, retail/storefronts, warehouses, industrial buildings
- **Other:** garages/parking, farms, mixed-use buildings, new-development projects

Each category shares a common base schema (price, location, area, photos, description) plus category-specific fields (e.g., number of bedrooms for houses; zoning type for land; ceiling height for warehouses).

---

## 4. Functional Requirements

### 4.1 Listing Creation & Management (Seller/Agent side)
- FR-1: User can create an account as an individual seller or as an agent/agency.
- FR-2: User can create a listing by selecting a property type, then filling a dynamic form with type-specific fields.
- FR-3: User can upload multiple photos (min 1, recommend up to 20–30), reorder them, and set a cover photo.
- FR-4: User can set the listing location via address input with map pin confirmation (geocoding).
- FR-5: User can set price, negotiable flag, and currency.
- FR-6: User can save a listing as draft before publishing.
- FR-7: User can edit or deactivate/delete a listing.
- FR-8: User can mark a listing as "sold"/"under offer."
- FR-9: Agents/agencies can manage multiple listings from a dashboard (list view, status filters, bulk actions).
- FR-10: User can optionally promote/feature a listing (paid) for higher visibility (see Section 7 Monetization).
- FR-11: System validates required fields per property type before publishing.
- FR-12: Listings go through basic automated checks (spam/duplicate detection) before going live; optionally manual review queue.

### 4.2 Search & Discovery (Buyer side)
- FR-13: User can search by location (city, neighborhood, or map area/radius).
- FR-14: User can filter by property type, price range, area (m²/sq ft), number of rooms, and other type-specific attributes.
- FR-15: User can view results as a list and/or on an interactive map (map + list split view).
- FR-16: User can sort results (price asc/desc, newest, area).
- FR-17: User can save searches and get notified (email) of new matching listings.
- FR-18: User can save/favorite individual listings (requires login).
- FR-19: Search supports pagination or infinite scroll with performant load times.
- FR-20: Basic keyword search across listing titles/descriptions.

### 4.3 Listing Detail Page
- FR-21: Displays full photo gallery, description, all attributes, price, and location map.
- FR-22: Displays seller/agent info (name, photo, agency if applicable, verified badge if applicable).
- FR-23: Contact options: message form, and optionally phone reveal (click-to-reveal to reduce scraping).
- FR-24: Displays similar/related listings.
- FR-25: Shows listing freshness (posted date, last updated).
- FR-26: Share listing via link/social sharing.
- FR-27: Report listing (flag as fraudulent/incorrect).

### 4.4 Messaging & Leads
- FR-28: Buyer can send an inquiry message to seller/agent from the listing page without needing a shared external channel.
- FR-29: Seller/agent receives leads in an inbox (in-app + email notification).
- FR-30: Basic conversation thread history per listing/lead.

### 4.5 User Accounts
- FR-31: Registration/login via email or social login (Google, etc.).
- FR-32: Profile management (name, photo, contact info, agency affiliation).
- FR-33: At registration, the user selects one of three account types: **Personal**, **Agent**, or **Agency**. (Site Admin/Moderator accounts are internal, not self-registered.)
- FR-33a: Users do **not** choose their own username. On registration, the system automatically generates a unique, non-editable identifier in the format `USRXXXXXXXXXX` (e.g., `USR0000001234`), used as the user's internal unique identifier.
- FR-33b: A separate, editable **display name** controls what appears publicly, with different behavior by account type:
  - **Personal accounts:** no display name override — the username (`USRXXXXXXXXXX`) itself is what's shown publicly.
  - **Agent accounts linked to an Agency:** the Agency sets a display name (the agency's name/brand), and that display name is shown publicly wherever the agent account is used (e.g., on listings, profile), rather than the agent's username.
  - **Agency accounts:** display name is the agency's public brand name.
- FR-34: Email verification and (optionally) phone verification for trust.
- FR-34a: Agency accounts require an additional step to invite/link Agent accounts as members of the agency (agency ↔ agent relationship), for future team management features.

### 4.6 Admin & Moderation
- FR-35: Admin dashboard to review flagged/reported listings.
- FR-36: Admin can suspend/remove listings and users.
- FR-37: Basic analytics dashboard (total listings, active users, top searches).

### 4.7 Notifications
- FR-38: Email notifications for: new lead/message, saved search matches, listing approaching expiration.
- FR-39: In-app notification center.

---

## 5. Non-Functional Requirements

| Category | Requirement |
|---|---|
| **Performance** | Search results should return in <1s for standard queries; pages should meet Core Web Vitals "Good" thresholds. |
| **Scalability** | Architecture should support growth from thousands to millions of listings without redesign (indexed search, e.g., Elasticsearch/OpenSearch). |
| **Availability** | Target 99.9% uptime for core browsing/search flows. |
| **Security** | HTTPS everywhere, secure auth (hashed passwords or OAuth), rate-limiting on contact/report endpoints, image upload scanning. |
| **Privacy** | GDPR-compliant data handling (assuming EU users); clear consent for data use; ability for users to delete their account/data. |
| **Accessibility** | WCAG 2.1 AA compliance for core flows. |
| **SEO** | Server-rendered or statically generated listing pages, clean URLs, structured data (schema.org RealEstateListing) for search engine visibility. |
| **Localization** | Support for multiple languages/currencies if targeting multiple regions (architect for it even if v1 launches single-locale). |
| **Responsiveness** | Fully responsive design; mobile-first, since a large share of property search happens on mobile. |

---

## 6. Information Architecture (Key Pages)

1. Homepage (search bar, featured listings, property type shortcuts)
2. Search Results (list + map view)
3. Listing Detail Page
4. Create/Edit Listing (multi-step form)
5. Seller/Agent Dashboard (my listings, leads, analytics)
6. Agency Profile Page (public-facing)
7. User Profile/Settings
8. Messaging/Inbox
9. Admin Panel
10. Static pages: About, Pricing/Plans, Terms, Privacy, Contact/Support, FAQ

---

## 7. Monetization & Account Tiering

### 7.1 Launch State (v1)
- Only a **free plan** is offered at launch, for all three account types (Personal, Agent, Agency). No paid plans, billing, or payment processing are in scope for v1.

### 7.2 Design Requirement: Built for Future Paid Plans
Even though v1 is free-only, the system must be architected so paid plans can be introduced later without a rebuild:
- Data model: every account should carry a `plan`/`tier` field (e.g., `free`, and placeholders for future tiers) rather than hardcoding "free" behavior throughout the app.
- Entitlements should be checked through a central plan/entitlement service (e.g., "max active listings," "can feature a listing," "analytics access") rather than scattered hardcoded limits — so future tiers only need new entitlement values, not new logic paths.
- Billing integration (payment provider, invoicing, subscription lifecycle) should be a pluggable module added later, not something v1 needs to build.

### 7.3 Design Requirement: Points, Experience & Reputation System (Future)
Not built in v1, but the account/data model must be designed to accommodate a future gamification/reputation layer, with different participation by account type:
- **Agent and Agency accounts** are the accounts that **accrue** points, experience level, and reputation score over time.
- **Personal accounts participate in the system's activities** — e.g., they can give ratings/reviews and be part of point-awarding interactions (such as rating an agent after a transaction) — but personal accounts **do not themselves accrue** points, reputation, or experience.
- Each Agent/Agency account should support an extensible set of trackable metrics over time (points earned, experience level, reputation score, badges/achievements) without requiring schema changes later — e.g., a flexible `stats`/`reputation` object or related table keyed by account ID.
- Anticipated future inputs to this system (do not build yet, but keep in mind for schema design): listings published, response time to leads, completed/sold transactions, ratings/reviews received from other users (including from Personal accounts), verification status.
- Reputation/points data should be attached to the Agent/Agency profile so it can later be surfaced publicly (e.g., a badge or score on the agency/agent profile page) and used internally (e.g., to affect search ranking or unlock features).

### 7.4 Longer-Term Monetization Ideas (Future, Not Scoped)
- Paid/featured listings to boost placement in search results and homepage.
- Agent/Agency subscription tiers with higher listing quotas, branded agency pages, and analytics.
- Possible pay-per-lead model as an alternative or complement to subscriptions.

---

## 8. Success Metrics (KPIs)

- Number of active listings (by property type)
- Monthly active buyers (searches performed, listings viewed)
- Listing-to-lead conversion rate (% of listing views resulting in a contact)
- Seller/agent retention (repeat listing creation)
- Time-to-first-lead after listing goes live
- Paid conversion rate (free → featured/paid plan)
- Search-to-contact funnel drop-off rates

---

## 9. MVP Scope (Phase 1)

To ship a usable v1 quickly, the MVP should include:

- Property types: Houses, Apartments, Land, Commercial (core 4 categories)
- Listing creation with photos, price, location, core attributes
- Search with location + basic filters (type, price, area) + map view
- Listing detail page with contact/message form
- Buyer accounts (favorites, saved search) and Seller/Agent accounts (dashboard)
- Basic admin moderation tools
- Manual/simple monetization (e.g., one "featured" paid tier)

**Deferred to Phase 2+:** advanced filters per niche property type, agency team management, saved-search email digests, verified-badge program, multi-language support, analytics dashboards, lead-fee monetization.

---

## 10. Open Questions

1. Which region(s)/country(ies) launch first, and what language(s)/currency(ies) are required?
2. Will listings be self-published instantly, or go through manual approval before going live?
3. Should individual (non-agent) sellers be limited in how many listings they can post for free?
4. Is a native mobile app planned for a later phase, or is mobile web sufficient long-term?
5. Do we need integration with external MLS (Multiple Listing Service) data feeds, or is this purely a self-serve marketplace?
6. What level of identity/property-ownership verification is required to reduce fraudulent listings?
7. Any legal/compliance requirements specific to real estate advertising in the target market(s)?

---

## 11. Appendix: Example Property Attribute Schema

**Common fields (all types):** Title, Description, Price, Currency, Negotiable (bool), Address, City, Region, Country, Latitude/Longitude, Photos[], Listing Type (Sale), Status (Active/Under Offer/Sold), Posted Date, Seller/Agent Username (`USRXXXXXXXXXX`)

**User account (common fields):** Username (`USRXXXXXXXXXX`, auto-generated, immutable), Display Name (editable), Account Type (Personal/Agent/Agency), Email, Phone, Plan/Tier (`free`, future: paid tiers), Verification Status, Created Date. **Agent/Agency accounts additionally:** Reputation/Stats object (placeholder for future points, experience level, reputation score, badges).

**House/Apartment:** Bedrooms, Bathrooms, Living Area (m²), Lot Size (m²), Year Built, Floors, Parking Spaces, Furnished (bool), Amenities (pool, garden, etc.)

**Land:** Lot Size (m²/hectares), Zoning Type (residential/agricultural/industrial), Road Access (bool), Utilities Available (water/electricity/sewage)

**Commercial:** Building Type (office/retail/warehouse), Floor Area (m²), Ceiling Height, Loading Dock (bool), Parking Spaces, Zoning/Permitted Use

