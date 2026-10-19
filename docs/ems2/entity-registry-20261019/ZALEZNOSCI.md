# Mapa zależności EMS2

```mermaid
flowchart TD
  A["Główny licznik kotłowni: A+B+C"] --> B["Bilans i historia kotłowni"]
  C["Podlicznik pompy"] --> D["Historia samej pompy"]
  E["Rotenso przez ESPHome"] --> F["CWU i CO: temperatury / nastawy"]
  G["SolarEdge M1 / I1 / B1"] --> H["Bilans budynku i magazynu"]
  I["Solcast / met.no / lokalna temperatura"] --> J["Prognozy SHADOW"]
  B --> J
  D --> J
  F --> J
  H --> J
  K["Workday i G13"] --> J
  J --> L["Plan oraz fingerprint"]
  L --> M["READ_ONLY: brak fizycznych poleceń"]
```

Podlicznik pompy jest częścią kotłowni: brak strzałki dodającej go do B.
Budynkowy licznik M1 obejmuje kotłownię: również nie dodawać jej drugi raz do H.
Bez potwierdzenia synchronizacji AC−M1 to oszacowanie diagnostyczne.

Zależności encja→encje znajdują się przy każdym rekordzie JSON; te nieodczytane
mają jawnie pustą listę i notę „not resolved”, nie oznacza to samodzielności.
Koszt dzienny ma zależności potwierdzone zgodnością liczb, ale nie formułą helpera.
Schemat nie przedstawia gotowej ścieżki sterowania ACTIVE.
