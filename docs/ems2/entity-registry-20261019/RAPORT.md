# EMS2 etap 3A — inwentaryzacja i przygotowanie integracji

Wersja 2026-10-19.1. Odczyt produkcji 19.10.2026, 21:46–21:49 CEST.
Termin użytkownika: 22.10.2026 16:00 Europe/Warsaw. Dokument wykonany wcześniej;
nie jest to monitoring ciągły do terminu. Nie uruchomiono zadania w tle.

## Wynik i zakres

472 potwierdzone encje: 271 GOTOWA do wykorzystania obserwacyjnego, 201 WYMAGA
POPRAWY; 159 encji niedostępnych/unknown/wyłączonych. Osobno 10 brakujących wymagań
bez wymyślonych entity_id. Kryteria statusu są konserwatywne; GOTOWA dla encji
sterującej oznacza wyłącznie rozpoznaną dostępną funkcję. Nigdy nie testowano zapisu.
Rejestr obejmuje wszystkie encje znalezione przez filtr funkcjonalny oraz pełne
listy, w tym wyłączone, 15 urządzeń: falownik, M1, B1, DERB1, dwa liczniki Zigbee,
sterownik pompy, termometry CO/bufora/zewnętrzne i dodatkowe urządzenia pomocnicze.
Nie jest wykazem wszystkich rejestrów urządzeń, niewystawionych przez integrację.

Nie powtarzano audytów, testów CI ani instalacji MCP. Nie wywołano żadnej usługi
sterującej, zapisu Modbus, ustawienia taryfy ani odświeżenia API Solcast.
Nie zmieniono automatyzacji, integracji, helperów, obrazu ani danych produkcji.
Stan bezpieczeństwa zachowany zgodnie z ostatnim odczytem: LEGACY, READ_ONLY,
autoryzacja OFF, epoch 0 i raportowane commands_sent 0. To nie jest deklaracja
ciągłego pomiaru fizycznych komend po zakończeniu odczytu.

## Licznik nadrzędny kotłowni — korekta właściciela instalacji

| Rola | Potwierdzona encja | Jednostka |
|---|---|---|
| Moc całej kotłowni | sensor.0x286847fffef5f4e9_power | W |
| Energia pobrana kotłowni | sensor.0x286847fffef5f4e9_energy | kWh |
| Drugi licznik kierunku, diagnostycznie | sensor.0x286847fffef5f4e9_produced_energy | kWh |
| Moce faz A/B/C | sensor.0x286847fffef5f4e9_power_a / _power_b / _power_c | W |
| Napięcia faz A/B/C | sensor.0x286847fffef5f4e9_voltage_a / _voltage_b / _voltage_c | V |
| Prądy faz A/B/C | sensor.0x286847fffef5f4e9_current_a / _current_b / _current_c | A |
| Moc samej pompy, podlicznik | sensor.0xa4c1389eebc44e6a_power_a | W |
| Energia samej pompy, podlicznik | sensor.0xa4c1389eebc44e6a_energy_a | kWh |

Skrócone sufiksy w tabeli służą czytelności; pełne literalne entity_id są w JSON.
IEEE potwierdzone zarówno w encjach urządzenia MQTT, jak i friendly_name w aktualnym
zigbee2mqtt/configuration.yaml: Licznik i Licznik pompa. Nazwa chmurowego urządzenia
„Licznik główny kotłowni” NIE dowodzi tego samego urządzenia — jego trzy encje Tuya
są wyłączone. Nie używać nazwy urządzenia zamiast IEEE.

Właściciel potwierdza układ trójfazowy i automatyczne przełączanie faz. Odczyt
21:48:55: total 1880 W; A 1789 W + B 92 W + C 0 W =1881 W. Różnica -1 W jest zgodna
z zaokrągleniem/niesynchronicznym raportem; to nie dowód pełnej synchronizacji.
C=0 W ma last_reported od 18:58:51Z. Nie traktować starego zera jako nowego pomiaru.
Natywna moc sumaryczna jest nadrzędna, suma faz tylko kontrolna lub przyszły
fallback po potwierdzeniu świeżości każdej fazy. Nie dodawać total do sumy faz.

