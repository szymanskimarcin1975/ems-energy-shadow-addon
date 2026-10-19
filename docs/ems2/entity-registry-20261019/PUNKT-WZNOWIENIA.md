# Punkt wznowienia — etap 3A

Stan zapisany19.10.2026; termin22.10.2026 16:00 Europe/Warsaw.
Rejestr i mapowanie są snapshotem, nie bieżącą bazą stanów. Nie ma uruchomionego
zadania w tle. Odświeżyć tylko zmienne odczyty przed następną decyzją; nie powtarzać
pełnego audytu, instalacji MCP ani testów500/500 z PR24.

1. Odczytać prywatne /data/options.json z istniejącego dodatku EMS, aby sprawdzić
   faktyczne sources/boiler_sources i kanał aktualizacji, bez zmian i ujawniania tokenu.
2. Potwierdzić źródło świeżości fazy C i semantykę liczników import/export przez
   pasywną obserwację. Nie wymuszać zaniku ani przełączania faz.
3. Przygotować osobną propozycję korekty kotlownia_g13_* i skrzynki danych:
   główny IEEE0x286847fffef5f4e9 zamiast podlicznika; oznaczyć granicę historii.
4. Potwierdzić brakujące tryby pracy/prior CWU i niezależny readback nastaw;
   nie tworzyć nowych encji automatycznie i nie zapisywać rejestrów.
5. Kontynuować osobne bramki wdrożenia .43: obraz, manifest instalacji .42,
   spójny backup i wycofanie, konkretny nowy fingerprint do zatwierdzenia.

PR dokumentacyjny nie instaluje mapping.proposed.json. Flagi apply_approved=false,
deployable=false. LEGACY / READ_ONLY / execution OFF. Bez merge i ACTIVE.
