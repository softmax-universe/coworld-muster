"""Muster's custom league commissioner.

WHY THIS EXISTS (2026-06-24): the stock `ruleset_strategy` commissioner makes two
assumptions that don't fit Muster, both of which broke live league rounds:

1. SAME variant for every division — it resolves the baked `num_agents` of
   `variants[0]` (the full 19-arena / 750-tick / 6-player world) for the Qualifiers
   staging gate too, so the qualifier ran a full-scale episode and blew the
   platform's 300s episode-job cap ("Episode job duration exceeded 300 seconds").

2. The stock preset would seat each division on the SAME baked variant with a fixed real
   field. Muster wants the opposite: EVERY submitted champion in ONE shared world, with the
   engine scripted-filling the rest. (Historically the platform also required an episode to
   seat exactly the variant's baked `num_agents` real policies — which forced a discrete
   "largest rung ≤ field" ladder and, with 4 champions, split them into two 2-player episodes.
   VERIFIED 2026-07-09 that constraint is GONE from the deployed backend: episode_tracker
   `_validate_one` checks only request_id/variant_id/valid-champion-ids, and episode_dispatch
   inserts one EpisodeRequestPolicy per provided id — so we seat 2–6 champions on the 6-seat
   island and the engine fills the empties.)

Kyle (commissioner framework author) confirmed: the presets don't expose this, but
a custom commissioner CAN. This subclass overrides ONLY the per-round seating:

  • QUALIFIERS (a `staging` division) → the tiny `qualifier` variant: ONE connected
    seat on a 2-arena world, 80 ticks, isQualifier=true. A pure connect/build/run/
    score LOAD-CHECK against scripted opponents — near-instant, can't time out.
  • COMPETITION (one flat division — no tiers) → EVERY real champion in ONE shared world,
    on the SMALLEST variant that fits them all, FLOORED at a full island (island6=6) and
    stepping up (ring12 → world24 → world64) as the field grows; the engine scripted-fills the
    remaining island-armies. MIN 2 champions to start a round; >MAX_COMPETITION_SEATS=64 windows
    into multiple full-world episodes, evenly spread. So 2–6 submitted policies all meet on one
    scripted-filled island (NOT paired off), and the shared world grows toward a full server.

⚠️ TOKEN-COUNT CEILING (empirical 2026-06-24): config_schema.tokens must be a FIXED
    count N (upload rejects a range), and the HOSTED smoke cert launches N REAL pods.
    Binary search of the hosted-smoke pod ceiling: N=16/36/64/72/76 PASS, N=78/80/96
    FAIL at job setup (episode_id:None / error_type:unknown — the original 96-connection-
    crash signature). N=77 was FLAKY (passed once, failed once) = the ragged edge. So we
    ship N=64 — reliable, with headroom below the flaky edge, still up to 64 real
    head-to-head. The world is still 96 island-armies; seats beyond the 64 real are
    always scripted.

It ALSO overrides `rank_division` to make the division standing an ALL-TIME HIGH (each
policy's best round score ever) rather than the base's decaying half-life-weighted mean —
see `rank_division` below. The platform calls `rank_division` at round completion and
serves exactly what it returns as the standing, so this IS the leaderboard a pinball-style
high-score game wants: glory is a trophy you keep, not a number that bleeds.

Everything else — promotion/relegation, membership events — is inherited verbatim from
RulesetStrategyCommissioner and still driven by muster-commissioner.yaml. Selected via
COMMISSIONER_KEY=muster (set in the image).
"""
from __future__ import annotations

from commissioners.common.commissioners import register_commissioner
from commissioners.common.models import DIVISION_TYPE_STAGING
from commissioners.common.protocol import (
    EpisodeRequest as CommissionerEpisodeRequest,
    RoundStart as CommissionerRoundStart,
    ScheduleEpisodes as CommissionerScheduleEpisodes,
)
from commissioners.common.ruleset_strategy.commissioner import RulesetStrategyCommissioner
from commissioners.common.ruleset_strategy.entrants import select_rule
from commissioners.common.ruleset_strategy.round_start import RoundStartView
from commissioners.common.ruleset_strategy.scheduling import schedule_entries

# The manifest variant ids (see coworld_manifest_template.json → "variants").
QUALIFIER_VARIANT_ID = "qualifier"
# The ONE competition variant — a full 19-arena world that OMITS a baked players[] list, so it
# seats a VARIABLE number of real champions (the rest scripted-filled by the engine).
COMPETITION_VARIANT_ID = "competition"
# A competition round needs at least this many REAL champions to start (the rest of
# the 19-arena world is scripted-filled by the engine). Maxwell 2026-06-24:
# "competition should require at least 2 in a division for a round to start."
MIN_COMPETITION_SEATS = 2
# Cap on REAL policies seated in one competition episode = the hosted-pod ceiling (empirical
# 2026-06-24: reliable to 64, flaky at 77+). Up to this many real champions play in ONE shared
# world; beyond it the round windows into multiple full episodes (rare — the league is far below).
MAX_COMPETITION_SEATS = 64

