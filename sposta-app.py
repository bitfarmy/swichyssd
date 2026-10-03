#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Swichy SSD - sposta le app Flatpak tra disco interno e SSD Predator.
Nessuno store, nessuna ricerca: mostra cio' che hai gia' installato.
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

INSTALLATION = "predator"
MOUNT_POINT = "/mnt/predator-fedora"
CONF_FILE = "/etc/flatpak/installations.d/predator.conf"


def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)


def find_terminal():
    for term in ("gnome-terminal", "kgx", "x-terminal-emulator"):
        if shutil.which(term):
            return term
    return None


class SwichySSD(Gtk.Window):
    def __init__(self):
        super().__init__(title="Swichy SSD")
        self.set_default_size(780, 600)

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        vbox.set_margin_top(10)
        vbox.set_margin_bottom(10)
        vbox.set_margin_start(10)
        vbox.set_margin_end(10)
        self.set_child(vbox)

        # barra di stato
        self.status = Gtk.Label()
        self.status.set_xalign(0)
        self.status.set_halign(Gtk.Align.START)
        vbox.append(self.status)

        # ---- sezione: disco interno ----
        vbox.append(self._title("Sul disco interno (dove le installa lo store)"))
        self.lista_interno = Gtk.ListBox()
        self.lista_interno.set_selection_mode(Gtk.SelectionMode.NONE)
        sw1 = Gtk.ScrolledWindow()
        sw1.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        sw1.set_min_content_height(200)
        sw1.set_child(self.lista_interno)
        vbox.append(sw1)

        # ---- sezione: predator ----
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
        if not os.path.isfile(CONF_FILE):
            problemi.append("installation 'predator' non configurata")
        if not os.path.ismount(MOUNT_POINT):
            problemi.append("Predator non collegato/montato")
        if problemi:
            self.status.set_markup('<span foreground="red"><b>ATTENZIONE:</b> '
                                   + "; ".join(problemi) + "</span>")
        else:
            self.status.set_markup('<span foreground="green"><b>Tutto ok.</b></span> '
                                   "Le tue app e i tuoi dati restano al loro posto: lo spostamento "
                                   "non tocca le impostazioni delle app.")

    # ---------------- elenchi ----------------
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
        r = run(["flatpak", "list", f"--installation={INSTALLATION}",
                 "--app", "--columns=application,name"])
        trovate = []
        if r.returncode == 0 and os.path.ismount(MOUNT_POINT):
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
        r = run(["flatpak", "list", f"--installation={INSTALLATION}",
                 "--app", "--columns=application"])
        return set(r.stdout.split()) if r.returncode == 0 else set()

    # ---------------- azioni ----------------
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
        if not os.path.ismount(MOUNT_POINT):
            self._warning("Predator non collegato", "Collega e monta il disco, poi riprova.")
            return
        cmd = (f"flatpak install --installation={INSTALLATION} -y flathub {app_id} && "
               f"(flatpak uninstall --system -y {app_id} 2>/dev/null; "
               f"flatpak uninstall --user -y {app_id} 2>/dev/null)")
        self._terminale(f"Sposto {nome} sul Predator", cmd)

    def sposta_su_interno(self, app_id, nome):
        cmd = (f"flatpak install --user -y flathub {app_id} && "
               f"flatpak uninstall --installation={INSTALLATION} -y {app_id}")
        self._terminale(f"Sposto {nome} sul disco interno", cmd)

    # ---------------- dialog ----------------
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


def on_activate(app):
    win = SwichySSD()
    win.set_application(app)
    win.present()


if __name__ == "__main__":
    try:
        app = Gtk.Application(application_id="com.bitfarmy.swichyssd")
        app.connect("activate", on_activate)
        app.run()
    except Exception:
        traceback.print_exc()
        input("Errore all'avvio (vedi sopra). Premi Invio per chiudere...")
