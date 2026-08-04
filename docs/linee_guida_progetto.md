# Linee Guida Progetto SDAI: Wildlife Rescue Center (CRAS)

Ecco una linea guida strutturata passo dopo passo per affrontare lo sviluppo del tuo progetto di Symbolic Distributed Artificial Intelligence. L'approccio è diviso in fasi incrementali per garantirti di avere una base funzionante prima di aggiungere complessità.

Questa versione delle linee guida adotta l'ecosistema **Python (SPADE + SPADE-BDI + PyGame)** per unire la flessibilità di Python con i requisiti simbolici del corso.

> ✅ **Approvazione del Docente (Luglio 2026)**
> L'uso di **SPADE + SPADE-BDI** è stato approvato. Il professore raccomanda di documentarsi bene sul framework — punti di forza, limitazioni, scelte architetturali — in modo da essere preparata a eventuali domande durante la discussione.

---

## 📚 Dove Documentarsi su SPADE

### Documentazione Ufficiale

| Risorsa | Link | Cosa trovi |
|---|---|---|
| **SPADE Docs** (principale) | https://spadeagents.eu/docs/spade/ | Agent Model, Behaviours, Communication, Quick Start |
| **SPADE-BDI Docs** | https://spade-bdi.readthedocs.io | Integrazione BDI, sintassi AgentSpeak, Beliefs |
| **SPADE GitHub** | https://github.com/javipalanca/spade | Codice sorgente, esempi, issues |
| **SPADE-BDI GitHub** | https://github.com/javipalanca/spade_bdi | Plugin BDI, README con esempi pratici |
| **PyPI spade** | https://pypi.org/project/spade/ | Versioni, dipendenze |
| **PyPI spade-bdi** | https://pypi.org/project/spade-bdi/ | Versioni, changelog |

### Percorso di Studio Consigliato (4 giorni)

**Giorno 1 – Architettura SPADE**
- Leggi il *Foreword* e *The SPADE Agent Model* dalla docs ufficiale
- Fai girare il *Quick Start* (un agente che manda un messaggio a se stesso)
- Capisci i **Behaviours**: `CyclicBehaviour`, `OneShotBehaviour`, `PeriodicBehaviour`, `FSMBehaviour`

**Giorno 2 – Comunicazione FIPA-ACL / XMPP**
- Leggi la sezione *Agent Communications*
- Comprendi la struttura di un messaggio: `to`, `sender`, `body`, `performative` (`inform`, `request`, `agree`, `refuse`)
- Usa il server XMPP locale in Python **`pyjabber`** (`pip install pyjabber` - zero installazioni di software esterni su Windows!)


**Giorno 3 – SPADE-BDI e AgentSpeak**
- Leggi il README di `spade_bdi` su GitHub
- Studia la sintassi dei file `.asl`: beliefs iniziali, goals, piani (`+!goal <- action1; action2.`)
- Capisci come SPADE-BDI **chiama azioni Python** da dentro un piano AgentSpeak
- Prendi nota delle **limitazioni** di AgentSpeak in SPADE-BDI (vedi sezione sotto)

**Giorno 4 – Integrazione Ibrida**
- Scopri come combinare `BDIAgent` con `Behaviour` classici di SPADE
- Studia come aggiornare le credenze (`set_belief`, `get_belief`) da Python durante il runtime
- Guarda gli esempi nella cartella `tests/` del repo `spade_bdi`

---

## ⚡ Punti di Forza di SPADE (per la discussione)

| Punto di Forza | Descrizione |
|---|---|
| **XMPP nativo** | Protocollo maturo e standardizzato; gestisce autenticazione, presenza e routing senza infrastrutture custom |
| **asyncio-first** | Tutti i behaviour girano come coroutine — concorrenza reale senza thread pesanti |
| **Modello a Behaviour** | Astrazione chiara e testabile: ogni task dell'agente è incapsulato in un behaviour dedicato |
| **Ecosistema Plugin** | `spade-bdi` (cognitivo), `spade-pubsub` (pub-sub), `spade-artifact` (artefatti CArtAgO-like) |
| **Semplicità vs JADE** | Rispetto al predecessore Java JADE, è significativamente più leggero e veloce da prototipare |
| **Dashboard Web** | Interfaccia web integrata per monitorare agenti attivi e messaggi in tempo reale |