Historia 19:35–19:48:20Z: import energy 213.81→214.17 kWh (+0.36 kWh), przy dodatniej
mocy; produced_energy pozostaje 7667.5 kWh. Zgodność z importem w badanym oknie,
ale bez kalibracji kierunku i bez obserwacji rzeczywistego przełączenia ATS.
Mediana odstępów ZMIAN Recorder 30.305 s, nie dowód okresu pomiaru urządzenia.
number.0x286847fffef5f4e9_data_report_duration=unknown. Brak dostępnych liczników
energii per-faza w rejestrze tego urządzenia; nie należy ich wymyślać.
Nie zmieniono signed_power/invert/energy_flow ani konfiguracji Zigbee2MQTT.

Podlicznik pompy jest PODZBIOREM głównego pomiaru. Nigdy nie sumować energii/mocy
obu liczników do całej kotłowni. Pomiar power_ab obejmuje kanały A+B tego podlicznika;
nie są to trzy fazy głównego licznika.

## Wykryte problemy danych i konfiguracji

1. configuration.yaml: wszystkie utility_meter kotlownia_g13_dzien/miesiac/rok
   mają source sensor.0xa4c1389eebc44e6a_energy_a — pompa, nie cała kotłownia.
   automation.ems_2_0_skrzynka_danych też zapisuje power_a/energy_a podlicznika
   pod nazwami kotlownia_*. BŁĘDNY ZAKRES. Propozycja zmiany jest wyłącznie
   dokumentacyjna. Przyszła migracja musi oznaczyć granicę historii, bez automatycznego
   resetowania liczników ani łączenia dawnych odczytów z nowym źródłem.
2. Stare sensor.rotenso_* i binary_sensor.rotenso_* to restored/unavailable.
   Aktywny sterownik to ESPHome „Sterownik Pompy”. Nie mapować starych nazw.
3. Nastawy CWU/CO nie mają jednostki w metadanych HA. Deployed YAML i kopie nastaw
   potwierdzają znaczenie °C; brak metadanych należy jawnie obsłużyć w mapowaniu.
4. Potwierdzenie CWU/CO w ESPHome to template zwracający stan encji number;
   nie niezależny odczyt temperatury zbiornika ani fizyczne zakończenie komendy.
5. Moc elektryczna ESPHome = prąd sprężarki × napięcie × stałe 0.85 /1000;
   jest estymacją. COP dzieli moc termiczną przez tę estymację. Do energii pompy
   używać podlicznika; nie używać estymacji do rozliczeń lub kalibracji COP.
6. binary_sensor.sterownik_pompy_pompka_obiegowa pochodzi z GPIO26 z inverted=true,
   filtrami 50 ms; nie jest potwierdzeniem z rejestru Modbus ani wszystkich pomp.
7. Brak bezpośredniego aktywnego trybu CWU/CO, natywnej temp. zewnętrznej Rotenso,
   binarnego stanu sprężarki i odczytu priorytetu CWU. Hz sprężarki może wspierać
   wnioskowanie, lecz nie zastępuje bezpośredniego potwierdzenia trybu.
8. sensor.solaredge_i1_dc_power jest w kW; template solaredge_pv_dc_power_w mnoży
   przez 1000. Ani nazwa template, ani moc AC/DC nie dowodzą czystej produkcji PV
   niezależnej od baterii w falowniku hybrydowym.
9. SOC B1=0%, available_energy≈8.847 kWh; nie traktować available_energy jako
   użytecznej energii zgromadzonej bez wyjaśnienia semantyki producenta.
10. M1 moc całkowita kW, fazy W; import licznika M1 to wartość ujemna mocy.
    Cloud SolarEdge pokazuje inne opóźnienia i konwencje; nie mieszać ze źródłem
    Modbus w spójnym snapshot. AC−M1 to warunkowy bilans budynku; nie dodawać B1.
11. Cost today 23.55 PLN zgadza się do 0.01 PLN z trzema aktualnymi dziennymi
    licznikami importu i stawkami. Duplikat _2=0.0 PLN, miesięczny=0.0 PLN.
    Formuł helperów UI nie można odczytać dostępnym narzędziem; sama zgodność
    liczb nie dowodzi ich definicji. Nie wybierać automatycznie duplikatu _2.
12. Disabled last_seen/linkquality i last_update ograniczają dowód dostępności.
    Nie włączano ich. HA last_reported nie jest fizycznym zegarem pomiaru.

## G13 i CWU — stan konfiguracji, nie nowe nastawy

Stawki robocze w aktywnym configuration.yaml i planning_sources:
0.6368 / 0.9235 / 1.5109 PLN/kWh (dolina/średnia/droga). Nie zweryfikowano umowy,
faktury ani oficjalnego cennika. Aktualny koszt całego budynku liczony z importu,
bez odejmowania eksportu; inne opłaty fakturowe nie są w ten sposób ustalone.

