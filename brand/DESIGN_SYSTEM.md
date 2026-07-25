# Phzyx Brand & Design System

**Meaning:** *Phzyx* ≈ **physics** + systems.  
**Mark:** **∫ integration** (continuous change / schema as calculus of state) + **quantum orbits** (superposition of desired vs live schema, multi-language ports) + **binary 01** (computation, drivers, code).

---

## 1. Assets

| File | Use |
|------|-----|
| [icons/phzyx-app-icon-1024.png](./icons/phzyx-app-icon-1024.png) | App / PWA / marketing icon master |
| [icons/phzyx-app-icon-512.png](./icons/phzyx-app-icon-512.png) | Medium |
| [icons/phzyx-app-icon-256.png](./icons/phzyx-app-icon-256.png) | Favicon source |
| [icons/phzyx-app-icon-64.png](./icons/phzyx-app-icon-64.png) | Small UI |
| [logos/phzyx-logo-dark.jpg](./logos/phzyx-logo-dark.jpg) | Raster lockup on dark |
| [logos/phzyx-logo-light.jpg](./logos/phzyx-logo-light.jpg) | Raster lockup on light |
| [logos/phzyx-mark.svg](./logos/phzyx-mark.svg) | Vector mark (preferred in product) |
| [logos/phzyx-logo.svg](./logos/phzyx-logo.svg) | Vector dark lockup |
| [logos/phzyx-logo-light.svg](./logos/phzyx-logo-light.svg) | Vector light lockup |
| [tokens.css](./tokens.css) | CSS custom properties + shell primitives |
| [preview/ui-shell.html](./preview/ui-shell.html) | macOS-like layout demo |

Wordmark in product UI should be set in **Geist** or **Inter** at weight 600, tracking ≈ `-0.04em`, lowercase **`phzyx`**.

---

## 2. Symbol rules

| Do | Don’t |
|----|--------|
| Keep ∫ dominant and centered | Replace with generic atom-only clichés |
| Orbits thin, luminous, slightly asymmetric | Busy 3D skeuomorphism in in-app chrome |
| Binary as *dust* (sparse 01) | Walls of random code |
| Cyan → violet brand gradient on mark | Rainbow / neon club gradients |
| Clear space ≥ 20% of mark height | Crowding logo against dense UI |

**Clear space:** empty margin around mark ≥ 0.2 × mark height.  
**Minimum size:** mark ≥ 24px; full lockup ≥ 120px wide.

---

## 3. Color

| Token | Hex | Role |
|-------|-----|------|
| Cyan 400 | `#22D3EE` | Primary accent, focus rings |
| Cyan 300 | `#67E8F9` | Highlights on mark |
| Violet 500 | `#8B5CF6` | Secondary accent, orbits |
| Indigo | `#6366F1` | Bridges cyan/violet |
| App bg (stellar) | `#0B0D12` | Canvas behind glass windows |
| Text primary | `rgba(255,255,255,0.92)` | Body on dark |
| Magical white canvas | `#F2F2F7` | iOS-like grouped background |

Full variables: `tokens.css`.

**Themes (AdminBoard):**

### Primary (enterprise standard — equal weight)

Enterprise users treat **light + dark** as the premium baseline. Both are first-class:

1. **Magical White** — primary light; clean daytime ops, `#F2F2F7` canvas, white elevated cards  
2. **Stellar Dark** — primary dark; deep space + glass; brand default in demos  

### Secondary (optional convenience)

3. **System Ambient** — follows `prefers-color-scheme`; **only switches between the two primaries** (not a third visual language)  

---

## 4. Typography (free, premium — not “Bootstrap defaults”)

Avoid default stacks of Material / Bootstrap / Chakra. Use:

### Primary UI / product

