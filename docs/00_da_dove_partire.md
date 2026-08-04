# Da dove partire

Questo documento è il punto di ingresso operativo del progetto. L'obiettivo è evitare di progettare tutto in anticipo e arrivare rapidamente a un primo scenario completo, osservabile e testabile.

## Stato di avanzamento

**Fase 0 completata:** due agenti SPADE-BDI eseguono i rispettivi piani AgentSpeak e scambiano localmente una richiesta e una risposta correlate. Il server XMPP integrato parte e si arresta insieme allo scenario; lo smoke test è automatizzato.

Il prossimo incremento è la modellazione del dominio e dell'`EnvironmentAgent`, prima della GUI.

## Decisioni consigliate subito

| Tema | Decisione iniziale | Motivo |
|---|---|---|
| Ambiente | Un `EnvironmentAgent` centralizzato mantiene lo stato autorevole | Evita conflitti e rende verificabili movimenti, risorse e capacità |
| Ragionamento | AgentSpeak per obiettivi e piani; Python per azioni ed effetti | Mantiene il BDI leggibile senza forzare la logica operativa in `.asl` |
| Comunicazione | Messaggi SPADE con metadata FIPA e body JSON | Consente filtri, tracciamento e validazione dei messaggi |
| XMPP locale | Server integrato di SPADE durante lo sviluppo | Riduce il setup iniziale e rende i test ripetibili sul PC |
| Visualizzazione | Pygame come prima scelta, separato dalla logica | È adatto a una griglia 2D e non deve diventare fonte dello stato |

Queste decisioni sono una baseline, non vincoli permanenti. Devono essere cambiate solo dopo un esperimento che mostri un problema concreto.

## Ordine di lavoro

1. ~~Eseguire uno **spike tecnico minimo**: due agenti SPADE-BDI si avviano e scambiano un messaggio usando il server XMPP integrato.~~ **Completato.**
2. Modellare il dominio senza grafica: griglia, aree, animali, ciotole, agenti e azioni valide.
3. Implementare una singola fetta verticale: Logistics rileva una ciotola vuota e Feeding la riempie.
4. Aggiungere la visualizzazione come proiezione dello stato dell'ambiente.
5. Procedere con cure mediche, più agenti e controllo della concorrenza.

## Primo risultato da ottenere

Il primo incremento non deve essere una demo grafica completa. Deve dimostrare questo flusso:

```text
ciotola vuota
    -> Logistics riceve la percezione
    -> Logistics richiede il rifornimento
    -> Feeding accetta il compito
    -> Feeding preleva una razione
    -> Feeding riempie la ciotola
    -> ambiente e test confermano il nuovo stato
```

Se questo scenario funziona, il progetto ha già validato ambiente condiviso, BDI, comunicazione, azioni e test di integrazione.

## Metodo di lavoro per ogni incremento

| Passaggio | Domanda da chiudere | Risultato atteso |
|---|---|---|
| Scenario | Quale storia osservabile deve funzionare? | Un flusso con stato iniziale e finale |
| Contratti | Quali messaggi e azioni servono? | Tabelle di payload, precondizioni ed effetti |
| Test | Come dimostriamo che funziona? | Criteri di accettazione automatizzabili |
| Implementazione | Qual è il minimo codice necessario? | Un incremento piccolo e avviabile |
| Retrospettiva | Cosa va corretto prima del prossimo scenario? | Decisioni annotate e debito esplicito |

## Definition of Done generale

Un incremento è concluso quando:

- parte da un unico comando documentato;
- funziona sul PC di sviluppo senza servizi configurati manualmente;
- ha almeno un test automatico dello scenario principale;
- produce log che mostrano agente, azione e identificativo del task;
- aggiorna la documentazione se cambia un contratto o una decisione.

## Mappa dei documenti

- [Architettura proposta](01_architettura_proposta.md)
- [Roadmap incrementale](02_roadmap_incrementale.md)
- [Primo incremento: alimentazione](03_primo_incremento_alimentazione.md)
- [Strategia di test](04_strategia_test.md)
- [Schemi degli agenti e dei flussi](schemi_agenti_flussi.md)
- [Linee guida generali](linee_guida_progetto.md)
