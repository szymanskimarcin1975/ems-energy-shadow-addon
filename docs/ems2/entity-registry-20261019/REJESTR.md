# Rejestr encji EMS2 — 2026-10-19.1

Źródło: bezpośrednie odczyty produkcyjnego HA, 21:46–21:49 CEST. Pełne pola, zależności, kryteria świeżości i zakresy znajdują się w registry.json. GOTOWA oznacza przydatność rekordu do odczytu/SHADOW, nigdy gotowość ACTIVE. Nie udowodniono czasu pomiaru urządzeń. Braki mają entity_id=null, bez wymyślonych identyfikatorów.

| Entity ID | Nazwa / przeznaczenie | Integracja | Typ | Jednostka | Stan | Dostępność | Priorytet | Status |
|---|---|---|---|---|---|---|---|---|
| automation.emhass_cykliczna_aktualizacja_planu_ai | Discovered supporting/legacy entity: EMHASS: Cykliczna Aktualizacja Planu (AI) | HA automation YAML | sterowanie | niepodana | off | AVAILABLE | pomocnicza | GOTOWA |
| automation.ems_2_0_predykcyjne_zarzadzanie_magazynem_i_pompa | Discovered supporting/legacy entity: EMS 2.0: Predykcyjne zarządzanie magazynem i pompą | HA automation YAML | sterowanie | niepodana | off | AVAILABLE | pomocnicza | GOTOWA |
| automation.ems_2_0_skrzynka_danych | Discovered supporting/legacy entity: EMS 2.0: Skrzynka danych | HA automation YAML | sterowanie | niepodana | on | AVAILABLE | pomocnicza | GOTOWA |
| automation.ems_2_0_sterownik_cwu_v1 | Discovered supporting/legacy entity: EMS 2.0 — Sterownik CWU v1 | HA automation YAML | sterowanie | niepodana | on | AVAILABLE | pomocnicza | GOTOWA |
| automation.ems_2_0_taryfa_g13_licznika_kotlowni | Discovered supporting/legacy entity: EMS 2.0: Taryfa G13 licznika kotłowni | HA automation YAML | sterowanie | niepodana | on | AVAILABLE | pomocnicza | GOTOWA |
| automation.ems_automatyzacja_zarzadzania_pompa_ciepla_tryb_zimowy_g13 | Discovered supporting/legacy entity: EMS: Automatyzacja Zarządzania Pompą Ciepła i Magazynem (Tryb Zimowy G13) | HA automation YAML | sterowanie | niepodana | off | AVAILABLE | pomocnicza | GOTOWA |
| automation.ems_powiadomienie_koniec_pracy | Discovered supporting/legacy entity: EMS: Powiadomienie - Koniec Pracy | HA automation YAML | sterowanie | niepodana | off | AVAILABLE | pomocnicza | GOTOWA |
| automation.ems_powiadomienie_start_pracy | Discovered supporting/legacy entity: EMS: Powiadomienie - Start Pracy | HA automation YAML | sterowanie | niepodana | off | AVAILABLE | pomocnicza | GOTOWA |
| automation.ems_przelacznik_taryf_g13_dzien_miesiac_rok | Discovered supporting/legacy entity: EMS: Przełącznik Taryf G13 (Dzień/Miesiąc/Rok) | HA automation YAML | sterowanie | niepodana | on | AVAILABLE | pomocnicza | GOTOWA |
| automation.notyfikacja_smart_grid_magazyn_pelny | Discovered supporting/legacy entity: NOTYFIKACJA: Smart Grid - Magazyn Pełny | HA automation YAML | sterowanie | niepodana | off | AVAILABLE | pomocnicza | GOTOWA |
| automation.pompa_alarm_brak_przeplywu_wody_2 | Discovered supporting/legacy entity: POMPA: ALARM - Brak Przepływu Wody! | HA automation YAML | sterowanie | niepodana | unavailable | UNAVAILABLE_OR_UNKNOWN | pomocnicza | WYMAGA POPRAWY |
| automation.pompa_ciepla_alarm_awarii_bez_dzwieku | Discovered supporting/legacy entity: Pompa ciepla alarm awarii bez dzwieku | HA automation YAML | sterowanie | niepodana | on | AVAILABLE | pomocnicza | GOTOWA |
| automation.pompa_ciepla_g13_grzanie_cwu_w_tanich_godzinach | Discovered supporting/legacy entity: Pompa Ciepła: G13 - Grzanie CWU w tanich godzinach | HA automation YAML | sterowanie | niepodana | off | AVAILABLE | pomocnicza | GOTOWA |
| automation.pompa_ciepla_smart_grid_cwu | Discovered supporting/legacy entity: Pompa Ciepła: Smart Grid CWU (Kaskada 60/55 + LOGGER) | HA automation YAML | sterowanie | niepodana | unavailable | UNAVAILABLE_OR_UNKNOWN | pomocnicza | WYMAGA POPRAWY |
| automation.pompa_skrzynia_biegow_v37 | Discovered supporting/legacy entity: EMS G13 - Pompa Ciepła i Magazyn SolarEdge | HA automation YAML | sterowanie | niepodana | unavailable | UNAVAILABLE_OR_UNKNOWN | pomocnicza | WYMAGA POPRAWY |
| automation.pompa_watchdog_podtrzymanie_modbus | Discovered supporting/legacy entity: POMPA: Watchdog (Podtrzymanie Modbus) | HA automation YAML | sterowanie | niepodana | on | AVAILABLE | pomocnicza | GOTOWA |
| automation.pompa_watchdog_podtrzymanie_modbus_2 | Discovered supporting/legacy entity: POMPA: Watchdog (Podtrzymanie Modbus) | HA automation YAML | sterowanie | niepodana | unavailable | UNAVAILABLE_OR_UNKNOWN | pomocnicza | WYMAGA POPRAWY |
| automation.zasilanie_g13_ladowanie_magazynu_na_podstawie_solcast | Discovered supporting/legacy entity: Zasilanie: G13 - Ładowanie magazynu na podstawie Solcast | HA automation YAML | sterowanie | niepodana | off | AVAILABLE | pomocnicza | GOTOWA |
| automation.zasilanie_g13_zakonczenie_ladowania_powrot_do_autokonsumpcji | Discovered supporting/legacy entity: Zasilanie: G13 - Zakończenie ładowania (Powrót do autokonsumpcji) | HA automation YAML | sterowanie | niepodana | off | AVAILABLE | pomocnicza | GOTOWA |
| binary_sensor.kotlownia_problem | Discovered supporting/legacy entity: Kotłownia  Problem | tuya | odczyt | niepodana | unavailable | UNAVAILABLE_OR_UNKNOWN | pomocnicza | WYMAGA POPRAWY |
| binary_sensor.pompa_pracuje_animacja | Discovered supporting/legacy entity: Pompa Pracuje Animacja | template | odczyt | niepodana | on | AVAILABLE | pomocnicza | GOTOWA |
| binary_sensor.rotenso_4_way_valve | Discovered supporting/legacy entity: Rotenso 4-Way Valve | UNCONFIRMED / restored legacy | odczyt | niepodana | unavailable | UNAVAILABLE_OR_UNKNOWN | pomocnicza | WYMAGA POPRAWY |
| binary_sensor.rotenso_aux_heater_1 | Discovered supporting/legacy entity: Rotenso Aux Heater 1 | UNCONFIRMED / restored legacy | odczyt | niepodana | unavailable | UNAVAILABLE_OR_UNKNOWN | pomocnicza | WYMAGA POPRAWY |
| binary_sensor.rotenso_compressor_running | Discovered supporting/legacy entity: Rotenso Compressor Running | UNCONFIRMED / restored legacy | odczyt | niepodana | unavailable | UNAVAILABLE_OR_UNKNOWN | pomocnicza | WYMAGA POPRAWY |
| binary_sensor.rotenso_flow_switch | Discovered supporting/legacy entity: Rotenso Flow Switch | UNCONFIRMED / restored legacy | odczyt | niepodana | unavailable | UNAVAILABLE_OR_UNKNOWN | pomocnicza | WYMAGA POPRAWY |
| binary_sensor.rotenso_grzalka_aux | Discovered supporting/legacy entity: Rotenso Grzalka Aux | UNCONFIRMED / restored legacy | odczyt | niepodana | unavailable | UNAVAILABLE_OR_UNKNOWN | pomocnicza | WYMAGA POPRAWY |
| binary_sensor.rotenso_praca_pompy_wody | Discovered supporting/legacy entity: Rotenso Praca Pompy Wody | UNCONFIRMED / restored legacy | odczyt | niepodana | unavailable | UNAVAILABLE_OR_UNKNOWN | pomocnicza | WYMAGA POPRAWY |
| binary_sensor.rotenso_water_pump | Discovered supporting/legacy entity: Rotenso Water Pump | UNCONFIRMED / restored legacy | odczyt | niepodana | unavailable | UNAVAILABLE_OR_UNKNOWN | pomocnicza | WYMAGA POPRAWY |
| binary_sensor.solaredge_i1_grid_status | Discovered supporting/legacy entity: Solaredge I1 Grid Status | solaredge_modbus_multi | odczyt | niepodana | on | AVAILABLE | pomocnicza | GOTOWA |
| binary_sensor.status_pompy_cwu | Discovered supporting/legacy entity: Status Pompy CWU | template | odczyt | niepodana | off | AVAILABLE | pomocnicza | GOTOWA |
| binary_sensor.sterownik_pompy_pompka_obiegowa | heatpump.circulation | esphome | odczyt | niepodana | on | AVAILABLE | krytyczna | WYMAGA POPRAWY |
| binary_sensor.workday_jutro | tariff.tomorrow_workday | workday | odczyt | niepodana | on | AVAILABLE | krytyczna | GOTOWA |
| binary_sensor.workday_sensor_pl | tariff.workday | workday | odczyt | niepodana | on | AVAILABLE | krytyczna | GOTOWA |
| button.gniazdko_cwu_identify | Discovered supporting/legacy entity: Gniazdko cwu Zidentyfikuj | mqtt | sterowanie | niepodana | unknown | UNAVAILABLE_OR_UNKNOWN | pomocnicza | WYMAGA POPRAWY |
| button.gniazdko_kotlownia_identify | Discovered supporting/legacy entity: Gniazdko kotlownia Zidentyfikuj | mqtt | sterowanie | niepodana | unknown | UNAVAILABLE_OR_UNKNOWN | pomocnicza | WYMAGA POPRAWY |
| button.solaredge_i1_refresh | Discovered supporting/legacy entity: Solaredge I1 Refresh | solaredge_modbus_multi | sterowanie | niepodana | unknown | UNAVAILABLE_OR_UNKNOWN | pomocnicza | WYMAGA POPRAWY |
| button.sterownik_pompy_puls_watchdoga | Discovered supporting/legacy entity: Sterownik Pompy Puls Watchdoga | esphome | sterowanie | niepodana | unknown | UNAVAILABLE_OR_UNKNOWN | pomocnicza | WYMAGA POPRAWY |
| calendar.workday_jutro_calendar | Discovered supporting/legacy entity: Workday Jutro Calendar | workday | odczyt | niepodana | on | AVAILABLE | pomocnicza | GOTOWA |
| calendar.workday_sensor_pl_calendar | Discovered supporting/legacy entity: Workday Sensor PL Calendar | workday | odczyt | niepodana | on | AVAILABLE | pomocnicza | GOTOWA |
| climate.0xa4c13873c988c6cf | Discovered supporting/legacy entity: 0xa4c13873c988c6cf | mqtt | sterowanie | niepodana | heat | AVAILABLE | pomocnicza | GOTOWA |
| climate.0xa4c13891297b6e9a | Discovered supporting/legacy entity: Sypialnia | mqtt | sterowanie | niepodana | heat | AVAILABLE | pomocnicza | GOTOWA |
| climate.korytarz | Discovered supporting/legacy entity: Korytarz  | tuya | sterowanie | niepodana | unavailable | UNAVAILABLE_OR_UNKNOWN | pomocnicza | WYMAGA POPRAWY |
| climate.kuchnia | Discovered supporting/legacy entity: Kuchnia  | tuya | sterowanie | niepodana | unavailable | UNAVAILABLE_OR_UNKNOWN | pomocnicza | WYMAGA POPRAWY |
| climate.salon_1 | Discovered supporting/legacy entity: Salon 1 | tuya | sterowanie | niepodana | unavailable | UNAVAILABLE_OR_UNKNOWN | pomocnicza | WYMAGA POPRAWY |
| input_boolean.dezynfekcja_zrobiona | Discovered supporting/legacy entity: Dezynfekcja CWU (Status) | HA helpers (YAML/UI) | sterowanie | niepodana | unavailable | UNAVAILABLE_OR_UNKNOWN | pomocnicza | WYMAGA POPRAWY |
| input_boolean.ems_battery_execution_authorized | safety.authorization | HA helpers (YAML/UI) | sterowanie | niepodana | off | AVAILABLE | krytyczna | GOTOWA |
| input_boolean.pompa_obiegowa | Discovered supporting/legacy entity: Pompa Obiegowa | HA helpers (YAML/UI) | sterowanie | niepodana | off | AVAILABLE | pomocnicza | GOTOWA |
| input_boolean.pompa_obiegowa_co | Discovered supporting/legacy entity: Pompa obiegowa CO | HA helpers (YAML/UI) | sterowanie | niepodana | off | AVAILABLE | pomocnicza | GOTOWA |
| input_boolean.pompa_obiegowa_co_2 | Discovered supporting/legacy entity: Pompa Obiegowa CO | HA helpers (YAML/UI) | sterowanie | niepodana | on | AVAILABLE | pomocnicza | GOTOWA |
| input_boolean.smart_grid_automatyzacja | Discovered supporting/legacy entity: Smart Grid Automatyzacja | HA helpers (YAML/UI) | sterowanie | niepodana | on | AVAILABLE | pomocnicza | GOTOWA |
| input_number.ems_battery_safety_soc_max | Discovered supporting/legacy entity: EMS Battery Safety SOC Max | HA helpers (YAML/UI) | sterowanie | % | 0.0 | AVAILABLE | pomocnicza | WYMAGA POPRAWY |
| input_number.ems_battery_safety_soc_min | Discovered supporting/legacy entity: EMS Battery Safety SOC Min | HA helpers (YAML/UI) | sterowanie | % | 0.0 | AVAILABLE | pomocnicza | WYMAGA POPRAWY |
| input_select.ems_battery_control_owner | safety.owner | HA helpers (YAML/UI) | sterowanie | niepodana | LEGACY | AVAILABLE | krytyczna | GOTOWA |
| input_text.pompa_ciepla_alarm_zdarzenie | Discovered supporting/legacy entity: Pompa ciepla alarm zdarzenie | HA helpers (YAML/UI) | odczyt | niepodana | {"code":0} | AVAILABLE | pomocnicza | GOTOWA |
| number.0x286847fffef5f4e9_data_report_duration | Discovered supporting/legacy entity: Licznik Data report duration | mqtt | sterowanie | niepodana | unknown | UNAVAILABLE_OR_UNKNOWN | pomocnicza | WYMAGA POPRAWY |
| number.0xa4c138006c97ffff_countdown | Discovered supporting/legacy entity: Gniazdko kotlownia Countdown | mqtt | sterowanie | s | 0 | AVAILABLE | pomocnicza | GOTOWA |
| number.0xa4c1383684dacee8_humidity_calibration | Discovered supporting/legacy entity: Temperatura co powrot Humidity calibration | mqtt | sterowanie | % | 0 | AVAILABLE | pomocnicza | GOTOWA |
| number.0xa4c1383684dacee8_humidity_sensitivity | Discovered supporting/legacy entity: Temperatura co powrot Humidity sensitivity | mqtt | sterowanie | % | 1 | AVAILABLE | pomocnicza | GOTOWA |
| number.0xa4c1383684dacee8_temperature_calibration | Discovered supporting/legacy entity: Temperatura co powrot Temperature calibration | mqtt | sterowanie | °C | 0 | AVAILABLE | pomocnicza | GOTOWA |
| number.0xa4c1383684dacee8_temperature_sensitivity | Discovered supporting/legacy entity: Temperatura co powrot Temperature sensitivity | mqtt | sterowanie | °C | 0.2 | AVAILABLE | pomocnicza | GOTOWA |
| number.0xa4c1389eebc44e6a_update_frequency | Discovered supporting/legacy entity: Licznik pompa Update frequency | mqtt | sterowanie | s | 10 | AVAILABLE | pomocnicza | GOTOWA |
| number.0xa4c138a5380f3cda_countdown | Discovered supporting/legacy entity: Gniazdko cwu Countdown | mqtt | sterowanie | s | 0 | AVAILABLE | pomocnicza | GOTOWA |
| number.0xa4c138c18fd67065_humidity_calibration | Discovered supporting/legacy entity: Temperatura bufor zasilanie Humidity calibration | mqtt | sterowanie | % | 0 | AVAILABLE | pomocnicza | GOTOWA |
| number.0xa4c138c18fd67065_humidity_sensitivity | Discovered supporting/legacy entity: Temperatura bufor zasilanie Humidity sensitivity | mqtt | sterowanie | % | 1 | AVAILABLE | pomocnicza | GOTOWA |
| number.0xa4c138c18fd67065_temperature_calibration | Discovered supporting/legacy entity: Temperatura bufor zasilanie Temperature calibration | mqtt | sterowanie | °C | 0 | AVAILABLE | pomocnicza | GOTOWA |
| number.0xa4c138c18fd67065_temperature_sensitivity | Discovered supporting/legacy entity: Temperatura bufor zasilanie Temperature sensitivity | mqtt | sterowanie | °C | 0.2 | AVAILABLE | pomocnicza | GOTOWA |
| number.0xa4c138e823c53c00_humidity_calibration | Discovered supporting/legacy entity: Temperatura co zasilanie Humidity calibration | mqtt | sterowanie | % | 0 | AVAILABLE | pomocnicza | GOTOWA |
| number.0xa4c138e823c53c00_humidity_sensitivity | Discovered supporting/legacy entity: Temperatura co zasilanie Humidity sensitivity | mqtt | sterowanie | % | 1 | AVAILABLE | pomocnicza | GOTOWA |
| number.0xa4c138e823c53c00_temperature_calibration | Discovered supporting/legacy entity: Temperatura co zasilanie Temperature calibration | mqtt | sterowanie | °C | 0 | AVAILABLE | pomocnicza | GOTOWA |
| number.0xa4c138e823c53c00_temperature_sensitivity | Discovered supporting/legacy entity: Temperatura co zasilanie Temperature sensitivity | mqtt | sterowanie | °C | 0.2 | AVAILABLE | pomocnicza | GOTOWA |
| number.ems_disabled_6022ee792be1bcc4 | Discovered supporting/legacy entity: number.ems_disabled_6022ee792be1bcc4 | solaredge_modbus_multi | sterowanie | niepodana | BRAK | DISABLED | pomocnicza | WYMAGA POPRAWY |
| number.ems_disabled_68849705b2ab62f7 | Discovered supporting/legacy entity: number.ems_disabled_68849705b2ab62f7 | solaredge_modbus_multi | sterowanie | niepodana | BRAK | DISABLED | pomocnicza | WYMAGA POPRAWY |
| number.solaredge_i1_ac_charge_limit | Discovered supporting/legacy entity: Solaredge I1 AC Charge Limit | solaredge_modbus_multi | sterowanie | niepodana | unavailable | UNAVAILABLE_OR_UNKNOWN | pomocnicza | WYMAGA POPRAWY |
| number.solaredge_i1_backup_reserve | control.reserve | solaredge_modbus_multi | sterowanie | % | 0 | AVAILABLE | krytyczna | GOTOWA |
| number.solaredge_i1_storage_charge_limit | control.charge_limit | solaredge_modbus_multi | sterowanie | W | 5000 | AVAILABLE | krytyczna | GOTOWA |
| number.solaredge_i1_storage_command_timeout | control.timeout | solaredge_modbus_multi | sterowanie | s | 3600 | AVAILABLE | krytyczna | GOTOWA |
| number.solaredge_i1_storage_discharge_limit | control.discharge_limit | solaredge_modbus_multi | sterowanie | W | 5000 | AVAILABLE | krytyczna | GOTOWA |
| number.sterownik_pompy_limit_mocy | Discovered supporting/legacy entity: Sterownik Pompy Limit Mocy | esphome | sterowanie | niepodana | 4.0 | AVAILABLE | pomocnicza | GOTOWA |
| number.sterownik_pompy_nastawa_temperatury_co | heating.setpoint | esphome | sterowanie | niepodana | 42.0 | AVAILABLE | krytyczna | WYMAGA POPRAWY |
| number.sterownik_pompy_nastawa_temperatury_cwu | dhw.setpoint | esphome | sterowanie | niepodana | 42.0 | AVAILABLE | krytyczna | WYMAGA POPRAWY |
| script.ems_battery_command_gateway | Discovered supporting/legacy entity: EMS Battery Command Gateway | HA script YAML | sterowanie | niepodana | off | AVAILABLE | pomocnicza | GOTOWA |
| select.0x0c4314fffe54b4f9_power_outage_memory | Discovered supporting/legacy entity: Oswietlenie św. taras Power outage memory | mqtt | sterowanie | niepodana | unknown | UNAVAILABLE_OR_UNKNOWN | pomocnicza | WYMAGA POPRAWY |
| select.0x70b3d52b60100cfa_power_on_behavior | Discovered supporting/legacy entity: Oświetlenie domu Power-on behavior | mqtt | sterowanie | niepodana | off | AVAILABLE | pomocnicza | GOTOWA |
| select.0xa4c138003fe7ffff_power_outage_memory | Discovered supporting/legacy entity: Oswietlenie św. wejście Power outage memory | mqtt | sterowanie | niepodana | unknown | UNAVAILABLE_OR_UNKNOWN | pomocnicza | WYMAGA POPRAWY |
| select.0xa4c138006c97ffff_indicator_mode | Discovered supporting/legacy entity: Gniazdko kotlownia Indicator mode | mqtt | sterowanie | niepodana | unknown | UNAVAILABLE_OR_UNKNOWN | pomocnicza | WYMAGA POPRAWY |
| select.0xa4c138006c97ffff_power_outage_memory | Discovered supporting/legacy entity: Gniazdko kotlownia Power outage memory | mqtt | sterowanie | niepodana | on | AVAILABLE | pomocnicza | GOTOWA |
| select.0xa4c138007a69ffff_power_outage_memory | Discovered supporting/legacy entity: Gniazdko salon Power outage memory | mqtt | sterowanie | niepodana | on | AVAILABLE | pomocnicza | GOTOWA |
| select.0xa4c13805aa7f2520_power_on_behavior | Discovered supporting/legacy entity: Sterownik Power-on behavior | mqtt | sterowanie | niepodana | on | AVAILABLE | pomocnicza | GOTOWA |
| select.0xa4c1383684dacee8_power_outage_memory | Discovered supporting/legacy entity: Temperatura co powrot Power outage memory | mqtt | sterowanie | niepodana | on | AVAILABLE | pomocnicza | GOTOWA |
| select.0xa4c138693a9d4a87_power_outage_memory | Discovered supporting/legacy entity: Oswietlenie szafa gniazdo Power outage memory | mqtt | sterowanie | niepodana | restore | AVAILABLE | pomocnicza | GOTOWA |
| select.0xa4c13875e7efb665_power_outage_memory | Discovered supporting/legacy entity: Ładowarka Power outage memory | mqtt | sterowanie | niepodana | on | AVAILABLE | pomocnicza | GOTOWA |
| select.0xa4c1387ab40f7ba4_power_on_behavior | Discovered supporting/legacy entity: Podgrzewacz CWU Smart Grid Power-on behavior | mqtt | sterowanie | niepodana | previous | AVAILABLE | pomocnicza | GOTOWA |
| select.0xa4c1387ab40f7ba4_switch_type | Discovered supporting/legacy entity: Podgrzewacz CWU Smart Grid Switch type | mqtt | sterowanie | niepodana | toggle | AVAILABLE | pomocnicza | GOTOWA |
| select.0xa4c138945869c3dd_power_outage_memory | Discovered supporting/legacy entity: 0xa4c138945869c3dd Power outage memory | mqtt | sterowanie | niepodana | off | AVAILABLE | pomocnicza | GOTOWA |
| select.0xa4c138a5380f3cda_indicator_mode | Discovered supporting/legacy entity: Gniazdko cwu Indicator mode | mqtt | sterowanie | niepodana | on | AVAILABLE | pomocnicza | GOTOWA |
| select.0xa4c138a5380f3cda_power_outage_memory | Discovered supporting/legacy entity: Gniazdko cwu Power outage memory | mqtt | sterowanie | niepodana | off | AVAILABLE | pomocnicza | GOTOWA |
| select.0xa4c138c18fd67065_power_outage_memory | Discovered supporting/legacy entity: Temperatura bufor zasilanie Power outage memory | mqtt | sterowanie | niepodana | on | AVAILABLE | pomocnicza | GOTOWA |
| select.0xa4c138e0c6831017_power_outage_memory | Discovered supporting/legacy entity: Ładowarka 2 Power outage memory | mqtt | sterowanie | niepodana | on | AVAILABLE | pomocnicza | GOTOWA |
| select.0xa4c138e823c53c00_power_outage_memory | Discovered supporting/legacy entity: Temperatura co zasilanie Power outage memory | mqtt | sterowanie | niepodana | on | AVAILABLE | pomocnicza | GOTOWA |
| select.0xa4c138f95f051e67_power_on_behavior | Discovered supporting/legacy entity: Przekaznik Power-on behavior | mqtt | sterowanie | niepodana | off | AVAILABLE | pomocnicza | GOTOWA |
| select.ems_disabled_1dc0f193cdbd2694 | Discovered supporting/legacy entity: select.ems_disabled_1dc0f193cdbd2694 | solaredge_modbus_multi | sterowanie | niepodana | BRAK | DISABLED | pomocnicza | WYMAGA POPRAWY |
| select.ems_disabled_e1a4546cf53dbabf | Discovered supporting/legacy entity: select.ems_disabled_e1a4546cf53dbabf | solaredge_modbus_multi | sterowanie | niepodana | BRAK | DISABLED | pomocnicza | WYMAGA POPRAWY |
| select.gniazdko_cwu_switch_type_button | Discovered supporting/legacy entity: Gniazdko cwu Switch type button | mqtt | sterowanie | niepodana | unknown | UNAVAILABLE_OR_UNKNOWN | pomocnicza | WYMAGA POPRAWY |
| select.gniazdko_kotlownia_switch_type_button | Discovered supporting/legacy entity: Gniazdko kotlownia Switch type button | mqtt | sterowanie | niepodana | unknown | UNAVAILABLE_OR_UNKNOWN | pomocnicza | WYMAGA POPRAWY |
| select.kotlownia_g13_dzien | Discovered supporting/legacy entity: Kotłownia G13 dzień | UNCONFIRMED / restored legacy | sterowanie | niepodana | dolina | AVAILABLE | pomocnicza | WYMAGA POPRAWY |
| select.kotlownia_g13_miesiac | Discovered supporting/legacy entity: Kotłownia G13 miesiąc | UNCONFIRMED / restored legacy | sterowanie | niepodana | dolina | AVAILABLE | pomocnicza | WYMAGA POPRAWY |
| select.kotlownia_g13_rok | Discovered supporting/legacy entity: Kotłownia G13 rok | UNCONFIRMED / restored legacy | sterowanie | niepodana | dolina | AVAILABLE | pomocnicza | WYMAGA POPRAWY |
| select.kotlownia_power_on_behavior | Discovered supporting/legacy entity: Kotłownia  Power-on behavior | tuya | sterowanie | niepodana | unavailable | UNAVAILABLE_OR_UNKNOWN | pomocnicza | WYMAGA POPRAWY |
| select.oswietlenie_domu_power_on_behavior | Discovered supporting/legacy entity: Oświetlenie domu Power-on behavior | tuya | sterowanie | niepodana | unavailable | UNAVAILABLE_OR_UNKNOWN | pomocnicza | WYMAGA POPRAWY |
| select.oswietlenie_numeru_domu_power_on_behavior | Discovered supporting/legacy entity: Oświetlenie numeru domu Power-on behavior | mqtt | sterowanie | niepodana | previous | AVAILABLE | pomocnicza | GOTOWA |
| select.oswietlenie_swiateczne_taras_power_on_behavior | Discovered supporting/legacy entity: Oświetlenie świąteczne taras Power-on behavior | tuya | sterowanie | niepodana | unavailable | UNAVAILABLE_OR_UNKNOWN | pomocnicza | WYMAGA POPRAWY |
| select.pompa_cwu_indicator_light_mode | Discovered supporting/legacy entity: Pompa cwu Indicator light mode | tuya | sterowanie | niepodana | relay | AVAILABLE | pomocnicza | GOTOWA |
| select.pompa_cwu_power_on_behavior | Discovered supporting/legacy entity: Pompa cwu Power-on behavior | tuya | sterowanie | niepodana | last | AVAILABLE | pomocnicza | GOTOWA |
| select.solaredge_i1_ac_charge_policy | Discovered supporting/legacy entity: Solaredge I1 AC Charge Policy | solaredge_modbus_multi | sterowanie | niepodana | Always Allowed | AVAILABLE | pomocnicza | GOTOWA |
| select.solaredge_i1_storage_command_mode | control.command | solaredge_modbus_multi | sterowanie | niepodana | Maximize Self Consumption | AVAILABLE | krytyczna | GOTOWA |
| select.solaredge_i1_storage_control_mode | control.mode | solaredge_modbus_multi | sterowanie | niepodana | Remote Control | AVAILABLE | krytyczna | GOTOWA |
| select.solaredge_i1_storage_default_mode | control.default | solaredge_modbus_multi | sterowanie | niepodana | Maximize Self Consumption | AVAILABLE | krytyczna | GOTOWA |
| select.solcast_pv_forecast_uzyj_pola_prognozy | Discovered supporting/legacy entity: Solcast PV Forecast Użyj pola prognozy | solcast_solar | sterowanie | niepodana | estimate | AVAILABLE | pomocnicza | GOTOWA |
| select.zasilanie_jadalnia_power_on_behavior | Discovered supporting/legacy entity: Zasilanie jadalnia  Power-on behavior | tuya | sterowanie | niepodana | last | AVAILABLE | pomocnicza | GOTOWA |
| select.zuzycie_dzienne_g13 | tariff.selector | utility_meter | sterowanie | niepodana | dolina | AVAILABLE | krytyczna | GOTOWA |
| select.zuzycie_miesieczne_g13 | Discovered supporting/legacy entity: Solaredge I1 M1 Zużycie miesięczne G13 | utility_meter | sterowanie | niepodana | dolina | AVAILABLE | pomocnicza | GOTOWA |
| select.zuzycie_roczne_g13 | Discovered supporting/legacy entity: Solaredge I1 M1 Zużycie roczne G13 | utility_meter | sterowanie | niepodana | dolina | AVAILABLE | pomocnicza | GOTOWA |
| sensor.0x286847fffef5f4e9_ac_frequency | Discovered supporting/legacy entity: Licznik Częstotliwość | mqtt | odczyt | Hz | 50.01 | AVAILABLE | pomocnicza | GOTOWA |
| sensor.0x286847fffef5f4e9_current_a | Discovered supporting/legacy entity: Licznik Natężenie prądu | mqtt | odczyt | A | 8.377 | AVAILABLE | pomocnicza | GOTOWA |
| sensor.0x286847fffef5f4e9_current_b | Discovered supporting/legacy entity: Licznik Natężenie prądu | mqtt | odczyt | A | 0.658 | AVAILABLE | pomocnicza | GOTOWA |
| sensor.0x286847fffef5f4e9_current_c | Discovered supporting/legacy entity: Licznik Natężenie prądu | mqtt | odczyt | A | 0.015 | AVAILABLE | pomocnicza | GOTOWA |
| sensor.0x286847fffef5f4e9_energy | boiler.import_energy | mqtt | odczyt | kWh | 214.19 | AVAILABLE | krytyczna | GOTOWA |
| sensor.0x286847fffef5f4e9_linkquality | Discovered supporting/legacy entity: Linkquality | mqtt | odczyt | niepodana | BRAK | DISABLED | pomocnicza | WYMAGA POPRAWY |
| sensor.0x286847fffef5f4e9_power | boiler.total_power | mqtt | odczyt | W | 1880 | AVAILABLE | krytyczna | GOTOWA |
| sensor.0x286847fffef5f4e9_power_a | boiler.phase_a_power | mqtt | odczyt | W | 1789 | AVAILABLE | krytyczna | GOTOWA |
| sensor.0x286847fffef5f4e9_power_b | boiler.phase_b_power | mqtt | odczyt | W | 92 | AVAILABLE | krytyczna | GOTOWA |
| sensor.0x286847fffef5f4e9_power_c | boiler.phase_c_power | mqtt | odczyt | W | 0 | AVAILABLE | krytyczna | WYMAGA POPRAWY |
| sensor.0x286847fffef5f4e9_power_factor | Discovered supporting/legacy entity: Współczynnik mocy | mqtt | odczyt | niepodana | BRAK | DISABLED | pomocnicza | WYMAGA POPRAWY |
| sensor.0x286847fffef5f4e9_produced_energy | boiler.export_energy_diagnostic | mqtt | odczyt | kWh | 7667.5 | AVAILABLE | krytyczna | WYMAGA POPRAWY |
| sensor.0x286847fffef5f4e9_voltage_a | Discovered supporting/legacy entity: Licznik Voltage a | mqtt | odczyt | V | 225.5 | AVAILABLE | pomocnicza | GOTOWA |
| sensor.0x286847fffef5f4e9_voltage_b | Discovered supporting/legacy entity: Licznik Voltage b | mqtt | odczyt | V | 227.9 | AVAILABLE | pomocnicza | GOTOWA |
| sensor.0x286847fffef5f4e9_voltage_c | Discovered supporting/legacy entity: Licznik Voltage c | mqtt | odczyt | V | 232.8 | AVAILABLE | pomocnicza | GOTOWA |
| sensor.0xa4c138006c97ffff_current | Discovered supporting/legacy entity: Gniazdko kotlownia Natężenie prądu | mqtt | odczyt | A | 0 | AVAILABLE | pomocnicza | GOTOWA |
| sensor.0xa4c138006c97ffff_energy | Discovered supporting/legacy entity: Gniazdko kotlownia Energia | mqtt | odczyt | kWh | 0.9 | AVAILABLE | pomocnicza | GOTOWA |
| sensor.0xa4c138006c97ffff_power | Discovered supporting/legacy entity: Gniazdko kotlownia Moc | mqtt | odczyt | W | 0 | AVAILABLE | pomocnicza | GOTOWA |
| sensor.0xa4c138006c97ffff_voltage | Discovered supporting/legacy entity: Gniazdko kotlownia Napięcie | mqtt | odczyt | V | 224 | AVAILABLE | pomocnicza | GOTOWA |
| sensor.0xa4c1383684dacee8_auto_settings | Discovered supporting/legacy entity: Temperatura co powrot Auto settings | mqtt | odczyt | niepodana |  | AVAILABLE | pomocnicza | GOTOWA |
| sensor.0xa4c1383684dacee8_humidity | Discovered supporting/legacy entity: Temperatura co powrot Wilgotność | mqtt | odczyt | % | unknown | UNAVAILABLE_OR_UNKNOWN | pomocnicza | WYMAGA POPRAWY |
| sensor.0xa4c1383684dacee8_linkquality | Discovered supporting/legacy entity: Linkquality | mqtt | odczyt | niepodana | BRAK | DISABLED | pomocnicza | WYMAGA POPRAWY |
| sensor.0xa4c1383684dacee8_temperature | heating.radiator_return | mqtt | odczyt | °C | 29.6 | AVAILABLE | krytyczna | GOTOWA |
| sensor.0xa4c1385d4d396787_battery | Discovered supporting/legacy entity: Temperatura na zewnatrz Bateria | mqtt | odczyt | % | 100 | AVAILABLE | pomocnicza | GOTOWA |
| sensor.0xa4c1385d4d396787_humidity | Discovered supporting/legacy entity: Temperatura na zewnatrz Wilgotność | mqtt | odczyt | % | 69.5 | AVAILABLE | pomocnicza | GOTOWA |
| sensor.0xa4c1385d4d396787_linkquality | Discovered supporting/legacy entity: Linkquality | mqtt | odczyt | niepodana | BRAK | DISABLED | pomocnicza | WYMAGA POPRAWY |
| sensor.0xa4c1385d4d396787_temperature | weather.local_temperature | mqtt | odczyt | °C | 8.64 | AVAILABLE | krytyczna | GOTOWA |
| sensor.0xa4c1385d4d396787_voltage | Discovered supporting/legacy entity: Temperatura na zewnatrz Napięcie | mqtt | odczyt | mV | unknown | UNAVAILABLE_OR_UNKNOWN | pomocnicza | WYMAGA POPRAWY |
| sensor.0xa4c1389eebc44e6a_ac_frequency | Discovered supporting/legacy entity: Licznik pompa Częstotliwość | mqtt | odczyt | Hz | 49.15 | AVAILABLE | pomocnicza | GOTOWA |
| sensor.0xa4c1389eebc44e6a_current_a | Discovered supporting/legacy entity: Licznik pompa Natężenie prądu | mqtt | odczyt | A | 7.732 | AVAILABLE | pomocnicza | GOTOWA |
| sensor.0xa4c1389eebc44e6a_current_b | Discovered supporting/legacy entity: Licznik pompa Natężenie prądu | mqtt | odczyt | A | 0 | AVAILABLE | pomocnicza | WYMAGA POPRAWY |
| sensor.0xa4c1389eebc44e6a_energy_a | heatpump.submeter_energy | mqtt | odczyt | kWh | 170.69 | AVAILABLE | krytyczna | GOTOWA |
| sensor.0xa4c1389eebc44e6a_energy_b | Discovered supporting/legacy entity: Licznik pompa Energia | mqtt | odczyt | kWh | 0 | AVAILABLE | pomocnicza | WYMAGA POPRAWY |
| sensor.0xa4c1389eebc44e6a_energy_flow_a | Discovered supporting/legacy entity: Licznik pompa Energy flow a | mqtt | odczyt | niepodana | consuming | AVAILABLE | pomocnicza | WYMAGA POPRAWY |
| sensor.0xa4c1389eebc44e6a_energy_flow_b | Discovered supporting/legacy entity: Licznik pompa Energy flow b | mqtt | odczyt | niepodana | consuming | AVAILABLE | pomocnicza | WYMAGA POPRAWY |
| sensor.0xa4c1389eebc44e6a_energy_produced_a | Discovered supporting/legacy entity: Licznik pompa Energia | mqtt | odczyt | kWh | 2664.81 | AVAILABLE | pomocnicza | WYMAGA POPRAWY |
| sensor.0xa4c1389eebc44e6a_energy_produced_b | Discovered supporting/legacy entity: Licznik pompa Energia | mqtt | odczyt | kWh | 0 | AVAILABLE | pomocnicza | WYMAGA POPRAWY |
| sensor.0xa4c1389eebc44e6a_linkquality | Discovered supporting/legacy entity: Linkquality | mqtt | odczyt | niepodana | BRAK | DISABLED | pomocnicza | WYMAGA POPRAWY |
| sensor.0xa4c1389eebc44e6a_power_a | heatpump.submeter_power | mqtt | odczyt | W | 1649 | AVAILABLE | krytyczna | GOTOWA |
| sensor.0xa4c1389eebc44e6a_power_ab | Discovered supporting/legacy entity: Licznik pompa Moc | mqtt | odczyt | W | 1649 | AVAILABLE | pomocnicza | GOTOWA |
| sensor.0xa4c1389eebc44e6a_power_b | Discovered supporting/legacy entity: Licznik pompa Moc | mqtt | odczyt | W | 0 | AVAILABLE | pomocnicza | WYMAGA POPRAWY |
| sensor.0xa4c1389eebc44e6a_power_factor_a | Discovered supporting/legacy entity: Licznik pompa Power factor a | mqtt | odczyt | % | 94 | AVAILABLE | pomocnicza | WYMAGA POPRAWY |
| sensor.0xa4c1389eebc44e6a_power_factor_b | Discovered supporting/legacy entity: Licznik pompa Power factor b | mqtt | odczyt | % | 100 | AVAILABLE | pomocnicza | WYMAGA POPRAWY |
| sensor.0xa4c1389eebc44e6a_timestamp_a | Discovered supporting/legacy entity: Licznik pompa Timestamp a | mqtt | odczyt | niepodana | 2026-10-19T19:48:45.907Z | AVAILABLE | pomocnicza | GOTOWA |
| sensor.0xa4c1389eebc44e6a_timestamp_b | Discovered supporting/legacy entity: Licznik pompa Timestamp b | mqtt | odczyt | niepodana | 2026-10-19T19:48:46.241Z | AVAILABLE | pomocnicza | GOTOWA |
| sensor.0xa4c1389eebc44e6a_voltage | Discovered supporting/legacy entity: Licznik pompa Napięcie | mqtt | odczyt | V | 225.3 | AVAILABLE | pomocnicza | GOTOWA |
| sensor.0xa4c138a5380f3cda_current | Discovered supporting/legacy entity: Gniazdko cwu Natężenie prądu | mqtt | odczyt | A | 0 | AVAILABLE | pomocnicza | GOTOWA |
| sensor.0xa4c138a5380f3cda_energy | Discovered supporting/legacy entity: Gniazdko cwu Energia | mqtt | odczyt | kWh | 0.45 | AVAILABLE | pomocnicza | GOTOWA |
| sensor.0xa4c138a5380f3cda_power | Discovered supporting/legacy entity: Gniazdko cwu Moc | mqtt | odczyt | W | 0 | AVAILABLE | pomocnicza | GOTOWA |
| sensor.0xa4c138a5380f3cda_voltage | Discovered supporting/legacy entity: Gniazdko cwu Napięcie | mqtt | odczyt | V | 224 | AVAILABLE | pomocnicza | GOTOWA |
| sensor.0xa4c138c18fd67065_auto_settings | Discovered supporting/legacy entity: Temperatura bufor zasilanie Auto settings | mqtt | odczyt | niepodana |  | AVAILABLE | pomocnicza | GOTOWA |
| sensor.0xa4c138c18fd67065_humidity | Discovered supporting/legacy entity: Temperatura bufor zasilanie Wilgotność | mqtt | odczyt | % | unknown | UNAVAILABLE_OR_UNKNOWN | pomocnicza | WYMAGA POPRAWY |
| sensor.0xa4c138c18fd67065_linkquality | Discovered supporting/legacy entity: Linkquality | mqtt | odczyt | niepodana | BRAK | DISABLED | pomocnicza | WYMAGA POPRAWY |
| sensor.0xa4c138c18fd67065_temperature | heating.buffer_supply | mqtt | odczyt | °C | 36 | AVAILABLE | krytyczna | GOTOWA |
| sensor.0xa4c138e823c53c00_auto_settings | Discovered supporting/legacy entity: Temperatura co zasilanie Auto settings | mqtt | odczyt | niepodana |  | AVAILABLE | pomocnicza | GOTOWA |
| sensor.0xa4c138e823c53c00_humidity | Discovered supporting/legacy entity: Temperatura co zasilanie Wilgotność | mqtt | odczyt | % | unknown | UNAVAILABLE_OR_UNKNOWN | pomocnicza | WYMAGA POPRAWY |
| sensor.0xa4c138e823c53c00_humidity_calibration | Discovered supporting/legacy entity: Humidity calibration | mqtt | odczyt | niepodana | BRAK | DISABLED | pomocnicza | WYMAGA POPRAWY |
| sensor.0xa4c138e823c53c00_humidity_sensitivity | Discovered supporting/legacy entity: Humidity sensitivity | mqtt | odczyt | niepodana | BRAK | DISABLED | pomocnicza | WYMAGA POPRAWY |
| sensor.0xa4c138e823c53c00_linkquality | Discovered supporting/legacy entity: Linkquality | mqtt | odczyt | niepodana | BRAK | DISABLED | pomocnicza | WYMAGA POPRAWY |
| sensor.0xa4c138e823c53c00_power_outage_memory | Discovered supporting/legacy entity: Power outage memory | mqtt | odczyt | niepodana | BRAK | DISABLED | pomocnicza | WYMAGA POPRAWY |
| sensor.0xa4c138e823c53c00_temperature | heating.radiator_supply | mqtt | odczyt | °C | 33.8 | AVAILABLE | krytyczna | GOTOWA |
| sensor.0xa4c138e823c53c00_temperature_calibration | Discovered supporting/legacy entity: Temperature calibration | mqtt | odczyt | niepodana | BRAK | DISABLED | pomocnicza | WYMAGA POPRAWY |
| sensor.0xa4c138e823c53c00_temperature_sensitivity | Discovered supporting/legacy entity: Temperature sensitivity | mqtt | odczyt | niepodana | BRAK | DISABLED | pomocnicza | WYMAGA POPRAWY |
| sensor.cwu_zasilacz_moc | Discovered supporting/legacy entity: Moc | UNCONFIRMED / restored legacy | odczyt | niepodana | BRAK | DISABLED | pomocnicza | WYMAGA POPRAWY |
| sensor.cwu_zasilacz_napiecie | Discovered supporting/legacy entity: Napięcie | UNCONFIRMED / restored legacy | odczyt | niepodana | BRAK | DISABLED | pomocnicza | WYMAGA POPRAWY |
| sensor.cwu_zasilacz_natezenie_pradu | Discovered supporting/legacy entity: Natężenie prądu | UNCONFIRMED / restored legacy | odczyt | niepodana | BRAK | DISABLED | pomocnicza | WYMAGA POPRAWY |
| sensor.cwu_zasilacz_temperatura | heating.buffer_return | tuya | odczyt | °C | 34.0 | AVAILABLE | krytyczna | GOTOWA |
| sensor.ems_diagnostyka_aktualizacji_sterownika_pompy | Discovered supporting/legacy entity: EMS diagnostyka aktualizacji sterownika pompy | UNCONFIRMED / restored legacy | odczyt | niepodana | HA_AKTUALIZUJE | AVAILABLE | pomocnicza | WYMAGA POPRAWY |
| sensor.koszt_poboru_dzisiejszy | cost.today | template | odczyt | PLN | 23.55 | AVAILABLE | krytyczna | GOTOWA |
| sensor.koszt_poboru_dzisiejszy_2 | Discovered supporting/legacy entity: Koszt poboru dzisiejszy | template | odczyt | PLN | 0.0 | AVAILABLE | pomocnicza | WYMAGA POPRAWY |
| sensor.koszt_poboru_miesieczny | Discovered supporting/legacy entity: Koszt poboru miesięczny | template | odczyt | PLN | 0.0 | AVAILABLE | pomocnicza | WYMAGA POPRAWY |
| sensor.kotlownia_g13_dzien_dolina | Discovered supporting/legacy entity: Kotłownia G13 dzień dolina | UNCONFIRMED / restored legacy | odczyt | kWh | 10.01 | AVAILABLE | pomocnicza | WYMAGA POPRAWY |
| sensor.kotlownia_g13_dzien_szczyt_popoludniowy | Discovered supporting/legacy entity: Kotłownia G13 dzień szczyt_popoludniowy | UNCONFIRMED / restored legacy | odczyt | kWh | 3.06 | AVAILABLE | pomocnicza | WYMAGA POPRAWY |
| sensor.kotlownia_g13_dzien_szczyt_przedpoludniowy | Discovered supporting/legacy entity: Kotłownia G13 dzień szczyt_przedpoludniowy | UNCONFIRMED / restored legacy | odczyt | kWh | 4.47 | AVAILABLE | pomocnicza | WYMAGA POPRAWY |
| sensor.kotlownia_g13_miesiac_dolina | Discovered supporting/legacy entity: Kotłownia G13 miesiąc dolina | UNCONFIRMED / restored legacy | odczyt | kWh | 126.48 | AVAILABLE | pomocnicza | WYMAGA POPRAWY |
| sensor.kotlownia_g13_miesiac_szczyt_popoludniowy | Discovered supporting/legacy entity: Kotłownia G13 miesiąc szczyt_popoludniowy | UNCONFIRMED / restored legacy | odczyt | kWh | 20.28 | AVAILABLE | pomocnicza | WYMAGA POPRAWY |
| sensor.kotlownia_g13_miesiac_szczyt_przedpoludniowy | Discovered supporting/legacy entity: Kotłownia G13 miesiąc szczyt_przedpoludniowy | UNCONFIRMED / restored legacy | odczyt | kWh | 20.14 | AVAILABLE | pomocnicza | WYMAGA POPRAWY |
| sensor.kotlownia_g13_rok_dolina | Discovered supporting/legacy entity: Kotłownia G13 rok dolina | UNCONFIRMED / restored legacy | odczyt | kWh | 126.48 | AVAILABLE | pomocnicza | WYMAGA POPRAWY |
| sensor.kotlownia_g13_rok_szczyt_popoludniowy | Discovered supporting/legacy entity: Kotłownia G13 rok szczyt_popoludniowy | UNCONFIRMED / restored legacy | odczyt | kWh | 20.28 | AVAILABLE | pomocnicza | WYMAGA POPRAWY |
| sensor.kotlownia_g13_rok_szczyt_przedpoludniowy | Discovered supporting/legacy entity: Kotłownia G13 rok szczyt_przedpoludniowy | UNCONFIRMED / restored legacy | odczyt | kWh | 20.14 | AVAILABLE | pomocnicza | WYMAGA POPRAWY |
| sensor.kotlownia_total_energy | Discovered supporting/legacy entity: Kotłownia  Total energy | tuya | odczyt | kWh | unavailable | UNAVAILABLE_OR_UNKNOWN | pomocnicza | WYMAGA POPRAWY |
| sensor.kuropatnik | Discovered supporting/legacy entity: Solcast PV Forecast Kuropatnik | solcast_solar | odczyt | kWh | 9.1789 | AVAILABLE | pomocnicza | GOTOWA |
| sensor.licznik_glowny_kotlowni_moc | Discovered supporting/legacy entity: Moc | UNCONFIRMED / restored legacy | odczyt | niepodana | BRAK | DISABLED | pomocnicza | WYMAGA POPRAWY |
| sensor.licznik_glowny_kotlowni_napiecie | Discovered supporting/legacy entity: Napięcie | UNCONFIRMED / restored legacy | odczyt | niepodana | BRAK | DISABLED | pomocnicza | WYMAGA POPRAWY |
| sensor.licznik_glowny_kotlowni_natezenie_pradu | Discovered supporting/legacy entity: Natężenie prądu | UNCONFIRMED / restored legacy | odczyt | niepodana | BRAK | DISABLED | pomocnicza | WYMAGA POPRAWY |
| sensor.licznik_last_seen | Discovered supporting/legacy entity: Last seen | mqtt | odczyt | niepodana | BRAK | DISABLED | pomocnicza | WYMAGA POPRAWY |
| sensor.licznik_pompa_last_seen | Discovered supporting/legacy entity: Last seen | mqtt | odczyt | niepodana | BRAK | DISABLED | pomocnicza | WYMAGA POPRAWY |
| sensor.rotenso_ambient_temperature | Discovered supporting/legacy entity: Rotenso Ambient Temperature | UNCONFIRMED / restored legacy | odczyt | °C | unavailable | UNAVAILABLE_OR_UNKNOWN | pomocnicza | WYMAGA POPRAWY |
| sensor.rotenso_buffer_tank_lower_temperature | Discovered supporting/legacy entity: Rotenso Buffer Tank Lower Temperature | UNCONFIRMED / restored legacy | odczyt | °C | unavailable | UNAVAILABLE_OR_UNKNOWN | pomocnicza | WYMAGA POPRAWY |
| sensor.rotenso_buffer_tank_upper_temperature | Discovered supporting/legacy entity: Rotenso Buffer Tank Upper Temperature | UNCONFIRMED / restored legacy | odczyt | °C | unavailable | UNAVAILABLE_OR_UNKNOWN | pomocnicza | WYMAGA POPRAWY |
| sensor.rotenso_cisnienie_skraplania | Discovered supporting/legacy entity: Rotenso Cisnienie Skraplania | UNCONFIRMED / restored legacy | odczyt | kPa | unavailable | UNAVAILABLE_OR_UNKNOWN | pomocnicza | WYMAGA POPRAWY |
| sensor.rotenso_compressor_current_speed | Discovered supporting/legacy entity: Rotenso Compressor Current Speed | UNCONFIRMED / restored legacy | odczyt | Hz | unavailable | UNAVAILABLE_OR_UNKNOWN | pomocnicza | WYMAGA POPRAWY |
| sensor.rotenso_compressor_target_speed | Discovered supporting/legacy entity: Rotenso Compressor Target Speed | UNCONFIRMED / restored legacy | odczyt | Hz | unavailable | UNAVAILABLE_OR_UNKNOWN | pomocnicza | WYMAGA POPRAWY |
| sensor.rotenso_condensing_pressure | Discovered supporting/legacy entity: Rotenso Condensing Pressure | UNCONFIRMED / restored legacy | odczyt | niepodana | unavailable | UNAVAILABLE_OR_UNKNOWN | pomocnicza | WYMAGA POPRAWY |
| sensor.rotenso_control_temperature | Discovered supporting/legacy entity: Rotenso Control Temperature | UNCONFIRMED / restored legacy | odczyt | °C | unavailable | UNAVAILABLE_OR_UNKNOWN | pomocnicza | WYMAGA POPRAWY |
| sensor.rotenso_current_running_mode | Discovered supporting/legacy entity: Rotenso Current Running Mode | UNCONFIRMED / restored legacy | odczyt | niepodana | unavailable | UNAVAILABLE_OR_UNKNOWN | pomocnicza | WYMAGA POPRAWY |
| sensor.rotenso_czestotliwosc_sprezarki | Discovered supporting/legacy entity: Rotenso Czestotliwosc Sprezarki | UNCONFIRMED / restored legacy | odczyt | Hz | unavailable | UNAVAILABLE_OR_UNKNOWN | pomocnicza | WYMAGA POPRAWY |
| sensor.rotenso_discharge_temperature | Discovered supporting/legacy entity: Rotenso Discharge Temperature | UNCONFIRMED / restored legacy | odczyt | °C | unavailable | UNAVAILABLE_OR_UNKNOWN | pomocnicza | WYMAGA POPRAWY |
| sensor.rotenso_evaporating_pressure | Discovered supporting/legacy entity: Rotenso Evaporating Pressure | UNCONFIRMED / restored legacy | odczyt | niepodana | unavailable | UNAVAILABLE_OR_UNKNOWN | pomocnicza | WYMAGA POPRAWY |
| sensor.rotenso_hot_water_tank_temperature | Discovered supporting/legacy entity: Rotenso Hot Water Tank Temperature | UNCONFIRMED / restored legacy | odczyt | °C | unavailable | UNAVAILABLE_OR_UNKNOWN | pomocnicza | WYMAGA POPRAWY |
| sensor.rotenso_indoor_temperature | Discovered supporting/legacy entity: Rotenso Indoor Temperature | UNCONFIRMED / restored legacy | odczyt | °C | unavailable | UNAVAILABLE_OR_UNKNOWN | pomocnicza | WYMAGA POPRAWY |
| sensor.rotenso_inverter_current | Discovered supporting/legacy entity: Rotenso Inverter Current | UNCONFIRMED / restored legacy | odczyt | A | unavailable | UNAVAILABLE_OR_UNKNOWN | pomocnicza | WYMAGA POPRAWY |
| sensor.rotenso_inverter_temperature | Discovered supporting/legacy entity: Rotenso Inverter Temperature | UNCONFIRMED / restored legacy | odczyt | °C | unavailable | UNAVAILABLE_OR_UNKNOWN | pomocnicza | WYMAGA POPRAWY |
| sensor.rotenso_outlet_water_temperature | Discovered supporting/legacy entity: Rotenso Outlet Water Temperature | UNCONFIRMED / restored legacy | odczyt | °C | unavailable | UNAVAILABLE_OR_UNKNOWN | pomocnicza | WYMAGA POPRAWY |
| sensor.rotenso_suction_temperature | Discovered supporting/legacy entity: Rotenso Suction Temperature | UNCONFIRMED / restored legacy | odczyt | °C | unavailable | UNAVAILABLE_OR_UNKNOWN | pomocnicza | WYMAGA POPRAWY |
| sensor.rotenso_target_temperature | Discovered supporting/legacy entity: Rotenso Target Temperature | UNCONFIRMED / restored legacy | odczyt | °C | unavailable | UNAVAILABLE_OR_UNKNOWN | pomocnicza | WYMAGA POPRAWY |
| sensor.rotenso_temp_wody_cwu | Discovered supporting/legacy entity: Rotenso Temp Wody CWU | UNCONFIRMED / restored legacy | odczyt | °C | unavailable | UNAVAILABLE_OR_UNKNOWN | pomocnicza | WYMAGA POPRAWY |
| sensor.rotenso_temp_wody_wyjsciowa | Discovered supporting/legacy entity: Rotenso Temp Wody Wyjsciowa | UNCONFIRMED / restored legacy | odczyt | °C | unavailable | UNAVAILABLE_OR_UNKNOWN | pomocnicza | WYMAGA POPRAWY |
| sensor.rotenso_temp_zadana_co | Discovered supporting/legacy entity: Rotenso Temp Zadana CO | UNCONFIRMED / restored legacy | odczyt | °C | unavailable | UNAVAILABLE_OR_UNKNOWN | pomocnicza | WYMAGA POPRAWY |
| sensor.rotenso_temp_zewnetrzna | Discovered supporting/legacy entity: Rotenso Temp Zewnetrzna | UNCONFIRMED / restored legacy | odczyt | °C | unavailable | UNAVAILABLE_OR_UNKNOWN | pomocnicza | WYMAGA POPRAWY |
| sensor.rotenso_tryb_pracy | Discovered supporting/legacy entity: Rotenso Tryb Pracy | UNCONFIRMED / restored legacy | odczyt | niepodana | unavailable | UNAVAILABLE_OR_UNKNOWN | pomocnicza | WYMAGA POPRAWY |
| sensor.rotenso_unit_status | Discovered supporting/legacy entity: Rotenso Unit Status | UNCONFIRMED / restored legacy | odczyt | niepodana | unavailable | UNAVAILABLE_OR_UNKNOWN | pomocnicza | WYMAGA POPRAWY |
| sensor.solaredge_aktualna_moc | Discovered supporting/legacy entity: solaredge Aktualna moc | solaredge | odczyt | kW | 0.0 | AVAILABLE | pomocnicza | GOTOWA |
| sensor.solaredge_baterie | Discovered supporting/legacy entity: solaredge Baterie | solaredge | odczyt | niepodana | 1 | AVAILABLE | pomocnicza | GOTOWA |
| sensor.solaredge_calkowita_energia | Discovered supporting/legacy entity: solaredge Całkowita energia | solaredge | odczyt | kWh | 4.431 | AVAILABLE | pomocnicza | GOTOWA |
| sensor.solaredge_eksportowana_energia | Discovered supporting/legacy entity: solaredge Eksportowana energia | solaredge | odczyt | Wh | 1689.0 | AVAILABLE | pomocnicza | GOTOWA |
| sensor.solaredge_energia_sloneczna | Discovered supporting/legacy entity: Bieżąca moc paneli | solaredge | odczyt | kW | 0.0 | AVAILABLE | pomocnicza | GOTOWA |
| sensor.solaredge_energia_sloneczna_2 | Discovered supporting/legacy entity: SolarEdge Energia Sloneczna | UNCONFIRMED / restored legacy | odczyt | W | unavailable | UNAVAILABLE_OR_UNKNOWN | pomocnicza | WYMAGA POPRAWY |
| sensor.solaredge_energia_w_tym_miesiacu | Discovered supporting/legacy entity: solaredge Energia w tym miesiącu | solaredge | odczyt | kWh | 734.423 | AVAILABLE | pomocnicza | GOTOWA |
| sensor.solaredge_energia_w_tym_roku | Discovered supporting/legacy entity: solaredge Energia w tym roku | solaredge | odczyt | MWh | 12.316162 | AVAILABLE | pomocnicza | GOTOWA |
| sensor.solaredge_gateways | Discovered supporting/legacy entity: solaredge Gateways | solaredge | odczyt | niepodana | 0 | AVAILABLE | pomocnicza | GOTOWA |
| sensor.solaredge_grid_power | Discovered supporting/legacy entity: solaredge Grid power | solaredge | odczyt | kW | 1.98 | AVAILABLE | pomocnicza | GOTOWA |
| sensor.solaredge_i1_ac_apparent_power | Discovered supporting/legacy entity: AC Apparent Power | solaredge_modbus_multi | odczyt | niepodana | BRAK | DISABLED | pomocnicza | WYMAGA POPRAWY |
| sensor.solaredge_i1_ac_current | Discovered supporting/legacy entity: Solaredge I1 AC Current | solaredge_modbus_multi | odczyt | A | 0.0 | AVAILABLE | pomocnicza | GOTOWA |
| sensor.solaredge_i1_ac_current_a | Discovered supporting/legacy entity: Solaredge I1 AC Current A | solaredge_modbus_multi | odczyt | A | 0.0 | AVAILABLE | pomocnicza | GOTOWA |
| sensor.solaredge_i1_ac_current_b | Discovered supporting/legacy entity: Solaredge I1 AC Current B | solaredge_modbus_multi | odczyt | A | 0.0 | AVAILABLE | pomocnicza | GOTOWA |
| sensor.solaredge_i1_ac_current_c | Discovered supporting/legacy entity: Solaredge I1 AC Current C | solaredge_modbus_multi | odczyt | A | 0.0 | AVAILABLE | pomocnicza | GOTOWA |
| sensor.solaredge_i1_ac_energy | Discovered supporting/legacy entity: Solaredge I1 AC Energy | solaredge_modbus_multi | odczyt | kWh | 33849.14 | AVAILABLE | pomocnicza | GOTOWA |
| sensor.solaredge_i1_ac_frequency | Discovered supporting/legacy entity: Solaredge I1 AC Frequency | solaredge_modbus_multi | odczyt | Hz | 49.98 | AVAILABLE | pomocnicza | GOTOWA |
| sensor.solaredge_i1_ac_power | inverter.ac_power | solaredge_modbus_multi | odczyt | W | 0 | AVAILABLE | krytyczna | GOTOWA |
| sensor.solaredge_i1_ac_power_factor | Discovered supporting/legacy entity: AC Power Factor | solaredge_modbus_multi | odczyt | niepodana | BRAK | DISABLED | pomocnicza | WYMAGA POPRAWY |
| sensor.solaredge_i1_ac_reactive_power | Discovered supporting/legacy entity: AC Reactive Power | solaredge_modbus_multi | odczyt | niepodana | BRAK | DISABLED | pomocnicza | WYMAGA POPRAWY |
| sensor.solaredge_i1_ac_voltage_ab | Discovered supporting/legacy entity: Solaredge I1 AC Voltage AB | solaredge_modbus_multi | odczyt | V | 390.8 | AVAILABLE | pomocnicza | GOTOWA |
| sensor.solaredge_i1_ac_voltage_an | Discovered supporting/legacy entity: Solaredge I1 AC Voltage AN | solaredge_modbus_multi | odczyt | V | 226.4 | AVAILABLE | pomocnicza | GOTOWA |
| sensor.solaredge_i1_ac_voltage_bc | Discovered supporting/legacy entity: Solaredge I1 AC Voltage BC | solaredge_modbus_multi | odczyt | V | 399.6 | AVAILABLE | pomocnicza | GOTOWA |
| sensor.solaredge_i1_ac_voltage_bn | Discovered supporting/legacy entity: Solaredge I1 AC Voltage BN | solaredge_modbus_multi | odczyt | V | 224.5 | AVAILABLE | pomocnicza | GOTOWA |
| sensor.solaredge_i1_ac_voltage_ca | Discovered supporting/legacy entity: Solaredge I1 AC Voltage CA | solaredge_modbus_multi | odczyt | V | 392.9 | AVAILABLE | pomocnicza | GOTOWA |
| sensor.solaredge_i1_ac_voltage_cn | Discovered supporting/legacy entity: Solaredge I1 AC Voltage CN | solaredge_modbus_multi | odczyt | V | 232.4 | AVAILABLE | pomocnicza | GOTOWA |
| sensor.solaredge_i1_b1_available_energy | Discovered supporting/legacy entity: Solaredge I1 B1 Available Energy | solaredge_modbus_multi | odczyt | kWh | 8.8473603515625 | AVAILABLE | pomocnicza | WYMAGA POPRAWY |
| sensor.solaredge_i1_b1_average_temperature | battery.temperature | solaredge_modbus_multi | odczyt | °C | 14.5 | AVAILABLE | krytyczna | GOTOWA |
| sensor.solaredge_i1_b1_dc_current | Discovered supporting/legacy entity: Solaredge I1 B1 DC Current | solaredge_modbus_multi | odczyt | A | 0.0 | AVAILABLE | pomocnicza | GOTOWA |
| sensor.solaredge_i1_b1_dc_power | battery.power | solaredge_modbus_multi | odczyt | W | 0.0 | AVAILABLE | krytyczna | GOTOWA |
| sensor.solaredge_i1_b1_dc_power_inverted | Discovered supporting/legacy entity: DC Power Inverted | solaredge_modbus_multi | odczyt | niepodana | BRAK | DISABLED | pomocnicza | WYMAGA POPRAWY |
| sensor.solaredge_i1_b1_dc_voltage | Discovered supporting/legacy entity: Solaredge I1 B1 DC Voltage | solaredge_modbus_multi | odczyt | V | 2.10226893424988 | AVAILABLE | pomocnicza | GOTOWA |
| sensor.solaredge_i1_b1_device | Discovered supporting/legacy entity: Solaredge I1 B1 Device | solaredge_modbus_multi | odczyt | niepodana | SolarEdge Home Battery 9.2kWh | AVAILABLE | pomocnicza | GOTOWA |
| sensor.solaredge_i1_b1_energy_export | Discovered supporting/legacy entity: Solaredge I1 B1 Energy Export | solaredge_modbus_multi | odczyt | kWh | 13.27 | AVAILABLE | pomocnicza | GOTOWA |
| sensor.solaredge_i1_b1_energy_import | Discovered supporting/legacy entity: Solaredge I1 B1 Energy Import | solaredge_modbus_multi | odczyt | kWh | 10.098 | AVAILABLE | pomocnicza | GOTOWA |
| sensor.solaredge_i1_b1_last_update | Discovered supporting/legacy entity: Last Update | solaredge_modbus_multi | odczyt | niepodana | BRAK | DISABLED | pomocnicza | WYMAGA POPRAWY |
| sensor.solaredge_i1_b1_max_charge_power | battery.max_charge | solaredge_modbus_multi | odczyt | W | 5000.0 | AVAILABLE | krytyczna | GOTOWA |
| sensor.solaredge_i1_b1_max_discharge_power | battery.max_discharge | solaredge_modbus_multi | odczyt | W | 5000.0 | AVAILABLE | krytyczna | GOTOWA |
| sensor.solaredge_i1_b1_max_temperature | Discovered supporting/legacy entity: Max Temperature | solaredge_modbus_multi | odczyt | niepodana | BRAK | DISABLED | pomocnicza | WYMAGA POPRAWY |
| sensor.solaredge_i1_b1_maximum_energy | battery.capacity | solaredge_modbus_multi | odczyt | kWh | 9.2 | AVAILABLE | krytyczna | GOTOWA |
| sensor.solaredge_i1_b1_peak_charge_power | battery.peak_charge | solaredge_modbus_multi | odczyt | W | 4936.0 | AVAILABLE | krytyczna | GOTOWA |
| sensor.solaredge_i1_b1_peak_discharge_power | battery.peak_discharge | solaredge_modbus_multi | odczyt | W | 5000.0 | AVAILABLE | krytyczna | GOTOWA |
| sensor.solaredge_i1_b1_state_of_energy | battery.soc | solaredge_modbus_multi | odczyt | % | 0.0 | AVAILABLE | krytyczna | GOTOWA |
| sensor.solaredge_i1_b1_state_of_health | Discovered supporting/legacy entity: Solaredge I1 B1 State of Health | solaredge_modbus_multi | odczyt | % | 96.0 | AVAILABLE | pomocnicza | GOTOWA |
| sensor.solaredge_i1_b1_status | battery.status | solaredge_modbus_multi | odczyt | niepodana | B_STATUS_POWER_SAVING | AVAILABLE | krytyczna | GOTOWA |
| sensor.solaredge_i1_b1_version | Discovered supporting/legacy entity: Solaredge I1 B1 Version | solaredge_modbus_multi | odczyt | niepodana | 48V DCDC 3.5.13 | AVAILABLE | pomocnicza | GOTOWA |
| sensor.solaredge_i1_dc_current | Discovered supporting/legacy entity: Solaredge I1 DC Current | solaredge_modbus_multi | odczyt | A | 0 | AVAILABLE | pomocnicza | GOTOWA |
| sensor.solaredge_i1_dc_power | inverter.dc_power | solaredge_modbus_multi | odczyt | kW | 0.0 | AVAILABLE | krytyczna | WYMAGA POPRAWY |
| sensor.solaredge_i1_dc_voltage | Discovered supporting/legacy entity: Solaredge I1 DC Voltage | solaredge_modbus_multi | odczyt | V | 1.4 | AVAILABLE | pomocnicza | GOTOWA |
| sensor.solaredge_i1_derb1_device | Discovered supporting/legacy entity: Solaredge I1 DERB1 Device | solaredge_modbus_multi | odczyt | niepodana | SE10K-RWB48BFN4 | AVAILABLE | pomocnicza | GOTOWA |
| sensor.solaredge_i1_derb1_last_update | Discovered supporting/legacy entity: Last Update | solaredge_modbus_multi | odczyt | niepodana | BRAK | DISABLED | pomocnicza | WYMAGA POPRAWY |
| sensor.solaredge_i1_derb1_state_of_energy | Discovered supporting/legacy entity: Solaredge I1 DERB1 State of Energy | solaredge_modbus_multi | odczyt | % | 0.0 | AVAILABLE | pomocnicza | GOTOWA |
| sensor.solaredge_i1_derb1_state_of_health | Discovered supporting/legacy entity: Solaredge I1 DERB1 State of Health | solaredge_modbus_multi | odczyt | % | unavailable | UNAVAILABLE_OR_UNKNOWN | pomocnicza | WYMAGA POPRAWY |
| sensor.solaredge_i1_derb1_status | Discovered supporting/legacy entity: Status | solaredge_modbus_multi | odczyt | niepodana | BRAK | DISABLED | pomocnicza | WYMAGA POPRAWY |
| sensor.solaredge_i1_device | Discovered supporting/legacy entity: Solaredge I1 Device | solaredge_modbus_multi | odczyt | niepodana | SE10K-RWB48BFN4 | AVAILABLE | pomocnicza | GOTOWA |
| sensor.solaredge_i1_last_update | Discovered supporting/legacy entity: Last Update | solaredge_modbus_multi | odczyt | niepodana | BRAK | DISABLED | pomocnicza | WYMAGA POPRAWY |
| sensor.solaredge_i1_m1_ac_apparent_power | Discovered supporting/legacy entity: AC Apparent Power | solaredge_modbus_multi | odczyt | niepodana | BRAK | DISABLED | pomocnicza | WYMAGA POPRAWY |
| sensor.solaredge_i1_m1_ac_apparent_power_a | Discovered supporting/legacy entity: AC Apparent Power A | solaredge_modbus_multi | odczyt | niepodana | BRAK | DISABLED | pomocnicza | WYMAGA POPRAWY |
| sensor.solaredge_i1_m1_ac_apparent_power_b | Discovered supporting/legacy entity: AC Apparent Power B | solaredge_modbus_multi | odczyt | niepodana | BRAK | DISABLED | pomocnicza | WYMAGA POPRAWY |
| sensor.solaredge_i1_m1_ac_apparent_power_c | Discovered supporting/legacy entity: AC Apparent Power C | solaredge_modbus_multi | odczyt | niepodana | BRAK | DISABLED | pomocnicza | WYMAGA POPRAWY |
| sensor.solaredge_i1_m1_ac_current | Discovered supporting/legacy entity: Solaredge I1 M1 AC Current | solaredge_modbus_multi | odczyt | A | 10.25 | AVAILABLE | pomocnicza | GOTOWA |
| sensor.solaredge_i1_m1_ac_current_a | Discovered supporting/legacy entity: Solaredge I1 M1 AC Current A | solaredge_modbus_multi | odczyt | A | 8.67 | AVAILABLE | pomocnicza | GOTOWA |
| sensor.solaredge_i1_m1_ac_current_b | Discovered supporting/legacy entity: Solaredge I1 M1 AC Current B | solaredge_modbus_multi | odczyt | A | 1.11 | AVAILABLE | pomocnicza | GOTOWA |
| sensor.solaredge_i1_m1_ac_current_c | Discovered supporting/legacy entity: Solaredge I1 M1 AC Current C | solaredge_modbus_multi | odczyt | A | 0.469 | AVAILABLE | pomocnicza | GOTOWA |
| sensor.solaredge_i1_m1_ac_energy_exported | grid.export_energy | solaredge_modbus_multi | odczyt | kWh | 20563.439 | AVAILABLE | krytyczna | GOTOWA |
| sensor.solaredge_i1_m1_ac_energy_exported_a | Discovered supporting/legacy entity: Solaredge I1 M1 AC Energy Exported A | solaredge_modbus_multi | odczyt | kWh | 5603.77 | AVAILABLE | pomocnicza | GOTOWA |
| sensor.solaredge_i1_m1_ac_energy_exported_b | Discovered supporting/legacy entity: Solaredge I1 M1 AC Energy Exported B | solaredge_modbus_multi | odczyt | kWh | 7868.55 | AVAILABLE | pomocnicza | GOTOWA |
| sensor.solaredge_i1_m1_ac_energy_exported_c | Discovered supporting/legacy entity: Solaredge I1 M1 AC Energy Exported C | solaredge_modbus_multi | odczyt | kWh | 7091.12 | AVAILABLE | pomocnicza | GOTOWA |
| sensor.solaredge_i1_m1_ac_energy_imported | grid.import_energy | solaredge_modbus_multi | odczyt | kWh | 17590.39 | AVAILABLE | krytyczna | GOTOWA |
| sensor.solaredge_i1_m1_ac_energy_imported_a | Discovered supporting/legacy entity: Solaredge I1 M1 AC Energy Imported A | solaredge_modbus_multi | odczyt | kWh | 12957.97 | AVAILABLE | pomocnicza | GOTOWA |
| sensor.solaredge_i1_m1_ac_energy_imported_b | Discovered supporting/legacy entity: Solaredge I1 M1 AC Energy Imported B | solaredge_modbus_multi | odczyt | kWh | 1474.94 | AVAILABLE | pomocnicza | GOTOWA |
| sensor.solaredge_i1_m1_ac_energy_imported_c | Discovered supporting/legacy entity: Solaredge I1 M1 AC Energy Imported C | solaredge_modbus_multi | odczyt | kWh | 3157.48 | AVAILABLE | pomocnicza | GOTOWA |
| sensor.solaredge_i1_m1_ac_frequency | Discovered supporting/legacy entity: Solaredge I1 M1 AC Frequency | solaredge_modbus_multi | odczyt | Hz | 49.99 | AVAILABLE | pomocnicza | GOTOWA |
| sensor.solaredge_i1_m1_ac_power | grid.net_power | solaredge_modbus_multi | odczyt | kW | -2.139 | AVAILABLE | krytyczna | GOTOWA |
| sensor.solaredge_i1_m1_ac_power_a | Discovered supporting/legacy entity: Solaredge I1 M1 AC Power A | solaredge_modbus_multi | odczyt | W | -1851.0 | AVAILABLE | pomocnicza | GOTOWA |
| sensor.solaredge_i1_m1_ac_power_b | Discovered supporting/legacy entity: Solaredge I1 M1 AC Power B | solaredge_modbus_multi | odczyt | W | -232.0 | AVAILABLE | pomocnicza | GOTOWA |
| sensor.solaredge_i1_m1_ac_power_c | Discovered supporting/legacy entity: Solaredge I1 M1 AC Power C | solaredge_modbus_multi | odczyt | W | -56.0 | AVAILABLE | pomocnicza | GOTOWA |
| sensor.solaredge_i1_m1_ac_power_factor | Discovered supporting/legacy entity: AC Power Factor | solaredge_modbus_multi | odczyt | niepodana | BRAK | DISABLED | pomocnicza | WYMAGA POPRAWY |
| sensor.solaredge_i1_m1_ac_power_factor_a | Discovered supporting/legacy entity: AC Power Factor A | solaredge_modbus_multi | odczyt | niepodana | BRAK | DISABLED | pomocnicza | WYMAGA POPRAWY |
| sensor.solaredge_i1_m1_ac_power_factor_b | Discovered supporting/legacy entity: AC Power Factor B | solaredge_modbus_multi | odczyt | niepodana | BRAK | DISABLED | pomocnicza | WYMAGA POPRAWY |
| sensor.solaredge_i1_m1_ac_power_factor_c | Discovered supporting/legacy entity: AC Power Factor C | solaredge_modbus_multi | odczyt | niepodana | BRAK | DISABLED | pomocnicza | WYMAGA POPRAWY |
| sensor.solaredge_i1_m1_ac_power_inverted | Discovered supporting/legacy entity: AC Power Inverted | solaredge_modbus_multi | odczyt | niepodana | BRAK | DISABLED | pomocnicza | WYMAGA POPRAWY |
| sensor.solaredge_i1_m1_ac_reactive_power | Discovered supporting/legacy entity: AC Reactive Power | solaredge_modbus_multi | odczyt | niepodana | BRAK | DISABLED | pomocnicza | WYMAGA POPRAWY |
| sensor.solaredge_i1_m1_ac_reactive_power_a | Discovered supporting/legacy entity: AC Reactive Power A | solaredge_modbus_multi | odczyt | niepodana | BRAK | DISABLED | pomocnicza | WYMAGA POPRAWY |
| sensor.solaredge_i1_m1_ac_reactive_power_b | Discovered supporting/legacy entity: AC Reactive Power B | solaredge_modbus_multi | odczyt | niepodana | BRAK | DISABLED | pomocnicza | WYMAGA POPRAWY |
| sensor.solaredge_i1_m1_ac_reactive_power_c | Discovered supporting/legacy entity: AC Reactive Power C | solaredge_modbus_multi | odczyt | niepodana | BRAK | DISABLED | pomocnicza | WYMAGA POPRAWY |
| sensor.solaredge_i1_m1_ac_voltage_ab | Discovered supporting/legacy entity: Solaredge I1 M1 AC Voltage AB | solaredge_modbus_multi | odczyt | V | 0.0 | AVAILABLE | pomocnicza | GOTOWA |
| sensor.solaredge_i1_m1_ac_voltage_an | Discovered supporting/legacy entity: Solaredge I1 M1 AC Voltage AN | solaredge_modbus_multi | odczyt | V | 225.3 | AVAILABLE | pomocnicza | GOTOWA |
| sensor.solaredge_i1_m1_ac_voltage_bc | Discovered supporting/legacy entity: Solaredge I1 M1 AC Voltage BC | solaredge_modbus_multi | odczyt | V | 0.0 | AVAILABLE | pomocnicza | GOTOWA |
| sensor.solaredge_i1_m1_ac_voltage_bn | Discovered supporting/legacy entity: Solaredge I1 M1 AC Voltage BN | solaredge_modbus_multi | odczyt | V | 226.69 | AVAILABLE | pomocnicza | GOTOWA |
| sensor.solaredge_i1_m1_ac_voltage_ca | Discovered supporting/legacy entity: Solaredge I1 M1 AC Voltage CA | solaredge_modbus_multi | odczyt | V | 0.0 | AVAILABLE | pomocnicza | GOTOWA |
| sensor.solaredge_i1_m1_ac_voltage_cn | Discovered supporting/legacy entity: Solaredge I1 M1 AC Voltage CN | solaredge_modbus_multi | odczyt | V | 232.69 | AVAILABLE | pomocnicza | GOTOWA |
| sensor.solaredge_i1_m1_ac_voltage_ll | Discovered supporting/legacy entity: Solaredge I1 M1 AC Voltage LL | solaredge_modbus_multi | odczyt | V | 0.0 | AVAILABLE | pomocnicza | GOTOWA |
| sensor.solaredge_i1_m1_ac_voltage_ln | Discovered supporting/legacy entity: Solaredge I1 M1 AC Voltage LN | solaredge_modbus_multi | odczyt | V | 225.3 | AVAILABLE | pomocnicza | GOTOWA |
| sensor.solaredge_i1_m1_apparent_energy_exported | Discovered supporting/legacy entity: Apparent Energy Exported | solaredge_modbus_multi | odczyt | niepodana | BRAK | DISABLED | pomocnicza | WYMAGA POPRAWY |
| sensor.solaredge_i1_m1_apparent_energy_exported_a | Discovered supporting/legacy entity: Apparent Energy Exported A | solaredge_modbus_multi | odczyt | niepodana | BRAK | DISABLED | pomocnicza | WYMAGA POPRAWY |
| sensor.solaredge_i1_m1_apparent_energy_exported_b | Discovered supporting/legacy entity: Apparent Energy Exported B | solaredge_modbus_multi | odczyt | niepodana | BRAK | DISABLED | pomocnicza | WYMAGA POPRAWY |
| sensor.solaredge_i1_m1_apparent_energy_exported_c | Discovered supporting/legacy entity: Apparent Energy Exported C | solaredge_modbus_multi | odczyt | niepodana | BRAK | DISABLED | pomocnicza | WYMAGA POPRAWY |
| sensor.solaredge_i1_m1_apparent_energy_imported | Discovered supporting/legacy entity: Apparent Energy Imported | solaredge_modbus_multi | odczyt | niepodana | BRAK | DISABLED | pomocnicza | WYMAGA POPRAWY |
| sensor.solaredge_i1_m1_apparent_energy_imported_a | Discovered supporting/legacy entity: Apparent Energy Imported A | solaredge_modbus_multi | odczyt | niepodana | BRAK | DISABLED | pomocnicza | WYMAGA POPRAWY |
| sensor.solaredge_i1_m1_apparent_energy_imported_b | Discovered supporting/legacy entity: Apparent Energy Imported B | solaredge_modbus_multi | odczyt | niepodana | BRAK | DISABLED | pomocnicza | WYMAGA POPRAWY |
| sensor.solaredge_i1_m1_apparent_energy_imported_c | Discovered supporting/legacy entity: Apparent Energy Imported C | solaredge_modbus_multi | odczyt | niepodana | BRAK | DISABLED | pomocnicza | WYMAGA POPRAWY |
| sensor.solaredge_i1_m1_device | Discovered supporting/legacy entity: Solaredge I1 M1 Device | solaredge_modbus_multi | odczyt | niepodana | PRO380-Mod | AVAILABLE | pomocnicza | GOTOWA |
| sensor.solaredge_i1_m1_last_update | Discovered supporting/legacy entity: Last Update | solaredge_modbus_multi | odczyt | niepodana | BRAK | DISABLED | pomocnicza | WYMAGA POPRAWY |
| sensor.solaredge_i1_m1_meter_events | Discovered supporting/legacy entity: Solaredge I1 M1 Meter Events | solaredge_modbus_multi | odczyt | niepodana | 0 | AVAILABLE | pomocnicza | GOTOWA |
| sensor.solaredge_i1_m1_oddana_energia_dzienna | Discovered supporting/legacy entity: Solaredge I1 M1 Oddana energia dzienna | utility_meter | odczyt | kWh | 1.689 | AVAILABLE | pomocnicza | GOTOWA |
| sensor.solaredge_i1_m1_oddana_energia_miesieczna | Discovered supporting/legacy entity: Solaredge I1 M1 Oddana energia miesięczna | utility_meter | odczyt | kWh | 554.189 | AVAILABLE | pomocnicza | GOTOWA |
| sensor.solaredge_i1_m1_oddana_energia_roczna | Discovered supporting/legacy entity: Solaredge I1 M1 Oddana energia roczna | utility_meter | odczyt | kWh | 815.139 | AVAILABLE | pomocnicza | GOTOWA |
| sensor.solaredge_i1_m1_reactive_energy_export_q3 | Discovered supporting/legacy entity: Reactive Energy Export Q3 | solaredge_modbus_multi | odczyt | niepodana | BRAK | DISABLED | pomocnicza | WYMAGA POPRAWY |
| sensor.solaredge_i1_m1_reactive_energy_export_q3_a | Discovered supporting/legacy entity: Reactive Energy Export Q3 A | solaredge_modbus_multi | odczyt | niepodana | BRAK | DISABLED | pomocnicza | WYMAGA POPRAWY |
| sensor.solaredge_i1_m1_reactive_energy_export_q3_b | Discovered supporting/legacy entity: Reactive Energy Export Q3 B | solaredge_modbus_multi | odczyt | niepodana | BRAK | DISABLED | pomocnicza | WYMAGA POPRAWY |
| sensor.solaredge_i1_m1_reactive_energy_export_q3_c | Discovered supporting/legacy entity: Reactive Energy Export Q3 C | solaredge_modbus_multi | odczyt | niepodana | BRAK | DISABLED | pomocnicza | WYMAGA POPRAWY |
| sensor.solaredge_i1_m1_reactive_energy_export_q4 | Discovered supporting/legacy entity: Reactive Energy Export Q4 | solaredge_modbus_multi | odczyt | niepodana | BRAK | DISABLED | pomocnicza | WYMAGA POPRAWY |
| sensor.solaredge_i1_m1_reactive_energy_export_q4_a | Discovered supporting/legacy entity: Reactive Energy Export Q4 A | solaredge_modbus_multi | odczyt | niepodana | BRAK | DISABLED | pomocnicza | WYMAGA POPRAWY |
| sensor.solaredge_i1_m1_reactive_energy_export_q4_b | Discovered supporting/legacy entity: Reactive Energy Export Q4 B | solaredge_modbus_multi | odczyt | niepodana | BRAK | DISABLED | pomocnicza | WYMAGA POPRAWY |
| sensor.solaredge_i1_m1_reactive_energy_export_q4_c | Discovered supporting/legacy entity: Reactive Energy Export Q4 C | solaredge_modbus_multi | odczyt | niepodana | BRAK | DISABLED | pomocnicza | WYMAGA POPRAWY |
| sensor.solaredge_i1_m1_reactive_energy_import_q1 | Discovered supporting/legacy entity: Reactive Energy Import Q1 | solaredge_modbus_multi | odczyt | niepodana | BRAK | DISABLED | pomocnicza | WYMAGA POPRAWY |
| sensor.solaredge_i1_m1_reactive_energy_import_q1_a | Discovered supporting/legacy entity: Reactive Energy Import Q1 A | solaredge_modbus_multi | odczyt | niepodana | BRAK | DISABLED | pomocnicza | WYMAGA POPRAWY |
| sensor.solaredge_i1_m1_reactive_energy_import_q1_b | Discovered supporting/legacy entity: Reactive Energy Import Q1 B | solaredge_modbus_multi | odczyt | niepodana | BRAK | DISABLED | pomocnicza | WYMAGA POPRAWY |
| sensor.solaredge_i1_m1_reactive_energy_import_q1_c | Discovered supporting/legacy entity: Reactive Energy Import Q1 C | solaredge_modbus_multi | odczyt | niepodana | BRAK | DISABLED | pomocnicza | WYMAGA POPRAWY |
| sensor.solaredge_i1_m1_reactive_energy_import_q2 | Discovered supporting/legacy entity: Reactive Energy Import Q2 | solaredge_modbus_multi | odczyt | niepodana | BRAK | DISABLED | pomocnicza | WYMAGA POPRAWY |
| sensor.solaredge_i1_m1_reactive_energy_import_q2_a | Discovered supporting/legacy entity: Reactive Energy Import Q2 A | solaredge_modbus_multi | odczyt | niepodana | BRAK | DISABLED | pomocnicza | WYMAGA POPRAWY |
| sensor.solaredge_i1_m1_reactive_energy_import_q2_b | Discovered supporting/legacy entity: Reactive Energy Import Q2 B | solaredge_modbus_multi | odczyt | niepodana | BRAK | DISABLED | pomocnicza | WYMAGA POPRAWY |
| sensor.solaredge_i1_m1_reactive_energy_import_q2_c | Discovered supporting/legacy entity: Reactive Energy Import Q2 C | solaredge_modbus_multi | odczyt | niepodana | BRAK | DISABLED | pomocnicza | WYMAGA POPRAWY |
| sensor.solaredge_i1_m1_version | Discovered supporting/legacy entity: Solaredge I1 M1 Version | solaredge_modbus_multi | odczyt | niepodana | 2.18 | AVAILABLE | pomocnicza | GOTOWA |
| sensor.solaredge_i1_m1_zuzycie_dzienne_g13_dolina | Discovered supporting/legacy entity: Solaredge I1 M1 Zużycie dzienne G13 dolina | utility_meter | odczyt | kWh | 13.461 | AVAILABLE | pomocnicza | GOTOWA |
| sensor.solaredge_i1_m1_zuzycie_dzienne_g13_szczyt_popoludniowy | Discovered supporting/legacy entity: Solaredge I1 M1 Zużycie dzienne G13 szczyt_popoludniowy | utility_meter | odczyt | kWh | 6.280 | AVAILABLE | pomocnicza | GOTOWA |
| sensor.solaredge_i1_m1_zuzycie_dzienne_g13_szczyt_przedpoludniowy | Discovered supporting/legacy entity: Solaredge I1 M1 Zużycie dzienne G13 szczyt_przedpoludniowy | utility_meter | odczyt | kWh | 5.949 | AVAILABLE | pomocnicza | GOTOWA |
| sensor.solaredge_i1_m1_zuzycie_miesieczne_g13_dolina | Discovered supporting/legacy entity: Solaredge I1 M1 Zużycie miesięczne G13 dolina | utility_meter | odczyt | kWh | 222.292 | AVAILABLE | pomocnicza | GOTOWA |
| sensor.solaredge_i1_m1_zuzycie_miesieczne_g13_szczyt_popoludniowy | Discovered supporting/legacy entity: Solaredge I1 M1 Zużycie miesięczne G13 szczyt_popoludniowy | utility_meter | odczyt | kWh | 27.694 | AVAILABLE | pomocnicza | GOTOWA |
| sensor.solaredge_i1_m1_zuzycie_miesieczne_g13_szczyt_przedpoludniowy | Discovered supporting/legacy entity: Solaredge I1 M1 Zużycie miesięczne G13 szczyt_przedpoludniowy | utility_meter | odczyt | kWh | 68.901 | AVAILABLE | pomocnicza | GOTOWA |
| sensor.solaredge_i1_m1_zuzycie_roczne_g13_dolina | Discovered supporting/legacy entity: Solaredge I1 M1 Zużycie roczne G13 dolina | utility_meter | odczyt | kWh | 255.169 | AVAILABLE | pomocnicza | GOTOWA |
| sensor.solaredge_i1_m1_zuzycie_roczne_g13_szczyt_popoludniowy | Discovered supporting/legacy entity: Solaredge I1 M1 Zużycie roczne G13 szczyt_popoludniowy | utility_meter | odczyt | kWh | 35.625 | AVAILABLE | pomocnicza | GOTOWA |
| sensor.solaredge_i1_m1_zuzycie_roczne_g13_szczyt_przedpoludniowy | Discovered supporting/legacy entity: Solaredge I1 M1 Zużycie roczne G13 szczyt_przedpoludniowy | utility_meter | odczyt | kWh | 75.622 | AVAILABLE | pomocnicza | GOTOWA |
| sensor.solaredge_i1_status | inverter.status | solaredge_modbus_multi | odczyt | niepodana | I_STATUS_SLEEPING | AVAILABLE | krytyczna | GOTOWA |
| sensor.solaredge_i1_status_vendor | Discovered supporting/legacy entity: Status Vendor | solaredge_modbus_multi | odczyt | niepodana | BRAK | DISABLED | pomocnicza | WYMAGA POPRAWY |
| sensor.solaredge_i1_status_vendor_4 | Discovered supporting/legacy entity: Solaredge I1 Status Vendor 4 | solaredge_modbus_multi | odczyt | niepodana | 0x0 | AVAILABLE | pomocnicza | GOTOWA |
| sensor.solaredge_i1_temperature | Discovered supporting/legacy entity: Solaredge I1 Temperature | solaredge_modbus_multi | odczyt | °C | 26.54 | AVAILABLE | pomocnicza | GOTOWA |
| sensor.solaredge_i1_version | Discovered supporting/legacy entity: Solaredge I1 Version | solaredge_modbus_multi | odczyt | niepodana | 0004.0025.0011 | AVAILABLE | pomocnicza | GOTOWA |
| sensor.solaredge_i1_write_count | Discovered supporting/legacy entity: Solaredge I1 Write Count | solaredge_modbus_multi | odczyt | niepodana | 598 | AVAILABLE | pomocnicza | GOTOWA |
| sensor.solaredge_imported_energy | Discovered supporting/legacy entity: solaredge Imported energy | solaredge | odczyt | kWh | 25.61 | AVAILABLE | pomocnicza | GOTOWA |
| sensor.solaredge_inverters | Discovered supporting/legacy entity: solaredge Inverters | solaredge | odczyt | niepodana | 1 | AVAILABLE | pomocnicza | GOTOWA |
| sensor.solaredge_lifetime_energy | Discovered supporting/legacy entity: solaredge Lifetime energy | solaredge | odczyt | kWh | 33464.446 | AVAILABLE | pomocnicza | GOTOWA |
| sensor.solaredge_local_bateria_moc | Discovered supporting/legacy entity: SolarEdge Local Bateria Moc | UNCONFIRMED / restored legacy | odczyt | W | unavailable | UNAVAILABLE_OR_UNKNOWN | pomocnicza | WYMAGA POPRAWY |
| sensor.solaredge_local_bateria_poziom | Discovered supporting/legacy entity: SolarEdge Local Bateria Poziom | UNCONFIRMED / restored legacy | odczyt | % | unavailable | UNAVAILABLE_OR_UNKNOWN | pomocnicza | WYMAGA POPRAWY |
| sensor.solaredge_local_moc_inwertera | Discovered supporting/legacy entity: SolarEdge Local Moc Inwertera | UNCONFIRMED / restored legacy | odczyt | W | unavailable | UNAVAILABLE_OR_UNKNOWN | pomocnicza | WYMAGA POPRAWY |
| sensor.solaredge_local_moc_licznika | Discovered supporting/legacy entity: SolarEdge Local Moc Licznika | UNCONFIRMED / restored legacy | odczyt | W | unavailable | UNAVAILABLE_OR_UNKNOWN | pomocnicza | WYMAGA POPRAWY |
| sensor.solaredge_meters | Discovered supporting/legacy entity: solaredge Meters | solaredge | odczyt | niepodana | 3 | AVAILABLE | pomocnicza | GOTOWA |
| sensor.solaredge_power_consumption | Discovered supporting/legacy entity: Bieżace zużycie | solaredge | odczyt | kW | 1.98 | AVAILABLE | pomocnicza | GOTOWA |
| sensor.solaredge_power_consumption_2 | Discovered supporting/legacy entity: SolarEdge Power Consumption | UNCONFIRMED / restored legacy | odczyt | W | unavailable | UNAVAILABLE_OR_UNKNOWN | pomocnicza | WYMAGA POPRAWY |
| sensor.solaredge_produced_energy | Discovered supporting/legacy entity: solaredge Produced energy | solaredge | odczyt | kWh | 4.431 | AVAILABLE | pomocnicza | GOTOWA |
| sensor.solaredge_pv_dc_power_w | Discovered supporting/legacy entity: SolarEdge PV DC Power W | HA template YAML | odczyt | W | 0 | AVAILABLE | pomocnicza | WYMAGA POPRAWY |
| sensor.solaredge_raw_ac_power | Discovered supporting/legacy entity: SolarEdge Raw AC Power | UNCONFIRMED / restored legacy | odczyt | W | unavailable | UNAVAILABLE_OR_UNKNOWN | pomocnicza | WYMAGA POPRAWY |
| sensor.solaredge_self_consumed_energy | Discovered supporting/legacy entity: solaredge Self-consumed energy | solaredge | odczyt | kWh | 2.742 | AVAILABLE | pomocnicza | GOTOWA |
| sensor.solaredge_sensors | Discovered supporting/legacy entity: solaredge Sensors | solaredge | odczyt | niepodana | 0 | AVAILABLE | pomocnicza | GOTOWA |
| sensor.solaredge_site_details | Discovered supporting/legacy entity: solaredge Site details | solaredge | odczyt | niepodana | Active | AVAILABLE | pomocnicza | GOTOWA |
| sensor.solaredge_storage_level | Discovered supporting/legacy entity: Naładowanie magazynu energi | solaredge | odczyt | % | 0 | AVAILABLE | pomocnicza | GOTOWA |
| sensor.solaredge_storage_level_2 | Discovered supporting/legacy entity: SolarEdge Storage Level | UNCONFIRMED / restored legacy | odczyt | % | unavailable | UNAVAILABLE_OR_UNKNOWN | pomocnicza | WYMAGA POPRAWY |
| sensor.solaredge_storage_power | Discovered supporting/legacy entity: solaredge Storage power | solaredge | odczyt | kW | 0.0 | AVAILABLE | pomocnicza | GOTOWA |
| sensor.solaredge_storage_power_2 | Discovered supporting/legacy entity: SolarEdge Storage Power | UNCONFIRMED / restored legacy | odczyt | W | unavailable | UNAVAILABLE_OR_UNKNOWN | pomocnicza | WYMAGA POPRAWY |
| sensor.solaredge_zuzyta_energia | Discovered supporting/legacy entity: solaredge Zużyta energia | solaredge | odczyt | kWh | 28.352 | AVAILABLE | pomocnicza | GOTOWA |
| sensor.solcast_pv_forecast_aktualna_moc | Discovered supporting/legacy entity: Solcast PV Forecast Aktualna moc | solcast_solar | odczyt | W | 0 | AVAILABLE | pomocnicza | GOTOWA |
| sensor.solcast_pv_forecast_czas_szczytowej_mocy_dzisiaj | Discovered supporting/legacy entity: Solcast PV Forecast Czas szczytowej mocy dzisiaj | solcast_solar | odczyt | niepodana | 2026-10-19T10:30:00+00:00 | AVAILABLE | pomocnicza | GOTOWA |
| sensor.solcast_pv_forecast_czas_szczytowej_mocy_jutro | Discovered supporting/legacy entity: Solcast PV Forecast Czas szczytowej mocy jutro | solcast_solar | odczyt | niepodana | 2026-10-20T12:30:00+00:00 | AVAILABLE | pomocnicza | GOTOWA |
| sensor.solcast_pv_forecast_liczba_wykorzystanych_zapytan_api | Discovered supporting/legacy entity: Solcast PV Forecast Liczba wykorzystanych zapytań API | solcast_solar | odczyt | niepodana | 10 | AVAILABLE | pomocnicza | GOTOWA |
| sensor.solcast_pv_forecast_limit_zapytan_api | Discovered supporting/legacy entity: Solcast PV Forecast Limit zapytań API | solcast_solar | odczyt | niepodana | 10 | AVAILABLE | pomocnicza | GOTOWA |
| sensor.solcast_pv_forecast_moc_w_1_godzine | Discovered supporting/legacy entity: Solcast PV Forecast Moc w 1 godzinę | solcast_solar | odczyt | W | 0 | AVAILABLE | pomocnicza | GOTOWA |
| sensor.solcast_pv_forecast_moc_w_30_minut | Discovered supporting/legacy entity: Solcast PV Forecast Moc w 30 minut | solcast_solar | odczyt | W | 0 | AVAILABLE | pomocnicza | GOTOWA |
| sensor.solcast_pv_forecast_ostatnia_aktualizacja_api | pv.forecast_issue_time | solcast_solar | odczyt | niepodana | 2026-10-19T14:50:07+00:00 | AVAILABLE | krytyczna | GOTOWA |
| sensor.solcast_pv_forecast_pozostala_prognoza_na_dzis | Discovered supporting/legacy entity: Solcast PV Forecast Pozostała prognoza na dziś | solcast_solar | odczyt | kWh | 0 | AVAILABLE | pomocnicza | GOTOWA |
| sensor.solcast_pv_forecast_prognoza_na_biezaca_godzine | Discovered supporting/legacy entity: Solcast PV Forecast Prognoza na bieżącą godzinę | solcast_solar | odczyt | Wh | 0 | AVAILABLE | pomocnicza | GOTOWA |
| sensor.solcast_pv_forecast_prognoza_na_dzisiaj | pv.forecast_today | solcast_solar | odczyt | kWh | 9.1789 | AVAILABLE | krytyczna | GOTOWA |
| sensor.solcast_pv_forecast_prognoza_na_jutro | pv.forecast_tomorrow | solcast_solar | odczyt | kWh | 22.9268 | AVAILABLE | krytyczna | GOTOWA |
| sensor.solcast_pv_forecast_prognoza_na_nastepna_godzine | Discovered supporting/legacy entity: Solcast PV Forecast Prognoza na następną godzinę | solcast_solar | odczyt | Wh | 0 | AVAILABLE | pomocnicza | GOTOWA |
| sensor.solcast_pv_forecast_szczytowa_moc_dzisiaj | Discovered supporting/legacy entity: Solcast PV Forecast Szczytowa moc dzisiaj | solcast_solar | odczyt | W | 2591 | AVAILABLE | pomocnicza | GOTOWA |
| sensor.solcast_pv_forecast_szczytowa_moc_jutro | Discovered supporting/legacy entity: Solcast PV Forecast Szczytowa moc jutro | solcast_solar | odczyt | W | 4346 | AVAILABLE | pomocnicza | GOTOWA |
| sensor.solcast_pv_forecast_ustawiony_twardy_limit | Discovered supporting/legacy entity: Solcast PV Forecast Ustawiony twardy limit | solcast_solar | odczyt | niepodana | False | AVAILABLE | pomocnicza | GOTOWA |
| sensor.sterownik_pompy_hz_sprezarki | heatpump.compressor_hz | esphome | odczyt | Hz | 53.0 | AVAILABLE | krytyczna | GOTOWA |
| sensor.sterownik_pompy_pompa_ciepla_aktualna_moc_termiczna | Discovered supporting/legacy entity: Sterownik Pompy Pompa Ciepła - Aktualna Moc Termiczna | esphome | odczyt | kW | 7.58275985717773 | AVAILABLE | pomocnicza | GOTOWA |
| sensor.sterownik_pompy_pompa_ciepla_pobor_mocy_elektrycznej | Discovered supporting/legacy entity: Sterownik Pompy Pompa Ciepła - Pobór Mocy Elektrycznej | esphome | odczyt | kW | 1.14240002632141 | AVAILABLE | pomocnicza | WYMAGA POPRAWY |
| sensor.sterownik_pompy_pompa_ciepla_realny_cop_live | Discovered supporting/legacy entity: Sterownik Pompy Pompa Ciepła - Realny COP Live | esphome | odczyt | niepodana | 6.63756990432739 | AVAILABLE | pomocnicza | WYMAGA POPRAWY |
| sensor.sterownik_pompy_potwierdzenie_co | Discovered supporting/legacy entity: Sterownik Pompy Potwierdzenie CO | esphome | odczyt | °C | 42.0 | AVAILABLE | pomocnicza | WYMAGA POPRAWY |
| sensor.sterownik_pompy_potwierdzenie_cwu | dhw.setpoint_echo | esphome | odczyt | °C | 42.0 | AVAILABLE | krytyczna | WYMAGA POPRAWY |
| sensor.sterownik_pompy_prad_sprezarki | Discovered supporting/legacy entity: Sterownik Pompy Prad Sprezarki | esphome | odczyt | A | 6.0 | AVAILABLE | pomocnicza | GOTOWA |
| sensor.sterownik_pompy_przeplyw_wody | heatpump.flow | esphome | odczyt | m3/h | 1.62999999523163 | AVAILABLE | krytyczna | GOTOWA |
| sensor.sterownik_pompy_status_diagnostyczny_urzadzenia | Discovered supporting/legacy entity: Sterownik Pompy Status diagnostyczny urządzenia | esphome | odczyt | niepodana | Stan prawidłowy (OK) | AVAILABLE | pomocnicza | WYMAGA POPRAWY |
| sensor.sterownik_pompy_sterownik_pompy_kod_bledu_surowy | heatpump.error | esphome | odczyt | niepodana | 0.0 | AVAILABLE | krytyczna | WYMAGA POPRAWY |
| sensor.sterownik_pompy_sterownik_pompy_licznik_motogodzin | Discovered supporting/legacy entity: Sterownik Pompy Sterownik pompy - Licznik motogodzin | esphome | odczyt | h | 9550.0 | AVAILABLE | pomocnicza | WYMAGA POPRAWY |
| sensor.sterownik_pompy_sterownik_pompy_napiecie_sieciowe | Discovered supporting/legacy entity: Sterownik Pompy Sterownik pompy - Napięcie sieciowe | esphome | odczyt | V | 224.0 | AVAILABLE | pomocnicza | GOTOWA |
| sensor.sterownik_pompy_sterownik_pompy_temperatura_tloczenia_kompresora | Discovered supporting/legacy entity: Sterownik Pompy Sterownik pompy - Temperatura tłoczenia kompresora | esphome | odczyt | °C | 56.0 | AVAILABLE | pomocnicza | GOTOWA |
| sensor.sterownik_pompy_sterownik_pompy_temperatura_wejsciowa_wody | heating.return_water | esphome | odczyt | °C | 37.0 | AVAILABLE | krytyczna | WYMAGA POPRAWY |
| sensor.sterownik_pompy_sterownik_pompy_temperatura_wyjsciowa_wody | heating.supply_water | esphome | odczyt | °C | 41.0 | AVAILABLE | krytyczna | GOTOWA |
| sensor.sterownik_pompy_temp_co | Discovered supporting/legacy entity: Sterownik Pompy Temp CO | esphome | odczyt | °C | 25.0 | AVAILABLE | pomocnicza | WYMAGA POPRAWY |
| sensor.sterownik_pompy_temp_cwu | dhw.temperature | esphome | odczyt | °C | 43.0 | AVAILABLE | krytyczna | WYMAGA POPRAWY |
| sensor.temp_bufor_temperatura | Discovered supporting/legacy entity: Temp.bufor  Temperatura | tuya | odczyt | °C | unavailable | UNAVAILABLE_OR_UNKNOWN | pomocnicza | WYMAGA POPRAWY |
| sensor.temperatura_bufor_zasilanie_last_seen | Discovered supporting/legacy entity: Last seen | mqtt | odczyt | niepodana | BRAK | DISABLED | pomocnicza | WYMAGA POPRAWY |
| sensor.temperatura_co_powrot_last_seen | Discovered supporting/legacy entity: Last seen | mqtt | odczyt | niepodana | BRAK | DISABLED | pomocnicza | WYMAGA POPRAWY |
| sensor.temperatura_co_zasilanie_last_seen | Discovered supporting/legacy entity: Last seen | mqtt | odczyt | niepodana | BRAK | DISABLED | pomocnicza | WYMAGA POPRAWY |
| sensor.temperatura_na_zewnatrz_last_seen | Discovered supporting/legacy entity: Last seen | mqtt | odczyt | niepodana | BRAK | DISABLED | pomocnicza | WYMAGA POPRAWY |
| sensor.temperatura_na_zewnatrz_temperatura | Discovered supporting/legacy entity: Temperatura na zewnątrz  Temperatura | tuya | odczyt | °C | unavailable | UNAVAILABLE_OR_UNKNOWN | pomocnicza | WYMAGA POPRAWY |
| sensor.temperatura_na_zewnatrz_wilgotnosc | Discovered supporting/legacy entity: Temperatura na zewnątrz  Wilgotność | tuya | odczyt | % | unavailable | UNAVAILABLE_OR_UNKNOWN | pomocnicza | WYMAGA POPRAWY |
| sensor.wlacznik_cwu_bateria | Discovered supporting/legacy entity: Włącznik CWu Bateria | tuya | odczyt | % | unavailable | UNAVAILABLE_OR_UNKNOWN | pomocnicza | WYMAGA POPRAWY |
| sensor.zuzycie_domu_live | building.load_conditional | HA template YAML | odczyt | W | 2139 | AVAILABLE | krytyczna | GOTOWA |
| switch.0xa4c138006c97ffff | Discovered supporting/legacy entity: Gniazdko kotlownia | mqtt | sterowanie | niepodana | on | AVAILABLE | pomocnicza | GOTOWA |
| switch.0xa4c138006c97ffff_child_lock | Discovered supporting/legacy entity: Gniazdko kotlownia Child lock | mqtt | sterowanie | niepodana | unknown | UNAVAILABLE_OR_UNKNOWN | pomocnicza | WYMAGA POPRAWY |
| switch.0xa4c1383684dacee8 | Discovered supporting/legacy entity: Temperatura co powrot | mqtt | sterowanie | niepodana | on | AVAILABLE | pomocnicza | GOTOWA |
| switch.0xa4c1383684dacee8_child_lock | Discovered supporting/legacy entity: Temperatura co powrot Child lock | mqtt | sterowanie | niepodana | unknown | UNAVAILABLE_OR_UNKNOWN | pomocnicza | WYMAGA POPRAWY |
| switch.0xa4c1383684dacee8_manual_mode | Discovered supporting/legacy entity: Temperatura co powrot Manual mode | mqtt | sterowanie | niepodana | on | AVAILABLE | pomocnicza | GOTOWA |
| switch.0xa4c1387ab40f7ba4 | Discovered supporting/legacy entity: Podgrzewacz CWU Smart Grid | mqtt | sterowanie | niepodana | off | AVAILABLE | pomocnicza | GOTOWA |
| switch.0xa4c138a5380f3cda | Discovered supporting/legacy entity: Gniazdko cwu | mqtt | sterowanie | niepodana | off | AVAILABLE | pomocnicza | GOTOWA |
| switch.0xa4c138a5380f3cda_child_lock | Discovered supporting/legacy entity: Gniazdko cwu Child lock | mqtt | sterowanie | niepodana | off | AVAILABLE | pomocnicza | GOTOWA |
| switch.0xa4c138c18fd67065 | Discovered supporting/legacy entity: Temperatura bufor zasilanie | mqtt | sterowanie | niepodana | on | AVAILABLE | pomocnicza | GOTOWA |
| switch.0xa4c138c18fd67065_child_lock | Discovered supporting/legacy entity: Temperatura bufor zasilanie Child lock | mqtt | sterowanie | niepodana | unknown | UNAVAILABLE_OR_UNKNOWN | pomocnicza | WYMAGA POPRAWY |
| switch.0xa4c138c18fd67065_manual_mode | Discovered supporting/legacy entity: Temperatura bufor zasilanie Manual mode | mqtt | sterowanie | niepodana | off | AVAILABLE | pomocnicza | GOTOWA |
| switch.0xa4c138e823c53c00 | Discovered supporting/legacy entity: Temperatura co zasilanie | mqtt | sterowanie | niepodana | on | AVAILABLE | pomocnicza | GOTOWA |
| switch.0xa4c138e823c53c00_manual_mode | Discovered supporting/legacy entity: Temperatura co zasilanie Manual mode | mqtt | sterowanie | niepodana | on | AVAILABLE | pomocnicza | GOTOWA |
| switch.cwu_zasilacz_switch_1 | Discovered supporting/legacy entity: Temperatura bufor powrot Switch 1 | tuya | sterowanie | niepodana | off | AVAILABLE | pomocnicza | GOTOWA |
| switch.kotlownia_blokada_dziecieca | Discovered supporting/legacy entity: Kotłownia  Blokada przed dziećmi | tuya | sterowanie | niepodana | unavailable | UNAVAILABLE_OR_UNKNOWN | pomocnicza | WYMAGA POPRAWY |
| switch.kotlownia_socket_1 | Discovered supporting/legacy entity: Kotłownia  Socket 1 | tuya | sterowanie | niepodana | unavailable | UNAVAILABLE_OR_UNKNOWN | pomocnicza | WYMAGA POPRAWY |
| switch.pompa_cwu_blokada_dziecieca | Discovered supporting/legacy entity: Pompa cwu Blokada przed dziećmi | tuya | sterowanie | niepodana | off | AVAILABLE | pomocnicza | GOTOWA |
| switch.pompa_cwu_socket_1 | Discovered supporting/legacy entity: Pompa cwu Socket 1 | tuya | sterowanie | niepodana | off | AVAILABLE | pomocnicza | GOTOWA |
| switch.tem_bufor_child_lock | Discovered supporting/legacy entity: Temperatura co zasilanie Child lock | mqtt | sterowanie | niepodana | off | AVAILABLE | pomocnicza | GOTOWA |
| switch.temp_bufor_switch_1 | Discovered supporting/legacy entity: Temp.bufor  Switch 1 | tuya | sterowanie | niepodana | unavailable | UNAVAILABLE_OR_UNKNOWN | pomocnicza | WYMAGA POPRAWY |
| switch.temperatura_na_zewnatrz_switch_1 | Discovered supporting/legacy entity: Temperatura na zewnątrz  Switch 1 | tuya | sterowanie | niepodana | unavailable | UNAVAILABLE_OR_UNKNOWN | pomocnicza | WYMAGA POPRAWY |
| switch.temperatura_na_zewnatrz_switch_2 | Discovered supporting/legacy entity: Temperatura na zewnątrz  Switch 2 | tuya | sterowanie | niepodana | unavailable | UNAVAILABLE_OR_UNKNOWN | pomocnicza | WYMAGA POPRAWY |
| update.0xa4c138006c97ffff | Discovered supporting/legacy entity: Gniazdko kotlownia | mqtt | sterowanie | niepodana | off | AVAILABLE | pomocnicza | GOTOWA |
| update.0xa4c1385d4d396787 | Discovered supporting/legacy entity: Temperatura na zewnatrz | mqtt | sterowanie | niepodana | off | AVAILABLE | pomocnicza | GOTOWA |
| update.0xa4c138a5380f3cda | Discovered supporting/legacy entity: Gniazdko cwu | mqtt | sterowanie | niepodana | off | AVAILABLE | pomocnicza | GOTOWA |
| update.emhass_update | Discovered supporting/legacy entity: EMHASS Update | hassio | sterowanie | niepodana | off | AVAILABLE | pomocnicza | GOTOWA |
| update.ems_energy_shadow_update | Discovered supporting/legacy entity: EMS Energy SHADOW Update | hassio | sterowanie | niepodana | off | AVAILABLE | pomocnicza | GOTOWA |
| update.ems_epoch_gateway_update | Discovered supporting/legacy entity: EMS Epoch Gateway Update | hacs | sterowanie | niepodana | off | AVAILABLE | pomocnicza | GOTOWA |
| update.power_flow_card_plus_update | Discovered supporting/legacy entity: Power Flow Card Plus Update | hacs | sterowanie | niepodana | off | AVAILABLE | pomocnicza | GOTOWA |
| update.solaredge_forecast_integration_update | Discovered supporting/legacy entity: Solaredge Forecast integration Update | hacs | sterowanie | niepodana | off | AVAILABLE | pomocnicza | GOTOWA |
| update.solaredge_modbus_multi_update | Discovered supporting/legacy entity: SolarEdge Modbus Multi Update | hacs | sterowanie | niepodana | on | AVAILABLE | pomocnicza | GOTOWA |
| update.solaredge_optimizers_data_update | Discovered supporting/legacy entity: SolarEdge Optimizers Data Update | hacs | sterowanie | niepodana | off | AVAILABLE | pomocnicza | GOTOWA |
| update.solcast_pv_forecast_update | Discovered supporting/legacy entity: Solcast PV Forecast Update | hacs | sterowanie | niepodana | off | AVAILABLE | pomocnicza | GOTOWA |
| update.sterownik_pompy_firmware | Discovered supporting/legacy entity: Oprogramowanie sprzętowe | esphome | sterowanie | niepodana | BRAK | DISABLED | pomocnicza | WYMAGA POPRAWY |
| weather.forecast_dom | weather.forecast | met | odczyt | niepodana | partlycloudy | AVAILABLE | krytyczna | GOTOWA |
