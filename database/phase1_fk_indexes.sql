create index if not exists game_businesses_city_id_idx on public.game_businesses(city_id);
create index if not exists game_character_jobs_employer_institution_idx on public.game_character_jobs(employer_institution_id);
create index if not exists game_city_governments_mayor_idx on public.game_city_governments(mayor_character_id);
create index if not exists game_company_applications_business_idx on public.game_company_applications(business_id);
create index if not exists game_institutions_business_idx on public.game_institutions(business_id);
create index if not exists game_institutions_owner_character_idx on public.game_institutions(owner_character_id);