# PUG Holding - Frontend (Next.js)

Phase 1 foundation for the Paris United Group Holding frontend.

## Stack

- Next.js 14 (App Router)
- TypeScript
- Tailwind CSS + tailwindcss-animate
- shadcn/ui conventions (CSS variables, `components.json`)
- Framer Motion
- Lucide React icons
- Recharts (added in Phase 5+ for dashboards)
- next-themes (light/dark)

## Local setup

```bash
cd frontend
npm install
cp .env.example .env.local
# adjust NEXT_PUBLIC_API_BASE_URL if your backend is not on :8000
npm run dev
```

Visit:

- Home (Phase 1 splash + health check): http://localhost:3000/
- Website admin placeholder:            http://localhost:3000/admin
- HR ATS placeholder:                   http://localhost:3000/hr
- Frontend health proxy:                http://localhost:3000/api/health

## Scripts

```bash
npm run dev          # next dev (hot reload)
npm run build        # next build
npm run start        # next start (after build)
npm run lint         # next lint
npm run type-check   # tsc --noEmit
```

## Layout

```
frontend/
  app/
    (public)/        # Public website (Phase 3+)
    admin/           # Website admin (Phase 2 login, Phase 5 CMS)
    hr/              # HR ATS portal (Phase 2 login, Phase 7+ modules)
    api/             # Next.js API routes (health proxy)
    layout.tsx       # Root layout (theme + fonts)
    page.tsx         # Phase 1 landing splash
  components/
    ui/              # shadcn primitives (Button etc.)
    theme-provider.tsx
    backend-health-card.tsx
  hooks/
  lib/
  styles/globals.css
  public/
  components.json    # shadcn config
  tailwind.config.ts
  tsconfig.json
  next.config.mjs
  .env.example
```
