#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sposta App - sposta le app Flatpak tra disco interno e SSD Predator.
Nessuno store, nessuna ricerca: mostra cio' che hai gia' installato.
"""
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

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


class SpostaApp(Gtk.Window):
    def __init__(self):
        super().__init__(title="Sposta App - Disco interno <-> Predator")
        self.set_default_size(780, 600)
        self.set_border_width(10)

        vbox = Gtk.Box(orientation=Gtk.VERTICAL, spacing=8)
        self.add(vbox)

        # barra di stato
        self.status = Gtk.Label()
        self.status.set_xalign(0)
        vbox.pack_start(self.status, False, False, 0)

        # ---- sezione: disco interno ----
        vbox.pack_start(self._title("Sul disco interno (dove le installa lo store)"), False, False, 0)
        self.lista_interno = Gtk.ListBox()
        self.lista_interno.set_selection_mode(Gtk.SelectionMode.NONE)
        sw1 = Gtk.ScrolledWindow()
        sw1.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        sw1.set_min_content_height(200)
        sw1.add(self.lista_interno)
        vbox.pack_start(sw1, True, True, 0)

        # ---- sezione: predator ----
        h = Gtk.Box(orientation=Gtk.HORIZONTAL, spacing=6)
        h.pack_start(self._title("Sul Predator (richiede il disco collegato)"), True, True, 0)
        refresh = Gtk.Button(label="Aggiorna")
        refresh.connect("clicked", lambda w: self.aggiorna())
        h.pack_start(refresh, False, False, 0)
        vbox.pack_start(h, False, False, 0)

        self.lista_predator = Gtk.ListBox()
        self.lista_predator.set_selection_mode(Gtk.SelectionMode.NONE)
        sw2 = Gtk.ScrolledWindow()
        sw2.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        sw2.set_min_content_height(200)
        sw2.add(self.lista_predator)
        vbox.pack_start(sw2, True, True, 0)

        self.check_prerequisiti()
        self.show_all()
        self.aggiorna()

    def _title(self, t):
        l = Gtk.Label(); l.set_markup(f"<b>{t}</b>"); l.set_xalign(0)
        return l

    def _row(self, app_id, nome, extra, bottone, handler, colore=None):
        row = Gtk.ListBoxRow()
        box = Gtk.Box(orientation=Gtk.HORIZONTAL, spacing=10)
        box.set_border_width(6)
        left = Gtk.Box(orientation=Gtk.VERTICAL, spacing=2)
        n = Gtk.Label(); n.set_markup(f"<b>{nome}</b>"); n.set_xalign(0)
        s = Gtk.Label(label=f"{app_id}  {extra}"); s.set_xalign(0); s.set_sensitive(False)
        left.pack_start(n, False, False, 0)
        left.pack_start(s, False, False, 0)
        btn = Gtk.Button(label=bottone)
        if colore:
            btn.get_style_context().add_class(colore)
        btn.connect("clicked", lambda w: handler(app_id, nome))
        box.pack_start(left, True, True, 0)
        box.pack_start(btn, False, False, 0)
        row.add(box)
        return row

    def _empty(self, lista, testo):
        l = Gtk.Label(label=testo); l.set_sensitive(False)
        r = Gtk.ListBoxRow(); r.add(l)
        lista.add(r)

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
        for r in list(lista.get_children()):
            lista.remove(r)

    def aggiorna(self):
        self.pulisci(self.lista_interno)
        self.pulisci(self.lista_predator)

        # app sul disco interno (installation di sistema + utente)
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
                    continue  # gia' presente anche sul predator
                self.lista_interno.add(self._row(
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
                self.lista_predator.add(self._row(
                    app_id, nome, "", "<- Sposta sul disco interno",
                    self.sposta_su_interno))
        self.lista_interno.show_all()
        self.lista_predator.show_all()

    def _id_predator(self):
        r = run(["flatpak", "list", f"--installation={INSTALLATION}",
                 "--app", "--columns=application"])
        return set(r.stdout.split()) if r.returncode == 0 else set()

    # ---------------- azioni ----------------
    def _terminale(self, titolo, comando):
        term = find_terminal()
        if not term:
            dlg = Gtk.MessageDialog(self, 0, Gtk.MessageType.ERROR, Gtk.ButtonsType.OK,
                                    "Nessun terminale trovato")
            dlg.run(); dlg.destroy(); return
        full = f"{comando}; echo; read -p 'Premi Invio per chiudere...'"
        if term == "gnome-terminal":
            subprocess.Popen([term, "--window", "--title", titolo, "--", "bash", "-c", full])
        elif term == "kgx":
            subprocess.Popen([term, "--", "bash", "-c", full])
        else:
            subprocess.Popen([term, "-e", f"bash -c '{full}'"])
        self.connect("focus-in-event", lambda w, e: self.aggiorna() or False)

    def sposta_su_predator(self, app_id, nome):
        if not os.path.ismount(MOUNT_POINT):
            dlg = Gtk.MessageDialog(self, 0, Gtk.MessageType.WARNING, Gtk.ButtonsType.OK,
                                    "Predator non collegato")
            dlg.format_secondary_text("Collega e monta il disco, poi riprova.")
            dlg.run(); dlg.destroy(); return
        # installa sul predator, poi rimuovi dal disco interno (sistema e/o utente)
        cmd = (f"flatpak install --installation={INSTALLATION} -y flathub {app_id} && "
               f"(flatpak uninstall --system -y {app_id} 2>/dev/null; "
               f"flatpak uninstall --user -y {app_id} 2>/dev/null)")
        self._terminale(f"Sposto {nome} sul Predator", cmd)

    def sposta_su_interno(self, app_id, nome):
        # installa come app utente sul disco interno, poi rimuovi dal predator
        cmd = (f"flatpak install --user -y flathub {app_id} && "
               f"flatpak uninstall --installation={INSTALLATION} -y {app_id}")
        self._terminale(f"Sposto {nome} sul disco interno", cmd)


if __name__ == "__main__":
    win = SpostaApp()
    win.connect("destroy", Gtk.main_quit)
    Gtk.main()
