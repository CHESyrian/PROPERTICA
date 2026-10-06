# UI/UX Specification
## Real Estate Listings Marketplace

**Version:** 1.0 (Draft)
**Date:** September 16, 2026
**Related:** PRD-Real-Estate-Listings-Website.md, API-Specification.md
**Status:** Draft for review — wireframe-level detail; visual design system (color/type) to be defined separately by design.

---

## 1. Design Principles
- **Search-first:** the fastest path from landing to relevant listings should be as short as possible.
- **Trust-visible:** account type, verification, and (later) reputation should be visible without digging, since buyers are making high-stakes decisions.
- **Low-friction listing creation:** sellers/agents should be able to publish a basic listing in minutes; advanced fields should not block the happy path.
- **Mobile-first, map-aware:** a large share of property search happens on mobile and benefits from map interaction.

---

## 2. Global Navigation

**Header (all pages):**
- Logo / Home link
- Search bar (persistent, condensed on scroll)
- Primary nav: Buy (search), *(future: Rent)*
- "Post a listing" CTA button
- Account menu (avatar/initial): shows **display name** per the resolution rule — the account's own username for Personal accounts, or the agency's display name for agency-linked agents (see PRD §4.5 / TDD §4.2). Not logged in → Login/Register.

**Footer:** About, Pricing/Plans, Terms, Privacy, Contact/Support, FAQ, language/currency selector (future).

---

## 3. Page Specifications

### 3.1 Homepage
**Goal:** get the user into search fast, or a specific featured listing.

Layout (desktop, top to bottom):
1. Hero section: large search bar (location input + property-type quick filter: House / Apartment / Land / Commercial / Other) + "Search" CTA.
2. Property-type shortcut tiles (visual cards linking to pre-filtered search).
3. Featured listings carousel (paid/featured placements — empty/hidden in v1 if no featured plan exists yet, or shows "recently added" as a fallback).
4. "How it works" band for new sellers (3 steps: Create account → List your property → Connect with buyers) with a CTA to register.
5. Footer.

Mobile: hero search bar full-width and sticky-ish; carousels become horizontal-scroll; sections stack vertically.

---

### 3.2 Search Results Page
**Goal:** let a buyer narrow down efficiently and compare listings.

Layout (desktop): **split view** — filter/list panel (left, ~55%) + interactive map (right, ~45%), synced (hovering a card highlights its map pin and vice versa).

- **Top bar:** applied filter chips (removable), sort dropdown (Price ↑/↓, Newest, Area), result count, "Save this search" button (auth required — prompts login if not authenticated).
- **Filter panel (collapsible):** Property type/category, price range (slider + inputs), area range, location radius, category-specific attributes (dynamically rendered based on selected category, e.g., bedrooms for houses, zoning type for land).
- **Result cards:** cover photo, price, title, key attributes (bed/bath/area or category equivalent), city, "posted X days ago", favorite (heart) icon, owner account-type badge (Personal/Agent/Agency).
- **Map:** clustered pins at zoom-out, individual pins with price on hover/click, "search this area" button when map is panned.

Mobile: default to list view with a "Map" toggle button (full-screen map replaces list when toggled, with a "List" button to return). Filters open as a bottom-sheet modal.

---

### 3.3 Listing Detail Page
**Goal:** give the buyer everything needed to decide to make contact.

Layout (desktop, two-column below the gallery):
1. **Photo gallery** (full-width, lightbox on click, thumbnail strip).
2. **Left column:**
   - Title, price, negotiable badge, address/city.
   - Key attributes as an icon row (bed/bath/area, or category-relevant equivalents).
   - Full description (expandable if long).
   - Category-specific attributes table (all `type_attributes`, formatted).
   - Location map (pin, not necessarily exact address if privacy is a concern — flag as an open question).
   - "Similar listings" carousel at the bottom.
3. **Right column (sticky):**
   - Owner card: display name (resolved per account-type rule), account-type badge (Personal/Agent/Agency), profile photo, verification badge if verified, *(future)* reputation score/badge for Agent/Agency owners.
   - "Contact" panel: message form (pre-filled with a default inquiry message), and a "Show phone number" click-to-reveal button (rate-limited).
   - Favorite (heart) and Share buttons.
   - "Report this listing" link (small, unobtrusive).

Mobile: single column, sticky "Contact" bar pinned to the bottom of the viewport once the user scrolls past the initial owner card.

---

### 3.4 Create/Edit Listing (Multi-Step Form)
**Goal:** minimize drop-off during listing creation.

