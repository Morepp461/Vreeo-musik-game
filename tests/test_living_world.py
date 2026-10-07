def test_batch12_living_world_migration_contract():
    from pathlib import Path

    sql = Path("database/wni_batch_12_living_world.sql").read_text(encoding="utf-8")

    assert "create table if not exists public.game_world_events" in sql
    assert "create table if not exists public.game_world_event_ticks" in sql
    assert "create or replace function public.game_run_world_event_tick" in sql
    assert "create or replace function public.game_world_event_after_tick" in sql
    assert "trg_game_world_event_after_tick" in sql
    assert "unique" in sql.lower()


def test_batch12_event_engine_is_idempotent_and_service_role_only():
    from pathlib import Path

    sql = Path("database/wni_batch_12_living_world.sql").read_text(encoding="utf-8")

    assert "if found then" in sql
    assert "revoke all on function public.game_run_world_event_tick(text) from public, anon, authenticated" in sql
    assert "grant execute on function public.game_run_world_event_tick(text) to service_role" in sql