Przełącznik G13 korzysta z binary_sensor.workday_sensor_pl. Dzień roboczy:
07–13 średnia,16–21 droga, reszta dolina; dzień wolny/święto dolina.
Dwa wpisy Workday obsługują dziś i jutro — nie uznawać automatycznie za duplikat.
Automatyzacja taryfy kotłowni nie ma tak pełnej osłony unknown jak przełącznik
liczników budynku. Emhass REST template opiera dzień na weekday i godzinie
period_start bez jawnego przeliczenia do Europe/Warsaw/świąt — nie używać go jako
źródła zatwierdzonego kalendarza cen.

Czynna automation.ems_2_0_sterownik_cwu_v1: 50°C w dni pn–pt 00–07 i13–16,
sobota17–21, niedziela11–15; poza tym42°C. Wymaganie właściciela pozostaje
50°C do04:00 pn–pt. Odczyt nastawy i włączenie automatyzacji nie potwierdzają
osiągnięcia celu. Priorytet CWU wymagany, ustawienie instalatora niezweryfikowane.
Nie przywracano dawnych okien z opisów/historycznej wyłączonej automatyzacji.

## Prognozy i historia

Solcast: dziś/jutro mają detailedForecast po48 półgodzin i detailedHourly po24
pozycje; P10 istnieje niezależnie od select ustawionego estimate. API wykorzystanie
10/10, ostatni issue 19.10 14:50:07Z. Nie wymuszano odświeżenia. Wh→kWh /1000;
PV estimate kW wymaga przemnożenia przez czas slotu do energii kWh.
Weather.forecast_dom jest z met.no; prognoza godzinowa jest pobierana istniejącym
workerem do pliku, nie w atrybucie forecast encji. Nie wywoływano ponownie usługi.

Lokalna temperatura: sensor.0xa4c1385d4d396787_temperature, 8.64°C; prawidłowy input
w demand_report. Stara chmurowa temperatura zewnętrzna unavailable. Nie mylić
zewnętrznego czujnika z natywnym czujnikiem Rotenso.
Dane optymalizacji są w demand_report/planning_report, nie w nowych helperach.
Demand to persistence kotłowni, bez zidentyfikowanej zależności temperaturowej i bez
podziału CWU/CO. Model temperatury wyłączony. Historyczny profil całego budynku
z 16.10 zawiera AC−M1 hourly mean z ujemnymi minimami/niesynchronizacją; nie jest
kalibrowaną historią fizycznego poboru. Nie backfillować luk zerami.

EMHASS: dodatek istnieje; cykliczna automatyzacja off. Definicje rest_command
pozostały. Brak bieżących encji p_pv/p_load/p_batt/mpc_* w odczytanym katalogu;
nie zakładać ich udziału w runtime EMS2. Nie wywoływano optymalizacji EMHASS.

## Gotowość

SHADOW: NO-GO do aktualizacji produkcji — zachowane blokady etapu3: rzeczywisty
kod/digest .42, dostęp do options.json i SQLite, poprzedni obraz, zimny backup
/data + konfiguracja HA, wersjonowany obraz kandydata, jawnie zatwierdzony nowy
fingerprint. Dodatkowo wymagane uzgodnienie zakresu kotłowni i świeżości faz.
ACTIVE: NO-GO — powyższe oraz wyłączność, zakończenie starej komendy przy poll120,
fallback, no-export, stan/limity BMS, uzgodnienie epoki i niezależne potwierdzenia
urządzeń. SOC0% nie jest naprawiany sztuczną wartością rezerwy.

## Jeden następny krok

Uzyskać ODCZYT pełnego /data/options.json istniejącego dodatku i porównać
boiler_sources oraz sources z nadrzędnym miernikiem IEEE0x286847fffef5f4e9.
To ustali, czy poza znanymi utility_meter/loggerem błędny zakres dotyczy też
aktywnych danych obserwatora/plannera. Bez tokenów w rozmowie i bez zmiany opcji.

## Referencje spoza katalogu funkcjonalnego

referenced-entities-check.json zawiera dodatkową kontrolę obecności identyfikatorów
użytych w automatyzacjach. Brak w maszynie stanów nie dowodzi usunięcia z rejestru;
część referencji pochodzi z wyłączonych lub historycznie zablokowanych gałęzi.
Nie tworzyć encji zastępczych ani nie uaktywniać dawnych automatyzacji.
