# Interfaccia grafica SPADE

## Obiettivo

La GUI rende visibile la simulazione unica di alimentazione e cure mediche,
senza introdurre un secondo scenario e senza leggere direttamente lo stato
interno dell'Environment.

## Flusso degli aggiornamenti

1. Un operatore SPADE-BDI invia un'azione all'Environment Agent.
2. L'Environment valida l'azione e modifica atomicamente lo stato.
3. L'Environment crea uno snapshot read-only della griglia.
4. Lo snapshot viene serializzato in JSON con ontologia `cras.visualization`.
5. Il Visualization Agent SPADE riceve il messaggio tramite XMPP.
6. La GUI Tkinter consuma l'aggiornamento e ridisegna griglia e cronologia.

Anche un'azione rifiutata viene pubblicata. Se, per esempio, due operatori sono
già nella Treatment Room, il tentativo del terzo appare come un evento di
attesa. Il rifiuto non modifica lo stato e l'agente continua a riprovare secondo
la politica di concorrenza già implementata.

## Cosa mostra la finestra

La parte sinistra contiene la griglia 12×8:

- Food Storage in giallo chiaro;
- Medical Storage in azzurro;
- Cage Area in verde, con tutte le gabbie e le ciotole;
- Treatment Room in rosa;
- operatori con iniziali `V`, `L` e `F` e colore distinto per ruolo;
- animali colorati secondo lo stato di salute.

Il bordo giallo di un operatore indica che possiede un permesso di accesso a
un'area. La sezione di riepilogo mostra inoltre il rapporto occupanti/capacità
per tutte le stanze, rendendo verificabile il limite `2`.

La parte destra contiene la cronologia. Le righe principali corrispondono agli
eventi atomici dell'Environment; le righe rientrate descrivono le cause di alto
livello, come una ciotola vuota, una richiesta di trasporto o il completamento
di una cura.

## Avvio

Da PowerShell nella directory del progetto:

```powershell
& .\.my_sdai\Scripts\python.exe -m tamagotchi_wild --gui --animals 5
```

Il numero dei tre tipi di operatore resta configurabile nello stesso comando:

```powershell
& .\.my_sdai\Scripts\python.exe -m tamagotchi_wild --gui `
  --veterinary-agents 2 `
  --logistics-agents 3 `
  --feeding-agents 2 `
  --animals 5 `
  --gui-delay 0.20
```

`--gui-delay` controlla solo la velocità con cui i frame già ricevuti vengono
mostrati. Non rallenta SPADE, non modifica l'ordine degli eventi e non influisce
sul timeout della simulazione.

## Scelta tecnologica

SPADE rimane responsabile della comunicazione e dell'agente di visualizzazione.
Tkinter è esclusivamente il renderer desktop: è incluso in Python 3.12 su questo
PC, quindi non è stata aggiunta alcuna dipendenza da installare. SPADE resta nel
processo principale, come richiesto dal server XMPP integrato; la finestra gira
in un processo separato per mantenersi reattiva mentre gli agenti lavorano.
