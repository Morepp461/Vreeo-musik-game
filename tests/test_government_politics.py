def test_world_scheduler_includes_government_tick():
    source = open("bot/games/economy.py", encoding="utf-8").read()
    assert 'game_run_government_tick' in source
    assert 'key+"-government"' in source

def test_government_tick_runs_before_economy_tick():
    source = open("bot/games/economy.py", encoding="utf-8").read()
    assert source.index("game_run_government_tick") < source.index("game_run_economy_tick")

def test_government_tick_is_idempotent():
    source = open("database/wni_batch_11_government_politics_society.sql", encoding="utf-8").read()
    assert "tick_key text not null unique" in source
