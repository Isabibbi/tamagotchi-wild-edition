# Tamagotchi Wild Edition: Multi-Agent Care for Virtual Pets

Sistema multi-agente didattico per la gestione automatizzata di un Centro di
Recupero Animali Selvatici (CRAS), ispirato all'esperienza di volontariato ENPA.

> **Stato:** alimentazione e cure mediche sono integrate in un'unica simulazione
> SPADE-BDI. Il numero degli operatori si decide all'avvio, fino a un massimo di
> 7; l'Environment Agent non rientra in questo limite. Ogni area ammette al
> massimo 2 operatori contemporaneamente.

## Agenti

| Agente | Responsabilità |
|---|---|
| **Veterinary** | Coordina il ciclo medico, prende il medicinale e cura l'animale |
| **Logistics** | Trasporta gli animali e coordina il rifornimento delle ciotole |
| **Feeding** | Preleva il cibo e riempie le ciotole |
| **Environment** | Mantiene lo stato autorevole, assegna atomicamente i task e controlla gli accessi alle aree |

La simulazione predefinita avvia contemporaneamente:

```text
2 Veterinary + 3 Logistics + 2 Feeding = 7 operatori
1 Environment Agent aggiuntivo = 8 agenti SPADE attivi
```

Alimentazione e cure non sono modalità alternative: i due flussi partono nella
stessa esecuzione e avanzano in modo concorrente tramite messaggi SPADE/XMPP.

## Concorrenza e assegnazione

- ogni fase di lavoro viene assegnata atomicamente a un solo agente;
- gli altri agenti dello stesso ruolo rifiutano il duplicato senza eseguirlo;
- per entrare in un'area operativa occorre un permesso dell'Environment;
- il terzo agente attende e riprova finché uno dei due posti viene rilasciato;
- il limite di 2 vale per Food Storage, Medical Storage, Cage Area e Treatment Room.

## Avvio

Da PowerShell, nella cartella del progetto:

```powershell
& .\.my_sdai\Scripts\python.exe -m tamagotchi_wild
```

Output finale atteso:

```text
SIMULATION OK
operators=7 veterinary=2 logistics=3 feeding=2
feeding=completed medical=completed animal=healthy bowl=1/1
max-room-occupancy=1/2
```

Il massimo osservato può essere `1` oppure `2`, in base all'ordine effettivo dei
messaggi. Non può mai superare `2`.

## Configurazione a runtime

Esempio con un agente per ruolo:

```powershell
& .\.my_sdai\Scripts\python.exe -m tamagotchi_wild `
  --veterinary-agents 1 `
  --logistics-agents 1 `
  --feeding-agents 1
```

Ogni ruolo deve avere almeno un agente, perché entrambi i flussi sono sempre
attivi. La somma dei tre valori deve essere al massimo 7. Per esempio,
`2 + 4 + 2 = 8` viene rifiutato prima di avviare SPADE.

Opzioni aggiuntive:

```text
--food N       quantità iniziale di cibo
--medicine N   quantità iniziale di medicinali
--timeout N    timeout in secondi
--json         risultato finale in JSON
```

## Test

```powershell
& .\.my_sdai\Scripts\python.exe -m pytest
```

I test verificano la configurazione fino a 7 operatori, l'assegnazione univoca
dei task, il limite di 2 accessi e l'esecuzione end-to-end simultanea dei due
flussi. Il server XMPP integrato viene avviato e arrestato automaticamente; non
servono Internet né credenziali esterne.

## Struttura principale

```text
src/tamagotchi_wild/
├── agents/          # agenti SPADE-BDI e accesso concorrente alle aree
├── bdi/             # piani AgentSpeak dei tre ruoli
├── domain/          # entità e comandi del dominio
├── environment/     # stato autorevole, claim atomici e capacità
├── messaging/       # contratti JSON e metadata FIPA
├── visualization/   # proiezione read-only per la futura GUI
├── simulation.py    # unica simulazione integrata
└── main.py          # parametri da terminale
```

La progettazione e le fasi incrementali sono descritte nella cartella
[`docs`](docs/).
