# CLAUDE.md

## Project Overview

This is a university final project implementing a distributed
**Police vs. Thief (Cops-and-Robbers) game over a Peer-to-Peer network**.

The system consists of two independent agents:

- Police
- Thief

Each agent runs as an independent process and eventually communicates
directly with the other peer.

**This repository is the POLICE agent only.**

The specification (ch. 2.4.2, ch. 9.4) requires the two agents to live in
two separate GitHub repositories and to run as two completely separate
processes. Sharing memory, importing a shared module that holds live
state, or reading shared variables between the two sides disqualifies the
solution even if the game technically works.

Consequences for work in this repo:

- do not add thief agent logic here;
- do not add a `config/thief/` directory here;
- rules the thief evaluates about itself (Appendix ה 46/47) are not
  computed here — the police receives them as signed claims and
  re-verifies them at the end-of-game audit;
- the thief is never an in-process object at runtime; for testing, use a
  test double under `tests/`.

The project includes several major areas:

- deterministic board and game rules;
- player movement;
- obstacles and Police barriers;
- capture and scoring rules;
- peer-to-peer communication using FastMCP;
- commit-reveal / verification mechanisms;
- partial observability;
- scent information;
- Bayesian belief maps;
- Police and Thief strategies;
- optional LLM/template-based language interaction;
- GUI / heatmap visualization;
- game logging and replay;
- reporting and interoperability with another student's implementation.

The game engine and authoritative movement/rules should be implemented
deterministically in Python.

Strategy should be separated from game rules.

The project should be developed incrementally:

1. Project setup
2. Core game/domain rules
3. Local playable simulation
4. P2P/FastMCP communication
5. Commit-reveal/security
6. Scent and belief system
7. Police/Thief strategies
8. GUI, replay and reporting
9. Final integration and interoperability testing

Do not attempt to implement the entire project at once.

For each development step:

- understand the requirement;
- inspect existing code;
- implement a small coherent feature;
- test it;
- verify existing functionality still works;
- then continue to the next feature.

---

## Official Specification

The official project specification is the source of truth.

When implementing a feature, always distinguish between:

1. what the specification requires;
2. what the reference repository does;
3. our own design/strategy decisions.

If the specification and reference implementation differ, follow the
official specification.

Do not invent important game/protocol rules when the specification is
unclear. Identify the ambiguity first.

---

## Reference Implementation

Use the following repository as an educational/reference implementation:

https://github.com/rmisegal/Game-P2P-Cop-Chase

You may inspect it to understand:

- project structure;
- architecture;
- board/game representation;
- FastMCP communication;
- peer orchestration;
- configuration;
- commit-reveal implementation;
- logging;
- replay;
- scent/belief representation;
- strategy interfaces;
- GUI organization;
- testing approaches.

The repository is a REFERENCE, not automatically the required design.

Do not blindly copy its implementation.

Before reusing or adapting an idea from it:

1. understand what the code does;
2. determine why it exists;
3. compare it with the official specification;
4. decide whether it fits our architecture;
5. implement/adapt it cleanly.

We may reuse useful architectural ideas and implementation approaches,
but our final system must satisfy the full project specification and
remain code that we understand and can explain.

In particular, do not assume the reference Police/Thief strategy is the
strategy we should submit. Strategy is an area we may design and improve
ourselves.

---

## Development Guidelines

Use:

- Python
- `uv` for project/dependency management
- `pytest` for testing
- `pytest-cov` for coverage
- Ruff for linting and formatting

Project requirements include:

- minimum 85% test coverage;
- zero Ruff violations;
- maximum 150 lines of code per Python source/test file;
- modular architecture sdk archetecture;
- no hardcoded secrets;
- meaningful tests for new functionality.

Keep game/domain logic independent from networking, GUI and LLM code.

Do not use an LLM as the authoritative game-rule or movement engine.

Do not expose an opponent's private true state to the other agent unless
the specification explicitly allows that information to be communicated.

---

## Working Rule

When given a task, work only on that task.

Before modifying an existing subsystem:

1. inspect the relevant implementation;
2. inspect its tests;
3. understand the current execution flow;
4. compare it with the specification;
5. make the smallest necessary change.

Do not automatically implement future parts of the project.

The goal is to build the system step-by-step so that every completed
stage is understandable, testable and working.
