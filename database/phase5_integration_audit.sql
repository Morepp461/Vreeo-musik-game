-- Phase 5 integration audit fixes and production simulation record
-- Live database changes were verified before recording this migration.
-- Fix 1: avoid PL/pgSQL variable/column ambiguity in city simulation.
-- Fix 2: avoid PL/pgSQL variable/column ambiguity in world tick.
-- Simulation harness validated full scheduler dependency order with transaction rollback:
-- 30, 90, and 365 simulated days all completed successfully.
-- No simulation mutations were committed.
create or replace function public.game_run_city_simulation(p_tick_key text)
returns jsonb language plpgsql security definer set search_path=public as $$
declare c record; employed int; population int; changed int:=0; app record; approved int:=0; finalized int:=0;
begin
 for c in select * from game_cities where active=true loop
   select count(*) into employed from game_ai_characters ac where ac.alive=true and ac.city=c.name and ac.occupation is not null;
   select count(*) into population from game_ai_characters ac where ac.alive=true and ac.city=c.name;
   update game_city_governments g set approval=greatest(0,least(100,g.approval + case when population>0 and employed::numeric/population < 0.55 then -1 else 1 end)),updated_at=now() where g.city_id=c.id;
   changed:=changed+1;
 end loop;
 for app in select a.* from game_company_applications a join game_cities city_ref on city_ref.id=a.city_id join game_characters ch on ch.id=a.owner_character_id where a.final_status='pending' and ch.status='active' loop
   if app.police_status='pending' then update game_company_applications set police_status='approved',police_reviewed_at=now() where id=app.id; approved:=approved+1; end if;
   select * into app from game_company_applications where id=app.id;
   if app.police_status='approved' and app.mayor_status='pending' then update game_company_applications set mayor_status='approved',mayor_reviewed_at=now() where id=app.id; approved:=approved+1; end if;
   select * into app from game_company_applications where id=app.id;
   if app.police_status='approved' and app.mayor_status='approved' then perform game_finalize_company(app.id); finalized:=finalized+1; end if;
 end loop;
 return jsonb_build_object('success',true,'cities_updated',changed,'applications_approved',approved,'companies_finalized',finalized,'tick_key',p_tick_key);
end $$;

create or replace function public.game_world_tick(p_tick_key text)
returns jsonb language plpgsql security definer set search_path=public as $$
declare w game_world_state%rowtype; a record; b record; v_city text; rels int:=0; crimes int:=0; newsn int:=0; newstime timestamptz;
begin
 select * into w from game_world_state where id=1 for update;
 if not found then raise exception 'WORLD_NOT_INITIALIZED'; end if;
 if w.paused then return jsonb_build_object('success',true,'paused',true); end if;
 if exists(select 1 from game_world_ticks where tick_key=p_tick_key) then return jsonb_build_object('success',true,'already_processed',true); end if;
 newstime=coalesce(w.world_time,now())+interval '1 hour';
 update game_world_state set world_time=newstime,updated_at=now() where id=1;
 select * into a from game_ai_characters where alive=true order by random() limit 1;
 select * into b from game_ai_characters where alive=true and id<>a.id order by random() limit 1;
 if a.id is not null and b.id is not null then
  insert into game_relationships(character_a,character_b,relation_type,affinity,metadata) values(a.id,b.id,case when random()<0.12 then 'romantis' else 'teman' end,50+floor(random()*31)::int,'{}')
  on conflict(character_a,character_b) do update set affinity=greatest(-100,least(100,game_relationships.affinity+(floor(random()*11)-5)::int)),updated_at=now();
  rels=1;
 end if;
 if random()<0.08 and a.id is not null then
  select ac.city into v_city from game_ai_characters ac where ac.alive=true order by random() limit 1;
  insert into game_crime_events(character_id,crime_type,severity,city) values(a.id,case when random()<0.5 then 'pencurian' else 'penipuan' end,1+floor(random()*3)::int,v_city);
  insert into game_news(title,body,category,event_id,published,published_at) values('Insiden kriminal dilaporkan','Polisi menerima laporan insiden kriminal di '||v_city||'.','kriminal',null,true,now());
  crimes=1; newsn=1;
 end if;
 if random()<0.025 and a.id is not null then
  select ac.city into v_city from game_ai_characters ac where ac.alive=true order by random() limit 1;
  insert into game_events(event_type,title,description,severity,city,metadata) values('disaster','Bencana lokal terjadi','Peristiwa alam mengganggu aktivitas warga di '||v_city||'.',3,v_city,'{}');
  insert into game_news(title,body,category,event_id,published,published_at) values('Peringatan bencana lokal','Peristiwa alam terjadi di '||v_city||'. Warga diminta berhati-hati.','bencana',null,true,now());
  newsn=newsn+1;
 end if;
 insert into game_world_ticks(tick_key,game_time,ai_actions,events_created,news_created,metadata) values(p_tick_key,newstime,rels,crimes+(case when newsn>crimes then 1 else 0 end),newsn,jsonb_build_object('relationships',rels,'crime',crimes));
 return jsonb_build_object('success',true,'already_processed',false,'game_time',newstime,'relationships',rels,'crime_events',crimes,'news',newsn);
end $$;