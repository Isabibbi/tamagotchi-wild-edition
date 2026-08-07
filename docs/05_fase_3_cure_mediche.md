# Fase 3: cure mediche

## Stato

**Completata e testata.** Lo scenario usa Veterinary, Logistics ed Environment
su SPADE/XMPP con `conversation-id = medical_001` per l'intero ciclo.

## Stato iniziale e finale

| Elemento | Iniziale | Finale |
|---|---|---|
| Animale | `sick`, nella Cage Area | `healthy`, di nuovo nella Cage Area |
| Medicinale | 1 dose | 0 dosi |
| Task | `pending` | `completed` |
| Trasporto | Nessun vettore | Nessun vettore (`carried_by = null`) |

## Transizioni controllate

```text
sick
  → in_outbound_transport
  → in_treatment
  → treated
  → in_return_transport
  → healthy
```

L'Environment verifica ruolo dell'agente, area, posizione, stato precedente,
medicinale disponibile, corrispondenza del task e idempotenza della richiesta.

## Responsabilità

| Componente | Responsabilità |
|---|---|
| Veterinary BDI | Rileva il malato, richiede trasporti, preleva medicina e cura |
| Logistics BDI | Preleva, consegna in Treatment Room e riporta in gabbia |
| Environment | Applica tutte le transizioni e aggiorna task e scorte |

## Comandi

Scenario completo:

```powershell
.\.my_sdai\Scripts\python.exe -m tamagotchi_wild
```

Fallimento controllato senza medicinali:

```powershell
.\.my_sdai\Scripts\python.exe -m tamagotchi_wild --medicine 0
```

Test dedicati:

```powershell
.\.my_sdai\Scripts\python.exe -m pytest tests/unit/test_medical_actions.py
.\.my_sdai\Scripts\python.exe -m pytest tests/scenarios/test_medical_workflow.py
```

## Fuori scope

Non sono stati aggiunti più agenti dello stesso ruolo, lock di capacità,
pathfinding o GUI. Questi aspetti appartengono alle fasi avanzate della roadmap.
