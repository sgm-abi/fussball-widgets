# fussball-widgets

Automatisierte HTML-Widgets für die Website der SGM ABI ([sgm-abi.de](https://sgm-abi.de)) – Spielpläne, Ligatabellen und Termine, die täglich von [fussball.de](https://www.fussball.de) gescrapt und per SFTP auf den IONOS-Webspace hochgeladen werden. Die Widgets werden dort per iFrame/Embed in die WordPress-Seiten eingebunden.

## Wie es funktioniert

1. `scripts/wochenplan.py` und `scripts/widget_pro_team.py` laden die Spielpläne und Ligatabellen aller ABI-Mannschaften von fussball.de.
2. Daraus werden statische HTML-Fragmente (Tabellen mit Inline-Styles, WordPress-kompatibel) erzeugt und in [htmls/](htmls/) abgelegt – versioniert im Repo als Backup/Verlauf.
3. Die generierten Dateien werden per SFTP auf den Webserver hochgeladen, wo sie direkt eingebunden werden.
4. Ein täglicher GitHub-Actions-Workflow erledigt das automatisch (siehe unten).

## Struktur

```
scripts/
  wochenplan.py            Haupt-Skript: Startseiten-Widget (aktuelle/nächste/letzte Woche,
                            Gesamtübersicht aller Teams, KW-Archiv, Ergebnisse)
  widget_pro_team.py        Pro-Team-Widgets (nächste Spiele + Ligatabelle je Mannschaft)
  highlights.py              Schneidet Spiel-Videos zu Instagram-Highlight-Reels zusammen
                             (ffmpeg-Crossfades, Formate reels/feed/square)
  Spiele_Links.csv          Team-Liste: Name, fussball.de-URL, Staffel, aktiv/inaktiv
  abi_termine.csv            Manuell gepflegte Zusatztermine (Turniere, Saisoneröffnung, …)
  All_games_from_fussball_de.csv   Generierter Rohdaten-Export aller Spiele (nicht versioniert)

htmls/                      Generierte HTML-Widgets (Output, versioniert als Backup)
notebooks/                  Jupyter-Notebooks für Datenaufbereitung, Ad-hoc-Auswertungen
.github/workflows/          GitHub-Actions-Workflow für die tägliche Automatisierung
```

## Automatisierung

Der Workflow [.github/workflows/update_widgets.yml](.github/workflows/update_widgets.yml) läuft täglich um 16:00 UTC (17/18 Uhr deutscher Zeit) sowie manuell per „Run workflow“:

1. Python-Abhängigkeiten installieren
2. `widget_pro_team.py` und `wochenplan.py` ausführen (scrapen, generieren, per SFTP hochladen)
3. Die generierten HTML-Dateien in `htmls/` zurück ins Repo committen

Die SFTP-Zugangsdaten liegen als GitHub Secrets (`SFTP_HOST`, `SFTP_PORT`, `SFTP_USER`, `SFTP_PASS`, `SFTP_REMOTE_DIR`).

## Lokale Ausführung

```bash
pip install requests beautifulsoup4 paramiko pandas

# SFTP-Zugangsdaten optional setzen – ohne SFTP_PASS wird der Upload übersprungen
export SFTP_PASS="..."

python scripts/widget_pro_team.py
python scripts/wochenplan.py
```

Ohne gesetztes `SFTP_PASS` werden die HTML-Dateien nur lokal in `htmls/` erzeugt, der Upload wird übersprungen.

### Teams pflegen

Mannschaften werden über [scripts/Spiele_Links.csv](scripts/Spiele_Links.csv) gesteuert (Spalte `aktiv` = 0/1). Zusatztermine wie Turniere oder die Saisoneröffnung trägt man in [scripts/abi_termine.csv](scripts/abi_termine.csv) ein.

### Highlight-Videos

`scripts/highlights.py` schneidet Ausschnitte aus einem Spielvideo (z. B. von der XbotGo-Kamera) zu einem Instagram-tauglichen Highlight-Reel zusammen. Voraussetzung sind `ffmpeg`/`ffprobe` sowie `yt-dlp`, wenn das Quellvideo per URL statt lokal angegeben wird. Gesteuert wird der Schnitt über eine Config-Datei (Standard: `scripts/highlights_config.yaml`, nicht im Repo versioniert):

```bash
python scripts/highlights.py [pfad/zur/config.yaml]
```

## Notebooks

In [notebooks/](notebooks/) liegen Jupyter-Notebooks für Ad-hoc-Aufgaben, u. a. Extraktion von Tabellen aus fussball.de, Prüfung auf tote Links, Bildbearbeitung und Google-Calendar-Abgleich.
