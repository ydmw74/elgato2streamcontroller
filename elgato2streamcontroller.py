#!/usr/bin/env python3
"""
Konvertiert ein Elgato-Stream-Deck-Profil (.streamDeckProfile / .zip / .sdProfile-Ordner)
in Seiten für StreamController (Flatpak com.core447.StreamController).

Unterstützte Elgato-Aktionen:
  com.elgato.streamdeck.system.hotkey         -> OSPlugin::Hotkey (Taste wird gehalten, solange gedrückt)
  com.elgato.streamdeck.system.hotkeyswitch   -> zwei Zustände: Hotkey + ChangeState
  com.elgato.streamdeck.profile.openchild     -> DeckPlugin::ChangePage (Ordner öffnen)
  com.elgato.streamdeck.profile.backtoparent  -> DeckPlugin::ChangePage (zurück)
  com.elgato.streamdeck.page.next / previous  -> DeckPlugin::ChangePage
Andere Aktionen werden nur mit Bild übernommen (ohne Funktion) und gemeldet.

Aufruf:
  python3 elgato2streamcontroller.py PROFIL [--name KURZNAME] [--layout de|us] [--dry-run]
"""
import argparse
import base64
import json
import shutil
import sys
import tempfile
import uuid
import zipfile
from pathlib import Path

SC_DATA = Path.home() / ".var/app/com.core447.StreamController/data"

# evdev key codes (linux/input-event-codes.h)
KEY = {
    "ESC": 1, "1": 2, "2": 3, "3": 4, "4": 5, "5": 6, "6": 7, "7": 8, "8": 9, "9": 10, "0": 11,
    "MINUS": 12, "EQUAL": 13, "BACKSPACE": 14, "TAB": 15,
    "Q": 16, "W": 17, "E": 18, "R": 19, "T": 20, "Y": 21, "U": 22, "I": 23, "O": 24, "P": 25,
    "LEFTBRACE": 26, "RIGHTBRACE": 27, "ENTER": 28, "LEFTCTRL": 29,
    "A": 30, "S": 31, "D": 32, "F": 33, "G": 34, "H": 35, "J": 36, "K": 37, "L": 38,
    "SEMICOLON": 39, "APOSTROPHE": 40, "GRAVE": 41, "LEFTSHIFT": 42, "BACKSLASH": 43,
    "Z": 44, "X": 45, "C": 46, "V": 47, "B": 48, "N": 49, "M": 50,
    "COMMA": 51, "DOT": 52, "SLASH": 53, "RIGHTSHIFT": 54, "KPASTERISK": 55, "LEFTALT": 56,
    "SPACE": 57, "CAPSLOCK": 58,
    "F1": 59, "F2": 60, "F3": 61, "F4": 62, "F5": 63, "F6": 64, "F7": 65, "F8": 66, "F9": 67, "F10": 68,
    "NUMLOCK": 69, "SCROLLLOCK": 70,
    "KP7": 71, "KP8": 72, "KP9": 73, "KPMINUS": 74, "KP4": 75, "KP5": 76, "KP6": 77, "KPPLUS": 78,
    "KP1": 79, "KP2": 80, "KP3": 81, "KP0": 82, "KPDOT": 83, "102ND": 86, "F11": 87, "F12": 88,
    "KPENTER": 96, "RIGHTCTRL": 97, "KPSLASH": 98, "SYSRQ": 99, "RIGHTALT": 100,
    "HOME": 102, "UP": 103, "PAGEUP": 104, "LEFT": 105, "RIGHT": 106, "END": 107, "DOWN": 108,
    "PAGEDOWN": 109, "INSERT": 110, "DELETE": 111, "PAUSE": 119, "LEFTMETA": 125,
    "F13": 183, "F14": 184, "F15": 185, "F16": 186, "F17": 187, "F18": 188, "F19": 189, "F20": 190,
    "F21": 191, "F22": 192, "F23": 193, "F24": 194,
}

