# EMS Energy SHADOW 0.1.0 — wersja publikacyjna

Dodatek eksperymentalny amd64. Odczytuje wyłącznie stany HA, bez wywołań usług,
MQTT i sterowania. Python3.12, polling20s, osobny obserwator i nadzorca.

## Ustawienia wymagane

Wypełnij sources w konfiguracji dodatku lokalnymi encjami. Publiczne wartości
są puste. Neutralny przykład jest w tests/example_options.json.

| Opcja | Wymagany pomiar |
|---|---|
| inverter_w | Moc AC falownika W, z uwzględnieniem magazynu po stronie AC |
| grid_kw | Wymiana z siecią kW: dodatnia eksport, ujemna import |
| boiler_w | Moc całej kotłowni W, nieujemny pobór |
| heatpump_w | Moc pompy W, podkategoria kotłowni |
| boiler_kwh | Narastająca energia kotłowni kWh |
| heatpump_kwh | Narastająca energia pompy kWh |
| workday | binary_sensor: on dzień roboczy, off dzień wolny; kalendarz PL |

Brak ustawień, błędny domain lub duplikaty blokują start przed DB/API.
Nie ma domyślnych źródeł ani wyszukiwania podobnych encji. Istnienie i znaczenie
źródeł trzeba potwierdzić lokalnie. Niedostępne dane nie stają się zerami.
Zmiana źródeł przy istniejącej bazie jest blokowana. Starsza baza bez odcisku
źródeł również wymaga osobnego planu migracji, jeśli zawiera próbki.

## Obserwacja i dane

Budynek = moc AC falownika - wymiana z siecią; dom=budynek-kotłownia.
Pompa nie jest dodawana ponownie. Warunek fizyczny: źródła w zgodnym zakresie.
Kontrola świeżości i synchronizacji, bez całkowania przez niewiarygodne luki.
G13 Europe/Warsaw: lato19–22 droga, zima16–21 droga;7–13 średnia;
pozostałe godziny oraz dni wolne tania. Brak Workday wyklucza wiarygodne
przypisanie. To zużycie odbiorników, nie koszt energii zakupionej z sieci.

SQLite prywatna/data/shadow.sqlite, WAL+FULL, lock jednej instancji.
Nadzorca ponawia po awarii10s; stopSIGTERM nie ponawia. Błędna konfiguracja
kończy uruchomienie zkodem78. Nie jest to watchdog zawieszonego procesu.
backup:cold zatrzymuje dodatek podczas kopii. Zachować kopię przed usunięciem.
Raport ems_shadow/report.yaml w katalogu konfiguracji HA jest odczytywalny
przez MCP get_config_file po włączeniu dostępu do konfiguracji. Brak portów
publicznych. W raporcie nie ma identyfikatorów źródeł, tokenów ani surowych stanów.
Sprawdzać generated_at; running samodzielnie nie potwierdza świeżości.

## Uprawnienia i instalacja testowa

homeassistant_api umożliwia technicznie szersze API; kod wykonuje tylkoGET.
Mount konfiguracji HA jest rw dla eksportu raportu; kod zapisuje tylko raport,
lecz uprawnienie kontenera nie jest ograniczone do podkatalogu.
Nie wpisywać sekretów do repozytorium ani parametrów adresu repozytorium.
Supervisor przekazuje token w środowisku, bez ręcznego wpisywania.

Po zatwierdzeniu: kopia HA, instalacja jednej kopii dodatku, uzupełnienie sources,
start, kontrola logów/raportu po kilku minutach i po1h. Obserwacja24–48h.
Nie uruchamiać produkcyjnych liczników bez potwierdzenia topologii i jakości.
Wycofanie: stop, wyłączyć autostart, backup dodatku, dopiero odinstalowanie.
Nie resetować istniejących statystyk.


## 0.1.2 — jawny, oddzielny rejestr

Wymagane ustawienie `ledger_id`, np. `corrected_sources_20261012`.
Dozwolone: małe litery, cyfry, `_`, `-`, pierwsza litera, do 64 znaków.
Pusta wartość, `legacy` i `shadow` są niedozwolone: obserwacja pozostaje wyłączona.
Nie ma automatycznej migracji ani automatycznego wyboru innego rejestru.

Baza: `/data/ledgers/<ledger_id>/shadow.sqlite`; odcisk siedmiu źródeł
jest przechowywany osobno w każdej bazie. Zmiana źródeł w tym samym rejestrze
nadal blokuje start. Nowy rejestr zaczyna od próbki bazowej, bez historii i
bez naliczania energii za przestój. Restart z tym samym ID kontynuuje dane.
Globalna blokada `/data/observer.lock` obejmuje wszystkie identyfikatory.
Stara `/data/shadow.sqlite` oraz WAL/SHM nie są otwierane, modyfikowane ani usuwane.

Raport `ems_shadow/report.yaml` dotyczy wyłącznie aktualnie wybranego rejestru:
`ledger_id`, `sources_digest`, `addon_version`, `generated_at` jednoznacznie
określają pochodzenie. Nie łączy wyników rejestrów. Po nieudanym starcie może
pozostać stary raport: zawsze sprawdzaj wersję, ID i czas. Bazy innych rejestrów
pozostają dostępne do późniejszej analizy, ale raport aktywny je zastępuje.

Aktualizacja dopiero po zgodzie na publikację i wdrożenie:
zatrzymać dodatek, wykonać zimną kopię dodatku wraz z całym `/data`, opcjami i
raportem; użyć aktualizacji zamiast odinstalowania. Zachować siedem źródeł,
wpisać jawne nowe ID. Przed startem zweryfikować ustawienia. Po osobnej zgodzie
na start sprawdzić ID/digest, świeżość, baseline i jakość raportu.
Cofnięcie: zatrzymać, zachować także nowy `/data` i raport; przywrócić zimną
kopię 0.1.1 wraz z jej opcjami. Nie usuwać nowych rejestrów. 0.1.1 może nadal
blokować start przy pierwotnej niezgodności źródeł — rollback nie usuwa przyczyny.
