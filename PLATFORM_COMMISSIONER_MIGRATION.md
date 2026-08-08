# Platform commissioner migration

This repository is the public source mirror for Muster's container commissioner.
The authoritative migration design lives in the private `Metta-AI/muster`
repository. The live league is `league_d0f34381-669e-4f6a-9e7a-28ab16ce42e3`;
Competition is `div_26f94a2e-a2db-4003-8161-da4e2cb28fe9`.

The target is the shared platform commissioner with:

- `scaling_roster`, rungs 2/4/8/16/32/64, and no run below two champions;
- every champion seated in one engine-padded world, three episodes per round;
- `score` ranking, max within a round and max across rounds.

Do not retire this mirror merely because the target settings document exists.
Retirement is gated on all of the following:

1. Metta's `scaling_roster` and score/max implementation has replay-idempotency
   tests and parity fixtures against the authoritative `MusterCommissioner`.
2. The live seed owns the League with `commissioner_key: platform`, the ladder
   is enabled, and several Temporal cycles have settled results, replays, and
   all-time-high standings correctly.
3. Rollback no longer needs this image in any deployed environment or pinned
   Coworld version.
4. The authoritative private source removes its mirrored commissioner in the
   same cleanup window.

Until those gates pass, changes to `muster-commissioner.yaml` and
`coworld_pkg/commissioner/` must continue to originate in the private repo and
be mirrored here. The production ownership cutover, image deletion, repository
archival, and manifest removal are separate explicitly authorized operations;
this documentation PR performs none of them.
