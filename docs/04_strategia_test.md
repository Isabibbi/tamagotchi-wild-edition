# Strategia di test

## Obiettivo

Ogni fase deve poter essere verificata automaticamente sul PC di sviluppo. La GUI è utile per la demo, ma non è una prova sufficiente della correttezza.

## Livelli di test

| Livello | Cosa verifica | Dipendenze reali |
|---|---|---|
| Unitario | Regole del dominio, transizioni e payload | Nessuna |
| Componente | Singolo agente o Environment Agent | SPADE, trasporto controllato |
| Integrazione | Scambio tra più agenti | Server XMPP integrato |
| Scenario | Workflow CRAS completo | Sistema locale completo |
| Manuale | Grafica, leggibilità e demo | Pygame e osservazione umana |

## Priorità iniziali

1. Testare regole e transizioni come funzioni pure.
2. Testare payload validi, mancanti e malformati.
3. Testare ogni scambio richiesta/risposta con timeout breve.
4. Testare gli scenari senza aprire la finestra grafica.
5. Mantenere pochi test visuali manuali separati.

## Matrice minima degli scenari

| Scenario | Stato iniziale | Risultato atteso |
|---|---|---|
| Alimentazione riuscita ✅ | Ciotola vuota, cibo presente | Verificato: ciotola piena, scorta decrementata |
| Magazzino vuoto ✅ | Ciotola vuota, cibo assente | Verificato: task `rejected`, nessuna modifica incoerente |
| Richiesta duplicata ✅ | Stesso `task_id` inviato due volte | Verificato: una sola esecuzione |
| Cura completa ✅ | Animale malato in gabbia | Verificato: animale sano e riportato in gabbia |
| Area piena | Capacità raggiunta | Agente in attesa o rifiuto controllato |

## Rendere i test deterministici

- assegnare identificativi noti nei test;
- usare una griglia e uno stato iniziale fissi;
- iniettare il generatore casuale con un seed;
- evitare attese reali lunghe usando timeout configurabili;
- verificare stato ed eventi, non soltanto il testo dei log.

## Testare il BDI

Non limitarsi a verificare che un metodo Python venga chiamato. Per ogni piano importante controllare:

| Aspetto | Esempio |
|---|---|
| Trigger | L'aggiunta di `bowl_empty(Cage)` attiva il piano corretto |
| Contesto | Il piano non parte se il task è già assegnato |
| Azione | La custom action riceve argomenti validi |
| Successo | Il belief temporaneo viene rimosso o aggiornato |
| Fallimento | Timeout e rifiuto portano a uno stato gestibile |

## Testare la concorrenza

I test avanzati devono creare contese intenzionali. Avviare più richieste nello stesso istante, registrare ingresso e uscita dalle aree e verificare che la capacità non venga mai superata.

Per evitare test instabili, non basare l'asserzione sull'ordine preciso degli agenti. Verificare invarianti: massimo numero di occupanti, unicità del task e rilascio finale della risorsa.

## Comandi locali attesi

Il repository offre questi comandi:

```powershell
.\.my_sdai\Scripts\python.exe -m pytest tests/unit
.\.my_sdai\Scripts\python.exe -m pytest tests/integration
.\.my_sdai\Scripts\python.exe -m pytest tests/scenarios
.\.my_sdai\Scripts\python.exe -m tamagotchi_wild
```

I comandi definitivi dovranno essere riportati nel README e provati da una nuova shell, senza dipendere dallo stato dell'IDE.

## Definition of Done per i test

- la suite termina senza intervento manuale;
- ogni bug corretto lascia un test di regressione;
- i test non dipendono da Internet;
- le credenziali non sono salvate nel repository;
- un fallimento indica scenario, task e causa leggibile.
