def test_autonomous_scheduler_is_wired():
    source = open("bot/games/economy.py", encoding="utf-8").read()
    assert "game_ai_autonomous_tick" in source
    assert '"p_limit":25' in source


def test_autonomous_engine_is_idempotent_by_tick_key():
    source = open("bot/games/economy.py", encoding="utf-8").read()
    assert 'key+"-ai"' in source
