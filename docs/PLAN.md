# Development Plan — Police Agent

Incremental build order (per [CLAUDE.md](../CLAUDE.md)). Each step must be
implemented, tested,
and verified against the specification before moving to the next. This repo
builds the **police** agent only; the thief is a separate repository.

1. **Project setup** — `uv` project, Ruff/pytest/coverage config, package
   skeleton, config separation. *(done)*
2. **Core game/domain rules** — board geometry, actions, movement, barriers,
   scoring (spec ch. 1, 3). *(done)*
3. **Local playable simulation** — drive the police through a scripted match
   against a test double standing in for the thief. Real two-agent play is
   step 4: ch. 2.4.2 requires the thief to be a *separate process from a
   separate repository*, never an in-process object.
4. P2P/FastMCP communication — real two-process peer connection (spec ch. 2).
5. Commit-reveal/security — signed moves, SHA-256, nonce anti-replay, and the
   end-of-game audit that re-verifies the thief's revealed log (spec ch. 5).
6. Scent and belief system — pheromone emission/decay, Bayesian belief map
   (spec ch. 4, 6).
7. Police strategy — decoupled from the rules engine (spec ch. 6).
8. GUI, replay, and reporting — live heatmap, replay viewer, mandatory Gmail
   report (spec ch. 7, 9).
9. Final integration and interoperability testing — league play against another
   group's thief implementation.

Do not implement future steps ahead of schedule.

## Submission mechanics (Appendix ג)

- Develop each capability on a dedicated branch; merge to the main branch only
  once it is stable.
- Pin the final submission with an annotated tag:
  `git tag -a v1.0-submission -m "Final submission: Police-Thief P2P, group N"`.
- Both repositories must be accessible to the grader, and each README must
  cross-link to the other.