Recommended step structure:
1. **Category selection** — visual tiles (House, Apartment, Land, Commercial, Other → sub-type).
2. **Basic details** — title, description, price, currency, negotiable toggle.
3. **Location** — address input with map-pin confirmation (draggable pin to fine-tune).
4. **Type-specific attributes** — dynamically rendered form fields sourced from `attribute_definitions` for the chosen category (see API Spec / DB Schema); required fields marked clearly.
5. **Photos** — drag-and-drop multi-upload, reorder via drag, set cover photo, upload progress indicators.
6. **Review & Publish** — summary preview (rendered as the actual listing detail page would look), "Save as draft" and "Publish" buttons.

Persistent elements: step indicator/progress bar, "Save as draft" always available, plan-limit warning banner if the account is at/near `max_active_listings` (from `/accounts/me/entitlements`).

Mobile: same steps, single-column, full-screen per step rather than a modal.

---

### 3.5 Seller/Agent Dashboard
**Goal:** manage listings and leads in one place.

Sections (left sidebar nav):
- **My Listings** — table/card list with status filter tabs (Draft / Active / Under Offer / Sold / Expired), quick actions (edit, deactivate, mark sold, feature — disabled with an upsell tooltip in v1 since featuring isn't purchasable yet).
- **Leads/Messages** — inbox-style thread list, unread indicator, linked to the relevant listing.
- **Profile & Settings** — display name (editable per account-type rule; Personal accounts see this field disabled/hidden with an explanatory note that their username is shown publicly), contact info, verification status.
- **Agency Team** *(Agency accounts only)* — list of linked agents, invite-agent form, pending invites.
- *(Future, greyed-out with "Coming soon"):* **Reputation & Points** tab for Agent/Agency accounts; **Plans & Billing** tab.

---

### 3.6 Agency Public Profile Page
- Agency display name, logo/photo, description, verification badge.
- Grid of the agency's active listings.
- *(Future)* Agency reputation score/badges.
- List of agents under the agency (each linking to that agent's listings, shown under the agency's display name per the resolution rule).

---

### 3.7 Account Registration
- Step 1: choose account type — **Personal / Agent / Agency** (three clear cards with a one-line description of each, since this choice isn't easily changed later).
- Step 2: email + password (or "Continue with Google").
- Step 3 (Agent only, optional): "Are you joining an existing agency?" — enter invite code/email, or skip to register as an independent agent.
- Confirmation screen explains that a unique ID (username) has been generated automatically and that it's used as their identifier; Personal accounts are told this ID is what others will see, while Agent/Agency accounts are told they can set a public display name.

---

### 3.8 Admin Panel (Internal Tool — Lower Fidelity)
- Moderation queue: table of flagged listings/accounts with reason, reporter, quick actions (approve/reject/suspend).
- User management: search by username/email, view account detail, suspend/reinstate.
- Basic analytics dashboard: totals and trend charts for listings, active users, top search terms.

---

## 4. Key User Flows (Sequence Summary)

**Buyer: Search → Contact**
Homepage → enter location/type → Search Results (filter/map) → Listing Detail → Contact form → confirmation toast ("Message sent") → (optional) prompted to create an account to track replies if not logged in.

**Seller: Register → Publish**
Register (choose Personal/Agent/Agency) → verify email → "Post a listing" → multi-step form → Review & Publish → Dashboard shows listing as Active/Pending Review.

**Agent joining an Agency**
Agency sends invite (email) → Agent registers or logs in → accepts invite → agent's public listings now display under the agency's display name.

---

## 5. Responsive & Accessibility Requirements
- Breakpoints: mobile (<640px), tablet (640–1024px), desktop (>1024px).
- All interactive elements keyboard-navigable; forms have associated labels (not placeholder-only).
- Color contrast meeting WCAG 2.1 AA on all text/background combinations.
- Map interactions must have a non-map fallback path (list view) for accessibility and low-bandwidth users.
- Image alt text required at upload time (optional field, defaulted to listing title if blank).

---

## 6. Component Inventory (for a shared design system)
- Property Card (search result / carousel variant)
- Filter Panel / Filter Chip
- Map with clustering pins
- Multi-step Form + Step Indicator
- Photo Uploader/Gallery (with lightbox)
- Account-type Badge (Personal / Agent / Agency)
- Verification Badge
- *(Future)* Reputation Badge / Score display
- Message Thread / Inbox list item
- Status Pill (Draft/Active/Under Offer/Sold/Expired)
- Entitlement/Upsell Banner (e.g., "You've reached your free listing limit")

---

## 7. Open UX Questions
1. Should the exact address be shown on the map, or an approximate area (privacy for Personal sellers)?
2. Should Personal-account "Contact" flows require the buyer to be logged in, or allow guest inquiries?
3. What does the "Coming soon" treatment look like for Reputation/Plans tabs — hidden entirely, or visible-but-disabled to set expectations?
