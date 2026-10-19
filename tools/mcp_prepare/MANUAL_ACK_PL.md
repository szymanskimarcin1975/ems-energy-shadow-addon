# MCP — jednorazowa aktualizacja z ręcznym ACK (wariant wybrany w zadaniu14)

Pakiet jest do kontroli. Przygotowanie NIE upoważnia do instalacji/restartu.
Nie tworzy klienta OAuth, nie wydaje ani nie zapisuje tokenu administratora.
Nie instaluje strony autoryzacji. Nie wywołuje urządzeń. Aktualizuje tylko MCP.
Używa wyłącznie istniejącego dostępu Supervisora z dodatku do kontroli Core/API.
Nie wypisuje tego poświadczenia, nie kopiuje go do plików i nie przekazuje agentowi.

## Przed zatwierdzonym uruchomieniem

- PREPARE istniejącego MCP PASS; kopia rzeczywistego kodu w
  /config/mcp_prepare_ems2_recovery/component oraz PREPARED. Niczego nie nadpisywać.
- Dostępne python3, ha, nohup i setsid w Terminal & SSH; /config zapisywalne,
  recovery prywatne0700, poprawny UID. Nie pobieramy dodatkowych narzędzi.
- Właściciel ma czas na kontrolę przez istniejące ChatGPT/MCP i Nabu Casa.
- Stary samodzielny /config/mcp-ems2/mcp-package/install.sh musi być wycofany
  z użycia, np. zachowany pod nazwą install.sh.disabled po zgodzie. Nowy kontroler
  odmówi startu, jeżeli w tym starym pliku pozostaje samodzielne ha core stop.
  Wszystkie przeglądane nowe wejścia współdzielą deploy.lock. Uprzywilejowany
  użytkownik/nieznany inny instalator nadal może tę konwencję ominąć.
- Brak wcześniejszego manual-watchdog-state.json/watchdog-state.json.
  Po nieznanym wyniku NIE usuwać dziennika w celu powtórzenia instalacji.
- Stan automatyki i okno restartu muszą być dopuszczone osobno. Ten pakiet
  nie ocenia bezpieczeństwa poleceń falownika i ich nie zmienia.

## Polecenia — dopiero po zgodzie na wdrożenie

Rozpakować NOWY pakiet do nowego katalogu, wejść do niego, sprawdzić SHA256SUMS.
Nie korzystać z wcześniejszego samodzielnego instalatora ani pakietu OAuth.

    python3 manual_ack_watchdog.py preflight

Wynik CODE_BACKUP_AND_LOCAL_API_PASS_OAUTH_MCP_NOT_TESTED potwierdza integralność
kodu/kopii i lokalny REST API. NIE jest potwierdzeniem OAuth ani nowych narzędzi.

Po osobnej zgodzie na instalację i zatrzymanie/start Core:

    sh install.sh apply CONFIRM_CORE_RESTART

Proces serwerowy jest odłączony od terminala przez nohup+setsid. Zatrzymuje Core,
zamienia wyłącznie zweryfikowany kod MCP i startuje Core. QUEUED nie oznacza
sukcesu. Zachowuje kopię poprzedniego i ewentualnie nieudanego kodu poza
custom_components. Nie przywraca .storage, SQLite, EMS2, CWU, CO ani G13.

Maksymalnie300s oczekiwania na Core/API po starcie, pojedyncze haCLI do90s.
Po uzyskaniu lokalnego API rozpoczyna się NIEPRZEDŁUŻALNE okno900s (15 minut) na ręczny ACK. Dostępność API nie dowodzi powrotu Nabu Casa ani gotowości OAuth/MCP. Opóźniony powrót zdalnego połączenia skraca rzeczywisty czas operatora; brak ACK powoduje rollback nawet gdy Core działa.
Status odczytuje się po powrocie Nabu Casa, z katalogu nowego pakietu:

    sh ack.sh status

Pokazuje identyfikator operacji, wyzwanie, SHA pakietu, diagnostic_operation_id
oraz termin. To metadane tej aktualizacji, bez tokenów. Wolno przekazać je do
istniejącego czatu MCP, aby skorelować kontrolę. Nie wystarczy widoczny ekran HA.

## Obowiązkowa kontrola istniejącym połączeniem MCP przed ACK

1. Odczytać aktualny stan Core przez dotychczasowe narzędzie.
2. Potwierdzić rzeczywistą odpowiedź z istniejącego połączenia OAuth — brak
   odpowiedzi/błąd uwierzytelnienia oznacza BRAK ACK. Nie kopiować tokenu.
3. Sprawdzić działanie dotychczasowych narzędzi, w tym odczyt
   ems_admin_options_inspect (bez Options Flow lub zmian encji).
4. Sprawdzić dostępność ems_admin_solaredge_prepare oraz
   ems_admin_solaredge_prepare_status. Odświeżenie katalogu klienta jest dopuszczalne;
   jeśli nowych narzędzi nie można wywołać w terminie, NIE potwierdzać ACK.
5. Wywołać prepare z diagnostic_operation_id z bieżącego statusu, a następnie
   status z TYM SAMYM ID. Oba wyniki muszą być COMPLETE i zgodne co do SHA
   manifestu. To kopia kodu SolarEdge, bez zapisu Modbus i bez restartu integracji.
   REJECTED/UNKNOWN/brak odpowiedzi -> NIE ponawiać nieznanej operacji, BRAK ACK.

