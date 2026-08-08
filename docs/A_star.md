# Navigazione A* e prevenzione dei soft deadlock

## Obiettivo implementato

Gli operatori non vengono più spostati direttamente da una stanza all'altra.
Quando un agente SPADE richiede l'accesso a un'area, comunica una cella target
all'Environment Agent. L'Environment calcola un percorso A*, applica una sola
mossa ortogonale e restituisce `moving`. L'agente ripete la richiesta finché
raggiunge la destinazione e ottiene il permesso operativo.

La GUI mostra, per ogni operatore:

- la posizione corrente;
- la cella target con un contorno tratteggiato;
- il percorso residuo come linea tratteggiata;
- un colore stabile e diverso da quello degli altri operatori;
- lo stato `moving`, `waiting` oppure `arrived`.

Il nome richiesto `A*.md` non è valido su Windows perché `*` è un carattere
riservato. Per questo il documento si chiama `A_star.md`.

## Come funziona A*

La griglia misura 14×10 celle. Sono ammessi soltanto i movimenti su, giù,
sinistra e destra; ogni arco costa `1`. L'euristica è la distanza Manhattan:

```text
h = abs(x corrente - x target) + abs(y corrente - y target)
```

La priorità di un nodo è `f = g + h`, dove `g` è il numero di passi già
percorsi. Con costo uniforme ed euristica Manhattan, A* trova un percorso più
breve quando ne esiste uno. A parità di priorità viene usato un ordinamento
deterministico, così le prove sono ripetibili.

Il percorso restituito non contiene la posizione iniziale: contiene soltanto
le celle che l'operatore deve ancora attraversare, target compreso. A ogni
richiesta viene eseguita esclusivamente la prima mossa.

## Ostacoli dinamici

Prima di ogni passo l'Environment ricostruisce gli ostacoli:

1. celle occupate dagli altri operatori;
2. tutte le celle di una stanza che ha già raggiunto la capacità fisica;
3. limiti esterni della griglia.

Il calcolo viene quindi ripetuto durante il viaggio. Se un altro agente cambia
posizione, il tragitto può cambiare senza invalidare il task. Nessun operatore
può saltare celle, uscire dalla griglia o entrare in una cella occupata. La
cella finale può essere condivisa da due operatori, coerentemente con la
capacità massima della stanza.

## Strategie anti soft deadlock implementate

Un soft deadlock si verifica quando gli agenti sono ancora attivi ma continuano
ad aspettarsi senza riuscire a progredire. Nel layout precedente le quattro
stanze coprivano tutta la griglia: sette operatori inattivi potevano occupare
tutti i posti e impedire qualsiasi lavoro. Sono state introdotte queste
protezioni:

1. **Corridoio neutro.** Separa le quattro stanze e contiene le posizioni di
   attesa dei sette operatori. Non è una risorsa operativa con limite `2`.
2. **Parcheggio dopo il rilascio.** Dopo aver terminato un'azione, l'agente
   rilascia il permesso e raggiunge via A* una cella vicina del corridoio. La
   stanza torna quindi libera anche fisicamente.
3. **Un solo task di navigazione per agente.** Due behaviour concorrenti dello
   stesso operatore non possono alternare target diversi. Il primo task mantiene
   il controllo del movimento finché rilascia l'area.
4. **Mossa atomica nell'Environment.** Controllo e aggiornamento di una cella
   avvengono nello stesso punto autorevole. Due messaggi concorrenti non possono
   occupare accidentalmente lo stesso posto.
5. **Attesa e ripianificazione.** Se il cammino o la stanza sono bloccati,
   l'agente resta in `waiting`, attende brevemente e prova di nuovo usando lo
   stato più recente.

Questa soluzione è stata verificata con l'esecuzione richiesta più intensa:
sette operatori, cinque animali, cinque task di alimentazione e cinque task
medici concorrenti. Tutti i task terminano e l'occupazione massima osservata
delle stanze rimane `2`.

## Perché non è una garanzia generale di assenza di deadlock

Il problema generale di pianificare contemporaneamente i percorsi di molti
agenti è chiamato Multi-Agent Path Finding. Il sistema implementato usa A*
individuale con ripianificazione reattiva: è adeguato al layout e al limite di
sette operatori di questo progetto, ma non dimostra formalmente la completezza
per qualsiasi griglia futura.

Un layout molto stretto, privo di celle laterali, potrebbe produrre due agenti
che si bloccano frontalmente. Per una garanzia più forte servirebbe una delle
seguenti estensioni:

- tabella di prenotazione spazio-temporale, includendo il tempo nello stato A*;
- priorità dinamiche e diritto di precedenza dopo un numero di attese;
- Cooperative A* oppure Conflict-Based Search;
- rilevamento di cicli di attesa e arretramento coordinato verso una cella sicura.

Queste tecniche aumentano stato, messaggi e complessità di test. Non sono
necessarie per gli scenari e i vincoli attuali, ma rappresentano il passo
successivo corretto se la griglia diventerà più affollata o meno connessa.

## File coinvolti

```text
src/tamagotchi_wild/environment/pathfinding.py  algoritmo A*
src/tamagotchi_wild/environment/state.py        ostacoli, movimento e navigazione
src/tamagotchi_wild/agents/environment_actions.py retry e parcheggio nel corridoio
src/tamagotchi_wild/messaging/visualization.py  target e percorso negli snapshot
src/tamagotchi_wild/visualization/nicegui_view.py rendering dei tragitti
tests/unit/test_pathfinding.py                  test mirati
```
