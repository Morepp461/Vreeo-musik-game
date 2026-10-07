update public.game_cities set
gdp_current_idr=case city_key
 when 'jakarta' then 3926153300000000 when 'bandung' then 403970710000000 when 'semarang' then 288050380000000
 when 'yogyakarta' then 52848540000000 when 'surabaya' then 830543350000000 when 'malang' then 108152820000000
 when 'tangerang' then 199839370000000 when 'medan' then 353289260000000 when 'palembang' then 226466130000000
 when 'denpasar' then 71099120000000 when 'balikpapan' then 169316600000000 else gdp_current_idr end,
gdp_year=case when city_key in ('jakarta','bandung','semarang','yogyakarta','surabaya','malang','tangerang','medan','palembang','denpasar','balikpapan') then 2025 else gdp_year end,
minimum_wage_idr=case city_key
 when 'jakarta' then 5396761 when 'bandung' then 2191232 when 'semarang' then 2169349 when 'yogyakarta' then 2264080
 when 'surabaya' then 4961753 when 'malang' then 3507693 when 'tangerang' then 5069708 when 'medan' then 2992559
 when 'palembang' then 3681570 when 'denpasar' then 2996561 when 'balikpapan' then 3579313
 else minimum_wage_idr end,
minimum_wage_year=case when city_key in ('jakarta','bandung','semarang','yogyakarta','surabaya','malang','tangerang','medan','palembang','denpasar','balikpapan') then 2025 else minimum_wage_year end,
data_status=case when city_key in ('jakarta','bandung','semarang','yogyakarta','surabaya','malang','tangerang','medan','palembang','denpasar','balikpapan','pekanbaru','makassar','jayapura') then 'verified' else data_status end,
metadata=metadata || jsonb_build_object('gdp_source','BPS PDRB 2025','minimum_wage_source','Kemnaker 2025','minimum_wage_level',case when city_key in ('surabaya','malang','tangerang','pekanbaru','makassar','jayapura') then 'city_umk' else 'province_ump_fallback' end),
updated_at=now();

insert into public.game_city_governments(city_id,budget,approval,tax_rate,policy)
select id,50000000000,60,0.0500,jsonb_build_object('city_focus',economy_profile)
from public.game_cities where active=true
on conflict(city_id) do nothing;
