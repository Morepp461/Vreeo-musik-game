from bot.games.tournament_engine import round_robin_pairings, standings, bracket_size


def test_round_robin_even_has_every_pair_once():
    rounds = round_robin_pairings([1, 2, 3, 4])
    pairs = {frozenset(pair) for rnd in rounds for pair in rnd}
    assert len(rounds) == 3
    assert len(pairs) == 6


def test_round_robin_odd_has_every_pair_once():
    rounds = round_robin_pairings([1, 2, 3, 4, 5])
    pairs = {frozenset(pair) for rnd in rounds for pair in rnd}
    assert len(rounds) == 5
    assert len(pairs) == 10


def test_standings_score_is_source_of_truth():
    result = standings([1, 2, 3], [
        {'status': 'completed', 'home_team_id': 1, 'away_team_id': 2, 'home_score': 2, 'away_score': 0},
        {'status': 'completed', 'home_team_id': 2, 'away_team_id': 3, 'home_score': 1, 'away_score': 1},
    ])
    assert result[0]['team_id'] == 1
    assert result[0]['points'] == 3
    assert result[1]['team_id'] == 3
    assert result[1]['points'] == 1


def test_bracket_size():
    assert bracket_size(2) == 2
    assert bracket_size(5) == 8
    assert bracket_size(16) == 16