# ── ONE SHARED WORLD THAT FILLS AS PLAYERS JOIN (Maxwell 2026-07-09: "as more players enter, the
# islands fill in … some partially full, some fully full") ─────────────────────────────────────
# THE PLATFORM MECHANISM (verified end-to-end 2026-07-09 against the deployed backend + a real
# manifest): a variant whose game_config OMITS `players` seats a VARIABLE real count. At dispatch
# `infer_token_count_for_game_config` returns None for a players-omitted, variable-`tokens` (1..64)
# schema → the backend seats exactly `len(policy_version_ids)`, and `game_config_with_named_players`
# BUILDS a players list sized to the seated names (no baked list to mismatch → no 400). At upload,
# `players` is NOT in config_schema.required (only `tokens` is), so a players-omitted variant
# validates + certifies. (This replaces the earlier per-size island ladder — and fixes the 0.1.28
# bug where seating N<baked on a fixed-`players` variant 400'd. Verify at the layer that dispatches.)
#
# ⇒ Seating is now dead simple: seat EVERY champion (2..64) in ONE episode on the single
# `competition` variant; the engine scripted-fills the rest of the ~96-army world, so islands fill
# in as more policies qualify. Only a field beyond MAX_COMPETITION_SEATS (64) windows into multiple
# full episodes (evenly), which the league is nowhere near.


