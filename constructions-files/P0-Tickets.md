# P0 Tickets — MVP Stabilization

**Project:** PROPERTICA (Real Estate Listings Marketplace)  
**Date:** 2026-09-17  
**Goal:** Close gaps so the core marketplace loop is production-ready for a usable v1.

Each ticket is independently implementable. Suggested order: P0-1 → P0-7 (dependencies noted).

---

## P0-1 — Enforce plan entitlements on publish ✅ DONE (2026-09-17)

**Priority:** P0  
**Estimate:** S (0.5–1 day)  
**Depends on:** None (model + `get_entitlement()` already exist)

### Problem
Free plan seeds `max_active_listings=10` and `can_feature_listing=false`, but publish flows do not check these. Users can exceed limits and there is no hard gate.

### Scope
- Before a listing can move to `ACTIVE` (web wizard publish, `ListingPublishView`, API `ListingPublishView` / status change to active), count the owner’s current active listings.
- If count ≥ `max_active_listings` entitlement → reject with clear error.
- Optionally surface remaining quota on dashboard and in wizard review step.
- Do **not** implement paid upgrade yet; just enforce the free-plan limit.

### Acceptance criteria
- [x] Publishing fails with a user-visible message when the owner already has ≥ N active listings (N from plan entitlement).
- [x] Same check applies on both server-rendered and API publish paths.
- [x] Draft / under_offer / sold listings do **not** count toward the active limit.
- [x] Unit tests cover under-limit success and over-limit rejection.
- [x] Dashboard (or wizard review) shows “X of N active listings used” (nice-to-have).

### Technical notes
- Use `Account.get_entitlement("max_active_listings", default="10")`.
- Count: `Listing.objects.filter(owner=user, status=ListingStatus.ACTIVE).count()`.
- Relevant code: `listings/views.py` (`ListingPublishView`, wizard post), `api/views.py` (`ListingPublishView`, `ListingStatusView`).

---

## P0-2 — Saved Searches full CRUD + UI ✅ DONE (2026-09-17)

**Priority:** P0  
**Estimate:** M (1–2 days)  
**Depends on:** None (`SavedSearch` model already exists)

### Problem
`SavedSearch` model + admin exist, but buyers cannot create, name, list, edit, or delete saved searches from the UI. Email digests are out of scope for this ticket.

### Scope
- From search results page: “Save this search” (authenticated) → name + optional notify toggle → create `SavedSearch` with current filters JSON.
- Dashboard / dedicated “Saved searches” section: list, rename, toggle `notify_by_email`, delete, and “Run again” (redirect to search with those filters).
- API endpoints (optional but preferred for consistency): list / create / update / delete under `/api/v1/saved-searches/`.

### Acceptance criteria
- [x] Authenticated user can save the current search filters with a name.
- [x] User can see all their saved searches and re-run them.
- [x] User can edit name / notify flag and delete a saved search.
- [x] Unauthenticated users see a login prompt when trying to save.
- [x] Filters JSON correctly captures q, category, city, price_min/max, sort (and any other active params).
- [x] Basic tests for create / list / delete.

### Out of scope
- Background email digests / `last_notified_at` processing (P1).

### Technical notes
- Model: `listings.models.SavedSearch`.
- Reuse search filter parsing from `ListingSearchView` / `SearchListingsView`.

---

## P0-3 — Email verification flow ✅ DONE (2026-09-17)

**Priority:** P0  
**Estimate:** M (1–2 days)  
**Depends on:** Email backend configuration (can start with console backend)

### Problem
`email_verified_at` field exists but there is no send / confirm flow. Trust and spam control suffer.

### Scope
- On registration (and optionally “resend” from profile): generate signed token, send verification email with link.
- Confirmation view sets `email_verified_at = now()` and redirects with success message.
- Soft gate (recommended for v1): show banner on dashboard / publish if not verified; hard gate on publish is optional and should be configurable.
- API: expose `email_verified` (already partially there) and a resend endpoint if useful.

### Acceptance criteria
- [x] New registrations receive a verification email (console or real backend).
- [x] Clicking the link marks the account verified and shows confirmation.
- [x] Expired / invalid tokens are handled gracefully.
- [x] User can request a new verification email from profile (rate-limited simply).
- [x] Unverified state is visible in profile / dashboard.
- [x] Tests cover token generation, valid confirm, and invalid/expired cases.

### Technical notes
- Use Django’s `TimestampSigner` or `django.core.signing` + email backend.
- Keep token TTL short (e.g. 24–48 h).
- Do not block login; only soft-gate sensitive actions if desired.

---

## P0-4 — Listing detail polish ✅ DONE (2026-09-17)

**Priority:** P0  
**Estimate:** M (1–1.5 days)  
**Depends on:** None

### Problem
Detail page has core content, contact, favorite, report, and map, but lacks similar listings, proper sharing, and a usable photo gallery experience.

