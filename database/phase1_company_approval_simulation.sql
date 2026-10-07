create or replace function public.game_run_city_simulation(p_tick_key text) returns jsonb
language plpgsql security definer set search_path=public as $$
declare c record; employed int; population int; changed int:=0; app record; approved int:=0; finalized int:=0;
begin
 for c in select * from game_cities where active=true loop
   select count(*) into employed from game_ai_characters where alive=true and city=c.name and occupation is not null;
   select count(*) into population from game_ai_characters where alive=true and city=c.name;
   update game_city_governments g set approval=greatest(0,least(100,g.approval + case when population>0 and employed::numeric/population < 0.55 then -1 else 1 end)),updated_at=now() where g.city_id=c.id;
   changed:=changed+1;
 end loop;
 for app in select a.* from game_company_applications a join game_cities c on c.id=a.city_id join game_characters ch on ch.id=a.owner_character_id where a.final_status='pending' and ch.status='active' loop
   if app.police_status='pending' then
     update game_company_applications set police_status='approved',police_reviewed_at=now() where id=app.id;
     approved:=approved+1;
   end if;
   select * into app from game_company_applications where id=app.id;
   if app.police_status='approved' and app.mayor_status='pending' then
     update game_company_applications set mayor_status='approved',mayor_reviewed_at=now() where id=app.id;
     approved:=approved+1;
   end if;
   select * into app from game_company_applications where id=app.id;
   if app.police_status='approved' and app.mayor_status='approved' then
     perform game_finalize_company(app.id);
     finalized:=finalized+1;
   end if;
 end loop;
 return jsonb_build_object('success',true,'cities_updated',changed,'applications_approved',approved,'companies_finalized',finalized,'tick_key',p_tick_key);
end $$;
revoke all on function public.game_run_city_simulation(text) from public,anon,authenticated;
grant execute on function public.game_run_city_simulation(text) to service_role;