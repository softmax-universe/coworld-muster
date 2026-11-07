# coworld-muster

Public **source mirror** of the league commissioner for the **Muster** coworld
(a spectator hex-RTS on the Softmax Observatory).

This repository exists so Muster's coworld manifest can declare a **public**
`commissioner.source_url` that the hosted certifier can resolve. The Muster game
engine and RL/LM policy source live in the private `softmax-universe/muster` repo; only
the commissioner — which already ships as a public running image — is mirrored here.

- `coworld_pkg/commissioner/` — the custom `MusterCommissioner`
  (`ruleset_strategy` subclass: tiny `qualifier` variant for staging, full `default`
  variant for competition).
- `Dockerfile` — builds the commissioner image (upstream `commissioners-default`
  base + the baked `muster-commissioner.yaml`).

Authoritative source: `softmax-universe/muster` `coworld_pkg/commissioner/`.
