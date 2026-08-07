# Roadmap incrementale

La roadmap è organizzata per risultati dimostrabili. Ogni fase deve lasciare il progetto avviabile e non deve dipendere da funzionalità previste nelle fasi successive.

## Sequenza consigliata

| Fase | Obiettivo | Risultato dimostrabile | Criterio di uscita |
|---|---|---|---|
| 0 — Spike tecnico archiviato | Validare SPADE-BDI e XMPP locale | La compatibilità è stata verificata; il codice temporaneo è stato rimosso | Decisioni consolidate nell'architettura |
| 1 — Dominio e ambiente ✅ | Creare una fonte unica dello stato | Azioni valide cambiano la griglia; azioni invalide sono rifiutate | Completata in Preview 01 con test unitari e di integrazione |
| 2 — Alimentazione ✅ | Completare la prima cooperazione | Logistics richiede e Feeding riempie una ciotola | Completata: scenario SPADE-BDI end-to-end verde |
| 3 — Cure mediche ✅ | Aggiungere trasporto e trattamento | Animale malato torna curato in gabbia | Completata: ciclo SPADE-BDI e transizioni verificati |
| 4 — Scalabilità | Avviare più agenti per ruolo | Un task viene eseguito una sola volta | Nessun task duplicato nei test concorrenti |
| 5 — Concorrenza | Applicare capacità alle aree | Gli agenti attendono senza violare i limiti | Test su capacità, timeout e rilascio risorse |
| 6 — Demo finale | Integrare GUI e osservabilità | Scenario completo visibile e riproducibile | Avvio documentato su PC pulito |

## Fase 0 — Spike tecnico

Durata indicativa: **mezza giornata**.

**Stato: archiviata.** La combinazione Python 3.12.4, SPADE 4.1.4 e SPADE-BDI 0.3.2 è stata validata sul PC di sviluppo. Lo spike era usa-e-getta ed è stato rimosso passando a Preview 01.

Produrre solo:

- ambiente Python riproducibile e dipendenze bloccate;
- due agenti BDI minimi con piani `.asl`;
- server XMPP integrato avviato dal progetto;
- un messaggio con metadata e risposta correlata;
- un test smoke eseguibile da terminale.

Se SPADE 4.1.x e SPADE-BDI 0.3.2 mostrano incompatibilità, fermarsi qui e fissare una coppia di versioni compatibili prima di procedere.

## Fase 1 — Dominio e ambiente

Durata indicativa: **1–2 giorni**.

**Stato: completata in Preview 01.**

Implementare prima regole pure, senza GUI:

1. coordinate, celle e quattro aree;
2. entità minime e identificativi univoci;
3. query dello stato e percezioni;
4. azioni con precondizioni ed effetti;
5. registro eventi utile a test e visualizzazione.

## Fase 2 — Alimentazione

Durata indicativa: **2–3 giorni**.

**Stato: completata.** Logistics, Feeding ed Environment comunicano realmente
tramite SPADE/XMPP; lo scenario positivo e quello senza cibo sono coperti da test
automatici.

È la prima milestone del progetto. Il dettaglio è in [Primo incremento: alimentazione](03_primo_incremento_alimentazione.md).

Non includere ancora animali malati, trasporto, più agenti, lock o pathfinding sofisticato.

## Fase 3 — Cure mediche

Durata indicativa: **3–4 giorni**.

**Stato: completata.** Veterinary richiede entrambi i trasporti, preleva il
medicinale, cura il paziente e ne verifica il rientro. Il caso senza medicinali
termina esplicitamente con task `rejected`.

Sviluppare in due sotto-scenari:

1. trasporto dalla gabbia alla Treatment Room;
2. cura e aggiornamento dello stato;
3. richiesta di rientro;
4. trasporto verso la gabbia;
5. verifica dell'intero ciclo di vita.

## Fasi avanzate

Scalabilità e concorrenza vanno aggiunte nell'ordine indicato: prima l'assegnazione univoca dei task, poi i limiti di capacità. Invertire l'ordine renderebbe difficile distinguere errori di coordinamento da errori di lock.

Per la demo finale preparare almeno tre scenari deterministici: alimentazione, cura completa e competizione per un'area a capacità limitata.

## Registro delle decisioni

Quando viene presa una scelta architetturale importante, aggiungere in `docs/decisions/` un breve ADR con:

```text
Titolo
Stato: proposta | accettata | sostituita
Contesto
Decisione
Conseguenze positive
Conseguenze negative
```

I primi ADR utili saranno: ambiente centralizzato, server XMPP locale, libreria grafica e formato dei messaggi.
