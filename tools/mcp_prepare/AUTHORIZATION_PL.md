# Odrębny OAuth watchdoga — wymaga osobnej zgody, nie wykonywać teraz

## Potwierdzone ograniczenie uprawnień

Odczyt HACS produkcji: OIDC Provider v1.5.2. Oficjalny tag wskazuje commit
fccf769b56d2cc3fdc06d6b38bcdc3e96ab2c86c. Udostępnia authorization_code+PKCE
S256, osobnego klienta oraz scope openid. NIE udostępnia scope ograniczającego
narzędzia administratora MCP. Wybór openid zamiast profile/email/groups ogranicza
claims tożsamości, NIE uprawnienia narzędzi. Oddzielny klient nie jest piaskownicą.
Admin-only Options Inspect wymaga administratora HA. Takie poświadczenie ma
potencjalnie pełny dostęp administracyjny MCP przez maksymalnie3600s.
Bez zgody na ten zakres: NIE rejestrować klienta i NIE wydawać tokenu.

Alternatywa o rzeczywiście wąskich uprawnieniach wymagałaby ograniczeń po stronie
serwera obowiązujących również w przywracanym ems.1. Nie udajemy, że takie
ograniczenia istnieją. Nie wprowadzamy ich przy okazji tego pakietu.

## Dokładny zakres wymaganej zgody

- Dwa tymczasowe pliki statyczne w /config/www:
  ems-watchdog-auth.html oraz watchdog-auth.js; nie zawierają sekretów.
- Jeden NOWY klient `ems-watchdog-<losowe32hex>` w istniejącym OIDC, wyłącznie dla
  tej aktualizacji; zgoda właściciela przez standardowy ekran OIDC jako admin.
- Grant authorization_code, PKCE S256, scope openid, brak dodatkowych scopes,
  token z aud=client_id, TTL<=3600s. To obsługiwany wariant OIDC1.5.2;
  server-side JWTRS256, issuer i aud nadal podlegają normalnej walidacji.
- Prywatny plik /config/mcp_prepare_ems2_recovery/oauth-probe.json, tryb0600,
  wyłącznie własny token nowego klienta. Zakaz wklejania do rozmowy, zdjęć,
  GitHub, narzędzi agenta lub dziennika. Żadnych starych tokenów/sesji/kluczy.
- Po zakończeniu: revoke_client wyłącznie tego nowego client_id, sprawdzenie
  odmowy401 i usunięcie lokalnego pliku tokenu. Bez zmiany innych klientów.
- Zgoda na powyższe NIE obejmuje APPLY, restartu Core lub sterowania urządzeniami.

## Przepływ po zgodzie — wyłącznie istniejący Nabu Casa HTTPS

1. Przesłać nowy pakiet i zweryfikować SHA256SUMS. Nie używać starego install.sh.
   Z zatwierdzonego katalogu pakietu skopiować dwa pliki autoryzacji do /config/www.
2. Otworzyć w swojej przeglądarce istniejący adres Nabu Casa z końcówką
   /local/ems-watchdog-auth.html. Samo otwarcie niczego nie rejestruje.
   Dopiero przycisk rozpoczyna NOWĄ rejestrację. Użytkownik następnie wyraża
   zgodę w zwykłym formularzu OIDC. Agent nie odczytuje sesji przeglądarki.
3. Klient generuje losowe state i verifier, PKCE S256; credential klienta i
   verifier są tymczasowo w sessionStorage tej samej domeny. Token exchange
   odbywa się przez HTTPS do tej samej domeny. Kod autoryzacji usuwany z URL.
   Skrypt odrzuca stary/niezgodny callback i nie ponawia nieznanej wymiany.
4. Pobierany jest oauth-probe.json, bez refresh/id tokenów i bez client_secret.
   Przesłać plik przez istniejący interfejs plików HA do prywatnego recovery,
   nie przez rozmowę. Ustawić0600. W pliku muszą być cztery pola:
   access_token, public_origin, client_id i client_name.
   Sprawdzić właściciela pliku — watchdog odmówi innemu UID.
5. Wyłącznie odczytowy test z terminala katalogu nowego pakietu:

       python3 watchdog.py preflight

   Musi zakończyć się AUTHENTICATED_BASELINE_PASS. Sprawdza API, initialize,
   tools/list, administrator-only Options Inspect oraz odmowę błędnego tokenu.
   Nie uruchamia APPLY ani nie unieważnia klienta. Błąd -> zatrzymać się.
6. Dopiero OSOBNA zgoda na aktualizację pozwala uruchomić:

       sh install.sh apply CONFIRM_CORE_RESTART

   Nowy wrapper używa wyłącznie kontrolera ze wspólnym deploy.lock. Nie używać
   równolegle poprzedniego samodzielnego instalatora; należy wycofać go z użycia.
7. Po pełnym sprawdzeniu nowego MCP lub po jednorazowym rollbacku: kontroler
   odwołuje własnego klienta i sprawdza401. Nie ponawia nieznanego odwołania.
   Brak możliwości odwołania -> jawne REVOCATION_UNCONFIRMED_EXPIRY_PENDING;
   token wygasa po maksymalnie1h od wydania. Poświadczenie lokalne jest usuwane.
   Nie nazywać usunięcia pliku kryptograficznym wymazaniem kopii na dysku.
8. Usunąć tymczasowe dwa pliki www oraz pobraną kopię tokenu po odbiorze,
   zgodnie z udzieloną zgodą. Nie usuwać kopii oryginalnego komponentu.

## Dlaczego aud=client_id

W oficjalnym1.5.2 revoke_client usuwa klienta. Walidator odrzuca potem jego
client-bound JWT, nawet jeśli exp jeszcze nie upłynął. Dla aud=adresMCP usuwa
klienta, ale JWT może nadal przejść walidację do exp. Testy podpisane RS256
potwierdzają obie sytuacje. Dlatego helper odrzuca resource-bound JWT, id_token,
obcego klienta, inne scopes, TTL>3600s i mniej niż1800s ważności przed startem.
Nie wyłącza podpisu ani nie zmienia walidatora produkcji.

## Granice potwierdzenia

Testy JS używają WebCrypto i symulowanych odpowiedzi HTTP. Testy kryptograficzne
korzystają z prawdziwego kodu walidatora OIDC i podpisów, ale z atrapą typu HA.
Nie są dowodem pełnego browser-consent/token grant na produkcji. Ten przepływ
NIE został jeszcze uruchomiony na produkcji. Nie ma nowego portu publicznego.
Wrażliwe dane pozostają u właściciela i na jego serwerze; sessionStorage i plik
pobrany w przeglądarce nadal wymagają ochrony przed XSS i dostępem innych osób.

Przy awarii Core/Nabu Casa brak ręcznego zdalnego wejścia. Automatyczny rollback
jest jedną próbą, nie gwarancją odzyskania. Awaria dodatku/Supervisora/hosta lub
nieznany wynik zatrzymania Core nadal wymaga operatora. Instalacji nie wolno
uznać za w pełni zabezpieczoną na podstawie samych testów izolowanych.
