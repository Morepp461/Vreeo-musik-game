-- Production hardening: cover all currently reported unindexed game foreign keys.
create index if not exists game_bank_loans_account_idx on public.game_bank_loans(account_id);
create index if not exists game_credit_history_loan_idx on public.game_credit_history(loan_id);
create index if not exists game_giveaways_recipient_idx on public.game_giveaways(recipient_character_id);
create index if not exists game_political_candidates_character_idx on public.game_political_candidates(character_id);
create index if not exists game_political_candidates_city_idx on public.game_political_candidates(city_id);
create index if not exists game_world_assets_owner_character_idx on public.game_world_assets(owner_character_id);