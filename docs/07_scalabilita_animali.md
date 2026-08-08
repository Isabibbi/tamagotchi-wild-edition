# Estensione della scalabilità — Animali, gabbie e task

## Stato

**Completata.** Il numero degli animali viene scelto all'avvio con:

```powershell
.\.my_sdai\Scripts\python.exe -m tamagotchi_wild --animals 5
```

Il valore deve essere compreso tra 1 e 40, pari al numero di celle disponibili
nella Cage Area della griglia predefinita.

## Generazione automatica

Per ogni animale vengono creati automaticamente:

```text
1 Animal
1 Cage
1 Bowl
1 task REFILL_BOWL
1 task TREAT_ANIMAL
```

Con cinque animali il mondo contiene quindi:

```text
5 animali
5 gabbie
5 ciotole
5 task Feeding
5 task Medical
```

Ogni gabbia occupa una cella distinta della stessa `Cage Area`. La gabbia
conserva gli identificativi del proprio animale e della propria ciotola. Anche
l'animale conserva `cage_id`, utilizzato come destinazione per il ritorno.

## Condizioni mediche

Ogni caso riceve una condizione differente. I primi cinque esempi sono:

| Animale | Specie | Condizione |
|---|---|---|
| `animal_001` | fox | `wing_injury` |
| `animal_002` | owl | `dehydration` |
| `animal_003` | hedgehog | `respiratory_infection` |
| `animal_004` | badger | `leg_fracture` |
| `animal_005` | hare | `malnutrition` |

Le condizioni rendono distinti i casi, mentre in questo incremento il ciclo di
cura rimane comune: trasporto, prelievo di una dose di medicinale, trattamento e
rientro. Cure specifiche per patologia potranno essere aggiunte separatamente.

## Posizioni e identificativi

I casi vengono generati deterministicamente:

```text
animal_001 → cage_01 → bowl_01
animal_002 → cage_02 → bowl_02
animal_003 → cage_03 → bowl_03
```

Feeding e Logistics ricevono una mappa delle posizioni delle ciotole e delle
gabbie. In questo modo ogni riempimento e ogni trasporto di ritorno utilizzano la
posizione corretta, senza dipendere da una singola gabbia fissa.

## Distribuzione del lavoro

I task vengono assegnati round-robin:

```text
feeding_001 → feeding_01
feeding_002 → feeding_02
feeding_003 → feeding_01
```

Lo stesso criterio viene applicato ai Veterinary e ai Logistics. Il claim
atomico dell'Environment resta obbligatorio, quindi ogni fase viene comunque
eseguita una volta sola.

## Risorse iniziali

Se `--food` e `--medicine` non sono specificati, vengono inizializzati con lo
stesso valore di `--animals`. Cinque animali ricevono quindi cinque unità di cibo
e cinque dosi di medicinale.

I valori possono essere ridotti intenzionalmente per verificare i fallimenti:

```powershell
.\.my_sdai\Scripts\python.exe -m tamagotchi_wild --animals 5 --medicine 3
```

## Verifica finale

La simulazione ha successo soltanto se:

- tutti i task Feeding sono completati;
- tutti i task Medical sono completati;
- tutte le ciotole sono piene;
- tutti gli animali sono sani nelle proprie gabbie;
- tutte le aree sono state rilasciate e non hanno mai superato capacità 2.
