# Tamagotchi Wild Edition: Multi-Agent Care for Virtual Pets

An educational multi-agent system for the automated management of a **Wildlife Rescue Center (CRAS)**, inspired by direct volunteering experience with ENPA.

> **Project status:** Phase 2 feeding workflow implemented. Logistics and Feeding are SPADE-BDI agents with AgentSpeak plans; they cooperate through the embedded XMPP server and update the authoritative environment through correlated FIPA/JSON messages.

## Overview

The project models a rescue center as a 2D grid divided into four operational areas:

- **Cage Area** — houses rescued animals and their food bowls.
- **Treatment Room** — supports medical examinations and treatments.
- **Food Storage** — stores food collected by feeding staff.
- **Medical Storage** — stores medicines collected by veterinarians.

Animals are passive resources whose position and condition are changed by autonomous agents. The system is designed for multiple agents of each role and will be developed incrementally, starting with the feeding workflow.

## Agent roles

| Agent | Responsibility | Main interactions |
|---|---|---|
| **Veterinary Agent** | Evaluates and treats sick animals | Requests transport from Logistics; uses the Treatment Room and Medical Storage |
| **Logistics Agent** | Moves animals and coordinates operational tasks | Transfers animals between cages and treatment; requests bowl refilling from Feeding |
| **Feeding Agent** | Replenishes food bowls | Collects food from Food Storage and delivers it to the Cage Area |

## Main workflows

1. **Feeding:** Logistics detects an empty bowl and requests support from a Feeding Agent.
2. **Medical care:** Veterinary requests an animal transfer, treats the patient, and requests transport back to its cage.
3. **Concurrency control (advanced objective):** shared areas enforce capacity constraints, such as a maximum of two agents at the same time.

## Technology direction

- **Python** as the implementation language.
- **SPADE** for agent lifecycle, asynchronous behaviours, and XMPP communication.
- **SPADE-BDI** for symbolic Belief–Desire–Intention reasoning with AgentSpeak plans.
- A Python 2D visualization library, such as **Pygame** or **Mesa**, to be selected during implementation.
- A local XMPP setup so the complete project can be run and tested on the development PC.

## Development roadmap

1. ~~Define the architecture and model the 2D environment.~~ **Completed.**
2. ~~Implement the feeding workflow to validate agent cooperation.~~ **Completed.**
3. Add animal transport and healthcare workflows.
4. Scale to multiple agents per role.
5. Add concurrency policies for shared operational areas.

## Repository structure

```text
.
├── docs/                    # Architecture, workflows, and project notes
├── src/tamagotchi_wild/
│   ├── agents/              # SPADE adapters
│   ├── bdi/                 # AgentSpeak plans added with role workflows
│   ├── domain/              # Pure domain entities and action contracts
│   ├── environment/         # Authoritative grid state and atomic actions
│   ├── messaging/           # Versioned JSON/FIPA contracts
│   └── visualization/       # Read-only state projection for a future GUI
├── tests/
│   ├── unit/                # Domain, environment, messages and projection
│   ├── integration/         # Boundaries between messages and environment
│   └── scenarios/           # End-to-end workflows added incrementally
├── pyproject.toml           # Package metadata and pinned direct dependencies
├── .gitignore               # Local and generated files excluded from Git
└── README.md                # Project overview
```

## Documentation

- [Where to start and how to organize the work](docs/00_da_dove_partire.md)
- [Proposed architecture](docs/01_architettura_proposta.md)
- [Incremental roadmap](docs/02_roadmap_incrementale.md)
- [First increment: feeding workflow](docs/03_primo_incremento_alimentazione.md)
- [Testing strategy](docs/04_strategia_test.md)
- [Agent architecture and workflows](docs/schemi_agenti_flussi.md)
- [Project development guidelines](docs/linee_guida_progetto.md)

## Running the project

From PowerShell, install the project in the existing local environment and run the feeding workflow:

```powershell
py -3.12 -m venv .my_sdai
& .\.my_sdai\Scripts\python.exe -m pip install -e ".[dev]"
& .\.my_sdai\Scripts\python.exe -m tamagotchi_wild
```

Expected result:

```text
task=task_001 agent=logistics_01 event=feeding_requested cage=cage_01
task=task_001 agent=feeding_01 event=task_accepted
task=task_001 agent=environment event=food_taken quantity=1
task=task_001 agent=environment event=bowl_filled cage=cage_01
task=task_001 agent=feeding_01 event=task_completed
PHASE 2 OK
task=task_001 status=completed
food=2->1 bowl=1/1
messages=8 conversation-id=task_001
```

Run all automated tests with:

```powershell
& .\.my_sdai\Scripts\python.exe -m pytest
```

The command starts and stops SPADE's embedded XMPP server automatically. The local agent accounts are registered for the duration of the scenario; no Internet access or external credentials are required.

To verify the explicit failure path with an empty Food Storage:

```powershell
& .\.my_sdai\Scripts\python.exe -m tamagotchi_wild --food 0
```
