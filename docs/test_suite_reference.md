# Riferimento alla suite di test

Questo documento descrive tutti i file di test che facevano parte del progetto,
eliminati in seguito perché non necessari al runtime.
Serve come memoria storica: cosa veniva verificato, perché, e con quale logica.

---

## Struttura originale

```
tests/
├── unit/               ← test veloci, logica isolata, nessun SPADE
│   ├── test_environment_state.py
│   ├── test_feeding_actions.py
│   ├── test_feeding_agent_queue.py
│   ├── test_medical_actions.py
│   ├── test_medical_messages.py
│   ├── test_message_contracts.py
│   ├── test_nicegui_view.py
│   ├── test_scalability_and_concurrency.py
│   ├── test_visualization_messages.py
│   └── test_visualization_projection.py
├── integration/        ← test che attraversano il confine domain → messaging
│   └── test_environment_request.py
├── scenarios/          ← test end-to-end con SPADE reale (lenti, ~2 min)
│   ├── test_integrated_simulation.py
│   └── test_visualization_spade_stream.py
└── smoke/              ← cartella vuota (riservata a futuri smoke test)
```

---

## Unit tests

### `test_environment_state.py`

**Cosa testa:** lo stato interno del mondo (griglia 12×8).

| Test | Cosa verifica |
|---|---|
| `test_default_grid_is_partitioned_into_four_areas` | Il mondo di default ha esattamente 4 aree (food storage, medical storage, cage area, treatment room) che coprono tutte le 96 celle della griglia |
| `test_valid_move_changes_state_and_records_event` | Un agente logistics può spostarsi da (2,4) a (8,4): la posizione viene aggiornata e l'evento viene registrato con l'origine corretta |
| `test_invalid_move_is_rejected_without_changing_state` | Un movimento fuori griglia (posizione negativa) viene rifiutato, lo stato non cambia e nessun evento viene generato |
| `test_entity_identifiers_are_unique_across_categories` | Se si prova a registrare un animale con lo stesso ID di un agente già esistente, il mondo lancia `DuplicateEntityError` |
| `test_health_update_is_an_explicit_environment_action` | Il veterinario può cambiare la salute di un animale tramite `UPDATE_ANIMAL_HEALTH`; la modifica si riflette nello snapshot |

---

### `test_feeding_actions.py`

**Cosa testa:** il ciclo completo di alimentazione a livello di dominio (senza SPADE).

| Test | Cosa verifica |
|---|---|
| `test_take_food_decrements_stock_and_starts_task` | `TAKE_FOOD` scala lo stock di 1 e porta il task in stato `IN_PROGRESS` assegnato all'agente |
| `test_fill_bowl_completes_task_after_food_was_taken` | Dopo `TAKE_FOOD`, `FILL_BOWL` porta la ciotola a capacità massima e il task in `COMPLETED` |
| `test_duplicate_take_food_is_idempotent` | Se lo stesso `TAKE_FOOD` arriva due volte (retry SPADE), il secondo viene accettato con `reason="already_applied"` ma non scala di nuovo lo stock e non genera un secondo evento |
| `test_take_food_fails_cleanly_when_storage_is_empty` | Con stock a 0, `TAKE_FOOD` viene rifiutato con `"not enough food"`, il task resta `PENDING` |
| `test_fill_bowl_requires_food_taken_for_the_same_task` | Non si può riempire una ciotola se il cibo non è stato prelevato per lo stesso `task_id`; la bowl resta vuota |

---

### `test_feeding_agent_queue.py`

**Cosa testa:** la coda interna del `FeedingAgent` (un task alla volta).

| Test | Cosa verifica |
|---|---|
| `test_feeding_agent_starts_only_one_task_at_a_time` | Se un secondo task arriva mentre il primo è in corso, viene messo in attesa sull'`asyncio.Lock`. Quando il primo finisce, il secondo parte e viene registrato nel log con `event=feeding_task_waiting` |

**Perché è importante:** garantisce che un singolo feeding agent non esegua mai due task in parallelo, prevenendo race condition sullo stock.

---

### `test_medical_actions.py`

**Cosa testa:** l'intero ciclo medico (pickup → trasporto → cura → ritorno) a livello di dominio.

| Test | Cosa verifica |
|---|---|
| `test_complete_medical_lifecycle_returns_healthy_animal_to_cage` | Sequenza completa: pickup dalla gabbia → consegna in treatment room → presa medicina → cura → pickup post-cura → ritorno in gabbia. Alla fine l'animale è `HEALTHY`, a casa, non trasportato, e la medicina è consumata |
| `test_treatment_requires_medicine_taken_for_same_task` | Il vet non può curare se prima non ha prelevato la medicina per lo stesso `task_id` |
| `test_duplicate_pickup_does_not_repeat_transition` | Un `PICKUP_SICK_ANIMAL` duplicato è idempotente: accettato con `"already_applied"` ma l'animale non cambia stato di nuovo |
| `test_take_medicine_fails_without_stock_and_changes_nothing` | Con stock medicine a 0, `TAKE_MEDICINE` fallisce, nessun evento generato |
| `test_logistics_cannot_pick_up_a_second_animal_while_carrying_one` | Un agente logistics non può portare due animali contemporaneamente; il secondo pickup viene rifiutato con `"already carries animal"` |
| `test_fourth_patient_waits_in_cage_until_a_treatment_slot_is_freed` | La treatment room ha 3 slot: il 4° paziente non può essere portato finché uno slot non si libera (dopo cura + pickup post-cura del 1° paziente) |