Dopiero po tych pięciu kontrolach właściciel w terminalu wpisuje:

    sh ack.sh OPERATION12 CHALLENGE12

Zastąpić dwie wartości dokładnie: pierwsze12 znaków operation_id oraz challenge
z bieżącego statusu. Przeczytać listę kontroli i wpisać TAK wyłącznie po ich
pozytywnym wykonaniu. ACK_RECORDED nie oznacza odbioru — sprawdzić
ponownie `sh ack.sh status`, wymagane SUCCESS_ACK_CONSUMED.

ACK jest deklaracją uprawnionego operatora. Bez osobnego tokenu watchdog NIE
może samodzielnie dowieść testu OAuth, działania wszystkich narzędzi ani tego,
kto utworzył plik diagnostyczny. Kontroluje natomiast świeżość i integralność
kopii diagnostycznej, identyfikator, wyzwanie, SHA aktualizacji, aktywną blokadę
watchdoga i termin. Samego manifestu diagnostyki nie nazywamy dowodem OAuth.
Administrator lokalny może celowo sfałszować deklarację — poza granicą ochrony.

## Brak ACK i odzyskiwanie

Brak/spóźniony/błędny ACK lub utrata Core/API -> maksymalnie JEDNA próba
stop, przywrócenia zweryfikowanego oryginalnego kodu i startu Core. Licznik próby
zapisany trwale PRZED operacją. Brak pętli i brak automatycznego wznowienia po
restarcie procesu/hosta. ACK innej aktualizacji lub poprzednio wykorzystany nie działa.

ROLLED_BACK_API_ONLY_MCP_UNVERIFIED oznacza powrót kodu i API, NIE sprawdzony
OAuth. Po powrocie trzeba sprawdzić poprzednie połączenie MCP. Nieudany powrót:
RECOVERY_FAILED_OPERATOR_REQUIRED. Nie resetować serwera ani baz automatycznie.

Nieznany wynik stop/start Supervisora -> UNKNOWN_REQUIRES_OPERATOR. Nie można
bezpiecznie zamieniać plików, jeżeli nie potwierdzono zatrzymania Core. W tym
przypadku automatyczna próba może zostać wstrzymana, zamiast ślepo ponowić zapis.

Zerwana sesja Nabu Casa nie zatrzymuje odłączonego procesu. Zabicie watchdoga,
awaria dodatku/Supervisora/hosta/sieci/dysku nadal może uniemożliwić odzyskanie.
Brak niezależnego dostępu awaryjnego pozostaje ryzykiem. Nie jest to gwarancja
zdalnego odzyskania w każdej awarii. Nie używać starego instalatora jako drugiego
wykonawcy. Awaryjny ręczny powrót po zgonie procesu wymaga osobnej rekonsyliacji
stanu Core i kodu — nie kasowania blokad ani powtórnego APPLY.

## Preflight: uprawnienia Terminal & SSH i trwałość Pythona

Terminal & SSH 10.5.0 deklaruje hassio_api: true i rolę manager, ale nie
homeassistant_api: true. Ten sam SUPERVISOR_TOKEN może więc działać w API
Supervisora i otrzymać 401 w proxy Core. Nie zastępuj go tokenem użytkownika,
nie edytuj manifestu oficjalnego dodatku i nie ignoruj odmowy.
Nowy preflight wypisuje osobno PACKAGE, RECOVERY_CODE, PRODUCTION_CODE oraz
przyczynę odmowy API. Pierwsza niezaliczona kontrola blokuje dalsze etapy.
HTTP 401 potwierdza problem autoryzacji API, ale nie potwierdza poprawności kopii.

Bez przyznanego oficjalnie homeassistant_api w środowisku wykonawczym ten
wariant watchdoga NIE JEST GOTOWY do APPLY. Wymagane jest osobne zatwierdzenie
środowiska z tą deklaracją; nie jest to przełącznik zwykłych opcji dodatku SSH.
Alternatywny mechanizm zdrowia bez Core API wymaga osobnej implementacji
i testów, nie zastąpienia kontroli samym HTTP 200 Supervisora.

Core restart nie odtwarza kontenera Terminal & SSH. Zainstalowany Python
i odłączony proces pozostają dostępne przy samym restarcie Core, lecz nie
przy restarcie/aktualizacji/odtworzeniu dodatku SSH, Supervisora lub hosta.
Pakiet apks: [python3] w opcjach dodatku jest obsługiwaną metodą odtworzenia
Pythona przy starcie dodatku; nie utrzymuje jednak uruchomionego watchdoga.
Podczas operacji nie restartować/aktualizować dodatku, Supervisora ani OS.
Te opcje nie zostały zmienione na produkcji. Brak niezależnego dostępu
zdalnego nadal oznacza ryzyko wymagające uwzględnienia przed zgodą na restart.

Okno ACK: 900 sekund od gotowości lokalnego API po starcie Core. Powrót
Nabu Casa i weryfikacja istniejącego OAuth/MCP zużywają to okno; nie przedłużają
go. Po braku ACK możliwa jest jedna próba przywrócenia zweryfikowanego kodu.
Nie jest to gwarancja odzyskania Nabu Casa ani działania OAuth.