### Scope
1. **Similar listings** — same category + same/nearby city (or price band), exclude current, limit 4–6, show under main content.
2. **Share** — copy-link button + basic native share / social links (Open Graph meta tags on the page).
3. **Gallery** — click-to-enlarge / simple lightbox (Alpine.js is already in the stack); ensure cover image is first.

### Acceptance criteria
- [ ] Detail page shows a “Similar listings” section with relevant cards.
- [ ] Share control copies the canonical URL and/or opens native share where available.
- [ ] Open Graph / Twitter card meta tags present for title, description, image.
- [ ] Photos open in a simple lightbox / full-size view.
- [ ] Works on mobile (responsive).

### Technical notes
- Similar query: `Listing.objects.filter(status=ACTIVE, category=…, city=…).exclude(pk=…).order_by("-published_at")[:6]`.
- Meta tags in `detail.html` or via context processor / extra block.

---

## P0-5 — Moderation basics (reports queue) ✅ DONE (2026-09-17)

**Priority:** P0  
**Estimate:** S–M (0.5–1 day)  
**Depends on:** Report model + create flow already exist

### Problem
Users can report listings, but staff have only the generic Django admin. No focused queue or quick actions.

### Scope
- Admin (or simple staff-only view) showing open reports ordered by newest.
- Quick actions: mark Reviewed / Dismissed / Actioned; suspend listing (set status `REMOVED` or `PENDING_REVIEW`); optionally suspend the reported account.
- Link from report to the listing and the reporter.

### Acceptance criteria
- [x] Staff can list all `Report` objects with status filter (default: open).
- [x] Staff can change report status and optionally act on the listing/account in one flow.
- [x] Actions are audited via Django admin log or a simple note field (optional).
- [x] Non-staff cannot access the queue.

### Technical notes
- Prefer enhancing `messaging.admin.ReportAdmin` (or move Report under a clearer app) with list filters, actions, and readonly links.
- If a custom staff dashboard is preferred, a simple `ListView` under `/admin-tools/reports/` is fine for v1.

---

## P0-6 — Static legal & trust pages ✅ DONE (2026-09-17)

**Priority:** P0  
**Estimate:** S (0.5 day)  
**Depends on:** None

### Problem
No Terms, Privacy, About, or Contact pages. Required for trust and basic compliance posture.

### Scope
- Add pages: **About**, **Terms of Service**, **Privacy Policy**, **Contact / Support** (and optionally FAQ).
- Link them in the site footer (and registration if relevant).
- Content can be placeholder but structured (real legal text can be swapped later).
- Contact page: simple form that emails support or stores a message (console backend OK for now).

### Acceptance criteria
- [x] `/about/`, `/terms/`, `/privacy/`, `/contact/` render and are linked in footer.
- [x] Pages use the standard base template and are mobile-friendly.
- [x] Contact form submits successfully (even if only console email).
- [x] No broken links from base layout.

### Technical notes
- Simple `TemplateView`s in `core` or a small `pages` app.
- Footer links already expected in `base.html` — wire them up.

---

## P0-7 — Harden listing wizard & media ✅ DONE (2026-09-17)

**Priority:** P0  
**Estimate:** M (1–2 days)  
**Depends on:** P0-1 (entitlement message should appear in review step)

### Problem
Wizard works end-to-end, but multi-photo UX, validation feedback, cover selection, and publish-time checks need tightening for a trustworthy seller experience.

### Scope
- Clearer step validation and error mapping (stay on the failing step).
- Multi-photo: upload multiple, set cover, basic reorder or at least “set as cover”, remove.
- On review/publish: show entitlement remaining quota and block with the same message as P0-1.
- Ensure required type attributes and at least one photo are enforced before publish (draft can stay looser).
- Improve success / error messaging after publish.

### Acceptance criteria
- [x] User can upload multiple photos, choose a cover, and remove photos.
- [x] Validation errors keep the user on the correct wizard step with visible messages.
- [x] Publish is blocked when active-listing quota is exhausted (message matches P0-1).
- [x] Publish requires ≥1 photo and all required category attributes.
- [x] Draft save remains possible with incomplete data.
- [x] Manual test path through all property types succeeds.

### Technical notes
- Wizard lives in `listings/views.py` (`ListingWizardView`) + `templates/listings/wizard.html` (Alpine).
- Media model: `ListingMedia` (cover flag / order field if present; add if missing).

---

## Suggested implementation order

| Order | Ticket | Reason |
|-------|--------|--------|
| 1 | P0-1 | Small, unblocks quota honesty everywhere |
| 2 | P0-6 | Fast trust win, no backend complexity |
| 3 | P0-5 | Low effort, uses existing Report model |
| 4 | P0-3 | Trust foundation; console email is enough to start |
| 5 | P0-4 | High user-visible polish on the most-viewed page |
| 6 | P0-2 | Completes buyer-side save flow |
| 7 | P0-7 | Touches the most complex UI; benefits from P0-1 already done |

---

## Tracking

- Mark tickets done by updating this file or moving them to a “Done” section.
- Each ticket should land with tests for the new behaviour and a short note in the PR / commit message referencing the ticket ID (e.g. `P0-1`).