---

### `test_medical_messages.py`

**Cosa testa:** la serializzazione/deserializzazione dei messaggi FIPA usati nel flusso medico.

| Test | Cosa verifica |
|---|---|
| `test_sick_animal_perception_round_trip` | `SickAnimalPerception` → JSON → `SickAnimalPerception` produce un oggetto uguale all'originale |
| `test_transport_request_round_trip` (OUTBOUND/RETURN) | `TransportRequest` con direzione outbound o return sopravvive al round-trip JSON |
| `test_transport_status_rejects_unknown_state` | Se arriva un JSON con stato `"teleported"` (non valido), viene lanciato `MessageContractError` con il messaggio corretto |

---

### `test_message_contracts.py`

**Cosa testa:** i contratti di messaggi che gli agenti si scambiano con l'environment agent.

| Test | Cosa verifica |
|---|---|
| `test_action_request_round_trip_preserves_typed_data` | Un `ActionRequest` con `MOVE_AGENT` e `Position(8,4)` sopravvive al round-trip JSON, inclusa la `Position` tipizzata |
| `test_unknown_schema_version_is_rejected` | Un payload con `schema_version=99` viene rifiutato con errore che menziona `schema_version` |
| `test_metadata_contains_fipa_routing_and_correlation` | `request_metadata("task-001")` produce esattamente i 4 campi FIPA: `performative`, `ontology`, `language`, `conversation-id` |

---

### `test_nicegui_view.py`

**Cosa testa:** il rendering della GUI (SVG planimetria, roster operatori, metriche, CSS).

| Test | Cosa verifica |
|---|---|
| `test_floorplan_shows_rooms_cages_and_all_humanoid_operators` | L'SVG contiene tutti e 3 gli agenti per ID, le 4 stanze etichettate, le gabbie, le sagome umane con animazione `animateTransform` |
| `test_roster_metrics_and_capacity_remain_visible` | Con 2 animali: `animal_count==2`, 3 chip "idle" nel roster, treatment room "Patients 0/3" |
| `test_operator_status_colors_free_busy_waiting` | `_operator_status()` restituisce verde per free, rosso per busy, grigio per waiting |
| `test_full_bowl_is_drawn_as_a_labelled_bowl_with_food` | Ciotola piena → `data-state="full"` e `aria-label="Bowl full"` nell'SVG |
| `test_timeline_wraps_long_events_instead_of_cutting_them` | Il CSS usa `white-space: normal` e `overflow-wrap: anywhere` (no troncamento dei testi lunghi) |
| `test_cli_exposes_nicegui_port_and_browser_control` | `--gui-port 8090` e `--gui-no-browser` sono argomenti CLI validi e tipizzati |
| `test_floorplan_scales_to_forty_distinct_cages` | Con 40 animali, l'SVG contiene esattamente 40 gabbie con `data-cage-id="cage_40"` |

---

### `test_scalability_and_concurrency.py`

**Cosa testa:** configurazione del pool di agenti, limiti di sistema, concorrenza sulle stanze.

| Test | Cosa verifica |
|---|---|
| `test_default_configuration_runs_seven_operational_agents` | `SimulationConfig()` di default → 7 operatori (2 vet + 3 logistics + 2 feeding) |
| `test_runtime_configuration_allows_fifteen_agents` | 5+5+5 agenti → 15 totali, accettato |
| `test_runtime_configuration_rejects_more_than_fifteen_agents` | 5+6+5 → 16 totali, `ValueError("at most 15")` |
| `test_runtime_configuration_builds_the_requested_agent_pool` | Con 1+2+1 agenti, gli IDs nel mondo sono ordinati correttamente |
| `test_environment_builds_with_ten_and_fifteen_agents` | 10 e 15 agenti costruiti correttamente |
| `test_five_animals_create_five_complete_and_distinct_cases` | 5 animali → 10 task (5 feeding + 5 medical), 5 specie univoche, tutte le gabbie in `CAGE_AREA` |
| `test_runtime_configuration_rejects_more_animals_than_cage_cells` | 41 animali → `ValueError("between 1 and 40")` |
| `test_task_phase_is_claimed_by_exactly_one_agent` | Due agenti competono per lo stesso task: il primo vince, il secondo è rifiutato con il nome del vincitore |
| `test_third_agent_cannot_enter_a_room_until_a_place_is_released` | Treatment room capacity=2: il 3° logistics è bloccato finché il 1° non esce |
| `test_agent_waits_and_retries_when_a_room_is_full` | `acquire_area` riprova automaticamente 3 volte prima di riuscire (monkeypatch) |

