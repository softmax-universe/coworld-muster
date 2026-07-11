"""Self-check for MusterCommissioner's ALL-TIME-HIGH standing (`rank_division` override).

THE STANDING IS WHATEVER `rank_division` RETURNS. At round completion the platform calls it once
and persists exactly what it returns to `division.leaderboard_config`; every leaderboard read serves
that saved copy (app_backend v2/pipeline.py ranks-and-persists, v2/leaderboards.py serves it, no
recompute). MusterCommissioner overrides `rank_division` to rank each policy by its BEST round score
ever (a pinball high score you keep) instead of the base's decaying half-life-weighted mean.

This proves the override against the REAL framework: a policy whose PEAK was an EARLY round (low
recent rounds) still ranks #1 at its peak — the exact case the base EWMA gets wrong (the live league
showed softmaxwell winning a 271K round but sitting #2 on its averaged-down history).

Run under the commissioner image (it provides the `commissioners.*` framework + the muster config):

    docker run --rm --platform linux/amd64 \
      -e COMMISSIONER_KEY=muster -e RULESET_STRATEGY_CONFIG_PATH=/config/muster-commissioner.yaml \
      -v "$PWD/coworld_pkg/commissioner:/app/coworld_pkg/commissioner:ro" \
      -v "$PWD/coworld_pkg/commissioner/all_time_high_test.py:/tmp/t.py:ro" \
      --entrypoint python3 <commissioner-image> /tmp/t.py
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from uuid import uuid4

sys.path.insert(0, "/app")

# Import the entrypoint first (registers "muster" before the stock app eagerly resolves a key).
import coworld_pkg.commissioner.app  # noqa: F401,E402
from commissioners.common.commissioners import (  # noqa: E402
    DivisionLeaderboardContext,
    LeaderboardRoundResultSnapshot,
    get_commissioner,
)
from commissioners.common.models import (  # noqa: E402
    DivisionSnapshot,
    LeagueSnapshot,
    RoundSnapshot,
)


def main() -> int:
    c = get_commissioner("muster")
    assert "rank_division" in type(c).__dict__, "MusterCommissioner must override rank_division"

    p_soft, p_must = "ply_soft", "ply_must"
    div_id, league_id = uuid4(), uuid4()
    now = datetime(2026, 6, 26, 21, 0, 0, tzinfo=timezone.utc)

    # 3 completed rounds, newest first (the base treats completed_rounds[0] as latest).
    rounds = [
        RoundSnapshot(id=uuid4(), public_id=str(uuid4()), division_id=div_id, round_number=rn,
                      status="completed", round_config={}, created_at=now - timedelta(hours=ago),
                      started_at=now - timedelta(hours=ago), completed_at=now - timedelta(hours=ago))
        for rn, ago in [(3, 0), (2, 1), (1, 2)]
    ]
    r3, r2, r1 = rounds  # r1 is oldest

    def rr(rd, pid, name, score, rank):
        return LeaderboardRoundResultSnapshot(
            round_id=rd.id, policy_version_id=uuid4(), rank=rank, score=score,
            result_metadata={"score_kind": "mean_round_score"}, player_id=pid, player_name=name)

    # softmaxwell PEAKS at 271400 in the OLD round; recent rounds low. musterd steady ~104-110k.
    results = [
        rr(r1, p_soft, "softmaxwell", 271400, 1), rr(r1, p_must, "musterd", 46400, 2),
        rr(r2, p_soft, "softmaxwell", 95000, 2), rr(r2, p_must, "musterd", 110000, 1),
        rr(r3, p_soft, "softmaxwell", 73000, 2), rr(r3, p_must, "musterd", 104000, 1),
    ]
    ctx = DivisionLeaderboardContext(
        league=LeagueSnapshot(id=league_id, commissioner_key="muster", commissioner_config={}),
        division=DivisionSnapshot(id=div_id, name="Competition", level=1,
                                  league_id=league_id, type="competition"),
        completed_rounds=rounds, recent_rounds=rounds, round_results=results,
    )

    board = c.rank_division(ctx)
    for s in board:
        print(f"  #{s.rank} {s.player_name}: score={s.score:,.0f} rounds_played={s.rounds_played}")

    assert board, "rank_division returned an empty board"
    assert board[0].player_name == "softmaxwell", "peak (271400) must rank #1 despite low recent rounds"
    assert board[0].score == 271400, f"#1 standing must be the peak 271400, got {board[0].score}"
    assert board[1].score == 110000, f"#2 standing must be musterd's peak 110000, got {board[1].score}"
    print("PASS: all-time-high standing — peak wins, never decays, ranks correctly.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