---

## ⚠️ Limitazioni di SPADE (per la discussione)

| Limitazione | Dettaglio | Come la gestiamo |
|---|---|---|
| **AgentSpeak parziale** | `spade-bdi` implementa solo un sottoinsieme di AgentSpeak(L): mancano annotazioni avanzate sulle credenze, meta-ragionamento e alcuni operatori logici complessi | Si delega la logica complessa a Python e si usa `.asl` solo per il ciclo BDI di alto livello |
| **Scalabilità** | Python + GIL + overhead XMPP non reggono scenari con migliaia di agenti | Per il CRAS (3–10 agenti) non è un problema reale |
| **Dipendenza XMPP** | Ogni deploy richiede un server XMPP attivo (locale o remoto) | Si usa un server locale (Prosody) o il server demo pubblico |
| **Community più piccola** | Alcune funzionalità avanzate (es. FIPA Contract Net completo) richiedono implementazione manuale | Si implementa solo ciò che serve per il dominio CRAS |
| **Debugging BDI** | Il ciclo di ragionamento BDI è meno trasparente rispetto al codice Python puro | Si integra `loguru` per log colorati e tracciamento esplicito dei belief |

---

## 🎯 Motivazione della Scelta (da avere pronta per la discussione orale)

> *"Ho scelto SPADE perché permette di combinare il paradigma **BDI simbolico** — richiesto dal corso — con la flessibilità di **Python** in modo nativo. SPADE-BDI fornisce il layer cognitivo tramite AgentSpeak, mentre SPADE core gestisce la comunicazione FIPA-ACL su XMPP. Rispetto a JaCaMo/Jason, la scelta introduce alcune limitazioni lato AgentSpeak, compensate però dalla possibilità di estendere liberamente la logica degli agenti in Python (asyncio, asyncio.Semaphore per la concorrenza, librerie di visualizzazione). Per il dominio del CRAS — con 3 tipologie di agenti, workflow di cooperazione e risorse condivise — le capacità di SPADE sono più che sufficienti, e la scelta è stata consapevole e motivata."*

---

## Fase 1: Setup e Scelte Architetturali
Prima di scrivere qualsiasi riga di codice, è fondamentale consolidare l'architettura.

*   **Valutazione Framework e Librerie:** 
    *   Usa **`spade`** per gestire l'architettura degli agenti (comunicazione XMPP, cicli di vita).
    *   Integra **`spade-bdi`** per mantenere il paradigma simbolico (Beliefs-Desires-Intentions) richiesto dal corso, scrivendo la logica decisionale degli agenti in file `.asl` (AgentSpeak).
    *   Scegli **`pygame`** o **`mesa`** per la modellazione e visualizzazione della griglia 2D.
*   **Definizione del Modello Dati (Python):**
    *   Mappa le coordinate e le dimensioni delle 4 aree: *Food Storage, Medical Storage, Cage Area, Treatment Room* all'interno di una classe Python.
    *   Definisci gli stati degli animali (es. `affamato`, `in_cura`, `da_trasportare`, `sano`).
    *   Definisci le ontologie dei messaggi (FIPA-ACL) che gli agenti useranno per comunicare (es. `richiesta_trasporto`, `cibo_necessario`).

## Fase 2: Sviluppo dell'Ambiente (Grid Environment)
In questa fase crei il "mondo" in cui si muoveranno gli agenti, focalizzandoti sulla rappresentazione piuttosto che sull'intelligenza.

*   **Implementazione della Griglia 2D:** Crea la matrice o lo spazio in cui opereranno gli agenti (es. una classe `Environment` in Python).
*   **Partizionamento delle Aree:** Assegna specifiche coordinate o zone della griglia ai magazzini (Food/Medical), all'area gabbie e alla sala visite.
*   **Popolamento e Renderizzazione:** Inserisci gli animali (come risorse passive) e usa `pygame` per visualizzare la griglia aggiornando graficamente lo stato delle celle e la posizione degli agenti in tempo reale.
*   **Agentificazione dell'Ambiente:** Non essendoci l'ambiente CArtAgO (di JaCaMo), valuta di creare un "Agente Ambiente" centralizzato che detiene la verità di stato della griglia e processa le richieste di movimento degli altri agenti.