class MusterCommissioner(RulesetStrategyCommissioner):
    """Per-division seating: tiny qualifier load-check + scripted-filled competition."""

    def _is_qualifier_division(self, division) -> bool:
        # Staging divisions are the qualifier gate (muster-commissioner.yaml marks
        # Qualifiers `type: staging`). Robust to renames; never matches competition.
        return getattr(division, "type", None) == DIVISION_TYPE_STAGING

    def _qualifier_variant_exists(self, round_start: CommissionerRoundStart) -> bool:
        return any(v.id == QUALIFIER_VARIANT_ID for v in round_start.variants)

    def schedule_episodes_for_round_start(
        self, round_start: CommissionerRoundStart
    ) -> CommissionerScheduleEpisodes:
        config = self._config()
        view = RoundStartView(round_start, config)
        division = view.current_division
        rule = select_rule(config, division, view.memberships)
        entries = view.entries(rule)
        baked_variant_id, baked_num_agents = view.variant()

        # ── QUALIFIER (staging) → tiny load-check variant, 1 connected seat ────────
        if self._is_qualifier_division(division) and self._qualifier_variant_exists(round_start):
            return schedule_entries(
                pool=view.pool(rule),
                primary_entries=entries,
                filler_entries=view.filler_entries(entries),
                num_agents=1,
                variant_id=QUALIFIER_VARIANT_ID,
                config=config,
                recent_results=round_start.recent_results,
            )

        # ── COMPETITION → EVERY champion in ONE shared world (variable-seat variant) ─
        # Seat ALL real champions in a SINGLE episode on the players-omitted `competition` variant;
        # the engine scripted-fills the rest of the ~96-army world (islands fill in as more policies
        # qualify). No baked players list → no exact-count constraint → any 2..64 seats in one game.
        # Only a field beyond MAX_COMPETITION_SEATS windows into multiple full episodes (evenly).
        champions = [e.policy_version_id for e in entries]
        num_real = len(champions)
        if num_real < MIN_COMPETITION_SEATS:
            # Not enough real champions yet — emit no episodes (round simply doesn't run
            # this tick) instead of letting stock scheduling raise/duplicate self-clones.
            return CommissionerScheduleEpisodes(episodes=[])

        available = {v.id for v in round_start.variants}
        # Use the variable `competition` variant when present; fall back to the round's baked
        # variant id if a manifest hasn't shipped it yet (degrades, never crashes).
        variant_id = COMPETITION_VARIANT_ID if COMPETITION_VARIANT_ID in available else baked_variant_id

        episodes: list[CommissionerEpisodeRequest] = []
        if num_real <= MAX_COMPETITION_SEATS:
            # The common case: EVERY champion in ONE shared world.
            episodes.append(CommissionerEpisodeRequest(
                request_id="competition-1", variant_id=variant_id,
                policy_version_ids=champions))
        else:
            # Field exceeds the hosted-pod ceiling — window into full episodes, evenly spread.
            seats = MAX_COMPETITION_SEATS
            n_eps = -(-num_real // seats)  # ceil, no import needed
            base = num_real // n_eps
            rem = num_real % n_eps
            start = 0
            for i in range(n_eps):
                size = base + (1 if i < rem else 0)
                episodes.append(CommissionerEpisodeRequest(
                    request_id=f"competition-{i + 1}", variant_id=variant_id,
                    policy_version_ids=champions[start:start + size]))
                start += size
        return CommissionerScheduleEpisodes(episodes=episodes)

    # ── ALL-TIME-HIGH at ROUND COMPLETION (the standing the platform ACTUALLY serves) ──────────
    # VERIFIED live 2026-07-09 (the hard way): the division standing the Observatory shows is written
    # at ROUND COMPLETION from RoundComplete → the backend persists it to division.leaderboard_config
    # (app_backend pipeline.py L2464, from `complete.leaderboards`, which its compat shim derives from
    # RoundComplete.results when an older commissioner sends only `results`). That per-round board
    # OVERWRITES the peak board rank_division writes on the separate scheduling-refresh path — so
    # overriding rank_division ALONE left the live board showing the latest round's scores, not peaks
    # (musterd's real 10.5M peak displayed as its 0.66M latest round). To make the standing a pinball
    # HIGH SCORE we must ALSO make the round-completion `results` carry each policy's PEAK.
    #
    # Implementation: let the base build the RoundComplete (handles per-round scoring, memberships,
    # the on_round_completed hook), then REPLACE each ranking's score with that policy's MAX over the
    # full history the platform ships us — round_start.recent_results (the last ≤50 completed rounds,
    # pipeline.py L2659) PLUS this round's own just-computed scores — and re-rank. The compat shim then
    # derives a PEAK leaderboards from these results. recent_results carries no result_metadata, so we
    # peak on raw score across all Muster rounds (single scoring scheme — no scale-mixing risk here).
    def complete_round_for_round_start(self, round_start, episode_results,
                                       scheduled_episodes=None, failed_episodes=None):
        complete = super().complete_round_for_round_start(
            round_start, episode_results, scheduled_episodes, failed_episodes)
        # Peak per policy over prior history (recent_results) + this round's own results.
        peak: dict = {}
        def _bump(pid, score):
            if pid is not None and score is not None and (pid not in peak or score > peak[pid]):
                peak[pid] = score
        for r in getattr(round_start, "recent_results", None) or []:
            _bump(r.policy_version_id, r.score)
        for div_ranking in complete.results:
            for entry in div_ranking.rankings:
                _bump(entry.policy_version_id, entry.score)
        # Rewrite each ranking to its peak, then re-rank within each division (stable tie-break).
        for div_ranking in complete.results:
            for entry in div_ranking.rankings:
                if entry.policy_version_id in peak:
                    entry.score = peak[entry.policy_version_id]
            div_ranking.rankings.sort(key=lambda e: (-e.score, str(e.player_id or ""), str(e.policy_version_id)))
            for i, entry in enumerate(div_ranking.rankings, start=1):
                entry.rank = i
        return complete

    # ── ALL-TIME-HIGH STANDING via rank_division (the scheduling-refresh path) ─────────────────
    # The platform ALSO refreshes the board from rank_division on the scheduling pass (pipeline.py
    # L493, over the full completed-round history). We override it too so BOTH writers agree on the
    # peak — otherwise whichever ran last would flip the board between peak and per-round. Same peak
    # logic as complete_round_for_round_start above, over the richer ctx.round_results (with metadata).
    def rank_division(self, ctx) -> list:
        base = super().rank_division(ctx)
        if not base:
            return base
        # Compute each player's peak over the SAME rounds the base counted: apply the config's
        # filter_metadata (e.g. score_kind==mean_round_score, so a later round_score switch doesn't
        # mix scales) and skip rounds flagged with a non-positive ranked-score count (non-scoring fills).
        from commissioners.common.commissioners import RANKED_SCORE_COUNT_METADATA_KEY
        filter_metadata = self._config().ranking.filter_metadata or {}
        peak: dict = {}
        for r in ctx.round_results:
            if not all(r.result_metadata.get(k) == v for k, v in filter_metadata.items()):
                continue
            if int(r.result_metadata.get(RANKED_SCORE_COUNT_METADATA_KEY, 1)) <= 0:
                continue
            if r.player_id not in peak or r.score > peak[r.player_id]:
                peak[r.player_id] = r.score
        # Re-score each snapshot to its peak, then re-rank by it (stable tie-break on name/id, as base).
        for snap in base:
            snap.score = peak.get(snap.player_id, snap.score)
        base.sort(key=lambda s: (-s.score, s.player_name or "", str(s.player_id)))
        for i, snap in enumerate(base, start=1):
            snap.rank = i
        return base


register_commissioner("muster", MusterCommissioner)
