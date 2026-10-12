# Przygotowana poprawka0.1.1 — nie publikować przed sukcesemCI

## Problem i zakres

W0.1.0 capture wybierał last_reported przez dict.get z fallbackiem tylko przy
braku klucza. last_reported:null nie uruchamiał fallbacku. Brak encji wAPI
również dawał None. dt przekazywał ten obiekt do fromisoformat bez kontroli
typu, więc błąd nie wskazywał roli źródła. Nie da się ustalić konkretnej roli
wyłącznie z ogólnego komunikatu starej wersji. Nie zakładać, że każde takie
zdarzenie wynika znull: może to być brak encji albo inny nieprawidłowy typ.

W0.1.1: kolejność last_reported,last_updated,last_changed; każdy kandydat musi
być niepustym ISO8601 ze strefą. Brak prawidłowego kandydata pozostaje None.
Nigdy nie podstawiamy now() ani zera. Dotychczasowe kontrole wieku/skew nadal
odrzucają stare lub niesynchronizowane wartości. Raport source_diagnostics
pokazuje rolę, entity_present, timestamp_field i typy pól, bez encji/sekretów.
Quality nazywa błędne pole (np.invalid_timestamp_inverter_time).

Regresja na strukturze stateRESTHA: entity_id,state,attributes,last_changed,
last_updated i opcjonalne last_reported:null. Syntetyczne encje/pomiary,
brak surowych danych użytkownika. CI mock zwraca null i wymaga fallbacku.

## Aktualizacja po potwierdzeniuCI i zatwierdzeniu publikacji

1. Pozostawić dodatek zatrzymany; zachować kopię dodatku z/data i jego opcji.
2. Potwierdzić buildamd64 i smoke tej poprawki. Następnie osobna publikacja
   do repo dodatków, bez danych prywatnych; version0.1.1 umożliwi aktualizację.
3. W sklepie odświeżyć repo, wybrać Update zamiast odinstalowania/reinstalacji.
4. Nie zmieniać siedmiu sources. Digest i schematSQLite pozostają bez zmian.
5. Po zgodzie uruchomić; pierwsza próbka po restarcie jest baseline, bez
   naliczania przestoju. Sprawdzić source_diagnostics i jakość przezMCP.
6. Zachować stare błędne próbki i unallocated; nie przeliczać ich wstecz
   i nie przedstawiać jako poprawnej energii taryfowej.
7. Cofnięcie tylko z kopią dodatku/danych; nie usuwaćSQLite, nie resetowaćG13.

Brak odczytu surowych próbekSQLite przez obecne MCP ogranicza diagnozę
konkretnego źródła w0.1.0. Nowy raport umożliwia odróżnienie błędu konfiguracji
encji od błędu timestamp bez ujawniania identyfikatorów publicznie.