# Windows Virtual-Key-Codes -> evdev (layoutunabhängiger Teil)
VK_COMMON = {
    0x08: "BACKSPACE", 0x09: "TAB", 0x0D: "ENTER", 0x13: "PAUSE", 0x14: "CAPSLOCK", 0x1B: "ESC",
    0x20: "SPACE", 0x21: "PAGEUP", 0x22: "PAGEDOWN", 0x23: "END", 0x24: "HOME",
    0x25: "LEFT", 0x26: "UP", 0x27: "RIGHT", 0x28: "DOWN", 0x2C: "SYSRQ", 0x2D: "INSERT", 0x2E: "DELETE",
    0x60: "KP0", 0x61: "KP1", 0x62: "KP2", 0x63: "KP3", 0x64: "KP4", 0x65: "KP5", 0x66: "KP6",
    0x67: "KP7", 0x68: "KP8", 0x69: "KP9", 0x6A: "KPASTERISK", 0x6B: "KPPLUS", 0x6D: "KPMINUS",
    0x6E: "KPDOT", 0x6F: "KPSLASH", 0x90: "NUMLOCK", 0x91: "SCROLLLOCK",
    0x10: "LEFTSHIFT", 0x11: "LEFTCTRL", 0x12: "LEFTALT", 0xA0: "LEFTSHIFT", 0xA1: "RIGHTSHIFT",
    0xA2: "LEFTCTRL", 0xA3: "RIGHTCTRL", 0xA4: "LEFTALT", 0xA5: "RIGHTALT", 0x5B: "LEFTMETA",
}
VK_COMMON.update({0x30 + i: str(i) for i in range(10)})
VK_COMMON.update({0x41 + i: chr(0x41 + i) for i in range(26)})
VK_COMMON.update({0x70 + i: f"F{i + 1}" for i in range(24)})

# OEM-Tasten: welche physische Taste erzeugt unter Windows diesen VK-Code?
VK_LAYOUT = {
    "us": {0xBA: "SEMICOLON", 0xBB: "EQUAL", 0xBC: "COMMA", 0xBD: "MINUS", 0xBE: "DOT", 0xBF: "SLASH",
           0xC0: "GRAVE", 0xDB: "LEFTBRACE", 0xDC: "BACKSLASH", 0xDD: "RIGHTBRACE", 0xDE: "APOSTROPHE",
           0xE2: "102ND"},
    # Deutsches Windows-Layout (QWERTZ): Y/Z vertauscht, OEM-Codes liegen auf anderen Tasten
    "de": {0x59: "Z", 0x5A: "Y",
           0xBA: "LEFTBRACE",   # Ü
           0xBB: "RIGHTBRACE",  # +
           0xBC: "COMMA", 0xBD: "SLASH", 0xBE: "DOT",
           0xBF: "BACKSLASH",   # #
           0xC0: "SEMICOLON",   # Ö
           0xDB: "MINUS",       # ß
           0xDC: "GRAVE",       # ^
           0xDD: "EQUAL",       # ´
           0xDE: "APOSTROPHE",  # Ä
           0xE2: "102ND"},      # <
}

MODIFIERS = [(2, "LEFTCTRL"), (1, "LEFTSHIFT"), (4, "LEFTALT"), (8, "LEFTMETA")]


def profile_dir_name(page_uuid: str) -> str:
    """Elgato benennt Unterprofil-Ordner nach der UUID in Base32 (Alphabet 0-9, A-T, V, W) plus 'Z'."""
    enc = base64.b32hexencode(uuid.UUID(page_uuid).bytes).decode().rstrip("=")
    return enc.translate(str.maketrans("UV", "VW")) + "Z"


