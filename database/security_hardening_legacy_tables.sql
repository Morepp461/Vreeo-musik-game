-- WNI SECURITY HARDENING
-- Enable RLS on legacy exposed game tables and keep them server-side only.
-- Discord bot uses the Supabase service_role connection for game operations.
alter table public.game_city_governments enable row level security;
alter table public.game_institutions enable row level security;
alter table public.game_company_applications enable row level security;
alter table public.game_business_finance_periods enable row level security;

revoke all on public.game_city_governments from anon, authenticated;
revoke all on public.game_institutions from anon, authenticated;
revoke all on public.game_company_applications from anon, authenticated;
revoke all on public.game_business_finance_periods from anon, authenticated;

grant all on public.game_city_governments to service_role;
grant all on public.game_institutions to service_role;
grant all on public.game_company_applications to service_role;
grant all on public.game_business_finance_periods to service_role;
