# MCP1.18.0+ems.2 — jednorazowa instalacja przez terminal HA

Nie wykonywać produkcyjnie bez osobnej zgody. Pakiet nie instaluje SolarEdge,
nie zmienia konfiguracji YAML/.storage, LEGACY, EMS2, G13, CWU ani falownika.

1. Pobierz artefakt z zatwierdzonego CI i przez dostępny menedżer plików HA
   prześlij go jako /config/mcp.zip. Nie pobieraj skryptu z nieznanego URL.
2. W terminalu serwera: `unzip /config/mcp.zip -d /config/mcp-ems2`.
   Katalog docelowy musi być nowy; nie nadpisuj istniejących plików.
3. `cd /config/mcp-ems2/mcp-package`
4. `sh install.sh prepare`

PREPARE sprawdza SHA pakietu i zgodność wszystkich plików rzeczywistego MCP z
baząems.1, odrzuca linki/dodatkowe pliki poza cache, wykonuje pełną kopię kodu do
/config/mcp_prepare_ems2_recovery/component i ponownie weryfikuje SHA.
Nie zatrzymuje Core. Jeśli backup już istnieje lub źródła są inne — zatrzymaj się,
nie usuwaj kopii i nie stosuj pakietu na siłę. Kody źródłowe/SHA pozostają na HA,
nie jest to niezależna kopia poza serwerem.

Dopiero po zgodzie na jednorazową wymianę kodu i restart oraz po sprawdzeniu
aktualnego stanu automatyki i drogi odzyskiwania:

`sh install.sh apply CONFIRM_CORE_RESTART`

Instalator ponownie sprawdza SHA, przygotowuje nowy katalog, wykonuje
`ha core check`, zatrzymuje Core, zamienia wyłącznie katalog komponentu MCP
(zachowując poprzedni kod), uruchamia Core. Używa nohup+setsid, aby odłączenie
terminala/Nabu Casa podczas restartu nie było wymaganym kanałem wykonania.
Wymaga obecności tych narzędzi; nie instaluje ich automatycznie.
Log: /config/mcp_prepare_ems2_recovery/apply.log.
Błąd CLI startu powoduje próbę przywrócenia poprzedniego kodu i startu Core.
Sukces CLI nie potwierdza załadowania MCP — trzeba zweryfikować połączenie OAuth,
tools/list (dwa nowe narzędzia plus stare), manifest i odmowę dostępu nieadmina.

Rollback kodu po zatwierdzeniu, z tego samego katalogu pakietu:

`sh install.sh rollback CONFIRM_CORE_RESTART`

Kod nieudanego wydania pozostaje w katalogu recovery. Nie odtwarzaj wcześniejszej
.storage, SQLite ani konfiguracji OAuth. Jeśli Core nie wraca, konieczna jest
rzeczywiście dostępna droga serwisowa niezależna od Core. Terminal przez Nabu Casa
nie jest automatycznie takim kanałem; samo istnienie procesu dodatku tego nie
dowodzi. Nadzorowany restart może rozłączyć zdalną sesję.

Test instalatora w CI używa izolowanych plików i symulowanego CLI `ha`.
Nie jest to test produkcyjnego Supervisora ani gwarancja dostępności Nabu Casa.
Test MCP/OAuth korzysta z rzeczywistego HAHTTP i walidatora OIDC podpisanych
RS256 tokenów; nie testuje interaktywnego logowania przeglądarkowego ChatGPT.
