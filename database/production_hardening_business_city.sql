-- Production hardening: legacy business creation must bind to a canonical city.
create or replace function public.game_create_business(p_owner_character_id bigint,p_business_key text,p_name text,p_sector text,p_city text,p_initial_capital bigint)
returns jsonb language plpgsql security definer set search_path=public as $function$
declare c game_characters%rowtype; b game_businesses%rowtype; cityrow game_cities%rowtype;
begin
 select * into c from game_characters where id=p_owner_character_id and status='active' for update;
 if not found then raise exception 'CHARACTER_NOT_FOUND'; end if;
 select * into cityrow from game_cities where name=trim(p_city) and active=true limit 1;
 if not found then raise exception 'CITY_NOT_FOUND'; end if;
 if p_initial_capital<1000000 then raise exception 'CAPITAL_TOO_LOW'; end if;
 if c.city<>cityrow.name then raise exception 'OWNER_CITY_MISMATCH'; end if;
 perform game_wallet_adjust(p_owner_character_id,'cash',-p_initial_capital,'business_investment','Modal awal '||p_name,p_business_key);
 insert into game_businesses(business_key,owner_character_id,name,sector,city,city_id,cash,reputation,status,legal_status,police_permit_status,mayor_approval_status)
 values(p_business_key,p_owner_character_id,trim(p_name),trim(p_sector),cityrow.name,cityrow.id,p_initial_capital,50,'active','legacy_active','not_required','not_required')
 returning * into b;
 return jsonb_build_object('success',true,'business_id',b.id,'business_key',b.business_key,'cash',b.cash,'city_id',b.city_id);
exception when unique_violation then raise exception 'BUSINESS_KEY_EXISTS';
end $function$;