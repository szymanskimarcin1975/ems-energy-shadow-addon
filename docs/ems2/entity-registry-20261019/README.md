# EMS2 — rejestr i mapowanie encji, etap 3A

Wersja2026-10-19.1. Rejestr472 encji potwierdzonych w produkcyjnym HA oraz10 braków
funkcjonalnych. Dokumentacja i propozycja mapowania, bez zmian runtime.

- RAPORT.md — ustalenia, błędny zakres kotłowni, gotowość i jeden następny krok.
- registry.json — jeden kompletny maszynowy rejestr ze wszystkimi wymaganymi polami.
- REJESTR.md — czytelny indeks wszystkich rekordów.
- mapping.proposed.json — propozycja, nie konfiguracja do automatycznego załadowania.
- SOLAREDGE-MOZLIWOSCI.md — wystawione możliwości odczytu/zapisu.
- ZALEZNOSCI.md — mapa zależności.
- evidence-summary.json — sumy faz, kierunek energii i rachunek kosztu.
- automation-dependencies.json — odczytane referencje encji, bez zmieniania automatyzacji.
- PUNKT-WZNOWIENIA.md — dokładne następne operacje.

Stan czasowy:19.10.2026 21:46–21:49 CEST. Nie traktować dostępności w snapshot jako
ciągłej gwarancji. Ranges z metadanych HA nie zastępują limitów BMS/urządzenia.
Wymagania bez encji mają null, bez zgadywania entity_id. Żaden sekret, token,
klucz MQTT, adres API ani pełna konfiguracja sieci nie są częścią tej dokumentacji.

Powiązania: PR24 d10e5f4c250ad1e47634351dcbc5826ef6b29388, CI500 PASS; dokumentacja
nie zmienia tamtego PR, wersji .42 ani czterech zatwierdzonych plików.

- referenced-entities-check.json — potwierdzona nieobecność dawnych referencji;
  nazwy usług zostały wykluczone z tej listy.
