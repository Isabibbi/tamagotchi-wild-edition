# Tamagotchi Wild Edition: Multi-Agent Care for Virtual Pets

Sistema multi-agente didattico per la gestione automatizzata di un Centro di
Recupero Animali Selvatici (CRAS), ispirato all'esperienza di volontariato ENPA.

> **Stato:** alimentazione e cure mediche sono integrate in un'unica simulazione
> SPADE-BDI. Il numero degli operatori si decide all'avvio, fino a un massimo di
> 7; l'Environment Agent non rientra in questo limite. Ogni stanza operativa
> ammette al massimo 2 operatori contemporaneamente. Anche il numero degli animali è
> configurabile: ogni animale genera automaticamente gabbia, ciotola e due task.
> È disponibile una GUI live con griglia e cronologia degli eventi SPADE.

## Agenti

| Agente | Responsabilità |
|---|---|
| **Veterinary** | Coordina il ciclo medico, prende il medicinale e cura l'animale |
| **Logistics** | Trasporta gli animali e coordina il rifornimento delle ciotole |
| **Feeding** | Preleva il cibo e riempie le ciotole |
| **Environment** | Mantiene lo stato autorevole, assegna atomicamente i task e controlla gli accessi alle aree |
| **Visualization** | Riceve via SPADE/XMPP gli snapshot dell'Environment e li consegna alla GUI |

La simulazione predefinita avvia contemporaneamente:

```text
2 Veterinary + 3 Logistics + 2 Feeding = 7 operatori
1 Environment Agent aggiuntivo = 8 agenti SPADE attivi
Con la GUI: 1 Visualization Agent aggiuntivo = 9 agenti SPADE attivi
```

Alimentazione e cure non sono modalità alternative: i due flussi partono nella
stessa esecuzione e avanzano in modo concorrente tramite messaggi SPADE/XMPP.

## Concorrenza e assegnazione

- ogni fase di lavoro viene assegnata atomicamente a un solo agente;
- gli altri agenti dello stesso ruolo rifiutano il duplicato senza eseguirlo;
- per entrare in un'area operativa occorre un permesso dell'Environment;
- il terzo agente attende e riprova finché uno dei due posti viene rilasciato;
- il limite di 2 vale per Food Storage, Medical Storage, Cage Area e Treatment Room.
- ogni spostamento avanza di una sola cella lungo un percorso calcolato con A*;
- le celle occupate dagli altri operatori sono ostacoli dinamici e il percorso
  viene ricalcolato durante il movimento;
- un corridoio neutro offre celle di attesa e impedisce agli operatori inattivi
  di saturare le quattro stanze operative.

## Avvio

Da PowerShell, nella cartella del progetto:

```powershell
& .\.my_sdai\Scripts\python.exe -m tamagotchi_wild
```

Output finale atteso:

```text
SIMULATION OK
operators=7 veterinary=2 logistics=3 feeding=2
animals=1 cages=1 bowls=1
feeding=1/1 medical=1/1 healthy=1/1
max-room-occupancy=1/2
```

Il massimo osservato può essere `1` oppure `2`, in base all'ordine effettivo dei
messaggi. Non può mai superare `2`.

## Configurazione a runtime

### Interfaccia grafica

Per vedere la simulazione, usare lo stesso comando con `--gui`:

```powershell
& .\.my_sdai\Scripts\python.exe -m tamagotchi_wild --gui --animals 5
```

Il browser si apre su una dashboard NiceGUI locale e mostra:

- a sinistra, la griglia 14×10 con stanze, corridoio, operatori, animali,
  gabbie e ciotole;
- per ogni operatore, un colore distinto identifica il tragitto A* e la cella target;
- in giallo, il bordo interno degli operatori che occupano una stanza;
- a destra, risorse, task completati e occupazione corrente delle aree;
- nella cronologia, percezioni, richieste, movimenti, azioni e attese;
- alla fine, l'esito complessivo senza chiudere automaticamente la pagina.

Gli aggiornamenti non accedono direttamente allo stato della simulazione:
l'Environment invia messaggi JSON con ontologia `cras.visualization` al
Visualization Agent SPADE. NiceGUI si limita a disegnare ciò che questo agente
riceve tramite un canale locale autenticato. `--gui-delay 0.20` regola i secondi
fra due frame; non rallenta i flussi interni degli agenti.

La pagina è servita soltanto su `127.0.0.1`: non viene pubblicata su Internet.
Se il browser non si apre automaticamente, visitare `http://127.0.0.1:8080`.

### Parametri della simulazione

Esempio con cinque animali e cinque casi completi:

```powershell
& .\.my_sdai\Scripts\python.exe -m tamagotchi_wild `
  --veterinary-agents 2 `
  --logistics-agents 3 `
  --feeding-agents 2 `
  --animals 5
```

Ogni ruolo deve avere almeno un agente, perché entrambi i flussi sono sempre
attivi. La somma dei tre valori deve essere al massimo 7. Per esempio,
`2 + 4 + 2 = 8` viene rifiutato prima di avviare SPADE.

`--animals N` accetta da 1 a 40. Con `--animals 5` vengono creati:

```text
5 animali con condizioni differenti
5 gabbie nella stessa Cage Area
5 ciotole
5 task Feeding
5 task Medical
```

Se non vengono specificati, cibo e medicinali iniziali sono automaticamente
uguali al numero degli animali.

Opzioni aggiuntive:

```text
--animals N    numero di animali e casi completi, da 1 a 40
--food N       quantità iniziale di cibo; default uguale agli animali
--medicine N   quantità iniziale di medicinali; default uguale agli animali
--timeout N    timeout in secondi
--gui          apre griglia e cronologia live
--gui-delay N  secondi fra due frame grafici; default 0.20
--gui-port N   porta locale della dashboard; default 8080
--gui-no-browser  avvia il server senza aprire automaticamente il browser
--json         risultato finale in JSON
```

## Test

```powershell
& .\.my_sdai\Scripts\python.exe -m pytest
```

I test verificano la configurazione fino a 7 operatori e 40 animali,
l'assegnazione univoca dei task, A*, i movimenti atomici, il limite fisico di 2
operatori nelle stanze e un'esecuzione
end-to-end con 5 animali e 10 task. I test dedicati avviano anche il
Visualization Agent, verificano lo stream SPADE e i renderer usati da NiceGUI.
Il server XMPP integrato viene avviato e arrestato automaticamente; non servono
Internet né credenziali esterne.

## Struttura principale

```text
src/tamagotchi_wild/
├── agents/          # agenti SPADE-BDI, Environment e Visualization
├── bdi/             # piani AgentSpeak dei tre ruoli
├── domain/          # entità e comandi del dominio
├── environment/     # stato autorevole, A*, claim atomici e capacità
├── messaging/       # contratti JSON e metadata FIPA
├── visualization/   # proiezione read-only, SVG e cronologia
├── gui.py           # pagina e componenti NiceGUI
├── gui_bridge.py    # canale locale autenticato NiceGUI ↔ SPADE
├── gui_worker.py    # processo autonomo della simulazione SPADE
├── simulation.py    # unica simulazione integrata
└── main.py          # parametri da terminale
```

La progettazione e le fasi incrementali sono descritte nella cartella
[`docs`](docs/). L'implementazione della navigazione è documentata in
[`docs/A_star.md`](docs/A_star.md).
