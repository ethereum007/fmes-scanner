# FMES Dashboard

Next.js 14 dashboard for the [FMES Scanner](../). Reads live setups from Supabase, displays them in a sortable table with stats.

## Local dev

```bash
cd dashboard
cp .env.example .env.local
# Fill in NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_ANON_KEY
npm install
npm run dev
```

Open http://localhost:3000.

## Deploy to Vercel

1. Push this repo to GitHub (already done)
2. Go to https://vercel.com/new
3. Import `ethereum007/fmes-scanner`
4. **Root directory:** `dashboard/`
5. **Build settings:** Next.js (auto-detected)
6. **Environment variables** — add both:
   - `NEXT_PUBLIC_SUPABASE_URL`
   - `NEXT_PUBLIC_SUPABASE_ANON_KEY`
7. Deploy

## Custom domain (fmes.alphabullacademy.com)

In Vercel project → Settings → Domains:

1. Add `fmes.alphabullacademy.com`
2. Vercel shows DNS records to add
3. Go to your Cloudflare/GoDaddy DNS for `alphabullacademy.com`:
   - Add `CNAME` record: `fmes` → `cname.vercel-dns.com`
4. Wait ~5 mins for DNS to propagate, then visit fmes.alphabullacademy.com

## Tech

- Next.js 14 App Router + RSC
- Tailwind CSS
- `@supabase/supabase-js` (read-only via anon key + RLS public-read policy)
- ISR with 60s revalidation
