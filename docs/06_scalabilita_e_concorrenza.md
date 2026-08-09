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

## Sicurezza del trasporto e priorità medica

Il limite di 2 appena descritto riguarda gli **operatori** presenti in una
stanza. La Treatment Room applica inoltre un vincolo separato: sul tavolo
possono esserci al massimo 3 animali.

Prima di prelevare un animale malato, l'Environment prenota uno dei tre posti.
La prenotazione resta occupata durante il viaggio di andata e fino all'inizio
del viaggio di ritorno. Se non ci sono posti disponibili, il Logistics non
preleva l'animale: lo lascia nella gabbia, attende e riprova.

Ogni Logistics dispone anche di un blocco di trasporto personale. Di
conseguenza può completare una sola sequenza di movimento alla volta e non può
mai avere più di un animale in carico. L'Environment verifica nuovamente questo
vincolo prima di ogni prelievo, così un errore dell'agente non può corrompere lo
stato del mondo.

Quando il Logistics deposita il paziente nella Treatment Room, invia il
messaggio `patient_ready` al Veterinary assegnato. Il piano BDI del Veterinary
si attiva automaticamente, preleva il medicinale e cura quel paziente. Dopo la
cura viene richiesta la restituzione alla gabbia. I trasporti di ritorno hanno
priorità sui nuovi prelievi: liberano un posto e permettono al primo paziente in
attesa di partire.

```text
posto libero → prelievo singolo → arrivo → cura automatica
            → rientro prioritario → posto liberato → prossimo paziente
```

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
- nessun Logistics con più di 1 animale trasportato;
- massimo 3 animali nella Treatment Room, inclusi i posti prenotati;
- attivazione automatica del Veterinary all'arrivo del paziente;
- priorità ai rientri per liberare la Treatment Room;
- tutte le aree rilasciate al termine;
- tutti gli animali sani nelle proprie gabbie e tutte le ciotole piene.