| Role | Font | License / source | Why |
|------|------|------------------|-----|
| **Sans (UI)** | **[Geist](https://vercel.com/font)** | SIL OFL — free | Modern product UI, excellent at small sizes, tech-native without being generic Inter-only |
| **Sans fallback** | **[Inter](https://rsms.me/inter/)** | OFL | Ubiquitous quality, SF Pro-adjacent metrics |
| **Mono** | **[Geist Mono](https://vercel.com/font)** | OFL | Code, SQL, IDs, binary motifs |
| **Mono alt** | **[IBM Plex Mono](https://github.com/IBM/plex)** | OFL | Slightly more “engineering manual” |

### Marketing / display (optional)

| Role | Font | Source |
|------|------|--------|
| Display headings | **[Satoshi](https://www.fontshare.com/fonts/satoshi)** (Fontshare free) | Soft premium geometric |
| Alt display | **[General Sans](https://www.fontshare.com/fonts/general-sans)** | Fontshare free |

### Loading example

```html
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/geist@1.3.1/dist/fonts/geist-sans/style.min.css" />
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/geist@1.3.1/dist/fonts/geist-mono/style.min.css" />
```

Or self-host OFL files under `brand/fonts/` for offline AdminBoard SPA.

### Type scale (macOS-adjacent)

| Name | Size | Use |
|------|------|-----|
| xs | 11px | Meta, badges |
| sm | 13px | Controls, tables, nav (default chrome) |
| md | 15px | Body in content |
| lg | 17px | Emphasized body |
| xl+ | 22 / 28 / 36 | Titles — tight tracking |

**Rules:** Prefer 13px chrome (not 16px Material). Slight negative tracking on titles. Never use pure black `#000` on pure white for long text — use near-black / near-white.

---

## 5. Layout & UX — macOS application model

**Inspiration:** Finder / System Settings / Linear-meets-Apple — **not** dense Bootstrap dashboards or Material cards-with-elevation-24.

### Window chrome

```
┌─ traffic lights ── title / search ─────────────────────┐
│ Sidebar (narrow) │ Content (fluid)                     │
│  · nav sections  │  toolbar                            │
│  · resources     │  table / form / detail              │
└──────────────────┴─────────────────────────────────────┘
```

| Pattern | Spec |
|---------|------|
| Window radius | ~12px |
| Hairline borders | `0.5px` (retina), not 1–2px grey slabs |
| Glass | `backdrop-filter: blur(40px) saturate(160%)` + translucent fill |
| Sidebar | ~240px, quieter background than content |
| Title bar | 52px, optional traffic lights on desktop web for brand demos |
| Controls | 28–32px height, 6px radius, subtle top-highlight gradient |
| Tables | Hairline row separators; hover wash; no zebra circus |
| Spacing | 4px grid; denser than Material (8/16), closer to Apple HIG |
| Focus | Cyan soft ring (`3px` accent-tinted), never default browser blue only |
| Motion | 120–200ms `cubic-bezier(0.22, 1, 0.36, 1)`; respect `prefers-reduced-motion` |
| Transparency | Provide opaque fallback for `prefers-reduced-transparency` |

### Interaction principles

1. **Clarity over decoration** — glass is atmosphere, not the product.  
2. **Content hierarchy** — primary action one per toolbar region.  
3. **Keyboard** — admin tables navigable; ⌘K-style command later.  
4. **Destructive** — never same weight as primary; use system red sparingly.  
5. **Empty states** — human sentences + one action (craft bar).  

### Anti-patterns (explicit)

| Avoid | Prefer |
|-------|--------|
| Default Tailwind purple/indigo SaaS cliché without tokens | Phzyx cyan–violet system |
| Bootstrap cards + jumbo buttons | Compact macOS controls |
| Material ripple everywhere | Subtle opacity / scale 0.98 |
| Inter only + random shadows | Geist + hairlines + glass |
| Rainbow charts by default | Restrained accent + neutrals |

---

## 6. AdminBoard theme mapping

| Rank | Theme id | Canvas | Window | Accent |
|------|----------|--------|--------|--------|
| **Primary** | `magical-white` | `#F2F2F7` | white / light glass | cyan–indigo |
| **Primary** | `stellar-dark` | `#0B0D12` | translucent graphite | cyan |
| Secondary | `system-ambient` | maps to OS → one of the primaries | same | cyan |

```html
<html data-theme="magical-white">  <!-- or stellar-dark; system-ambient optional -->
```

**Product rules:** feature parity on both primaries; marketing always shows light **and** dark; Ambient never ships without both primaries complete.

---

## 7. Implementation notes for SPA / sites

1. Import `tokens.css` once at app root.  
2. Shell structure classes: `.phzyx-app-shell` → `.phzyx-window` → sidebar/content (see preview HTML).  
3. Prefer CSS variables over hard-coded hex in components.  
4. Icon: use PNG/SVG mark; don’t redraw with emoji.  
5. Marketing site can use raster logo JPG for hero; product uses SVG.  

---

## 8. Legal / attribution

- Generated raster marks: Phzyx brand assets for the project.  
- Geist / Inter / IBM Plex / Fontshare faces: keep OFL license files when self-hosting.  
- Do not claim Apple affiliation; “macOS-like” is **interaction quality**, not copying Apple trademarks or SF Pro (use free alternatives above).

---

## 9. Link to product plan

Themes and AdminBoard product naming: [research/plan/06_brand_website_portfolio.md](../research/plan/06_brand_website_portfolio.md).
