# SolarEdge Modbus Multi — rozpoznane możliwości, bez zapisów

Integracja solaredge_modbus_multi załadowana. Falownik SE10K-RWB48BFN4,
firmware0004.0025.0011, B1 SolarEdge Home Battery9.2kWh. Bez enumeracji adresów
rejestrów przez sieć; źródłem są encje HA. Wszystkie pełne encje i zakresy są
w registry.json; wartości max z HA nie są limitami bezpieczeństwa urządzenia.

| Funkcja | Encja | Zakres/opcje HA | Klasyfikacja |
|---|---|---|---|
| Tryb sterowania | select.solaredge_i1_storage_control_mode | Disabled, Maximize Self Consumption, Time of Use, Backup Only, Remote Control | zapis możliwy, nietestowany |
| Komenda magazynu | select.solaredge_i1_storage_command_mode | Solar Power Only (Off), Charge from Clipped Solar Power, Charge from Solar Power, Charge from Solar Power and Grid, Discharge to Maximize Export, Discharge to Minimize Import, Maximize Self Consumption | zapis możliwy; eksport baterii niedopuszczony w EMS |
| Tryb domyślny | select.solaredge_i1_storage_default_mode | jak opcje komendy | zapis możliwy, nietestowany |
| Ładowanie AC | select.solaredge_i1_ac_charge_policy | Disabled, Always Allowed, Fixed Energy Limit, Percent of Production | zapis możliwy, nietestowany |
| Rezerwa | number.solaredge_i1_backup_reserve |0–100%, aktualnie0 | nie utożsamiać z niezależną rezerwą BMS |
| Timeout | number.solaredge_i1_storage_command_timeout |0–86400s, aktualnie3600 | nie zmieniano |
| Limit ładowania | number.solaredge_i1_storage_charge_limit |0–1000000W w HA, aktualnie5000 | zakres HA nie jest dopuszczalną mocą fizyczną |
| Limit rozładowania | number.solaredge_i1_storage_discharge_limit |0–1000000W w HA, aktualnie5000 | jak wyżej |
| Limit AC | number.solaredge_i1_ac_charge_limit |unavailable, min=max0, brak jednostki | WYMAGA POPRAWY, nie używać |
| Odświeżenie | button.solaredge_i1_refresh | przycisk | nie naciskano; nie służy do dowodu samoczynnej świeżości |

Odczyty: status/firmware, AC/DC, prądy/napięcia faz, M1 net/import/export,
B1 SOC/status/temperatura/limity/pojemność oraz write_count. Maksymalna temperatura,
inverted power i last_update są zarejestrowane, ale wyłączone. DERB1 jest
alternatywnym endpointem tego samego falownika/baterii, nie drugim magazynem:
nie sumować energii ani pojemności B1+DERB1. DERB1 SOH unavailable.

Domena usług solaredge_modbus_multi zwróciła pusty katalog; funkcje sterowania
wystawiono jako encje number/select/button. Nie oznacza to braku zapisu Modbus.
Istniejąca domena ems_epoch_gateway wystawia status/emergency_stop/dispatch/
command_status/transition_owner/stop_command; nie wywoływano żadnej usługi.
Zgodność .42 dotyczy nazw/jednostek i rozpoznanych stanów. Zapis tylko przez
zatwierdzony algorytm/bramkę po osobnym zamknięciu bramek ACTIVE. Nie korzystać
z surowego number/select jako obejścia własności. Cztery encje ems_disabled_*
są wyłączone; nie włączać ich na podstawie inwentaryzacji.

B_STATUS_POWER_SAVING jest opcją w HA, ale poprawka walidatora pozostaje w PR24.
Nie jest dozwolonym statusem aktuacji BMS. Zachować kontrolę fingerprintów,
dynamicznych limitów, niespójności telemetrycznej i zakaz eksportu.
