# Web Monitor Enterprise 7 Beta

Dieses Repository ist der konsolidierte aktuelle Stand.

Es basiert auf dem zuletzt funktionierenden Enterprise-6.1-Macro-System.
Alle bisherigen Funktionen bleiben erhalten. Der visuelle Makro-Rekorder
wurde zusätzlich integriert.

## Enthaltene Funktionen

### Bestehende Funktionen

- Monitor anlegen
- Monitor bearbeiten
- Monitor manuell prüfen
- Monitor pausieren und aktivieren
- Monitor löschen
- Intervall nachträglich ändern
- Cron-Ausdrücke
- visueller Cron-Generator
- wöchentlich und bestimmte Wochentage
- mehrere Uhrzeiten
- Ordner und Tags
- Suche und Statusfilter
- Benutzerverwaltung
- Rollen Admin/Benutzer
- PostgreSQL
- Cookie-Banner-Erkennung
- CSS-Selektoren ignorieren
- Screenshots und Differenzbilder
- offene Änderungen bleiben sichtbar, bis die Detailseite geöffnet wird
- einzelne Historieneinträge löschen
- komplette Historie und Bilddateien löschen
- Baseline zurücksetzen
- einklappbare Monitor-Konfiguration
- responsive Oberfläche
- automatischer Dark-/Lightmode
- Monitorliste fest dunkel mit weißer Schrift
- REST/OpenAPI unter `/docs`

### Backup & Restore

- CSV-Backup
- CSV-Restore
- JSON-Backup
- JSON-Restore
- Makro-Schritte werden mitgesichert
- CSV ist für Excel/LibreOffice geeignet
- UTF-8 mit BOM und Semikolon als Trennzeichen

### Interaktions-Makros

- visueller Makro-Rekorder über noVNC
- Auswahlfelder
- Texteingaben
- Checkboxen und Radio-Buttons
- Klicks
- Enter, Tab und Escape
- Scrollbewegungen
- persistente Zwischenspeicherung der aufgenommenen Schritte
- manueller Makro-Editor
- Reihenfolge ändern
- Schritte löschen
- Makros werden vor jedem Screenshot ausgeführt

## GitHub Repository

Empfohlener Name:

```text
web-monitor-enterprise-7-beta
```

Nach jedem Push auf `main` wird automatisch folgendes Image gebaut:

```text
ghcr.io/jimmbob23/web-monitor-enterprise-7-beta:beta
```

Zusätzlich entstehen:

```text
ghcr.io/jimmbob23/web-monitor-enterprise-7-beta:latest
ghcr.io/jimmbob23/web-monitor-enterprise-7-beta:sha-...
```

## Portainer

Die fertige Stack-Datei lautet:

```text
stack.portainer.yml
```

Weboberfläche:

```text
http://SERVER-IP:8007
```

noVNC-Makro-Browser:

```text
http://SERVER-IP:6080/vnc.html?autoconnect=true&resize=scale&reconnect=true
```

## Standardzugang

```text
Benutzer: admin
Passwort:  admin123
```

Bitte in Portainer unbedingt ändern:

```yaml
POSTGRES_PASSWORD: bitte-aendern
APP_SECRET: bitte-unbedingt-aendern
ADMIN_PASSWORD: admin123
```

## Wichtig

Für Enterprise 7 Beta eigene Volumes verwenden:

```text
wm7_beta_postgres
wm7_beta_data
```

Die Volumes einer vorhandenen Enterprise-6-Installation nicht überschreiben.
