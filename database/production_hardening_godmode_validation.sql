-- Production hardening: God Mode validation and asset lookup safety.
create or replace function public.game_god_spawn_asset(p_actor text,p_asset_type text,p_asset_key text,p_name text,p_city text,p_quantity bigint,p_metadata jsonb)
returns bigint language plpgsql security definer set search_path=public as $function$
declare v_id bigint;
begin
 if p_actor<>'1441030290280550513' then raise exception 'God Mode denied'; end if;
 if p_quantity<1 then raise exception 'Invalid quantity'; end if;
 insert into game_world_assets(asset_type,asset_key,name,city,quantity,metadata)
 values(p_asset_type,p_asset_key,p_name,p_city,p_quantity,coalesce(p_metadata,'{}'))
 on conflict(asset_key) do update set quantity=game_world_assets.quantity+excluded.quantity;
 select wa.id into v_id from game_world_assets wa where wa.asset_key=p_asset_key;
 insert into game_admin_audit_log(actor_discord_id,action,target_type,target_id,metadata)
 values(p_actor,'spawn_asset','world_asset',v_id,jsonb_build_object('quantity',p_quantity));
 return v_id;
end $function$;

create or replace function public.game_set_world_paused(p_paused boolean,p_actor_id text default null)
returns jsonb language plpgsql security definer set search_path=public as $function$
declare r game_world_state;
begin
 if coalesce(p_actor_id,'')<>'1441030290280550513' then raise exception 'God Mode denied'; end if;
 update game_world_state set paused=p_paused,updated_at=now() where id=1 returning * into r;
 if r.id is null then raise exception 'world_state_not_found'; end if;
 insert into game_audit_log(actor_type,actor_id,action,target_type,target_id,metadata)
 values('godmode',p_actor_id,case when p_paused then 'world_pause' else 'world_resume' end,'world','1',jsonb_build_object('paused',p_paused));
 return jsonb_build_object('success',true,'paused',r.paused,'updated_at',r.updated_at);
end $function$;

create or replace function public.game_god_edit_character(p_actor text,p_character_id bigint,p_changes jsonb)
returns jsonb language plpgsql security definer set search_path=public as $function$
declare r public.game_characters; v_city text; v_gender text;
begin
 if p_actor<>'1441030290280550513' then raise exception 'God Mode denied'; end if;
 v_city:=nullif(trim(p_changes->>'city'),'');
 if v_city is not null and not exists(select 1 from game_cities where active and name=v_city) then raise exception 'CITY_NOT_FOUND'; end if;
 v_gender:=nullif(p_changes->>'gender','');
 if v_gender is not null and v_gender not in ('Laki-laki','Perempuan') then raise exception 'INVALID_GENDER'; end if;
 update game_characters set gender=coalesce(v_gender,gender),province=coalesce(p_changes->>'province',province),city=coalesce(v_city,city),district=coalesce(p_changes->>'district',district),village=coalesce(p_changes->>'village',village),status=coalesce(p_changes->>'status',status),health=coalesce((p_changes->>'health')::smallint,health),happiness=coalesce((p_changes->>'happiness')::smallint,happiness),stress=coalesce((p_changes->>'stress')::smallint,stress),updated_at=now() where id=p_character_id returning * into r;
 if not found then raise exception 'Character not found'; end if;
 insert into game_admin_audit_log(actor_discord_id,action,target_type,target_id,metadata) values(p_actor,'edit_character','character',p_character_id,p_changes);
 return jsonb_build_object('id',r.id,'name',r.name,'city',r.city,'status',r.status);
end $function$;

create or replace function public.game_god_edit_world_state(p_actor text,p_changes jsonb)
returns jsonb language plpgsql security definer set search_path=public as $function$
declare r public.game_world_state; v_city text; v_econ numeric; v_inf numeric; v_target integer;
begin
 if p_actor<>'1441030290280550513' then raise exception 'God Mode denied'; end if;
 v_city:=nullif(trim(p_changes->>'current_city_focus'),'');
 if v_city is not null and not exists(select 1 from game_cities where active and name=v_city) then raise exception 'CITY_NOT_FOUND'; end if;
 v_econ:=nullif(p_changes->>'economy_multiplier','')::numeric;
 v_inf:=nullif(p_changes->>'inflation_rate','')::numeric;
 v_target:=nullif(p_changes->>'ai_population_target','')::integer;
 if v_econ is not null and (v_econ<=0 or v_econ>10) then raise exception 'INVALID_ECONOMY_MULTIPLIER'; end if;
 if v_inf is not null and (v_inf<-0.5 or v_inf>2) then raise exception 'INVALID_INFLATION_RATE'; end if;
 if v_target is not null and (v_target<1 or v_target>10000) then raise exception 'INVALID_AI_TARGET'; end if;
 update game_world_state set world_name=coalesce(nullif(trim(p_changes->>'world_name'),''),world_name),real_seconds_per_game_day=coalesce((p_changes->>'real_seconds_per_game_day')::bigint,real_seconds_per_game_day),ai_population_target=coalesce(v_target,ai_population_target),economy_multiplier=coalesce(v_econ,economy_multiplier),inflation_rate=coalesce(v_inf,inflation_rate),paused=coalesce((p_changes->>'paused')::boolean,paused),current_city_focus=coalesce(v_city,current_city_focus),updated_at=now() where id=1 returning * into r;
 if r.id is null then raise exception 'world_state_not_found'; end if;
 insert into game_admin_audit_log(actor_discord_id,action,target_type,target_id,metadata) values(p_actor,'edit_world_state','world_state',1,p_changes);
 return to_jsonb(r);
end $function$;