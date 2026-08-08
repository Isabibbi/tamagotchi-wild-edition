# Fasi 4 e 5 — Scalabilità e concorrenza

## Stato

**Completate.** Il programma esegue un'unica simulazione nella quale
alimentazione e cure mediche partono insieme.

## Configurazione degli agenti

Il numero di operatori viene deciso a runtime con tre parametri:

```text
--veterinary-agents N
--logistics-agents N
--feeding-agents N
```

Ogni ruolo richiede almeno un agente e la somma non può superare 7.
L'Environment Agent è infrastruttura tecnica e non viene contato nel limite.
La configurazione predefinita è `2 Veterinary + 3 Logistics + 2 Feeding`.

Ogni istanza usa un JID distinto, per esempio `feeding_01@localhost` e
`feeding_02@localhost`.

## Assegnazione univoca

I task vengono distribuiti round-robin tra gli agenti del ruolo corretto. Ogni
assegnatario deve comunque reclamare atomicamente la fase presso l'Environment,
che impedisce a un altro agente di eseguire lo stesso lavoro.

Le fasi reclamabili sono:

| Fase | Ruolo ammesso |
|---|---|
| `feeding_coordination` | Logistics |
| `feeding_execution` | Feeding |
| `medical_coordination` | Veterinary |
| `transport_outbound` | Logistics |
| `transport_return` | Logistics |

Un nuovo tentativo dello stesso assegnatario è idempotente. Un altro agente non
può sottrargli la fase. Questo impedisce consumi doppi di cibo o medicinali e
trasporti duplicati, mentre il round-robin utilizza realmente l'intero gruppo.

## Accesso concorrente alle aree

Prima di agire, un operatore invia `acquire_area` all'Environment. L'accesso è
concesso soltanto se nella stanza sono presenti meno di 2 operatori attivi.
Quando la capienza è raggiunta, l'agente attende brevemente e riprova fino al
timeout. Al termine invia sempre `release_area`.

La sequenza è:

```text
richiesta accesso → attesa eventuale → ingresso → azione → rilascio
```

L'Environment elabora le richieste una alla volta: controllo e aggiornamento
dell'occupazione sono quindi atomici. Lo snapshot espone occupanti correnti,
capienza e massimo osservato per consentire test e futura visualizzazione.

## Simulazione integrata

Per ogni animale vengono create due attività distinte:

- ciotola vuota, destinata ai Logistics;
- animale malato, destinato ai Veterinary.

Tutte le percezioni vengono pubblicate insieme con `asyncio.gather`. Da quel
momento i workflow BDI avanzano indipendentemente e possono contendere le stesse
aree. La simulazione termina soltanto quando tutti i task risultano conclusi.

## Criteri verificati

- massimo 7 operatori configurabili, oltre a Environment;
- da 1 a 40 animali configurabili con gabbie, ciotole e task dedicati;
- entrambi i workflow nella stessa esecuzione;
- una sola assegnazione vincente per ogni fase;
- nessuna area oltre 2 accessi simultanei;
- tutte le aree rilasciate al termine;
- tutti gli animali sani nelle proprie gabbie e tutte le ciotole piene.
