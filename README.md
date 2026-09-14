# Tamagotchi Wild Edition: Multi-Agent Care for Virtual Pets

Educational multi-agent system for the automated management of a Wildlife Rescue Center (CRAS), inspired by volunteer experience at ENPA.

> **Status:** Feeding routines and medical care workflows are integrated into a single SPADE-BDI simulation. The number of operators is configured at startup, up to a maximum of 7; the Environment Agent is additional and does not count toward this limit. Each operational area admits at most 2 operators simultaneously. The number of animals is also configurable (from 1 to 40): each animal automatically generates a cage, a bowl, a feeding task, and a medical task. A live web GUI featuring an illustrated floor plan and real-time SPADE event timeline is available.

---

## Agents

| Agent | Responsibility |
|---|---|
| **Veterinary** | Deliberates medical cycles, collects medicine from storage, and treats the patient |
| **Logistics** | Transports animals and coordinates bowl replenishment |
| **Feeding** | Collects food and refills bowls |
| **Environment** | Maintains authoritative ground truth, atomically assigns tasks, and enforces area capacities |
| **Visualization** | Receives state snapshots from the Environment via SPADE/XMPP and delivers them to the GUI |

The default baseline simulation starts simultaneously:

```text
2 Veterinary + 3 Logistics + 2 Feeding = 7 operators
1 additional Environment Agent = 8 active SPADE agents
With GUI: 1 additional Visualization Agent = 9 active SPADE agents
```

Feeding and medical care are not mutually exclusive modes: both workflows run concurrently within the same execution through SPADE/XMPP message exchanges.

---

## Concurrency and Mutual Exclusion

- **Atomic Task Claim:** Each work phase is atomically reserved by a single agent via the Environment; duplicate claims by other operators of the same role are rejected.
- **Operator Availability:** Feeding operators handle one task at a time; subsequent requests remain queued until an operator becomes free.
- **Area Semaphores:** Entering an operational area requires Environment authorization. If an area already holds 2 occupants, the requesting agent enters a non-blocking retry loop (`await asyncio.sleep(0.05)`) until a slot is freed upon `RELEASE_AREA`.
- **Global Area Capacity Limit:** The limit of 2 concurrent operators applies strictly to Food Storage, Medical Storage, Cage Area, and Treatment Room.
- **Carrying Capacity:** Each Logistics agent can transport only one animal at a time.
- **Clinical Table Capacity:** The Treatment Room can hold a maximum of 3 patients simultaneously on the examination table.
- **Precondition & Staging:** Treatment spots are reserved prior to picking up the animal from its cage. If all 3 table spots are occupied, the patient remains safely inside its cage.
- **Workflow Coordination:** When a patient is delivered to the examination table, the `patient_ready` message immediately activates the assigned Veterinary agent. Return transports are prioritized over new departures from cages.

---

## Running the Simulation

From the project root (using your Python environment):

```powershell
python -m tamagotchi_wild
```
*(Or with the local virtual environment: `& .\.my_sdai\Scripts\python.exe -m tamagotchi_wild`)*

### Expected Terminal Summary:

```text
SIMULATION OK
operators=7 veterinary=2 logistics=3 feeding=2
animals=5 cages=5 bowls=5
feeding=5/5 medical=5/5 healthy=5/5
max-room-occupancy=2/2
max-treatment-patients=3/3 max-carried-per-logistics=1/1
```

The maximum observed room occupancy will be `1` or `2`, depending on message arrival order. It will never exceed `2`.

---

## Runtime Configuration

### Graphical Mode (NiceGUI Dashboard)

To observe the simulation live in your browser, launch with the `--gui` flag:

```powershell
python -m tamagotchi_wild --gui --animals 5
```

The browser automatically opens the local dashboard at `http://127.0.0.1:8080`, displaying:

- **Interactive Floor Plan:** An illustrated SVG map of the CRAS showing the four operational rooms, cages, animals, food bowls, and the examination table.
- **Active Staff Avatars:** Visual avatars representing veterinarians, logistics operators, and feeding staff, color-coded and animated as they move between rooms.
- **Area Capacity Monitors:** Real-time occupancy indicators showing current vs. maximum capacity (e.g., `2/2` with alerts upon saturation).
- **Resource Counters & Metrics:** Instant inventory levels for food stocks and medical supplies, along with total completed tasks and healthy animals.
- **Live Event Timeline:** Chronological event log showing physical actions approved or rejected by the Environment (`#001`, `#002`), along with internal agent communications (prefixed with `↳`).

Graphical updates do not access simulation state directly: the Environment Agent publishes JSON frames over the `cras.visualization` ontology to the `VisualizationAgent`. A dedicated, authenticated inter-process channel (`gui_bridge.py`) forwards frames to the web server without slowing down agent execution loops.

### Command-Line Arguments

Example running 5 animals with a custom staff allocation:

```powershell
python -m tamagotchi_wild `
  --veterinary-agents 2 `
  --logistics-agents 3 `
  --feeding-agents 2 `
  --animals 5
```

Each role requires at least 1 agent. The total sum of operators must not exceed 7.

With `--animals 5`, the system generates:
- 5 animals with randomized health states
- 5 cages in the Cage Area
- 5 bowls
- 5 Feeding tasks
- 5 Medical tasks

#### Available Flags:

```text
--animals N          Number of animals (1 to 40, default: 5)
--veterinary-agents  Number of veterinarians (default: 2)
--logistics-agents   Number of logistics operators (default: 3)
--feeding-agents     Number of feeding operators (default: 2)
--food N             Initial food units (default: equal to animal count)
--medicine N         Initial medicine units (default: equal to animal count)
--timeout N          Simulation timeout in seconds (default: 60.0)
--gui                Opens the real-time web dashboard
--gui-delay N        Seconds between GUI frame updates (default: 0.20)
--gui-port N         Local web server port (default: 8080)
--gui-no-browser     Starts the GUI web server without automatically opening the browser
--json               Exports structured task execution results as JSON to stdout
```

---

## Project Structure

```text
src/tamagotchi_wild/
├── agents/          # SPADE-BDI roles, EnvironmentAgent, and VisualizationAgent
├── bdi/             # AgentSpeak (.asl) cognitive decision plans
├── domain/          # Core entities, action models, and domain rules
├── environment/     # Authoritative world state, atomic claims, and area capacities
├── visualization/   # Read-only state projection, SVG rendering, and event timeline
├── config.py        # Environment geometry, thresholds, and simulation parameters
├── gui.py           # NiceGUI dashboard pages and interface components
├── gui_bridge.py    # Authenticated inter-process channel (NiceGUI ↔ SPADE)
├── messaging.py     # FIPA metadata, ontologies, and typed JSON message contracts
├── observability.py # Activity logger and event metrics
├── simulation.py    # Integrated simulation runner and orchestration
└── __main__.py      # CLI entry point and argument parsing
```