## Fase 3: Core Logic 1 - Gestione Nutrizione (Approccio Incrementale)
Questo è il primo test di cooperazione basato sui messaggi SPADE.

*   **Sviluppo del Logistics Agent (ruolo base):**
    *   Insegna all'agente (usando la logica BDI) a percepire quando le ciotole nella *Cage Area* sono vuote.
    *   Fagli generare e inviare un messaggio FIPA-ACL di tipo `REQUEST` al *Feeding Agent*.
*   **Sviluppo del Feeding Agent:**
    *   Insegna all'agente a ricevere il messaggio, estrarne il contenuto e accettare il task.
    *   Implementa l'azione di movimento verso il *Food Storage*, il prelievo del cibo e il movimento verso la *Cage Area* per riempire le ciotole.
*   **Validazione:** Testa che i messaggi XMPP vengano scambiati correttamente (usa `loguru` per stampare log chiari e colorati sul terminale).

## Fase 4: Core Logic 2 - Gestione Cure Mediche
Una volta validata la cooperazione di base, introduci il workflow più complesso.

*   **Sviluppo del Veterinary Agent:**
    *   Rendilo in grado di identificare (tramite credenze/beliefs BDI) un animale malato.
    *   Insegna al veterinario a inviare una richiesta al *Logistics Agent* per portare l'animale nella *Treatment Room*.
*   **Estensione del Logistics Agent (trasporto animali):**
    *   Implementa l'azione di prelievo dell'animale dalla *Cage Area* e lo spostamento alla *Treatment Room*.
    *   Invio di un messaggio di notifica ("Paziente pronto") al veterinario.
*   **Workflow di Cura (Veterinario):**
    *   Il veterinario si reca al *Medical Storage* se necessita di medicinali.
    *   Torna nella *Treatment Room* e cambia lo stato dell'animale (da `malato` a `curato`).
    *   Richiede nuovamente alla logistica di riportare l'animale nella *Cage Area*.

## Fase 5: Scalabilità (N Agenti)
Ora espandi il sistema avviando N Veterinari, N Feeding Staff e N Logistics Staff all'interno del main in Python.

*   **Gestione dei Task Asincroni:** Sfrutta i behaviour concorrenti di SPADE e l'asincronia nativa di Python (`asyncio`) per gestire più task e movimenti simultaneamente.
*   **Prevenzione Duplicati:** Assicurati che i task (es. trasportare un animale) vengano negoziati correttamente tra gli agenti logistici per evitare che due agenti vadano a prendere lo stesso animale.

## Fase 6: Obiettivo Avanzato - Controllo della Concorrenza
Questa è la fase finale per gestire l'accesso limitato alle risorse condivise.

*   **Definizione dei Colli di Bottiglia:** Identifica le aree critiche (es. la *Treatment Room* ospita max 1 veterinario; i corridoi o il *Food Storage* max 2 agenti).
*   **Implementazione dei Lock in Python:**
    *   **Opzione 1 (Agente Ambiente):** Se l'ambiente è un Agente, gestirà code di attesa interne tramite `asyncio.Semaphore`. Quando un agente chiede di entrare in una stanza piena, la risposta di permesso al movimento viene ritardata finché non si libera un posto.
    *   **Opzione 2 (Redis):** Usa un database in memoria rapido come Redis per gestire *distributed locks*. Un agente tenta di acquisire il lock di una cella; se fallisce, il suo comportamento SPADE rimane in stato di attesa.
*   **Gestione dei Deadlock:** Implementa meccanismi di timeout per evitare che gli agenti si blocchino all'infinito aspettando una risorsa.

## Fase 7: Documentazione e Presentazione
*   Prepara una documentazione che illustri come hai architettato il sistema, specificando in che modo l'ecosistema Python (SPADE, PyGame) si sposa con il paradigma dell'IA Simbolica (BDI) per risolvere il dominio del CRAS e il controllo della concorrenza.
*   **Sii pronta a rispondere a domande su SPADE**: punti di forza, limitazioni di AgentSpeak in `spade-bdi`, e perché hai preferito questo stack rispetto a JaCaMo/Jason.