class Converter:
    def __init__(self, src: Path, name: str | None, layout: str, warn):
        self.src = src
        self.layout = layout
        self.warn = warn
        self.manifest = json.loads((src / "manifest.json").read_text())
        self.name = name or self.manifest.get("Name") or "Elgato"
        self.subdirs = {p.name: p for p in (src / "Profiles").iterdir() if p.is_dir()}
        self.page_files: dict[str, str] = {}   # Elgato-Ordnername -> SC-Seitendatei (Name ohne .json)
        self.parents: dict[str, str] = {}      # Ordner-Unterprofil -> Elternseite
        self.pages_out: dict[str, dict] = {}
        self.assets_out: dict[Path, Path] = {}
        self.vk_map = {**VK_COMMON, **VK_LAYOUT[layout]}

    # ---------- Seitenstruktur ----------
    def plan(self):
        top = [profile_dir_name(u) for u in self.manifest["Pages"]["Pages"]]
        for i, d in enumerate(top, 1):
            if d not in self.subdirs:
                self.warn(f"Seite {d} fehlt im Profil")
                continue
            self.page_files[d] = f"{self.name} - Seite {i}"
        self.top = [d for d in top if d in self.page_files]

        # Ordner rekursiv einsammeln
        queue = list(self.top)
        folder_no = 0
        while queue:
            d = queue.pop(0)
            for _, act in self.actions(d):
                if act["UUID"] == "com.elgato.streamdeck.profile.openchild":
                    child = profile_dir_name(act["Settings"]["ProfileUUID"])
                    if child in self.subdirs and child not in self.page_files:
                        folder_no += 1
                        self.page_files[child] = f"{self.name} - Ordner {folder_no}"
                        self.parents[child] = d
                        queue.append(child)

    def actions(self, d):
        m = json.loads((self.subdirs[d] / "manifest.json").read_text())
        for ctl in m.get("Controllers", []):
            if ctl.get("Type", "Keypad") != "Keypad":
                self.warn(f"Controller-Typ {ctl.get('Type')} (Drehregler o.ä.) wird ignoriert")
                continue
            for pos, act in (ctl.get("Actions") or {}).items():
                yield pos, act

    def page_path(self, d) -> str:
        return str(SC_DATA / "pages" / f"{self.page_files[d]}.json")

    # ---------- Aktionen ----------
    def hotkey_events(self, hk):
        if hk is None or hk.get("VKeyCode", -1) == -1:
            return None
        vk = hk["VKeyCode"]
        key = self.vk_map.get(vk)
        if key is None:
            self.warn(f"Unbekannter Tastencode VK={vk} – übersprungen")
            return None
        mods = [KEY[m] for bit, m in MODIFIERS if hk.get("KeyModifiers", 0) & bit]
        code = KEY[key]
        return [[m, 1] for m in mods] + [[code, 1], [code, 0]] + [[m, 0] for m in reversed(mods)]

    def hotkey_action(self, events, hold=True):
        return {"id": "com_core447_OSPlugin::Hotkey",
                "settings": {"keys": events, "delay": 0.03, "repeat": False, "hold_until_release": hold}}

    @staticmethod
    def change_page_action(path):
        return {"id": "com_core447_DeckPlugin::ChangePage",
                "settings": {"selected_page": path, "deck_number": None, "return_timeout": 0}}

    @staticmethod
    def change_state_action(state):
        return {"id": "com_core447_DeckPlugin::ChangeState",
                "settings": {"target_input": None, "state": state, "return_timeout": 0}}

    def state_visual(self, d, st):
        out = {}
        img = st.get("Image")
        if img:
            src_img = self.subdirs[d] / img
            if src_img.is_file():
                dst = SC_DATA / "imported" / self.name / d / Path(img).name
                self.assets_out[src_img] = dst
                out["media"] = {"path": str(dst), "size": 1, "valign": 0, "halign": 0}
        if st.get("ShowTitle", True) and st.get("Title"):
            pos = {"top": "top", "middle": "center", "bottom": "bottom"}.get(st.get("TitleAlignment"), "bottom")
            out["labels"] = {pos: {"text": st["Title"], "color": hex_to_rgba(st.get("TitleColor", "#ffffff")),
                                   "font-size": max(int(st.get("FontSize", 12)), 10)}}
        return out

    def convert_page(self, d):
        keys = {}
        top_idx = self.top.index(d) if d in self.top else None
        for pos, act in self.actions(d):
            col, row = pos.split(",")
            ident = f"{col}x{row}"
            uid = act["UUID"]
            states = act.get("States") or [{}]
            title = states[0].get("Title") or ""
            s0 = self.state_visual(d, states[0])
            key = {"states": {"0": s0}}
            acts = []

            if uid == "com.elgato.streamdeck.system.hotkey":
                ev = self.hotkey_events((act["Settings"].get("Hotkeys") or [None])[0])
                if ev:
                    acts = [self.hotkey_action(ev, hold=True)]
            elif uid == "com.elgato.streamdeck.system.hotkeyswitch":
                hks = act["Settings"].get("Hotkeys") or []
                ev0 = self.hotkey_events(hks[0] if len(hks) > 0 else None)
                ev1 = self.hotkey_events(hks[1] if len(hks) > 1 else None)
                if len(states) > 1:
                    s1 = self.state_visual(d, states[1])
                    a0 = ([self.hotkey_action(ev0, hold=False)] if ev0 else []) + [self.change_state_action(1)]
                    a1 = ([self.hotkey_action(ev1, hold=False)] if ev1 else []) + [self.change_state_action(0)]
                    s0["actions"] = a0
                    s1["actions"] = a1
                    key["states"]["1"] = s1
                    keys[ident] = key
                    continue
                if ev0:
                    acts = [self.hotkey_action(ev0, hold=False)]
            elif uid == "com.elgato.streamdeck.profile.openchild":
                child = profile_dir_name(act["Settings"]["ProfileUUID"])
                if child in self.page_files:
                    acts = [self.change_page_action(self.page_path(child))]
            elif uid == "com.elgato.streamdeck.profile.backtoparent":
                if d in self.parents:
                    acts = [self.change_page_action(self.page_path(self.parents[d]))]
            elif uid in ("com.elgato.streamdeck.page.next", "com.elgato.streamdeck.page.previous"):
                if top_idx is not None and len(self.top) > 1:
                    step = 1 if uid.endswith("next") else -1
                    acts = [self.change_page_action(self.page_path(self.top[(top_idx + step) % len(self.top)]))]
            else:
                self.warn(f"{self.page_files[d]} Taste {pos}: Aktion '{uid}' ({title}) wird nicht unterstützt – nur Bild übernommen")

            s0["actions"] = acts
            keys[ident] = key
        return {"keys": keys}

    def run(self):
        self.plan()
        for d in self.page_files:
            self.pages_out[self.page_files[d]] = self.convert_page(d)
        return self.pages_out


