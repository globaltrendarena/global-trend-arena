# Inaaya's Mart — Supabase Setup

This covers wiring the storefront + admin dashboard to a real Supabase backend:
Auth, a `profiles` table (with an admin role flag), a `products` table, and a
`site_config` table for future dashboard-driven settings.

## 1. Create a Supabase project and get your keys

1. Go to https://supabase.com/dashboard → **New project**.
2. Once it's provisioned, go to **Project Settings → API**.
3. Copy the **Project URL** and the **anon / public** key (not the `service_role` key — that one must never go in client-side code).

## 2. Run the schema

1. In the Supabase dashboard, open **SQL Editor → New query**.
2. Paste the full contents of `supabase/schema.sql` from this repo and click **Run**.
3. This creates:
   - `public.profiles` — one row per signed-up user, with a `role` column (`customer` / `admin`), auto-populated by a trigger on `auth.users`.
   - `public.products` — public can read `active = true` rows; only admins can write.
   - `public.site_config` — public read, admin write; a key/value table reserved for dashboard-driven settings later.
   - A few seed products so the storefront has something to show immediately.

## 3. Create your admin account

1. Supabase dashboard → **Authentication → Users → Add user**. Create yourself an account with an email + password (check "Auto Confirm User" so you don't need to click an email link).
2. Back in **SQL Editor**, run:
   ```sql
   update public.profiles set role = 'admin' where email = 'you@example.com';
   ```
   (Replace with the email you just created. The trigger from step 2 already created the `profiles` row for you — this just flips the role.)

## 4. Add your credentials to `config.json`

Open `config.json` and replace the placeholders:

```json
"supabase": {
    "url": "https://YOUR-PROJECT-REF.supabase.co",
    "anonKey": "YOUR_ANON_PUBLIC_KEY"
}
```

The anon key is meant to be public — it's safe in client-side code because every table is protected by the Row Level Security policies from `schema.sql`. Never put the `service_role` key anywhere in this repo.

## 5. Test locally

Opening `index.html` directly as a `file://` URL won't work — `fetch('config.json')` needs a real HTTP server. From the project root:

```bash
python3 -m http.server 8000
# or: npx serve .
```

Then:
- **Storefront**: open `http://localhost:8000/index.html`. The home page status line should read **"Live from Supabase · N product(s)"** in green. If it instead says "Demo catalog (Supabase not connected yet)" in grey, check the browser console — it logs the Supabase error.
- **Admin**: open `http://localhost:8000/admin.html`. Sign in with the account from step 3. You should land in the dashboard with your email shown in the sidebar. Signing in with a non-admin account should show "not an admin" and sign you back out. Wrong password should show the Supabase auth error inline.

## 6. Test on Cloudflare Pages

1. Push this repo to GitHub/GitLab.
2. Cloudflare dashboard → **Workers & Pages → Create → Pages → connect your repo**.
3. Build settings: no build command, output directory `/` (this is a static site, no bundler).
4. Deploy, then repeat the same two checks from step 5 against your `*.pages.dev` URL.
5. In Supabase → **Authentication → URL Configuration**, add your `*.pages.dev` URL (and any custom domain) to the allowed redirect/site URLs list, or auth requests from that origin will be rejected.

---

Once both checks in step 5/6 pass — live products on the storefront, working admin login gated by the `admin` role — the core backend is confirmed working end to end. Cloudinary and the eprolo import pipeline are separate, additive pieces on top of this.
