# Dedykowany instalator MCP (bez instalacji produkcyjnej)

Oddzielny dodatek, niezależny od EMS SHADOW i HA Core. Python 3.14.8 jest
częścią obrazu. Nie ma portów publicznych, listenera HTTP, dostępu Docker,
nowych tokenów OAuth ani interfejsu sterowania urządzeniami.

Uprawnienia: homeassistant_api do autoryzowanego testu Core API;
hassio_api/manager do kontrolowanych operacji Core check/stop/start.
RW /config jest potrzebne do wymiany wyłącznie kodu MCP i kopii kodu.
Są to szerokie uprawnienia serwisowe, nie sandbox per plik. Kontener i
zatwierdzony pakiet są zaufanym kodem. Nie uruchamiać obcych pakietów.

## Wdrożenie po osobnej zgodzie
1. W sklepie dodatków dodać adres repozytorium z gałęzią #mcp-installer.
   Zainstalować wyłącznie MCP Controlled Installer.
2. Pakiet jest już w obrazie, sprawdzany podczas budowy i uruchomienia.
   Nie trzeba przenosić plików ani wpisywać poleceń w terminalu. Zachować
   domyślny SHA-256 oraz istniejący katalog kopii recovery w /config.
3. Uruchomić dodatek. Sam start NIE wykonuje instalacji ani restartu Core.
4. Przez administracyjną usługę hassio.addon_stdin dla tego dodatku przesłać:
   addon: local_mcp_controlled_installer oraz input: {"action":"preflight"}. Odczytać log: wszystkie kontrole muszą być PASS.
5. Dopiero po osobnej zgodzie na restart przesłać:
   {"action":"deploy","confirmation":"CONFIRM_CORE_RESTART"}.
6. Po powrocie Nabu Casa sprawdzić istniejący OAuth, stare i oba nowe narzędzia,
   wykonać świeżą diagnostykę dla diagnostic_operation_id z action=status.
   ACK przez tę samą usługę wymaga action=ack, operation (pierwsze 12 znaków),
   challenge i pięciu jawnych checks=true zgodnych z CHECKS watchdoga.
   Nie potwierdzać przed rzeczywistymi kontrolami. Status SUCCESS_ACK_CONSUMED
   kończy operację; samo przyjęcie ACK nie dowodzi zaakceptowania.

## Trwałość i odzyskiwanie
Core restart nie zatrzymuje dodatku. stdin EOF nie kończy kontenera; watchdog
pracuje jako proces potomny. Nie restartować/aktualizować dodatku, Supervisora
ani OS podczas operacji. Restart dodatku NIE wznawia wcześniejszego deploymentu:
trwały stage i journal blokują automatyczne ponowienie. Awaria hosta, dodatku
lub dysku pozostaje ryzykiem; brak niezależnego zdalnego dostępu nie jest naprawiany
przez ten dodatek. Obsługiwany zakres to restart samego Core.

ACK: nieprzedłużalne 900 s od gotowości lokalnego API. Powrót Nabu Casa
zużywa ten czas. Brak ACK lub błąd powoduje najwyżej jedną próbę przywrócenia
zweryfikowanego kodu ems.1; .storage, OAuth i SQLite nie są cofane. Wynik UNKNOWN
operacji Supervisora nie jest automatycznie ponawiany. Wtedy potrzebne jest
rozstrzygnięcie operatora; nie uruchamiać drugiego instalatora.

Nie wykonywano instalacji, restartu ani testu na produkcyjnym Supervisorze.
Testy CI kontenera i symulacje nie są dowodem działania Nabu Casa po awarii hosta.

## Odbiór stanu w 0.1.1
Po weryfikacji pakietu log pokazuje READY_PACKAGE_VERIFIED_WAITING_FOR_REQUEST_NO_APPLY.
Nie oznacza to wykonania preflight ani deploy. Stały raport /config/mcp_installer_status.yaml
można odczytać przez istniejące MCP get_config_file. IDLE_NO_DEPLOYMENT_RECORD
oznacza brak dziennika wdrożenia, nie pomyślną instalację. STATUS_UNAVAILABLE_DO_NOT_DEPLOY
blokuje decyzję o wdrożeniu. Kod zakończenia workera i jego aktywność są raportowane.
Nie aktualizować/restartować dodatku przy aktywnym lub nierozstrzygniętym deployment.
Istniejący stage jest tylko weryfikowany bajt po bajcie, nigdy nadpisywany; ponowny
start dodatku nie uruchamia ani nie wznawia instalacji.

0.1.2: odczytowe inspect i raport wskazują zgodność produkcyjnego kodu, kopii,
obecność starego instalatora, dziennika i aktywnej blokady. Nie wykonują
Core stop/start ani nie odblokowują APPLY. UNKNOWN nie uprawnia do aktualizacji
instalatora. Nie wycofywać poprzedniego instalatora bez rozstrzygnięcia stanu.