def hex_to_rgba(h):
    h = h.lstrip("#")
    try:
        return [int(h[i:i + 2], 16) for i in (0, 2, 4)] + [255]
    except ValueError:
        return [255, 255, 255, 255]


def find_sdprofile(path: Path, tmp: Path) -> Path:
    if path.is_dir() and (path / "manifest.json").is_file():
        return path
    if path.is_file() and zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as z:
            z.extractall(tmp)
        path = tmp
    if path.is_dir():
        found = [p.parent for p in path.rglob("manifest.json") if p.parent.suffix == ".sdProfile"]
        if found:
            return found[0]
    sys.exit(f"Kein Elgato-Profil gefunden in: {path}")


def main():
    ap = argparse.ArgumentParser(description="Elgato-Stream-Deck-Profil nach StreamController konvertieren")
    ap.add_argument("profile", type=Path, help=".streamDeckProfile, .zip oder .sdProfile-Ordner")
    ap.add_argument("--name", help="Kurzname für die Seiten (Standard: Profilname)")
    ap.add_argument("--layout", choices=list(VK_LAYOUT), default="de",
                    help="Tastaturlayout des Systems (Standard: de)")
    ap.add_argument("--dry-run", action="store_true", help="nur anzeigen, nichts schreiben")
    ap.add_argument("--force", action="store_true", help="vorhandene Seiten gleichen Namens überschreiben")
    args = ap.parse_args()

    warnings = []
    with tempfile.TemporaryDirectory() as tmp:
        src = find_sdprofile(args.profile.expanduser(), Path(tmp))
        conv = Converter(src, args.name, args.layout, warnings.append)
        pages = conv.run()

        pages_dir = SC_DATA / "pages"
        existing = [n for n in pages if (pages_dir / f"{n}.json").exists()]
        if existing and not args.force and not args.dry_run:
            sys.exit("Seiten existieren bereits (mit --force überschreiben):\n  " + "\n  ".join(existing))

        for n, p in pages.items():
            n_keys = len(p["keys"])
            n_act = sum(1 for k in p["keys"].values() for s in k["states"].values() if s.get("actions"))
            print(f"  {n}.json  ({n_keys} Tasten, {n_act} mit Funktion)")

        if not args.dry_run:
            pages_dir.mkdir(parents=True, exist_ok=True)
            for src_img, dst in conv.assets_out.items():
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src_img, dst)
            for n, p in pages.items():
                (pages_dir / f"{n}.json").write_text(json.dumps(p, indent=2, ensure_ascii=False))
            print(f"\n{len(pages)} Seiten und {len(conv.assets_out)} Bilder nach {SC_DATA} geschrieben.")

    for w in dict.fromkeys(warnings):
        print("Hinweis:", w)


if __name__ == "__main__":
    main()