---

### `test_visualization_messages.py`

**Cosa testa:** la traduzione degli eventi tecnici in testo leggibile nella Live Timeline.

| Test | Cosa verifica |
|---|---|
| `test_visualization_update_round_trip_contains_complete_world` | `VisualizationUpdate` con 2 animali sopravvive al round-trip JSON con tutti i campi |
| `test_rejected_area_access_becomes_a_readable_wait_event` | Blocco su treatment room → testo "The treatment room is at full capacity. Logistics operator 3 tries to enter but must wait." |
| `test_rejected_cage_access_explains_the_attempt_and_the_reason` | Blocco su cage-area → testo con numero sequenza e nome stanza leggibile |
| `test_other_temporary_blocks_are_explained_clearly` | Stanza piena di pazienti → "all 3 slots taken"; già porta animale → "already carrying another animal" |
| `test_identical_retries_produce_one_warning_until_the_action_succeeds` | Lo stesso blocco consecutivo genera 1 solo warning; si resetta dopo la pulizia |
| `test_environment_events_use_simple_italian_names` | `acquire_area` → "Feeding staff 2 enters into the food storage."; `deliver_to_treatment` → "Logistics operator 1 brings the animal 5 to the treatment room." |
| `test_agent_activities_explain_the_medical_flow_without_technical_words` | I testi della timeline non contengono parole interne come "task", "outbound", "medical_" |
| `test_waiting_feeding_task_explains_that_the_operator_is_busy` | `feeding_task_waiting` → "Feeding staff 1 is already filling another bowl: the request for bowl 5 is on hold." |
| `test_task_assignment_is_explained_without_internal_phase_names` | `claim_task` con target `medical_coordination` → "Vet 2 takes care of animal 5." |

---

### `test_visualization_projection.py`

**Cosa testa:** la proiezione della griglia per il rendering SVG.

| Test | Cosa verifica |
|---|---|
| `test_projection_contains_entities_without_exposing_world_mutation` | `project_grid()` produce 96 celle; la cella a (2,4) contiene correttamente `animal-001` e `cage-001` |

---

## Integration tests

### `test_environment_request.py`

**Cosa testa:** il confine tra messaggistica JSON e domain model.
Simula quello che fa `EnvironmentAgent` quando riceve un messaggio SPADE.

| Test | Cosa verifica |
|---|---|
| `test_json_request_reaches_authoritative_environment` | `ActionRequest` JSON con `MOVE_AGENT` → `process_action_request()` → agente spostato nel mondo |
| `test_invalid_json_is_rejected_without_an_event` | JSON malformato → `accepted=False`, `task_id="unknown"`, nessun evento nel mondo |
| `test_feeding_actions_are_applied_through_json_contracts` | Sequenza `acquire_area → take_food → release_area → acquire_area → fill_bowl` via JSON → stock scalato, bowl piena |

---

## Scenario tests

### `test_integrated_simulation.py`

**Cosa testa:** la simulazione completa end-to-end con SPADE reale.
Lancia il processo Python come sottoprocesso: `--json --animals 10 --timeout 120`.

**Cosa verifica:**
- 7 operatori + 1 env agent + 1 viz agent = 8 agenti SPADE totali
- 10/10 feeding task e 10/10 medical task completati
- Tutti e 10 gli animali `healthy` alla fine, stock esauriti
- Max 2 agenti in una stanza, max 3 pazienti in treatment, max 1 animale per logistics
- 50 task claim totali (5 fasi × 10 animali), 20 conversation ID univoci
- Nessun feeding agent gestisce 2 task contemporaneamente
- Almeno un evento `feeding_task_waiting` (la coda di attesa funziona)

### `test_visualization_spade_stream.py`

**Cosa testa:** che il `VisualizationAgent` riceva i frame live durante la simulazione.
Lancia un sottoprocesso che esegue `run_simulation()` con una `visualization_queue`.

**Cosa verifica:**
- `success=True` con 5 agenti SPADE (1+1+1+1 env+1 viz)
- Più di 10 frame ricevuti nella coda
- Il primo frame ha `action="initial_state"`, poi arrivano `fill_bowl`, `treat_animal`, `return_animal_to_cage`
- Alla fine: 1 animale `healthy`, 1 bowl piena

---

## Come rieseguire i test (se reintrodotti)

```bash
# Test unitari e di integrazione (~10 secondi)
.\.my_sdai\Scripts\python.exe -m pytest tests/unit tests/integration -v

# Scenario test end-to-end (~2-3 minuti, richiede SPADE)
.\.my_sdai\Scripts\python.exe -m pytest tests/scenarios -v -s
```
