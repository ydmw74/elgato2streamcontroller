# elgato2streamcontroller

Elgato-Stream-Deck-Profile (`.streamDeckProfile`) unter **Linux** mit
[StreamController](https://github.com/StreamController/StreamController) nutzen.

Viele Spiele-Profile – z. B. die Icon-Packs von iConCity für *Train Sim World* –
gibt es nur für die offizielle Elgato-Software, die unter Linux nicht läuft.
StreamController und OpenDeck können solche Profile nicht direkt importieren.
Dieses Skript wandelt ein Elgato-Profil in StreamController-Seiten um –
inklusive Icons, Tastenkürzeln, Umschaltern, Ordnern und Seitenwechseln.

*English summary: converts Elgato Stream Deck profiles into StreamController
pages so Windows/macOS game profiles can be used on Linux. Usage is identical;
the script output is in German.*

---

## Was wird übernommen?

| Elgato-Aktion | In StreamController |
|---|---|
| Tastenkombination (*Hotkey*) | OS-Plugin **Hotkey** – die Taste bleibt gedrückt, solange die Stream-Deck-Taste gehalten wird (wichtig z. B. für Fahrschalter/Bremse) |
| Tastenkombi-Umschalter (*Hotkey Switch*) | Taste mit **zwei Zuständen**: jeweils Hotkey + *Change State*, Bild wechselt wie im Original |
| Ordner öffnen / Zurück | DeckPlugin **Change Page** |
| Nächste / vorherige Seite | DeckPlugin **Change Page** (am Ende wird zur ersten Seite gesprungen) |
| alle Icons | werden kopiert und auf die Tasten gelegt |
| andere Aktionen (Plugins wie OBS, Discord …) | nur Bild, ohne Funktion – das Skript gibt einen Hinweis aus |

Ein Profil mit mehreren Seiten und Ordnern ergibt mehrere StreamController-Seiten,
z. B. `TSW6 - Seite 1` … `TSW6 - Seite 5` und `TSW6 - Ordner 1` … `TSW6 - Ordner 6`.

## Voraussetzungen

- Linux mit einem Elgato Stream Deck (getestet: Stream Deck XL, 32 Tasten)
- [StreamController](https://flathub.org/apps/com.core447.StreamController) als **Flatpak**
  mit den Plugins **OS** und **Deck** (Standard-Plugins, ggf. im Store installieren)
- Python 3.10 oder neuer (keine zusätzlichen Pakete nötig)
- Schreibzugriff auf `/dev/uinput`, damit StreamController Tastendrücke senden kann.
  Siehe [OS-Plugin: Hotkeys](https://github.com/StreamController/OSPlugin?tab=readme-ov-file#hotkeys--write-text).
  Prüfen mit `getfacl /dev/uinput` – dein Benutzer sollte dort `rw-` haben.

## Anleitung

### 1. Skript herunterladen

```bash
git clone https://github.com/ydmw74/elgato2streamcontroller.git
cd elgato2streamcontroller
```

### 2. Profil finden

Spiele-Profile liegen meist als ZIP vor. Nimm die Datei, die zu deinem Gerät passt:

- `… [32 Key XL] ….streamDeckProfile` → Stream Deck XL
- `… [15 Key Mk] ….streamDeckProfile` → Stream Deck MK.2 / Original

Das Skript akzeptiert eine `.streamDeckProfile`-Datei, eine `.zip`-Datei oder einen
entpackten `.sdProfile`-Ordner.

### 3. StreamController beenden

StreamController sollte während der Umwandlung **nicht laufen**
(auch nicht im Hintergrund/Tray). OpenDeck darf ebenfalls nicht laufen –
es können nicht zwei Programme gleichzeitig das Stream Deck steuern.

### 4. Probelauf

```bash
python3 elgato2streamcontroller.py "Mein Spiel - [32 Key XL].streamDeckProfile.zip" --name TSW6 --dry-run
```

Es wird nur angezeigt, welche Seiten entstehen würden – nichts wird geschrieben.

### 5. Umwandeln

```bash
python3 elgato2streamcontroller.py "Mein Spiel - [32 Key XL].streamDeckProfile.zip" --name TSW6
```

Die Seiten landen in `~/.var/app/com.core447.StreamController/data/pages/`,
die Icons in `~/.var/app/com.core447.StreamController/data/imported/<Name>/`.

### 6. In StreamController auswählen

StreamController starten, oben die Seite **`<Name> - Seite 1`** auswählen.
Damit sie beim Start automatisch geladen wird: in den Seiten-Einstellungen
des Decks als **Standardseite** festlegen.

## Optionen

| Option | Bedeutung |
|---|---|
| `--name KURZNAME` | Präfix für die Seitennamen (Standard: Profilname) |
| `--layout de` \| `us` | Tastaturlayout, siehe unten (Standard: `de`) |
| `--dry-run` | nur anzeigen, nichts schreiben |
| `--force` | vorhandene Seiten mit gleichem Namen überschreiben (z. B. für einen zweiten Versuch) |

## Vorlage: Seite für deutsche Züge (`--preset de`)

Statt ein Profil umzuwandeln, kann das Skript eine fertige Seite für deutsche Züge
in *Train Sim World* bauen (Stream Deck XL, 32 Tasten). Als Pfad wird der Ordner des
iConCity-Icon-Packs angegeben (oder direkt dessen Unterordner `Icons`):

```bash
python3 elgato2streamcontroller.py ~/Dokumente/"Train Sim World 6 - iConCity" --preset de --name TSW6
```

Ergebnis: die Seite **`TSW6 - DE Bahnen`** mit

| Zeile | Tasten |
|---|---|
| 1 | SIFA, PZB Wachsam / Frei / Befehl, LZB an/aus, SIFA an/aus, Notbremse, zurück zu `TSW6 - Seite 1` |
| 2 | Fahrschalter +/−, Zugbremse +/−, Zusatzbremse +/−, Richtungswender +/− |
| 3 | Hauptschalter +/−, Stromabnehmer +/−, Leistungsschalter, AFB +/−, Sanden |
| 4 | Tür links/rechts, Horn 1/2, Spitzenlicht +/−, Scheibenwischer, Führerstandslicht |

Die Tastenkürzel entsprechen denen der iConCity-Profile. Zugbremse + und Stromabnehmer
sind dort nicht belegt; hier gilt die Standardbelegung von Train Sim World (`'` bzw. `P`).
`--layout`, `--dry-run` und `--force` funktionieren wie beim Umwandeln.

## Tastaturlayout (wichtig!)

Elgato-Profile speichern Windows-Tastencodes (z. B. „Taste Z“). Unter Linux sendet
StreamController dagegen *physische* Tasten. Das Skript rechnet deshalb so um, als
liefe das Original auf einem Windows mit deinem Tastaturlayout:

- `--layout de` (Standard, deutsche QWERTZ-Tastatur): Y/Z sind vertauscht,
  Sonderzeichen-Tasten (Ü, Ö, Ä, ß, #, +, ^ …) liegen wie bei deutschem Windows.
- `--layout us`: amerikanisches Layout, keine Umrechnung.

Wenn im Spiel falsche Funktionen ausgelöst werden (z. B. Y statt Z), wandle das
Profil mit dem anderen Layout erneut um:

```bash
python3 elgato2streamcontroller.py "Profil.streamDeckProfile.zip" --name TSW6 --layout us --force
```

## Fehlerbehebung

- **Tasten tun im Spiel nichts:** StreamController braucht Zugriff auf `/dev/uinput`
  (siehe Voraussetzungen). Im Aktions-Editor einer Taste steht sonst
  „Missing permission“.
- **StreamController startet nicht mehr / stürzt ab:** Ein früherer, fehlgeschlagener
  Import in StreamController kann kaputte Dateien wie `Device.json`, `Name.json`,
  `Pages.json`, `Version.json` in `~/.var/app/com.core447.StreamController/data/pages/`
  hinterlassen. Diese Dateien sind keine gültigen Seiten – verschiebe sie in einen
  anderen Ordner.
- **Spiel reagiert nur kurz auf gehaltene Tasten:** Proton/Wine und das Spiel müssen
  im Fokus sein; manche Spiele brauchen etwas Verzögerung. Den Wert *Delay* kannst du
  pro Taste im Aktions-Editor von StreamController anpassen.

## Rechtliches

Dieses Repository enthält **keine** Profile oder Icons. Profile und Icon-Packs
(z. B. von iConCity) unterliegen den Lizenzen ihrer Hersteller und dürfen nur
mit einer eigenen, gültigen Lizenz verwendet werden.

Nicht mit Elgato, Corsair, iConCity oder dem StreamController-Projekt verbunden.
„Stream Deck“ ist eine Marke von Corsair/Elgato.

Lizenz des Skripts: [MIT](LICENSE)
