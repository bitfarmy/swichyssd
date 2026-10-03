#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Swichy SSD - sposta le app Flatpak tra disco interno e SSD esterno.
Richiede: GTK4 (python3-gobject).
"""
import sys
import traceback

try:
    import gi
    gi.require_version("Gtk", "4.0")
    from gi.repository import Gtk, GLib
except Exception as e:
    print("ERRORE: manca python3-gobject oppure GTK4 non e' disponibile.")
    print("Installa: sudo dnf install python3-gobject gtk4")
    print(e)
    traceback.print_exc()
    input("Premi Invio per chiudere...")
    sys.exit(1)

import os
import shutil
import subprocess

CONFIG_DIR = os.path.expanduser("~/.config/swichyssd")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")

DEFAULT_CONFIG = {
    "installation_name": "predator",
    "mount_point": "/mnt/predator-fedora",
    "programs_path": "/mnt/predator-fedora/programs",
    "conf_file": "/etc/flatpak/installations.d/predator.conf",
    "img_path": "/mnt/predator-ssd/asus-linux/fedora-apps.img"
}


def load_config():
    if os.path.isfile(CONFIG_FILE):
        try:
            with open(CONFIG_FILE) as f:
                return {**DEFAULT_CONFIG, **json.load(f)}
        except Exception:
            pass
    return DEFAULT_CONFIG.copy()


def save_config(cfg):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2)


def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)


def find_terminal():
    for term in ("gnome-terminal", "kgx", "x-terminal-emulator"):
        if shutil.which(term):
            return term
    return None


class SettingsDialog(Gtk.Window):
    def __init__(self, parent):
        super().__init__(title="Impostazioni Swichy SSD")
        self.set_transient_for(parent)
        self.set_modal(True)
        self.set_default_size(480, 360)
        self.parent = parent
        cfg = parent.config

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_top(18)
        box.set_margin_bottom(18)
        box.set_margin_start(18)
        box.set_margin_end(18)
        self.set_child(box)

        # Titolo
        title = Gtk.Label()
        title.set_markup("<b>Impostazioni</b>")
        title.set_xalign(0)
        box.append(title)

        # Campi
        self.entry_installation = self._add_field(box, "Nome installation Flatpak:", cfg["installation_name"])
        self.entry_mount = self._add_field(box, "Mount point SSD:", cfg["mount_point"])
        self.entry_programs = self._add_field(box, "Percorso programs:", cfg["programs_path"])
        self.entry_conf = self._add_field(box, "File configurazione:", cfg["conf_file"])
        self.entry_img = self._add_field(box, "File immagine (sul disco esterno):", cfg.get("img_path", ""))

        # Info
        info = Gtk.Label()
        info.set_markup("<small>I percorsi devono corrispondere a una custom installation Flatpak valida.\n"
                        "Dopo aver salvato, l'app aggiorna automaticamente i parametri.</small>")
        info.set_wrap(True)
        info.set_xalign(0)
        box.append(info)

        # Bottoni
        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        btn_box.set_halign(Gtk.Align.END)
        cancel = Gtk.Button(label="Annulla")
        cancel.connect("clicked", lambda w: self.destroy())
        save = Gtk.Button(label="Salva")
        save.get_style_context().add_class("suggested-action")
        save.connect("clicked", self.on_save)
        btn_box.append(cancel)
        btn_box.append(save)
        box.append(btn_box)

    def _add_field(self, parent, label_text, value):
        lbl = Gtk.Label(label=label_text)
        lbl.set_xalign(0)
        lbl.set_halign(Gtk.Align.START)
        entry = Gtk.Entry()
        entry.set_text(value)
        parent.append(lbl)
        parent.append(entry)
        return entry

    def on_save(self, w):
        new_cfg = {
            "installation_name": self.entry_installation.get_text().strip(),
            "mount_point": self.entry_mount.get_text().strip(),
            "programs_path": self.entry_programs.get_text().strip(),
            "conf_file": self.entry_conf.get_text().strip(),
            "img_path": self.entry_img.get_text().strip(),
        }
        save_config(new_cfg)
        self.parent.apply_config(new_cfg)
        self.destroy()


class SwichySSD(Gtk.Window):
    def __init__(self):
        super().__init__(title="Swichy SSD")
        self.set_default_size(800, 640)
        self.config = load_config()
        self.apply_config(self.config, refresh=False)

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        vbox.set_margin_top(14)
        vbox.set_margin_bottom(14)
        vbox.set_margin_start(14)
        vbox.set_margin_end(14)
        self.set_child(vbox)

        # --- Header ---
        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        title_lbl = Gtk.Label()
        title_lbl.set_markup("<span size='large'><b>Swichy SSD</b></span>")
        title_lbl.set_hexpand(True)
        title_lbl.set_xalign(0)
        settings_btn = Gtk.Button(label="Impostazioni")
        settings_btn.connect("clicked", self.on_settings_clicked)
        header.append(title_lbl)
        header.append(settings_btn)
        vbox.append(header)

        # --- Barra di stato ---
        self.status = Gtk.Label()
        self.status.set_xalign(0)
        self.status.set_halign(Gtk.Align.START)
        vbox.append(self.status)

        # --- Percorso attuale ---
        self.path_lbl = Gtk.Label()
        self.path_lbl.set_xalign(0)
        self.path_lbl.set_halign(Gtk.Align.START)
        self._update_path_label()
        vbox.append(self.path_lbl)

        # --- sezione: disco interno ---
        vbox.append(self._title("Sul disco interno (dove le installa lo store)"))
        self.lista_interno = Gtk.ListBox()
        self.lista_interno.set_selection_mode(Gtk.SelectionMode.NONE)
        sw1 = Gtk.ScrolledWindow()
        sw1.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        sw1.set_min_content_height(200)
        sw1.set_child(self.lista_interno)
        vbox.append(sw1)

        # --- sezione: predator ---
        h = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        h.append(self._title("Sul Predator (richiede il disco collegato)"))
        refresh = Gtk.Button(label="Aggiorna")
        refresh.connect("clicked", lambda w: self.aggiorna())
        h.append(refresh)
        vbox.append(h)

        self.lista_predator = Gtk.ListBox()
        self.lista_predator.set_selection_mode(Gtk.SelectionMode.NONE)
        sw2 = Gtk.ScrolledWindow()
        sw2.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        sw2.set_min_content_height(200)
        sw2.set_child(self.lista_predator)
        vbox.append(sw2)

        self.check_prerequisiti()
        self.aggiorna()

    def apply_config(self, cfg, refresh=True):
        self.config = cfg
        self.installation = cfg["installation_name"]
        self.mount_point = cfg["mount_point"]
        self.programs_path = cfg["programs_path"]
        self.conf_file = cfg["conf_file"]
        self.img_path = cfg.get("img_path", "")
        if refresh:
            self._update_path_label()
            self.check_prerequisiti()
            self.aggiorna()

    def _update_path_label(self):
        img = self.img_path or "Non impostato"
        txt = (f"<small><b>File immagine (disco esterno):</b> {img}\n"
               f"<b>Percorso montato:</b> {self.programs_path}  |  "
               f"<b>Installation:</b> {self.installation}</small>")
        self.path_lbl.set_markup(txt)

    def _title(self, t):
        l = Gtk.Label()
        l.set_markup(f"<b>{t}</b>")
        l.set_xalign(0)
        l.set_halign(Gtk.Align.START)
        return l

    def _row(self, app_id, nome, extra, bottone, handler, colore=None):
        row = Gtk.ListBoxRow()
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        box.set_margin_top(6)
        box.set_margin_bottom(6)
        box.set_margin_start(6)
        box.set_margin_end(6)
        left = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        n = Gtk.Label()
        n.set_markup(f"<b>{nome}</b>")
        n.set_xalign(0)
        s = Gtk.Label(label=f"{app_id}  {extra}")
        s.set_xalign(0)
        s.set_sensitive(False)
        left.append(n)
        left.append(s)
        btn = Gtk.Button(label=bottone)
        if colore:
            btn.get_style_context().add_class(colore)
        btn.connect("clicked", lambda w: handler(app_id, nome))
        box.append(left)
        box.append(btn)
        row.set_child(box)
        return row

    def _empty(self, lista, testo):
        l = Gtk.Label(label=testo)
        l.set_sensitive(False)
        r = Gtk.ListBoxRow()
        r.set_child(l)
        lista.append(r)

    def check_prerequisiti(self):
        problemi = []
        if not os.path.isfile(self.conf_file):
            problemi.append("installation non configurata (manca il file .conf)")
        if not os.path.ismount(self.mount_point):
            problemi.append("SSD non collegato/montato")
        if problemi:
            self.status.set_markup('<span foreground="red"><b>ATTENZIONE:</b> '
                                   + "; ".join(problemi) + "</span>")
        else:
            self.status.set_markup('<span foreground="green"><b>Tutto ok.</b></span> '
                                   "Le tue app e i tuoi dati restano intatti.")

    def pulisci(self, lista):
        while True:
            r = lista.get_first_child()
            if r is None:
                break
            lista.remove(r)

    def aggiorna(self):
        self.pulisci(self.lista_interno)
        self.pulisci(self.lista_predator)

        # app sul disco interno
        interne = {}
        for flag, orig in (("--system", "[sistema]"), ("--user", "[utente]")):
            r = run(["flatpak", "list", flag, "--app", "--columns=application,name"])
            if r.returncode == 0:
                for line in r.stdout.splitlines():
                    p = line.split("\t")
                    if len(p) >= 2:
                        interne[p[0].strip()] = (p[1].strip(), orig)
        if not interne:
            self._empty(self.lista_interno, "Nessuna app Flatpak sul disco interno.")
        else:
            pred = self._id_predator()
            for app_id, (nome, orig) in sorted(interne.items(), key=lambda x: x[1][0].lower()):
                if app_id in pred:
                    continue
                self.lista_interno.append(self._row(
                    app_id, nome, orig, "Sposta su Predator ->",
                    self.sposta_su_predator, "suggested-action"))

        # app sul predator
        r = run(["flatpak", "list", f"--installation={self.installation}",
                 "--app", "--columns=application,name"])
        trovate = []
        if r.returncode == 0 and os.path.ismount(self.mount_point):
            for line in r.stdout.splitlines():
                p = line.split("\t")
                if len(p) >= 2:
                    trovate.append((p[0].strip(), p[1].strip()))
        if not trovate:
            self._empty(self.lista_predator, "Nessuna app sul Predator (o disco scollegato).")
        else:
            for app_id, nome in sorted(trovate, key=lambda x: x[1].lower()):
                self.lista_predator.append(self._row(
                    app_id, nome, "", "<- Sposta sul disco interno",
                    self.sposta_su_interno))

    def _id_predator(self):
        r = run(["flatpak", "list", f"--installation={self.installation}",
                 "--app", "--columns=application"])
        return set(r.stdout.split()) if r.returncode == 0 else set()

    def on_settings_clicked(self, btn):
        dlg = SettingsDialog(self)
        dlg.present()

    def _terminale(self, titolo, comando):
        term = find_terminal()
        if not term:
            self._dialog("Errore", "Nessun terminale trovato (gnome-terminal/kgx).", error=True)
            return
        full = f"{comando}; echo; read -p 'Premi Invio per chiudere...'"
        if term == "gnome-terminal":
            subprocess.Popen([term, "--window", "--title", titolo, "--", "bash", "-c", full])
        elif term == "kgx":
            subprocess.Popen([term, "--", "bash", "-c", full])
        else:
            subprocess.Popen([term, "-e", f"bash -c '{full}'"])

    def sposta_su_predator(self, app_id, nome):
        if not os.path.ismount(self.mount_point):
            self._warning("Predator non collegato", "Collega e monta il disco, poi riprova.")
            return
        cmd = (f"flatpak install --installation={self.installation} -y flathub {app_id} && "
               f"(flatpak uninstall --system -y {app_id} 2>/dev/null; "
               f"flatpak uninstall --user -y {app_id} 2>/dev/null)")
        self._terminale(f"Sposto {nome} sul Predator", cmd)

    def sposta_su_interno(self, app_id, nome):
        cmd = (f"flatpak install --user -y flathub {app_id} && "
               f"flatpak uninstall --installation={self.installation} -y {app_id}")
        self._terminale(f"Sposto {nome} sul disco interno", cmd)

    def _dialog(self, title, message, error=False):
        dlg = Gtk.MessageDialog(
            transient_for=self,
            message_type=Gtk.MessageType.ERROR if error else Gtk.MessageType.INFO,
            buttons=Gtk.ButtonsType.OK,
            text=title
        )
        dlg.format_secondary_text(message)
        dlg.connect("response", lambda d, r: d.destroy())
        dlg.present()

    def _warning(self, title, message):
        dlg = Gtk.MessageDialog(
            transient_for=self,
            message_type=Gtk.MessageType.WARNING,
            buttons=Gtk.ButtonsType.OK,
            text=title
        )
        dlg.format_secondary_text(message)
        dlg.connect("response", lambda d, r: d.destroy())
        dlg.present()


def install_app():
    """Copia lo script in ~/.local/bin e crea il lanciatore nel menu."""
    import json as _json
    bin_dir = os.path.expanduser("~/.local/bin")
    app_dir = os.path.expanduser("~/.local/share/applications")
    os.makedirs(bin_dir, exist_ok=True)
    os.makedirs(app_dir, exist_ok=True)

    # copia se stesso
    src = os.path.abspath(__file__)
    dst = os.path.join(bin_dir, "sposta-app.py")
    shutil.copy2(src, dst)

    # crea il .desktop
    desktop = (
        "[Desktop Entry]\n"
        "Name=Swichy SSD\n"
        "Comment=Sposta le app Flatpak tra disco interno e SSD esterno\n"
        f"Exec=python3 {dst}\n"
        "Icon=drive-harddisk\n"
        "Terminal=false\n"
        "Type=Application\n"
        "Categories=Utility;\n"
    )
    with open(os.path.join(app_dir, "swichyssd.desktop"), "w") as f:
        f.write(desktop)

    subprocess.run(["update-desktop-database", app_dir], capture_output=True)
    print("Installato! Cerca 'Swichy SSD' nel menu delle applicazioni.")
    print(f"File copiato in: {dst}")


def on_activate(app):
    win = SwichySSD()
    win.set_application(app)
    win.present()


if __name__ == "__main__":
    if "--install" in sys.argv:
        install_app()
        sys.exit(0)

    try:
        app = Gtk.Application(application_id="com.bitfarmy.swichyssd")
        app.connect("activate", on_activate)
        app.run()
    except Exception:
        traceback.print_exc()
        input("Errore all'avvio (vedi sopra). Premi Invio per chiudere...")
