def test_final_security_hardening_contract():
    from pathlib import Path

    sql = Path("database/final_security_performance_hardening.sql").read_text(encoding="utf-8")
    assert "revoke execute on function public.game_record_ai_memory" in sql
    assert "revoke execute on function public.game_adjust_ai_reputation" in sql
    assert "set search_path = public" in sql
    assert "idx_game_businesses_owner_character" in sql
    assert "idx_game_world_event_ticks_event" in sql


def test_godmode_owner_is_fixed():
    from pathlib import Path

    source = Path("bot/games/commands.py").read_text(encoding="utf-8")
    assert "GODMODE_OWNER_ID = 1441030290280550513" in source
