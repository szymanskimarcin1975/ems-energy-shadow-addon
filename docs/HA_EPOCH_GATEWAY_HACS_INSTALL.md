# Instalacja HA Epoch Gateway — etap nieaktywny (HACS)

Ta integracja jest osobnym komponentem Python dla HA Core, a nie dodatkiem
Supervisor ani aplikacją AppDaemon. Nie rusza sterowania pompy, CWU, G13
ani istniejących encji SolarEdge.

## Warunki
- Dotychczasowy `EMS Energy SHADOW` .35 zostaje zainstalowany.
- `LEGACY` pozostaje właścicielem; `input_boolean.ems_battery_execution_authorized`
  pozostaje `off`.
- Przed instalacją wykonaj zwykłą kopię konfiguracji HA.
- Nie zmieniaj aktywnego skryptu `ems_battery_command_gateway` przed
  sprawdzeniem, że nowy komponent zarejestrował usługi.
- Integracja wersji 0.1.0 **nigdy nie wykonuje fizycznego dispatch**.

## Instalacja bez terminala
1. Home Assistant → HACS → menu ⋮ → **Custom repositories**.
2. Wklej adres:
   `https://github.com/szymanskimarcin1975/ems-energy-shadow-addon`
   i wybierz typ **Integration**.
3. Znajdź **EMS Epoch Gateway** i wybierz Download.
4. Zrestartuj **Home Assistant Core** w ustalonym bezpiecznym momencie
   (restart tymczasowo wstrzymuje automatyzacje LEGACY).
5. Ustawienia → Urządzenia i usługi → Dodaj integrację →
   **EMS Epoch Gateway** → Zatwierdź.
6. Narzędzia deweloperskie → Akcje:
   `ems_epoch_gateway.status` (odpowiedź wymagane).
   Oczekiwane `BLOCKED_SAFE`, `trusted_owner: LEGACY`,
   `trusted_epoch: 0`, `physical_dispatch_supported: false`.

Jeżeli HACS odrzuci repozytorium, nie omijaj instalatora i nie modyfikuj
`/config/custom_components` na ślepo. Zanotuj błąd.

## Co zawiera wersja 0.1.0
- Własny lokalny plik `/config/.storage/ems_epoch_gateway.sqlite` w trybie WAL,
  z `synchronous=FULL`.
- Transakcyjne rezerwacje `request_id` z wiązaniem planu, epoki,
  trybu, mocy i terminu ważności.
- Konflikt danych dla tego samego ID oraz status `PENDING` po przerwanym
  procesie; nigdy nie powtarza takiego żądania.
- Własny zaufany rekord epoki inicjalizowany jako LEGACY/0.
- Zewnętrzni zapisujący oraz rzeczywiste ograniczenia BMS/fallback
  nie są jeszcze udowodnione. Integracja nie pozwala przełączyć właściciela
  ani wykonać jakiegokolwiek zapisu do urządzenia.

## Ważne: nadal potrzebny jest drugi etap
Po instalacji administrator może bezpiecznie skierować odrzucane żądania
EMS2 z istniejącego skryptu HA do usługi `ems_epoch_gateway.dispatch`,
zachowując LEGACY bez zmian. To ustanowi trwałą ewidencję i dedup na
granicy HA, ale **nie odblokuje** poleceń baterii. Fizyczna obsługa wymaga
osobno wdrożonego pojedynczego piszącego oraz zweryfikowanego zakresu SOC,
no-export i bezpiecznego fallback, zanim można ją wdrożyć.

## Aktualizacja i wycofanie
Przy błędzie instalacji pozostaw `ems_battery_command_gateway` bez zmian.
Nie usuwaj automatycznie pliku SQLite z dziennikiem żądań podczas rollback.
Nigdy nie ustawiaj `EMS2 ACTIVE` ani flag zaufania na podstawie samego
statusu `BLOCKED_SAFE`.
