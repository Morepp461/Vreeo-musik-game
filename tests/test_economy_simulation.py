def test_economy_scheduler_still_runs():
    source = open("bot/games/economy.py", encoding="utf-8").read()
    assert "game_run_economy_tick" in source
    assert "game_ai_autonomous_tick" in source


def test_economy_tick_has_idempotent_key():
    source = open("bot/games/economy.py", encoding="utf-8").read()
    assert 'key+"-ai"' in source
    assert 'game_run_economy_tick' in source
