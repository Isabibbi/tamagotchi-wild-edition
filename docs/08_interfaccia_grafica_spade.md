# Interfaccia grafica SPADE con NiceGUI

## Obiettivo

La dashboard web rende visibile l'unica simulazione concorrente di alimentazione
e cure mediche. Non legge direttamente lo stato interno dell'Environment e non
introduce un secondo scenario.

## Flusso degli aggiornamenti

1. Un operatore SPADE-BDI invia un'azione all'Environment Agent.
2. L'Environment valida l'azione e modifica atomicamente lo stato.
3. L'Environment serializza uno snapshot JSON con ontologia `cras.visualization`.
4. Il Visualization Agent riceve lo snapshot via SPADE/XMPP.
5. Il worker SPADE inoltra l'oggetto read-only attraverso un canale locale autenticato.
6. NiceGUI riproduce i frame nel browser e aggiorna pianta, indicatori e cronologia.

NiceGUI non sostituisce SPADE: è soltanto il livello di presentazione. Le
decisioni, i messaggi tra operatori e gli aggiornamenti visuali continuano a
passare dagli agenti SPADE.

## Perché esistono due processi

Il server XMPP integrato di SPADE e il server web NiceGUI devono entrambi essere
avviati come processo principale. Per questo la dashboard avvia la simulazione
SPADE in un worker autonomo. I due processi comunicano soltanto su `127.0.0.1`
con una chiave casuale generata a ogni avvio.

```text
Environment Agent
    -> messaggio SPADE/XMPP
Visualization Agent
    -> bridge locale autenticato
NiceGUI nel browser
```

## Cosa mostra la dashboard

- pianta architettonica illustrata, senza mostrare le celle della griglia interna;
- Food Storage, Medical Storage, Cage Area e Treatment Room con arredi distintivi;
- gabbie con struttura, sbarre, targhetta, animale e stato della ciotola;
- tutti gli operatori rappresentati come figure umane con uniforme del ruolo;
- animazione fluida di corpo, braccia e gambe durante il cambio di stanza;
- roster completo degli operatori, compresi quelli in attesa;
- indicatori per animali sani, ciotole piene, cure e scorte;
- cronologia ordinata di trigger SPADE, decisioni, azioni e attese;
- occupanti e capacità di ogni area, sempre confrontabili con il limite `2`.

Pianta e cronologia sono affiancate su schermi desktop e si dispongono in una
sola colonna sulle finestre più strette.

## Avvio

Da PowerShell nella directory del progetto:

```powershell
& .\.my_sdai\Scripts\python.exe -m tamagotchi_wild --gui --animals 5
```

NiceGUI apre il browser su `http://127.0.0.1:8080`. Il numero degli operatori
resta configurabile nello stesso comando:

```powershell
& .\.my_sdai\Scripts\python.exe -m tamagotchi_wild --gui `
  --veterinary-agents 2 `
  --logistics-agents 3 `
  --feeding-agents 2 `
  --animals 5 `
  --gui-delay 0.20
```

Opzioni della dashboard:

```text
--gui-delay N     intervallo di playback dei frame; default 0.20 secondi
--gui-port N      porta locale; default 8080
--gui-no-browser  non apre automaticamente il browser
```

Il selettore nella pagina consente di cambiare la velocità durante il playback.
Il pulsante di pausa ferma soltanto la visualizzazione: gli agenti SPADE
continuano a lavorare. Il pulsante **Chiudi** arresta il server e l'eventuale
worker ancora attivo.

## Controlli di correttezza

I renderer SVG e HTML sono testati come funzioni pure. Un test di scenario
verifica che gli snapshot arrivino realmente dal Visualization Agent via SPADE.
La prova manuale finale verifica nel browser anche il bridge, l'assenza di
scorrimento orizzontale, le animazioni e la leggibilità contemporanea di pianta
e cronologia.
