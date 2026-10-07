create or replace function public.game_run_city_government_tick(p_tick_key text)
returns jsonb language plpgsql security definer set search_path=public as $$
declare g record; c record; chosen bigint; chosen_name text; pol record; changed int:=0; elections int:=0;
begin
 if exists(select 1 from game_government_ticks where tick_key='citygov:'||p_tick_key) then
   return jsonb_build_object('success',true,'idempotent',true,'tick_key',p_tick_key);
 end if;
 for g in select cg.*,c.name city_name,c.id city_id,c.gdp_current_idr,c.minimum_wage_idr from game_city_governments cg join game_cities c on c.id=cg.city_id where c.active=true loop
   if g.term_ends_at is not null and g.term_ends_at <= now() then
     select x.id,x.name into chosen,chosen_name from game_characters x where x.status='active' and x.city=g.city_name order by md5(x.id::text||p_tick_key) limit 1;
     if chosen is not null then
       update game_city_governments set mayor_character_id=chosen,mayor_name=chosen_name,approval=greatest(45,least(80,approval)),term_started_at=now(),term_ends_at=now()+interval '365 days' where id=g.id;
       elections:=elections+1;
     end if;
   end if;
   select * into pol from game_policies where active=true order by abs(economic_effect) limit 1;
   if pol.id is not null and g.budget >= pol.fiscal_cost then
     update game_city_governments set policy_key=pol.policy_key,budget=budget-pol.fiscal_cost,approval=greatest(0,least(100,approval+pol.approval_effect)),revenue_monthly=greatest(0,round(g.gdp_current_idr*g.tax_rate/12)),expense_monthly=pol.fiscal_cost where id=g.id;
   end if;
   changed:=changed+1;
 end loop;
 insert into game_government_ticks(tick_key,policies_applied,elections_started,elections_completed,approval_changes,notes)
 values('citygov:'||p_tick_key,changed,elections,elections,changed,'City government tick');
 return jsonb_build_object('success',true,'cities_updated',changed,'elections_rotated',elections,'tick_key',p_tick_key);
end $$;
revoke all on function public.game_run_city_government_tick(text) from public,anon,authenticated;
grant execute on function public.game_run_city_government_tick(text) to service_role;