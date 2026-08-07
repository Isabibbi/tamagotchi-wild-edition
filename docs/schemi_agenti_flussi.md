# Schemi e Flussi: Wildlife Rescue Center (CRAS)

## Stato di implementazione

Lo scenario **Cure Mediche** descritto in questo documento è implementato e
testato. Veterinary e Logistics usano piani AgentSpeak reali, mentre Environment
valida ogni transizione dell'animale e conserva lo stato autorevole.

Esecuzione:

```powershell
.\.my_sdai\Scripts\python.exe -m tamagotchi_wild
```

Risultato verificato: animale `sick → in_outbound_transport → in_treatment →
treated → in_return_transport → healthy`, restituito alla posizione della gabbia.

Questo documento illustra l'architettura logica, i ruoli degli agenti, la macchina a stati degli animali e i diagrammi di sequenza del sistema.

## 1. Dettaglio degli Operatori (Agenti) e Interazioni

```mermaid
graph TD
    classDef vet fill:#f9d0c4,stroke:#333,stroke-width:2px;
    classDef log fill:#c4e3f9,stroke:#333,stroke-width:2px;
    classDef feed fill:#dcf9c4,stroke:#333,stroke-width:2px;
    classDef area fill:#eee,stroke:#999,stroke-dasharray: 5 5;

    V(Veterinary Agent):::vet
    L(Logistics Agent):::log
    F(Feeding Agent):::feed
    
    TR[[Treatment Room]]:::area
    CA[[Cage Area]]:::area
    MS[[Medical Storage]]:::area
    FS[[Food Storage]]:::area
    
    V -- "1. Task: Porta animale" --> L
    V -. "Preleva medicinali" .-> MS
    V -. "Cura animale" .-> TR
    
    L -. "Preleva/Riporta animale" .-> CA
    L -. "Consegna animale" .-> TR
    L -- "2. Task: Riempi ciotole" --> F
    
    F -. "Preleva razioni" .-> FS
    F -. "Distribuisce cibo" .-> CA
```

### 🩺 Veterinary Agent (Veterinario)
* **Dove può muoversi:** `Treatment Room`, `Medical Storage`.
* **Cosa percepisce:** Salute degli animali, disponibilità medicinali.
* **Azioni fisiche:** Preleva medicinali, Cura l'animale (cambia stato).
* **Comunicazioni:** Richiede alla Logistica di portare/riportare un animale.

### 📦 Logistics Agent (Addetto Logistica)
* **Dove può muoversi:** `Cage Area`, `Treatment Room`.
* **Cosa percepisce:** Stato gabbie (ciotole, presenza animali), messaggi ricevuti.
* **Azioni fisiche:** Carica, trasporta e scarica animali.
* **Comunicazioni:** Conferma consegna paziente, Delega riempimento cibo al Feeding Agent.

### 🍎 Feeding Agent (Addetto Alimentazione)
* **Dove può muoversi:** `Food Storage`, `Cage Area`.
* **Cosa percepisce:** Richieste della Logistica, quantità di cibo.
* **Azioni fisiche:** Preleva cibo, Riempie ciotole.

---

## 2. Ciclo di Vita dell'Animale (Risorsa Passiva)

L'animale non prende decisioni; il suo stato viene modificato esclusivamente dalle azioni degli agenti sull'ambiente.

```mermaid
stateDiagram-v2
    classDef danger fill:#f9c4c4,stroke:#333,stroke-width:2px;
    classDef transit fill:#c4e3f9,stroke:#333,stroke-width:2px;
    classDef safe fill:#dcf9c4,stroke:#333,stroke-width:2px;

    [*] --> MALATO : Arrivo al CRAS
    MALATO:::danger --> IN_TRASPORTO_1 : Logistics lo preleva
    IN_TRASPORTO_1:::transit --> IN_VISITA : Rilasciato in Treatment Room
    IN_VISITA:::danger --> CURATO : Veterinario agisce
    CURATO:::safe --> IN_TRASPORTO_2 : Logistics lo preleva
    IN_TRASPORTO_2:::transit --> SANO_IN_GABBIA : Rilasciato in Cage Area
    SANO_IN_GABBIA:::safe --> [*] : Rilasciato in natura
```

---

## 3. Diagrammi di Sequenza (Flussi Operativi)

### A) Scenario "Cure Mediche"
```mermaid
sequenceDiagram
    autonumber
    participant V as 🩺 Veterinary
    participant L as 📦 Logistics
    participant E as 🌍 Environment (Griglia)
    
    Note over V,E: Fase di trasporto
    V->>E: Percepisce Animale Malato (in Cage)
    V->>L: ✉️ REQUEST: "Portami l'Animale X"
    L->>E: Si muove verso Cage Area e preleva Animale
    L->>E: Si muove verso Treatment Room e lo rilascia
    L->>V: ✉️ INFORM: "Paziente pronto"
    
    Note over V,E: Fase di cura
    V->>E: Azione: Cura l'animale
    E-->>V: (Stato Animale X diventa "Curato")
    
    Note over V,E: Fase di rientro
    V->>L: ✉️ REQUEST: "Riporta Animale X"
    L->>E: Preleva Animale X e lo riporta in Cage Area
```

### B) Scenario "Nutrizione"
```mermaid
sequenceDiagram
    autonumber
    participant L as 📦 Logistics
    participant F as 🍎 Feeding
    participant E as 🌍 Environment (Griglia)

    Note over L,E: Fase di monitoraggio
    L->>E: Pattuglia la Cage Area
    E-->>L: Percezione: "Ciotola vuota"
    
    Note over L,E: Fase di delega
    L->>F: ✉️ REQUEST: "Cibo necessario"
    F->>E: Va al Food Storage, preleva cibo
    F->>E: Va in Cage Area, riempie ciotola
    F->>L: ✉️ INFORM: "Ciotola riempita" (Opzionale)
```
