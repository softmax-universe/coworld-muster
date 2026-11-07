# Platform commissioner migration

This repository is the public source mirror for Muster's container commissioner.
The authoritative migration design lives in the private `softmax-universe/muster`
repository. The live league is `league_d0f34381-669e-4f6a-9e7a-28ab16ce42e3`;
Competition is `div_26f94a2e-a2db-4003-8161-da4e2cb28fe9`.

The directly postable disabled settings are
[`platform_migration/ladder_settings.json`](platform_migration/ladder_settings.json).
Validate settings, rollback files, and pinned digests with:

```bash
python3 -m platform_migration.verify
```

When the private repository is available locally, also prove semantic source
and byte-for-byte config parity:

```bash
python3 -m platform_migration.verify --authoritative-root ../muster
```

The target is the shared platform commissioner with:

- `scaling_roster`, rungs 2/4/8/16/32/64, no run below two champions, and
  even partitioning above the 64-policy per-episode ceiling with one episode
  per overflow table;
- every champion seated in one engine-padded world while the field is at most
  64, with three episodes per round;
- `score` ranking, max within a round and max across rounds.

For overflow fields, each partitioned table runs once, matching the mirrored
container implementation. The three-episode best-of-N applies to the common
single-table field at or below 64 champions. Platform ownership also makes the
old one-seat Qualifiers commissioner unavailable; this target therefore admits
new submissions directly to Competition and archives Qualifiers only during the
authorized cutover.

Do not retire this mirror merely because the target settings document exists.
[`platform_migration/retirement_contract.json`](platform_migration/retirement_contract.json)
keeps the repository in `rollback_ready` and pins the rollback source/config.
Changing it to `retired` makes the verifier require those artifacts to be gone.
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
