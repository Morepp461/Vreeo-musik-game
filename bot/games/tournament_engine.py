from __future__ import annotations

from itertools import combinations
from math import ceil, log2
from typing import Iterable


def round_robin_pairings(team_ids: list[int]) -> list[list[tuple[int, int]]]:
    ids = list(team_ids)
    if len(ids) < 2:
        return []
    if len(ids) % 2:
        ids.append(-1)
    rounds = []
    n = len(ids)
    for _ in range(n - 1):
        pairs = []
        for i in range(n // 2):
            a, b = ids[i], ids[n - 1 - i]
            if a != -1 and b != -1:
                pairs.append((a, b))
        rounds.append(pairs)
        ids = [ids[0], ids[-1], *ids[1:-1]]
    return rounds


def standings(team_ids: Iterable[int], matches: Iterable[dict], win_points=3, draw_points=1, loss_points=0):
    rows = {
        team_id: {
            "team_id": team_id, "played": 0, "wins": 0, "draws": 0, "losses": 0,
            "for": 0, "against": 0, "difference": 0, "points": 0,
        }
        for team_id in team_ids
    }
    for m in matches:
        if m.get("status") != "completed" or m.get("home_score") is None or m.get("away_score") is None:
            continue
        h, a = m["home_team_id"], m["away_team_id"]
        if h not in rows or a not in rows:
            continue
        hs, ass = int(m["home_score"]), int(m["away_score"])
        rows[h]["played"] += 1
        rows[a]["played"] += 1
        rows[h]["for"] += hs
        rows[h]["against"] += ass
        rows[a]["for"] += ass
        rows[a]["against"] += hs
        if hs > ass:
            rows[h]["wins"] += 1
            rows[h]["points"] += win_points
            rows[a]["losses"] += 1
            rows[a]["points"] += loss_points
        elif ass > hs:
            rows[a]["wins"] += 1
            rows[a]["points"] += win_points
            rows[h]["losses"] += 1
            rows[h]["points"] += loss_points
        else:
            rows[h]["draws"] += 1
            rows[a]["draws"] += 1
            rows[h]["points"] += draw_points
            rows[a]["points"] += draw_points
    for row in rows.values():
        row["difference"] = row["for"] - row["against"]
    return sorted(rows.values(), key=lambda r: (-r["points"], -r["difference"], -r["for"], r["team_id"]))


def bracket_size(participants: int) -> int:
    return 1 if participants <= 1 else 2 ** ceil(log2(participants))


def next_round_pairings(winners: list[int | None]) -> list[tuple[int | None, int | None]]:
    return [(winners[i], winners[i + 1]) for i in range(0, len(winners), 2)]
