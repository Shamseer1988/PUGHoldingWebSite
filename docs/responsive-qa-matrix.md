# Responsive QA Matrix

The Tailwind-based UI scales fluidly, but rendering each route at every
target breakpoint and confirming there's no horizontal overflow, no
unreadable text, and no untappable controls remains a manual pass. This
document is the device matrix to walk through before a release.

Use Chrome DevTools' **Toggle device toolbar** (`Cmd/Ctrl + Shift + M`)
with the **Responsive** device type to step through the widths below.

---

## 1 · Target breakpoints

The matrix targets six widths covering the modal devices on the public
web:

| Width   | Maps to                                              | Tailwind class |
|---------|------------------------------------------------------|----------------|
| 360 px  | Android (Galaxy S8 / Pixel 5 portrait, narrow phones)| default (`<sm`) |
| 390 px  | iPhone 13/14/15 portrait                             | default (`<sm`) |
| 430 px  | iPhone 14/15 Pro Max portrait                        | default (`<sm`) |
| 768 px  | iPad portrait, large phones landscape                | `md`            |
| 1024 px | iPad landscape, small laptops                        | `lg`            |
| 1440 px | Desktop / laptop main target                         | `xl` / `2xl`    |

Each route below is checked against every breakpoint in this list.

---

## 2 · Per-breakpoint risk areas

When walking the matrix, the recurring risks at each breakpoint are:

| Width  | What to look for                                                                                                                  |
|--------|-----------------------------------------------------------------------------------------------------------------------------------|
| 360 px | Hamburger menu opens cleanly; no element forces horizontal scroll; all CTAs are at least 44×44 px; numbers in dashboard cards don't truncate; long emails wrap. |
| 390 px | Same as 360 plus: bottom of forms reachable above the iOS Safe Area; sticky CTAs don't overlap the iOS home indicator.            |
| 430 px | Same as 390 plus: spacing doesn't feel cramped — there's enough room for 2-column dense cards (companies grid).                    |
| 768 px | Hamburger transitions to inline nav (or stays as drawer — confirm the chosen breakpoint); two-column layouts appear; tables remain scrollable horizontally. |
| 1024 px| Sidebar layouts appear in admin / HR; main + sidebar grid stable; modals don't cover the whole screen.                            |
| 1440 px| Content doesn't stretch ugly — max-width container kicks in around `xl:max-w-7xl`; hero imagery still fills viewport.              |

---

## 3 · Route × breakpoint matrix

`✓` = passes; leave blank when not yet checked; `⚠` = known issue
(link to the row in §5).

### Public site (`/`, `/about`, `/companies`, etc.)

| Route                                | 360 | 390 | 430 | 768 | 1024 | 1440 |
|--------------------------------------|-----|-----|-----|-----|------|------|
| `/` (homepage)                       |     |     |     |     |      |      |
| `/about`                             |     |     |     |     |      |      |
| `/companies`                         |     |     |     |     |      |      |
| `/companies/[slug]`                  |     |     |     |     |      |      |
| `/news`                              |     |     |     |     |      |      |
| `/news/[slug]`                       |     |     |     |     |      |      |
| `/careers`                           |     |     |     |     |      |      |
| `/careers/[slug]` (Apply Now form)   |     |     |     |     |      |      |
| `/contact`                           |     |     |     |     |      |      |
| `/media`                             |     |     |     |     |      |      |
| `/privacy-policy`                    |     |     |     |     |      |      |
| `/terms-and-conditions`              |     |     |     |     |      |      |
| `/pages/[slug]` (CMS pages)          |     |     |     |     |      |      |
| Public AI assistant widget (open)    |     |     |     |     |      |      |
| Mobile nav drawer (open)             |     |     |     |     |      |      |

### Website Admin (`/admin/*`)

