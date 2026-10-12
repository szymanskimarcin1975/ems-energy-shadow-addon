# EMS Energy SHADOW 0.1.0

Experimental Home Assistant add-on for amd64. Observes energy without controlling devices.

Add this repository URL to the Home Assistant app store:

https://github.com/szymanskimarcin1975/ems-energy-shadow-addon

Install EMS Energy SHADOW, then configure all seven source entities locally before starting. No installation-specific defaults are included.

See [configuration and backup instructions](ems_shadow/DOCS.md).

Source snapshot: `d693dfeb490770f048c17d0d8f9c56c60c6bc8d0`. Add-on files are copied unchanged; no source repository history was transferred.

SQLite remains private in `/data`. Reports are exported to `ems_shadow/report.yaml` in the Home Assistant configuration directory for authorized MCP reads. The add-on therefore requests write access to that directory. It exposes no public ports and uses no embedded credentials.

Build and isolated synthetic container tests passed before this publication. Actual Supervisor installation and real measurement quality still require a test installation. No production billing claims.
