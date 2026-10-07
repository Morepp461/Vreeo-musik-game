-- WNI PHASE 4 — SOCIETY, CONTROL, NPC IDENTITY & WORLD CAUSALITY
-- Server-side only. God Mode owner: 1441030290280550513.
-- Applied to production after live validation.

create index if not exists game_legal_investigations_crime_idx on public.game_legal_investigations(crime_event_id,status);
create index if not exists game_political_events_city_time_idx on public.game_political_events(city_id,occurred_at desc);
create index if not exists game_npc_identities_character_idx on public.game_npc_identities(character_id);
create index if not exists game_npc_life_profiles_character_idx on public.game_npc_life_profiles(character_id);
create index if not exists game_giveaways_event_idx on public.game_giveaways(event_id,status);

create or replace function public.game_god_edit_character(p_actor text,p_character_id bigint,p_changes jsonb)
returns jsonb language plpgsql security definer set search_path=public as $$
declare r public.game_characters;
begin
 if p_actor <> '1441030290280550513' then raise exception 'God Mode denied'; end if;
 update public.game_characters set gender=coalesce(p_changes->>'gender',gender),province=coalesce(p_changes->>'province',province),city=coalesce(p_changes->>'city',city),district=coalesce(p_changes->>'district',district),village=coalesce(p_changes->>'village',village),status=coalesce(p_changes->>'status',status),health=coalesce((p_changes->>'health')::smallint,health),happiness=coalesce((p_changes->>'happiness')::smallint,happiness),stress=coalesce((p_changes->>'stress')::smallint,stress),updated_at=now() where id=p_character_id returning * into r;
 if not found then raise exception 'Character not found'; end if;
 insert into public.game_admin_audit_log(actor_discord_id,action,target_type,target_id,metadata) values(p_actor,'edit_character','character',p_character_id,p_changes);
 return jsonb_build_object('id',r.id,'name',r.name,'city',r.city,'status',r.status);
end $$;

create or replace function public.game_god_edit_world_state(p_actor text,p_changes jsonb)
returns jsonb language plpgsql security definer set search_path=public as $$
declare r public.game_world_state;
begin
 if p_actor <> '1441030290280550513' then raise exception 'God Mode denied'; end if;
 update public.game_world_state set world_name=coalesce(p_changes->>'world_name',world_name),real_seconds_per_game_day=coalesce((p_changes->>'real_seconds_per_game_day')::bigint,real_seconds_per_game_day),ai_population_target=coalesce((p_changes->>'ai_population_target')::integer,ai_population_target),economy_multiplier=coalesce((p_changes->>'economy_multiplier')::numeric,economy_multiplier),inflation_rate=coalesce((p_changes->>'inflation_rate')::numeric,inflation_rate),paused=coalesce((p_changes->>'paused')::boolean,paused),current_city_focus=coalesce(p_changes->>'current_city_focus',current_city_focus),updated_at=now() where id=1 returning * into r;
 insert into public.game_admin_audit_log(actor_discord_id,action,target_type,target_id,metadata) values(p_actor,'edit_world_state','world_state',1,p_changes);
 return to_jsonb(r);
end $$;

create or replace function public.game_god_give_item(p_actor text,p_character_id bigint,p_item_key text,p_item_name text,p_quantity bigint,p_metadata jsonb default '{}'::jsonb)
returns bigint language plpgsql security definer set search_path=public as $$
declare iid bigint;
begin
 if p_actor <> '1441030290280550513' then raise exception 'God Mode denied'; end if;
 if p_quantity<1 then raise exception 'Invalid quantity'; end if;
 insert into public.game_inventory(character_id,item_key,item_name,quantity,metadata,updated_at) values(p_character_id,p_item_key,p_item_name,p_quantity,coalesce(p_metadata,'{}'::jsonb),now())
 on conflict (character_id,item_key) do update set quantity=public.game_inventory.quantity+excluded.quantity,item_name=excluded.item_name,metadata=excluded.metadata,updated_at=now() returning id into iid;
 insert into public.game_admin_audit_log(actor_discord_id,action,target_type,target_id,metadata) values(p_actor,'give_item','inventory',iid,jsonb_build_object('character_id',p_character_id,'item_key',p_item_key,'quantity',p_quantity));
 return iid;
end $$;