| Route                                | 360 | 390 | 430 | 768 | 1024 | 1440 |
|--------------------------------------|-----|-----|-----|-----|------|------|
| `/admin/login`                       |     |     |     |     |      |      |
| `/admin` (dashboard)                 |     |     |     |     |      |      |
| `/admin/hero-slides`                 |     |     |     |     |      |      |
| `/admin/companies`                   |     |     |     |     |      |      |
| `/admin/news`                        |     |     |     |     |      |      |
| `/admin/leadership`                  |     |     |     |     |      |      |
| `/admin/brands`                      |     |     |     |     |      |      |
| `/admin/media`                       |     |     |     |     |      |      |
| `/admin/menu`                        |     |     |     |     |      |      |
| `/admin/pages`                       |     |     |     |     |      |      |
| `/admin/inbox`                       |     |     |     |     |      |      |
| `/admin/subscribers`                 |     |     |     |     |      |      |
| `/admin/seo`                         |     |     |     |     |      |      |
| `/admin/ai-settings`                 |     |     |     |     |      |      |
| `/admin/users`                       |     |     |     |     |      |      |
| `/admin/audit`                       |     |     |     |     |      |      |
| `/admin/settings`                    |     |     |     |     |      |      |

### HR ATS (`/hr/*`)

| Route                                | 360 | 390 | 430 | 768 | 1024 | 1440 |
|--------------------------------------|-----|-----|-----|-----|------|------|
| `/hr/login`                          |     |     |     |     |      |      |
| `/hr` (dashboard)                    |     |     |     |     |      |      |
| `/hr/jobs`                           |     |     |     |     |      |      |
| `/hr/candidates`                     |     |     |     |     |      |      |
| `/hr/interviews`                     |     |     |     |     |      |      |
| `/hr/offers`                         |     |     |     |     |      |      |
| `/hr/reports`                        |     |     |     |     |      |      |
| `/hr/audit`                          |     |     |     |     |      |      |
| `/hr/users`                          |     |     |     |     |      |      |

---

## 4 · Cross-cutting checks (every page, every breakpoint)

- [ ] **No horizontal scroll.** With `document.documentElement.scrollWidth ===
      innerWidth`. Common offenders: tables, long strings without
      `break-words`, fixed-width images.
- [ ] **Touch targets ≥ 44×44 px** on phone widths. Buttons, nav links,
      icon-only actions.
- [ ] **Forms.** Labels visible, inputs at least 16 px font (prevents
      iOS auto-zoom), submit button reachable without obscuring the
      keyboard.
- [ ] **Modals / dialogs.** Close affordance visible; scroll trap works
      on small screens; backdrop covers the iOS Safe Area.
- [ ] **Sticky elements.** Header doesn't cover the first heading;
      bottom sticky CTAs sit above the iOS home indicator
      (`safe-area-inset-bottom`).
- [ ] **Images.** Have `width` + `height` to avoid layout shift; use
      `next/image` so they ship as AVIF/WebP at the right size.
- [ ] **Data tables.** Wrapped in a horizontally-scrollable container
      (`overflow-x-auto`) on small widths.
- [ ] **Dark mode.** Toggle dark mode (if the route supports it) and
      re-check contrast — Tailwind's `dark:` variants exist throughout
      the admin shell.
- [ ] **Reduced motion.** Animations honor `prefers-reduced-motion`
      where they exist (carousels, hero transitions).

---

## 5 · Known issues / open items

_Empty — fill rows here as the first walkthrough surfaces problems._

| # | Page | Breakpoint | Issue | Suggested fix |
|---|------|------------|-------|----------------|
|   |      |            |       |                |

---

## 6 · Device compatibility matrix

Tested against the following real devices/browsers in addition to the
DevTools emulator:

| Device                  | OS                | Browser            | Result |
|-------------------------|-------------------|--------------------|--------|
| iPhone 13 Pro           | iOS 17            | Safari             |        |
| iPhone 15               | iOS 17            | Safari, Chrome     |        |
| Galaxy S22              | Android 14        | Chrome             |        |
| Pixel 7                 | Android 14        | Chrome, Firefox    |        |
| iPad Pro 11"            | iPadOS 17         | Safari             |        |
| MacBook Pro 14"         | macOS 14          | Safari, Chrome, Firefox |   |
| Windows 11 laptop       | Windows 11        | Edge, Chrome, Firefox |     |

Fill the result column on each release: `✓`, `⚠ (link)`, or `✗ (link)`.

---

## 7 · Sign-off

The release is mobile-ready when:

- [ ] Every cell in §3 is `✓` for at least one device per row of §6.
- [ ] §5 is empty or every entry has a tracking ticket linked.
- [ ] All checks in §4 pass.
- [ ] Screenshots of the homepage at 360, 768, and 1440 are attached
      to the release ticket as a visual record.
