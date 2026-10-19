# Jednorazowy watchdog MCP — przygotowanie, NIE zgoda na instalację

Nie zmienia SolarEdge, EMS2, CWU, G13 ani SQLite. Nie edytuje bezpośrednio
.storage. Po zgodzie może odwołać wyłącznie własnego nowego klienta OAuth,
przez oficjalną usługę; pozostałych klientów nie zmienia. Działa w
Terminal & SSH, poza Core. Brak nowych portów. Nie zastępuje dostępu awaryjnego.

## Warunki przed uruchomieniem

1. Zweryfikowany PREPARE i oryginał w
   `/config/mcp_prepare_ems2_recovery/component`; brak wcześniejszego stanu
   watchdog-state.json. Nie usuwać stanu, aby powtórzyć nieznaną operację.
2. Dostępne python3 (stdlib z fcntl), ha, nohup, setsid i uprawnienia do /config.
   Pakiet niczego nie doinstalowuje. SUPERVISOR_TOKEN pobierany wyłącznie ze
   środowiska dodatku; nie wpisywać go w polecenia ani nie publikować.
3. Osobno autoryzowany, krótko żyjący token OAuth aktywnego administratora dla
   istniejącego zasobu MCP. Nie używać tokenu z ChatGPT ani zwykłego tokenu HA
   jako zamiennika. Nie zmieniać konfiguracji OAuth ani nie obchodzić wydawania
   tokenów. Nowy przepływ przeglądarkowy wymaga zgody i potwierdzenia na produkcji.
4. Prywatny plik oauth-probe.json w katalogu recovery, właściciel=proces dodatku,
   tryb0600, cztery pola: access_token, public_origin, client_id, client_name.
   Wyłącznie nowy klient z aud=client_id, scope openid, TTL<=3600s; patrz AUTHORIZATION_PL.md. Token musi wystarczyć na cały test, powrót i margines czasu.
   Nie umieszczać tego pliku w Git ani artefaktach. Nie podawać sekretu w argv.
5. Test preflight musi potwierdzić faktyczny API proxy Supervisora oraz endpoint
   MCP z dodatku, pozytywny OAuth, odmowę nieprawidłowego tokenu i admin-only
   odczyt Options Inspect. Wymagany identyfikator istniejącej integracji SolarEdge
   01M39WCJ1Y5FQTXXR2FZJBV76K. Nie wykonuje Options Flow ani zapisów.
6. Wszystkie operacje wymiany kodu muszą używać nowego install.sh. Stary
   samodzielny instalator nie współdzieli blokady — przed zatwierdzonym wdrożeniem
   trzeba wycofać go z użycia. Lokalny administrator nadal może ominąć blokadę;
   nie jest to mechanizm ochrony przed złośliwym administratorem.

## Minimalna procedura PO ODRĘBNEJ ZGODZIE

Przesłać i rozpakować pakiet watchdog w nowym katalogu /config/mcp-watchdog.
Nie nadpisywać kopii PREPARE. Zweryfikować SHA256SUMS. Najpierw przeprowadzić
`python3 watchdog.py preflight` z dodatku; dopóki nie ma poprawnego testu, NIE uruchamiać apply.
Polecenie uruchomienia po zatwierdzeniu, z katalogu pakietu:

    sh install.sh apply CONFIRM_CORE_RESTART

Proces odłącza sesję (nohup+setsid, stdin=/dev/null), blokuje wspólny deploy.lock
przez cały apply i jedną próbę rollbacku. Stan oraz dziennik fsync w katalogu
recovery. Drugi proces otrzymuje odmowę. Po restarcie procesu/hosta nie wznawia
nieznanej instalacji. Wymagana ręczna rekonsyliacja dziennika.

## Kontrola i ograniczenia

Preflight: stan oryginalny musi działać z OAuth. Po zmianie: API, initialize,
tools/list, nowe i stare nazwy narzędzi, admin-only odczyt. HTTP200 nie wystarcza.
Na gotowość maksymalnie300s plus ograniczone czasy żądań (5s każde); pojedyncza
operacja ha ma90s. Nie ma nieograniczonej pętli. Wersja oryginalna po rollbacku
musi ponownie przejść uwierzytelniony test, bez nowych narzędzi.

Nieznany wynik operacji Supervisora (np. timeout stop/start) NIE jest dowodem
zatrzymania Core. Mechanizm zachowuje stan UNKNOWN_REQUIRES_OPERATOR i nie
wykonuje równoległych zmian. Może to pozostawić serwer niedostępny.

Nieudane uruchomienie lub brak zdrowego MCP powoduje JEDNĄ próbę stop,
przywrócenia zweryfikowanego kodu i start. Brak zdrowia po tej próbie ->
RECOVERY_FAILED_OPERATOR_REQUIRED. Brak kolejnych restartów. Nie kopiuje baz.
Dziennik nie zawiera tokenów, HTTP body ani treści wyjątków.

Utrata sesji klienta nie zabija procesu odłączonego. Awaria dodatku, systemu,
dysku, sieci, Supervisora lub samego watchdoga nie jest objęta gwarancją.
Automatyczny test lokalny nie potwierdza zachowania produkcyjnego Nabu Casa.
Przy braku prawdziwego tokenu OAuth testy syntetyczne nie dają GO do instalacji.