create or replace function public.game_god_create_giveaway(p_actor text,p_event_id bigint,p_item_key text,p_quantity bigint,p_recipient_character_id bigint default null)
returns bigint language plpgsql security definer set search_path=public as $$
declare gid bigint;
begin
 if p_actor <> '1441030290280550513' then raise exception 'God Mode denied'; end if;
 if p_quantity<1 then raise exception 'Invalid quantity'; end if;
 insert into public.game_giveaways(event_id,item_key,quantity,recipient_character_id,status) values(p_event_id,p_item_key,p_quantity,p_recipient_character_id,case when p_recipient_character_id is null then 'pending' else 'assigned' end) returning id into gid;
 if p_recipient_character_id is not null then perform public.game_god_give_item(p_actor,p_recipient_character_id,p_item_key,p_item_key,p_quantity,'{}'::jsonb); update public.game_giveaways set status='delivered' where id=gid; end if;
 insert into public.game_admin_audit_log(actor_discord_id,action,target_type,target_id,metadata) values(p_actor,'create_giveaway','giveaway',gid,jsonb_build_object('event_id',p_event_id,'item_key',p_item_key,'quantity',p_quantity,'recipient',p_recipient_character_id));
 return gid;
end $$;

create or replace function public.game_run_social_control_tick(p_tick_key text)
returns jsonb language plpgsql security definer set search_path=public as $$
declare c record; ce record; pe record; n integer:=0; inv integer:=0; pol integer:=0; key text;
begin
 key:='social:'||p_tick_key;
 if exists(select 1 from public.game_government_ticks where tick_key=key) then return jsonb_build_object('idempotent',true,'tick_key',p_tick_key); end if;
 for c in select id,name,gender,birth_date,city,province,status from public.game_characters where status='active' loop
  insert into public.game_npc_identities(character_id,nationality,name_confidence,identity_metadata) values(c.id,'Indonesian',1.0,jsonb_build_object('name',c.name,'gender',c.gender,'age',extract(year from age(current_date,c.birth_date))::int,'city',c.city,'province',c.province))
  on conflict(character_id) do update set identity_metadata=excluded.identity_metadata,name_confidence=greatest(public.game_npc_identities.name_confidence,excluded.name_confidence);
  insert into public.game_npc_life_profiles(character_id,autonomy,household_status,education_level,occupation,relationships,last_decision_at) values(c.id,0.85,'independent','general',coalesce((select position_title from public.game_character_jobs where character_id=c.id and status='active' limit 1),'unemployed'),'{}'::jsonb,now())
  on conflict(character_id) do update set occupation=coalesce((select position_title from public.game_character_jobs where character_id=c.id and status='active' limit 1),public.game_npc_life_profiles.occupation),last_decision_at=now();
  n:=n+1;
 end loop;
 for ce in select * from public.game_crime_events where status in ('reported','open') loop
  insert into public.game_legal_investigations(crime_event_id,lead_investigator,status,evidence_score,witness_count) values(ce.id,'polri-national','active',least(100,greatest(10,ce.severity*18)),greatest(1,ce.severity)) on conflict do nothing;
  update public.game_crime_events set status='investigating' where id=ce.id and status in ('reported','open'); inv:=inv+1;
 end loop;
 for pe in select cg.city_id,cg.approval from public.game_city_governments cg loop
  if pe.approval < 40 then insert into public.game_political_events(city_id,event_type,title,description,metadata) values(pe.city_id,'approval_crisis','Public approval crisis','Low city-government approval is affecting political stability.',jsonb_build_object('approval',pe.approval)); pol:=pol+1;
  elsif pe.approval > 80 then insert into public.game_political_events(city_id,event_type,title,description,metadata) values(pe.city_id,'approval_boom','Public approval surge','Strong public approval is strengthening the city government.',jsonb_build_object('approval',pe.approval)); pol:=pol+1; end if;
 end loop;
 insert into public.game_government_ticks(tick_key,policies_applied,elections_started,votes_cast,elections_completed,approval_changes,notes) values(key,0,0,0,0,0,format('social control: characters=%s investigations=%s political_events=%s',n,inv,pol));
 return jsonb_build_object('tick_key',p_tick_key,'characters',n,'investigations',inv,'political_events',pol,'idempotent',false);
end $$;

revoke all on function public.game_god_edit_character(text,bigint,jsonb),public.game_god_edit_world_state(text,jsonb),public.game_god_give_item(text,bigint,text,text,bigint,jsonb),public.game_god_create_giveaway(text,bigint,text,bigint,bigint),public.game_run_social_control_tick(text) from public,anon,authenticated;
grant execute on function public.game_god_edit_character(text,bigint,jsonb),public.game_god_edit_world_state(text,jsonb),public.game_god_give_item(text,bigint,text,text,bigint,jsonb),public.game_god_create_giveaway(text,bigint,text,bigint,bigint),public.game_run_social_control_tick(text) to service_role;
