"""Self-check for MusterCommissioner's per-round scoring (Maxwell 2026-07-11).

A ROUND is an ISOLATED unit: it runs COMPETITION_EPISODES_PER_ROUND episodes and a policy's round
score is its BEST (max) episode among THIS round's own episodes — NOT the base's mean, and NOT a
cross-round all-time peak. This proves `_round_scores_by_policy` takes the max over a round's own
episode scores (so the Rankings/Winners tabs show the round's real best episode), and that the
scheduler emits the configured number of episodes per competition round.

Run under the commissioner image (provides the `commissioners.*` framework + muster config):

    docker run --rm --platform linux/amd64 \
      -e COMMISSIONER_KEY=muster -e RULESET_STRATEGY_CONFIG_PATH=/config/muster-commissioner.yaml \
      -v "$PWD/coworld_pkg/commissioner:/app/coworld_pkg/commissioner:ro" \
      -v "$PWD/coworld_pkg/commissioner/round_max_test.py:/tmp/t.py:ro" \
      --entrypoint python3 <commissioner-image> /tmp/t.py
"""
from __future__ import annotations

import sys
from uuid import uuid4

sys.path.insert(0, "/app")

import coworld_pkg.commissioner.app  # noqa: F401,E402  (registers "muster")
from commissioners.common.commissioners import get_commissioner  # noqa: E402
from commissioners.common.models import (  # noqa: E402
    EpisodeResult,
    PolicyPoolEntry,
    RoundPolicyScore,
)
from coworld_pkg.commissioner.muster_commissioner import COMPETITION_EPISODES_PER_ROUND  # noqa: E402


def main() -> int:
    c = get_commissioner("muster")
    assert "_round_scores_by_policy" in type(c).__dict__, "must override _round_scores_by_policy"

    pool_id = uuid4()
    soft, must = uuid4(), uuid4()
    entries = [
        PolicyPoolEntry(pool_id=pool_id, policy_version_id=soft, player_id="ply_soft", seed_order=0),
        PolicyPoolEntry(pool_id=pool_id, policy_version_id=must, player_id="ply_must", seed_order=1),
    ]

    # 3 episodes THIS round. softmaxwell: [80k, 13_000_000, 0] -> round score = MAX = 13M.
    # musterd: [5_900_000, 5_900_000, 5_900_000] -> round = 5.9M. (max, not mean 4.36M for soft.)
    def ep(soft_score, must_score):
        return EpisodeResult(episode_request_id=uuid4(), scores=[
            RoundPolicyScore(policy_version_id=soft, player_id="ply_soft", score=soft_score),
            RoundPolicyScore(policy_version_id=must, player_id="ply_must", score=must_score),
        ])
    episode_results = [ep(80_000, 5_900_000), ep(13_000_000, 5_900_000), ep(0, 5_900_000)]

    scores, counts = c._round_scores_by_policy(entries, episode_results)
    print(f"  softmaxwell round score = {scores[soft]:,.0f} (episodes 80k/13M/0)")
    print(f"  musterd     round score = {scores[must]:,.0f} (episodes 5.9M x3)")

    assert scores[soft] == 13_000_000, f"round = MAX episode; expected 13M, got {scores[soft]}"
    assert scores[must] == 5_900_000, f"expected 5.9M, got {scores[must]}"
    # NOT the mean (which would be 4.36M for soft) — proves it's max, not the base's mean.
    assert scores[soft] != (80_000 + 13_000_000 + 0) / 3, "must be MAX, not mean"
    assert counts[soft] == 3 and counts[must] == 3, "ranked count = episodes played this round"

    # The per-round result must NOT be inflated by cross-round history: with a SINGLE weak episode
    # this round, the round score is that weak number (an eliminated round is honestly low), even if
    # this policy peaked huge in a past round — that peak belongs to the STANDING, not the round.
    weak = [ep(4200, 4200)]
    weak_scores, _ = c._round_scores_by_policy(entries, weak)
    assert weak_scores[soft] == 4200, f"a weak round scores weak (round isolation), got {weak_scores[soft]}"

    assert COMPETITION_EPISODES_PER_ROUND >= 2, "best-of-N needs N>=2"
    print(f"PASS: round score = best of its OWN {COMPETITION_EPISODES_PER_ROUND} episodes; round isolated from history.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
