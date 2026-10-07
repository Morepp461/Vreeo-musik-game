-- Production hardening: company approvals must be sequential, conditional and refundable on rejection.
create or replace function public.game_run_city_simulation(p_tick_key text)
returns jsonb language plpgsql security definer set search_path=public as $function$
declare c record; employed int; population int; changed int:=0; app record; approved int:=0; finalized int:=0; rejected int:=0; police_ok boolean; mayor_ok boolean; wallet_id bigint;
begin
 if p_tick_key is null or length(trim(p_tick_key))=0 then raise exception 'INVALID_TICK_KEY'; end if;
 for c in select * from game_cities where active=true loop
  select count(*) into employed from game_ai_characters ac where ac.alive=true and ac.city=c.name and ac.occupation is not null;
  select count(*) into population from game_ai_characters ac where ac.alive=true and ac.city=c.name;
  update game_city_governments g set approval=greatest(0,least(100,g.approval+case when population>0 and employed::numeric/population<0.55 then -1 else 1 end)),updated_at=now() where g.city_id=c.id;
  changed:=changed+1;
 end loop;
 for app in select a.* from game_company_applications a join game_cities city_ref on city_ref.id=a.city_id join game_characters ch on ch.id=a.owner_character_id where a.final_status='pending' and ch.status='active' for update of a loop
  if app.police_status='pending' then
   police_ok:=not exists(select 1 from game_law_profiles lp where lp.character_id=app.owner_character_id and lp.wanted_level>=4);
   if police_ok then
    update game_company_applications set police_status='approved',police_reviewed_at=now() where id=app.id; approved:=approved+1;
    select * into app from game_company_applications where id=app.id;
   else
    update game_company_applications set police_status='rejected',police_reviewed_at=now(),mayor_status='rejected',mayor_reviewed_at=now(),final_status='rejected' where id=app.id;
    select id into wallet_id from game_wallets where character_id=app.owner_character_id;
    if wallet_id is null then raise exception 'WALLET_NOT_FOUND'; end if;
    perform game_wallet_adjust(wallet_id,'cash',app.capital,'company_application_refund','Refund perusahaan ditolak','company-refund:'||app.id);
    rejected:=rejected+1; continue;
   end if;
  end if;
  if app.police_status='approved' and app.mayor_status='pending' then
   mayor_ok:=exists(select 1 from game_city_governments cg where cg.city_id=app.city_id and cg.approval>=40 and cg.budget>=0);
   if mayor_ok then
    update game_company_applications set mayor_status='approved',mayor_reviewed_at=now() where id=app.id; approved:=approved+1;
    select * into app from game_company_applications where id=app.id;
   else
    update game_company_applications set mayor_status='rejected',mayor_reviewed_at=now(),final_status='rejected' where id=app.id;
    select id into wallet_id from game_wallets where character_id=app.owner_character_id;
    if wallet_id is null then raise exception 'WALLET_NOT_FOUND'; end if;
    perform game_wallet_adjust(wallet_id,'cash',app.capital,'company_application_refund','Refund perusahaan ditolak pemerintah kota','company-refund:'||app.id);
    rejected:=rejected+1; continue;
   end if;
  end if;
  if app.police_status='approved' and app.mayor_status='approved' and app.final_status='pending' then perform game_finalize_company(app.id); finalized:=finalized+1; end if;
 end loop;
 return jsonb_build_object('success',true,'cities_updated',changed,'applications_approved',approved,'companies_finalized',finalized,'applications_rejected',rejected,'tick_key',p_tick_key);
end $function$;