# Tamagotchi Wild Edition: Multi-Agent Care for Virtual Pets

An educational multi-agent system for the automated management of a **Wildlife Rescue Center (CRAS)**, inspired by direct volunteering experience with ENPA.

> **Project status:** Phase 0 technical spike implemented. Two SPADE-BDI agents run locally and exchange a correlated message through SPADE's embedded XMPP server.

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

1. Model and visualize the 2D environment.
2. Implement the feeding workflow to validate agent cooperation.
3. Add animal transport and healthcare workflows.
4. Scale to multiple agents per role.
5. Add concurrency policies for shared operational areas.

## Repository structure

```text
.
├── docs/                    # Architecture, workflows, and project notes
├── src/tamagotchi_wild/     # Python package and AgentSpeak plans
├── tests/smoke/             # Local end-to-end compatibility test
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

The current executable is the Phase 0 compatibility spike. From PowerShell:

```powershell
py -3.12 -m venv .my_sdai
& .\.my_sdai\Scripts\python.exe -m pip install -e ".[dev]"
& .\.my_sdai\Scripts\python.exe -m tamagotchi_wild.spike
```

Expected result:

```text
PHASE 0 OK
BDI ready: requester=yes responder=yes
response_status=acknowledged
```

Run the automated smoke test with:

```powershell
& .\.my_sdai\Scripts\python.exe -m pytest
```

The spike starts and stops its own local XMPP server. It does not require Internet access, external accounts, or manually configured agent credentials at runtime.
