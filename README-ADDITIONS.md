# Web Monitor Enterprise 7 Beta 2 – additive Erweiterungen

Dieser Stand basiert auf dem zuletzt funktionierenden Enterprise-7-Beta-System.
Keine bestehende Funktion wurde entfernt.

## Neue Ergänzungen

1. Ungelesene Änderungen stehen automatisch ganz oben.
2. Solange eine Änderung ungelesen ist, erfolgt kein weiterer Scan dieses Monitors.
3. Optional kann ein einzelner Seitenbereich per CSS-Selektor geprüft werden.
4. Die obere Navigationszeile bleibt beim Scrollen sichtbar.
5. Browser- und Statuscache beschleunigen wiederholte Seitenaufrufe.

## Prüfbereich

Im Monitor befindet sich das neue Feld:

```text
Nur diesen Bereich prüfen (CSS-Selektor)
```

Beispiele:

```css
#preise
main .ergebnisliste
[data-testid="content"]
```

Bleibt das Feld leer, wird wie bisher die komplette Seite geprüft.

## Cache

- Screenshots und Differenzbilder: langfristiger Browsercache
- CSS und JavaScript: fünf Minuten mit Revalidierung
- Ungelesen-Status: kurzer serverseitiger Speicher
- HTML: wird weiterhin revalidiert, damit Änderungen sofort sichtbar bleiben

## Datenbank

Die neue Spalte `monitor_selector` wird beim Start automatisch additiv angelegt.
Bestehende Daten und Funktionen bleiben erhalten.

## Image

```text
ghcr.io/jimmbob23/web-monitor-enterprise-7-beta:beta
```

## Installation

Den bisherigen Repository-Inhalt vollständig durch diesen Stand ersetzen,
GitHub Actions abwarten und den Stack in Portainer mit **Pull latest image**
neu deployen.
