# P3 / Phase 2+ Tickets

**Project:** PROPERTICA  
**Date:** 2026-09-17  
**Depends on:** P0–P2  

Focus: foundations for reputation, privacy, monetization, agent tools, digests, and OAuth — implementable without live third-party accounts.

---

## P3-1 — Reputation / points event system ✅ DONE (2026-09-17)

**Scope:** `ReputationEvent` + `ReputationSummary` for Agent/Agency only; record helpers; show score on public profile when present.

## P3-2 — Account self-deletion & data export (GDPR-lite) ✅ DONE (2026-09-17)

**Scope:** Export JSON of account data; soft-delete account (status=deleted, anonymize email, deactivate).

## P3-3 — Paid plan foundation (no live billing) ✅ DONE (2026-09-17)

**Scope:** Seed `starter` plan entitlements; plan catalog page; staff/owner can assign plan; upgrade UI shows “coming soon” payment stub with entitlement switch for manual activation.

## P3-4 — Saved-search email digests (command) ✅ DONE (2026-09-17)

**Scope:** Management command scans `SavedSearch` with `notify_by_email`, finds new matching listings since `last_notified_at`, emails user, updates timestamp.

## P3-5 — Agent bulk status actions ✅ DONE (2026-09-17)

**Scope:** Dashboard multi-select + bulk set status (draft / active via publish rules / under_offer / sold) for own listings.

## P3-6 — OAuth scaffolding (Google) ✅ DONE (2026-09-17)

**Scope:** Settings + login button UI; optional `social-auth` style stub endpoint that documents how to wire Google; keep email/password primary.

## P3-7 — Multi-currency display helpers ✅ DONE (2026-09-17)

**Scope:** Supported currencies setting; listing currency already exists; format helper + filter preference on search (currency filter).
