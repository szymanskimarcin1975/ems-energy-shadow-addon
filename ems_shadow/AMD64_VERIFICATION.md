# Walidacja wersji publikacyjnej

Cel linux/amd64; minimumCore2026.9.4. Testy lokalne sprawdzają konfigurację,
SQLite, duplikaty, SIGTERM, crashrestart, HTTP i dokładną liczbę procesów.
Pełna budowa i smoke test są wykonywane przez CI. Nie deklarować sukcesu
CI bez logów. Smoke używa tylko example_options.json i sztucznego API.
Brak zależności od prawdziwego HA. Docker build sam wykonuje testy dodatku.
Raport MCP i Supervisor wymagają lokalnej weryfikacji po instalacji testowej.
