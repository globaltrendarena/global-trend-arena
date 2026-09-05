-- ============================================================
-- Inaaya's Mart — Supabase schema
-- Run this once in Supabase Dashboard → SQL Editor → New query → Run.
-- Safe to re-run: uses IF NOT EXISTS / OR REPLACE / DROP..CREATE for triggers.
-- ============================================================

-- ------------------------------------------------------------
-- 1. PROFILES — one row per auth.users row, carries the role flag
-- ------------------------------------------------------------
create table if not exists public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  email text not null,
  role text not null default 'customer' check (role in ('customer', 'admin')),
  created_at timestamptz not null default now()
);

alter table public.profiles enable row level security;

-- Auto-create a profile row whenever someone signs up via Supabase Auth.
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer set search_path = public
as $$
begin
  insert into public.profiles (id, email)
  values (new.id, new.email);
  return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();

-- SECURITY DEFINER helper so RLS policies can check "is this user an admin?"
-- without a policy-on-profiles-querying-profiles recursion error.
create or replace function public.is_admin()
returns boolean
language sql
security definer set search_path = public
stable
as $$
  select exists (
    select 1 from public.profiles
    where id = auth.uid() and role = 'admin'
  );
$$;

drop policy if exists "profiles: read own row" on public.profiles;
create policy "profiles: read own row"
  on public.profiles for select
  using (auth.uid() = id);

drop policy if exists "profiles: admins read all" on public.profiles;
create policy "profiles: admins read all"
  on public.profiles for select
  using (public.is_admin());

drop policy if exists "profiles: admins update roles" on public.profiles;
create policy "profiles: admins update roles"
  on public.profiles for update
  using (public.is_admin());

-- ------------------------------------------------------------
-- 2. PRODUCTS
-- ------------------------------------------------------------
create table if not exists public.products (
  id uuid primary key default gen_random_uuid(),
  title text not null,
  description text,
  price numeric(10, 2) not null default 0,
  currency text not null default 'USD',
  category text,
  image_url text,
  stock integer not null default 0,
  active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

alter table public.products enable row level security;

drop policy if exists "products: public can read active" on public.products;
create policy "products: public can read active"
  on public.products for select
  using (active = true);

drop policy if exists "products: admins read all" on public.products;
create policy "products: admins read all"
  on public.products for select
  using (public.is_admin());

drop policy if exists "products: admins insert" on public.products;
create policy "products: admins insert"
  on public.products for insert
  with check (public.is_admin());

drop policy if exists "products: admins update" on public.products;
create policy "products: admins update"
  on public.products for update
  using (public.is_admin());

drop policy if exists "products: admins delete" on public.products;
create policy "products: admins delete"
  on public.products for delete
  using (public.is_admin());

create or replace function public.touch_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists products_touch_updated_at on public.products;
create trigger products_touch_updated_at
  before update on public.products
  for each row execute function public.touch_updated_at();

-- ------------------------------------------------------------
-- 3. SITE CONFIGURATION — key/value store for dashboard-driven settings
--    (e.g. future home for the "staged_routes" the auto-scan module collects,
--    or storefront-wide flags). Public read so the storefront can use it,
--    admin-only write.
-- ------------------------------------------------------------
create table if not exists public.site_config (
  key text primary key,
  value jsonb not null,
  updated_at timestamptz not null default now()
);

alter table public.site_config enable row level security;

drop policy if exists "site_config: public can read" on public.site_config;
create policy "site_config: public can read"
  on public.site_config for select
  using (true);

drop policy if exists "site_config: admins insert" on public.site_config;
create policy "site_config: admins insert"
  on public.site_config for insert
  with check (public.is_admin());

drop policy if exists "site_config: admins update" on public.site_config;
create policy "site_config: admins update"
  on public.site_config for update
  using (public.is_admin());

drop trigger if exists site_config_touch_updated_at on public.site_config;
create trigger site_config_touch_updated_at
  before update on public.site_config
  for each row execute function public.touch_updated_at();

-- ------------------------------------------------------------
-- 4. SEED DATA — optional, delete this block if you don't want sample rows
-- ------------------------------------------------------------
insert into public.products (title, description, price, category, stock)
values
  ('Aurora Table Lamp', 'Warm ambient lighting for any room.', 34.99, 'home-decor', 40),
  ('Cedarwood Pet Bed', 'Machine-washable cover, memory foam base.', 49.50, 'pet-care', 25),
  ('Nomad Travel Mug', 'Double-walled, keeps drinks hot for 6 hours.', 18.00, 'home-decor', 60),
  ('Sunwoven Throw Blanket', 'Reversible cotton-blend throw.', 29.99, 'home-decor', 35)
on conflict do nothing;
