-- Final security/performance hardening applied after full WNI audit.
-- Service-role-only simulation APIs must not be callable by public roles.
alter function public.game_record_ai_memory(bigint,text,text,text,text,integer,integer,jsonb) set search_path = public;
alter function public.game_adjust_ai_reputation(bigint,text,text,integer,integer,integer,integer,jsonb) set search_path = public;
revoke execute on function public.game_record_ai_memory(bigint,text,text,text,text,integer,integer,jsonb) from public, anon, authenticated;
revoke execute on function public.game_adjust_ai_reputation(bigint,text,text,integer,integer,integer,integer,jsonb) from public, anon, authenticated;

-- Cover foreign keys identified by the performance advisor.
create index if not exists idx_game_businesses_owner_character on public.game_businesses(owner_character_id);
create index if not exists idx_game_children_family on public.game_children(family_id);
create index if not exists idx_game_crime_events_character on public.game_crime_events(character_id);
create index if not exists idx_game_election_votes_voter on public.game_election_votes(voter_character_id);
create index if not exists idx_game_elections_winner_character on public.game_elections(winner_character_id);
create index if not exists idx_game_families_spouse_a on public.game_families(spouse_a);
create index if not exists idx_game_families_spouse_b on public.game_families(spouse_b);
create index if not exists idx_game_government_leader_character on public.game_government(leader_character_id);
create index if not exists idx_game_news_event on public.game_news(event_id);
create index if not exists idx_game_owned_assets_template on public.game_owned_assets(template_id);
create index if not exists idx_game_relationships_character_b on public.game_relationships(character_b);
create index if not exists idx_game_world_event_ticks_event on public.game_world_event_ticks(event_id);
drop index if exists public.game_business_employees_character_idx;
