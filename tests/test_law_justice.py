def test_world_scheduler_includes_law_tick():
    source = open("bot/games/economy.py", encoding="utf-8").read()
    assert 'game_run_law_tick' in source
    assert 'key+"-law"' in source


def test_law_tick_runs_before_economy_tick():
    source = open("bot/games/economy.py", encoding="utf-8").read()
    assert source.index("game_run_law_tick") < source.index("game_run_economy_tick")
