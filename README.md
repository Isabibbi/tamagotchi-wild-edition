# Tamagotchi Wild Edition: Multi-Agent Care for Virtual Pets

An educational multi-agent system for the automated management of a **Wildlife Rescue Center (CRAS)**, inspired by direct volunteering experience with ENPA.

> **Project status:** architecture and documentation phase. The executable implementation has not started yet.

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
├── src/                     # Application source code (future)
├── tests/                   # Automated tests (future)
├── .gitignore               # Local and generated files excluded from Git
└── README.md                # Project overview
```

## Documentation

- [Agent architecture and workflows](docs/schemi_agenti_flussi.md)
- [Project development guidelines](docs/linee_guida_progetto.md)

## Running the project

There is no executable application yet. Runtime setup, dependency installation, and test commands will be added with the first implementation increment. Development will remain local-first so each increment can be executed and verified on the target Windows PC.
