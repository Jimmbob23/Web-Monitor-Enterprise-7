from pathlib import Path

index_path = Path("app/templates/index.html")
site_path = Path("app/templates/site.html")

index = index_path.read_text(encoding="utf-8")
site = site_path.read_text(encoding="utf-8")

old_create = '<option value="auto">Auto</option><option value="click">Klicken</option><option value="hide">Ausblenden</option><option value="off">Aus</option>'
new_create = '<option value="necessary" selected>Nur notwendige ablehnen</option><option value="accept">Alle akzeptieren</option><option value="hide">Banner nur ausblenden</option><option value="strict">Strenger Screenshot-Modus</option><option value="off">Keine Behandlung</option>'

if old_create in index:
    index = index.replace(old_create, new_create, 1)

start = site.find('<select class="form-select" name="cookie_mode">')
if start != -1:
    end = site.find("</select>", start)
    if end != -1:
        old = site[start:end + len("</select>")]
        new = '''<select class="form-select" name="cookie_mode">
<option value="necessary" {% if site.cookie_mode in ["necessary","auto"] %}selected{% endif %}>Nur notwendige ablehnen</option>
<option value="accept" {% if site.cookie_mode in ["accept","click"] %}selected{% endif %}>Alle akzeptieren</option>
<option value="hide" {% if site.cookie_mode=="hide" %}selected{% endif %}>Banner nur ausblenden</option>
<option value="strict" {% if site.cookie_mode=="strict" %}selected{% endif %}>Strenger Screenshot-Modus</option>
<option value="off" {% if site.cookie_mode=="off" %}selected{% endif %}>Keine Behandlung</option>
</select>'''
        site = site.replace(old, new, 1)

index = index.replace("CSS ignorieren", "CSS ignorieren / Cookie-Overlays")
site = site.replace("CSS ignorieren", "CSS ignorieren / Cookie-Overlays")

index_path.write_text(index, encoding="utf-8")
site_path.write_text(site, encoding="utf-8")

print("Cookie-Modi aktualisiert.")
