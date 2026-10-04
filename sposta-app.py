#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Swichy SSD - sposta le app Flatpak tra disco interno e SSD esterno.
Richiede: GTK4 (python3-gobject).
"""
import json
import pwd
import shlex
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
import re
import shutil
import subprocess

CONFIG_DIR = os.path.expanduser("~/.config/swichyssd")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")

# UUID del Predator (non cambia mai)
PREDATOR_UUID = "5AA6-3C9C"

DEFAULT_CONFIG = {
    "installation_name": "predator",
    "mount_point": "/mnt/predator-fedora",
    "programs_path": "/mnt/predator-fedora/programs",
    "conf_file": "/etc/flatpak/installations.d/predator.conf",
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


def user_account():
    """L'utente vero, anche se lo script è stato rilanciato con sudo."""
    if os.geteuid() == 0 and os.environ.get("SUDO_USER"):
        return pwd.getpwnam(os.environ["SUDO_USER"])
    return pwd.getpwuid(os.getuid())


def ensure_privileges():
    """Il repository sul Predator è di root: senza sudo la copia non può scriverlo."""
    account = user_account()
    os.environ["HOME"] = account.pw_dir
    os.environ["USER"] = account.pw_name
    os.environ["LOGNAME"] = account.pw_name
    os.environ["XDG_DATA_HOME"] = os.path.join(account.pw_dir, ".local", "share")
    os.environ["XDG_CACHE_HOME"] = os.path.join(account.pw_dir, ".cache")
    if os.geteuid() == 0:
        return
    print("Servono i permessi di amministrazione per scrivere sul Predator.", flush=True)
    try:
        os.execvp(
            "sudo",
            ["sudo", "--preserve-env=HOME", sys.executable, os.path.abspath(__file__), *sys.argv[1:]],
        )
    except OSError as exc:
        sys.exit(f"sudo non disponibile: {exc}")


def give_back(path):
    """I file creati da root nella home vanno restituiti all'utente."""
    if os.geteuid() != 0 or not os.environ.get("SUDO_USER") or not os.path.exists(path):
        return
    account = user_account()
    for current, dirs, files in os.walk(path):
        os.chown(current, account.pw_uid, account.pw_gid)
        for name in dirs + files:
            os.chown(os.path.join(current, name), account.pw_uid, account.pw_gid)
    subprocess.run(["restorecon", "-R", path], capture_output=True)


def place_args(place, installation):
    if place == "system":
        return ["--system"]
    if place == "user":
        return ["--user"]
    return [f"--installation={installation}"]


def repo_path(place, programs_path):
    if place == "system":
        return "/var/lib/flatpak/repo"
    if place == "user":
        return os.path.join(os.environ["XDG_DATA_HOME"], "flatpak", "repo")
    return os.path.join(programs_path, "repo")


def is_installed(install_args, ref):
    return run(["flatpak", "info", *install_args, ref]).returncode == 0


def remote_url(install_args, origin):
    result = run(["flatpak", "remotes", *install_args, "--columns=name,url"])
    for line in result.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) >= 2 and parts[0] == origin:
            url = parts[1].strip()
            if url and url != "-":
                return url
    return None


def ensure_remote(dest_args, origin, url):
    if remote_url(dest_args, origin):
        return
    result = run(["flatpak", "remote-add", *dest_args, "--if-not-exists", origin, url])
    if result.returncode != 0:
        print(result.stderr, end="")
        sys.exit(f"Non riesco ad aggiungere il remote {origin}.")


def info_lines(install_args, ref):
    result = run(["flatpak", "info", *install_args, "-e", ref])
    if result.returncode != 0:
        print(result.stderr, end="")
        sys.exit(f"flatpak info fallito per {ref}.")
    runtime = None
    extensions = []
    for line in result.stdout.splitlines():
        stripped = line.strip()
        if stripped.startswith("Runtime:"):
            runtime = stripped.split(":", 1)[1].strip()
        elif stripped.startswith("Extension:"):
            extensions.append(stripped.split(":", 1)[1].strip())
    return runtime, extensions


def refs_to_copy(src_args, app_id):
    runtime, app_extensions = info_lines(src_args, app_id)
    app_ref = run(["flatpak", "info", *src_args, "-r", app_id]).stdout.strip()
    refs = []
    if runtime:
        runtime_ref = runtime if runtime.startswith("runtime/") else "runtime/" + runtime
        refs.append(runtime_ref)
        runtime_extensions = info_lines(src_args, runtime_ref)[1]
        refs.extend(runtime_extensions)
    if app_ref:
        refs.append(app_ref)
    refs.extend(app_extensions)
    unique = []
    for ref in refs:
        if ref and ref not in unique and is_installed(src_args, ref):
            unique.append(ref)
    return unique


def stage_and_install(src_repo, dest_repo, dest_args, origin, ref):
    kind, name, arch, branch = ref.split("/", 3)
    work = os.path.join(os.environ["XDG_CACHE_HOME"], "swichyssd")
    os.makedirs(work, exist_ok=True)
    bundle = os.path.join(work, "transfer.flatpak")
    if os.path.exists(bundle):
        os.remove(bundle)
    command = ["flatpak", "build-bundle", src_repo, bundle, name, branch, "--arch", arch]
    if kind == "runtime":
        command.append("--runtime")
    result = run(command)
    if result.returncode != 0:
        print(result.stderr, end="")
        sys.exit(f"Copia locale fallita per {ref}. L'app originale non è stata rimossa.")
    result = run(["flatpak", "build-import-bundle", dest_repo, bundle])
    os.remove(bundle)
    if result.returncode != 0:
        print(result.stderr, end="")
        sys.exit(f"Import fallito per {ref}. L'app originale non è stata rimossa.")
    heads = os.path.join(dest_repo, "refs", "heads", *ref.split("/"))
    found = re.search(r"\(([0-9a-f]{64})\)", result.stdout)
    if os.path.isfile(heads):
        checksum = open(heads).read().strip()
    elif found:
        checksum = found.group(1)
    else:
        sys.exit(f"Commit non trovato dopo l'import: {heads}")
    remote_ref = os.path.join(dest_repo, "refs", "remotes", origin, *ref.split("/"))
    os.makedirs(os.path.dirname(remote_ref), exist_ok=True)
    with open(remote_ref, "w") as handle:
        handle.write(checksum + "\n")
    result = run(["flatpak", "install", *dest_args, "-y", "--noninteractive", "--no-pull", origin, ref])
    print(result.stdout, end="")
    if result.returncode != 0:
        print(result.stderr, end="")
        sys.exit(f"Installazione locale fallita per {ref}. L'app originale non è stata rimossa.")


def icon_names(app_id, filename):
    return filename == app_id or filename.startswith(app_id + ".") or filename.startswith(app_id + "-")


def export_desktop(programs_path, installation, app_id):
    desktop_src = os.path.join(programs_path, "exports", "share", "applications", f"{app_id}.desktop")
    if not os.path.isfile(desktop_src):
        sys.exit(f"Voce di menu non trovata dopo l'installazione: {desktop_src}")
    text = open(desktop_src).read()

    def rewrite(match):
        return f"Exec=flatpak run --installation={installation} "

    new_text, replaced = re.subn(r"(?m)^Exec=(?:/usr/bin/)?flatpak run ", rewrite, text, count=1)
    if replaced != 1:
        sys.exit("Il file .desktop non ha una riga Exec=flatpak run da aggiornare.")
    dst_dir = os.path.join(os.environ["XDG_DATA_HOME"], "applications")
    os.makedirs(dst_dir, exist_ok=True)
    dst = os.path.join(dst_dir, f"{app_id}.desktop")
    with open(dst, "w") as handle:
        handle.write(new_text)

    src_icons = os.path.join(programs_path, "exports", "share", "icons")
    dst_icons = os.path.join(os.environ["XDG_DATA_HOME"], "icons")
    if os.path.isdir(src_icons):
        for current, _dirs, files in os.walk(src_icons):
            for name in files:
                if not icon_names(app_id, name):
                    continue
                src = os.path.join(current, name)
                dst_icon = os.path.join(dst_icons, os.path.relpath(src, src_icons))
                os.makedirs(os.path.dirname(dst_icon), exist_ok=True)
                shutil.copy2(src, dst_icon)
    subprocess.run(["update-desktop-database", dst_dir], capture_output=True)
    give_back(dst_dir)
    give_back(dst_icons)


def remove_desktop(app_id):
    path = os.path.join(os.environ["XDG_DATA_HOME"], "applications", f"{app_id}.desktop")
    if os.path.isfile(path):
        os.remove(path)
        subprocess.run(
            ["update-desktop-database", os.path.join(os.environ["XDG_DATA_HOME"], "applications")],
            capture_output=True,
        )


def remove_copied_icons(app_id):
    root = os.path.join(os.environ["XDG_DATA_HOME"], "icons")
    if not os.path.isdir(root):
        return
    for current, _dirs, files in os.walk(root):
        for name in files:
            if icon_names(app_id, name):
                os.remove(os.path.join(current, name))


def move_app(direction, app_id):
    ensure_privileges()
    cfg = load_config()
    installation = cfg["installation_name"]
    programs = cfg["programs_path"]
    if direction == "to-predator":
        dest = "predator"
        source_order = ["system", "user"]
    else:
        dest = "user"
        source_order = ["predator"]

    present = [place for place in ("system", "user", "predator") if is_installed(place_args(place, installation), app_id)]
    sources = [place for place in source_order if place in present]
    if not sources:
        sys.exit(f"{app_id} non è installata nel punto da cui andrebbe copiata.")
    src = sources[0]
    src_args = place_args(src, installation)
    dest_args = place_args(dest, installation)
    origin = run(["flatpak", "info", *src_args, "-o", app_id]).stdout.strip()
    if not origin:
        sys.exit("Impossibile leggere il remote di origine.")
    url = remote_url(src_args, origin)
    if not url:
        sys.exit(f"Il remote {origin} non ha un URL: non posso copiare l'app senza riscaricarla da un nome fisso.")

    print(f"Copio {app_id} da {src} (remote {origin}) verso {dest}.", flush=True)
    print("Uso i file già installati, senza riscaricarli.", flush=True)
    ensure_remote(dest_args, origin, url)
    src_repo = repo_path(src, programs)
    dest_repo = repo_path(dest, programs)
    if not os.path.isdir(src_repo) or not os.path.isdir(dest_repo):
        sys.exit(f"Repository mancante.\norigine: {src_repo}\ndestinazione: {dest_repo}")

    for ref in refs_to_copy(src_args, app_id):
        if is_installed(dest_args, ref):
            print(f"Già presente: {ref}", flush=True)
            continue
        print(f"Copio {ref}", flush=True)
        stage_and_install(src_repo, dest_repo, dest_args, origin, ref)

    if direction == "to-predator":
        export_desktop(programs, installation, app_id)
        print("Voce di menu creata.", flush=True)
    else:
        remove_desktop(app_id)
        remove_copied_icons(app_id)
        give_back(os.path.join(os.environ["XDG_DATA_HOME"], "flatpak"))
        print("Voce di menu dell'SSD rimossa.", flush=True)

    for place in sources:
        print(f"Rimuovo la copia su {place}.", flush=True)
        result = run(["flatpak", "uninstall", *place_args(place, installation), "-y", "--noninteractive", app_id])
        print(result.stdout, end="")
        if result.returncode != 0:
            print(result.stderr, end="")
            sys.exit(f"Disinstallazione da {place} fallita. L'app è ancora installata anche lì.")
    give_back(os.path.join(os.environ["XDG_CACHE_HOME"], "swichyssd"))
    print("Fatto. Torna su Swichy SSD e clicca Aggiorna.", flush=True)


def find_predator_mount():
    """Trova dove GNOME ha montato il Predator usando l'UUID."""
    r = run(["findmnt", "-n", "-o", "TARGET", "-S", f"UUID={PREDATOR_UUID}"])
    path = r.stdout.strip()
    return path if path else None


def find_img_path():
    """Costruisce il percorso del file immagine in base al mount attuale del Predator."""
    mount = find_predator_mount()
    if mount:
        return os.path.join(mount, "asus-linux", "fedora-apps.img")
    return None


def find_terminal():
    for term in ("ptyxis", "gnome-terminal", "kgx", "x-terminal-emulator"):
        if shutil.which(term):
            return term
    return None


def build_full_command(cmd):
    """Costruisce il comando con pausa finale compatibile con tutti i terminali."""
    return f"{cmd}; echo; echo 'Premi Invio per chiudere...'; read dummy"


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

        title = Gtk.Label()
        title.set_markup("<b>Impostazioni</b>")
        title.set_xalign(0)
        box.append(title)

        self.entry_installation = self._add_field(box, "Nome installation Flatpak:", cfg["installation_name"])
        self.entry_mount = self._add_field(box, "Mount point SSD:", cfg["mount_point"])
        self.entry_programs = self._add_field(box, "Percorso programs:", cfg["programs_path"])
        self.entry_conf = self._add_field(box, "File configurazione:", cfg["conf_file"])

        info = Gtk.Label()
        info.set_markup("<small>I percorsi devono corrispondere a una custom installation Flatpak valida.</small>")
        info.set_wrap(True)
        info.set_xalign(0)
        box.append(info)

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

        self.status = Gtk.Label()
        self.status.set_xalign(0)
        self.status.set_halign(Gtk.Align.START)
        vbox.append(self.status)

        # Bottoni disco (compaiono solo quando servono)
        azioni_disco = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.monta_btn = Gtk.Button(label="Monta il Predator")
        self.monta_btn.set_visible(False)
        self.monta_btn.connect("clicked", self.on_monta_clicked)
        self.smonta_btn = Gtk.Button(label="Smonta immagine")
        self.smonta_btn.set_visible(False)
        self.smonta_btn.connect("clicked", self.on_smonta_clicked)
        self.espelli_btn = Gtk.Button(label="Espelli disco")
        self.espelli_btn.set_visible(False)
        self.espelli_btn.connect("clicked", self.on_espelli_clicked)
        azioni_disco.append(self.monta_btn)
        azioni_disco.append(self.smonta_btn)
        azioni_disco.append(self.espelli_btn)
        vbox.append(azioni_disco)

        vbox.append(self._title("Sul disco interno (dove le installa lo store)"))
        self.lista_interno = Gtk.ListBox()
        self.lista_interno.set_selection_mode(Gtk.SelectionMode.NONE)
        sw1 = Gtk.ScrolledWindow()
        sw1.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        sw1.set_min_content_height(200)
        sw1.set_child(self.lista_interno)
        vbox.append(sw1)

        h = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        h.append(self._title("Sul Predator (richiede il disco collegato)"))
        refresh = Gtk.Button(label="Aggiorna")
        refresh.connect("clicked", lambda w: self.aggiorna())
        h.append(refresh)
        aggiorna_btn = Gtk.Button(label="Aggiorna app Predator")
        aggiorna_btn.connect("clicked", self.on_aggiorna_predator_clicked)
        h.append(aggiorna_btn)
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
        if refresh:
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
        conf_mancante = ""
        if not os.path.isfile(self.conf_file):
            conf_mancante = " Manca il file di installation Flatpak."

        loop_montato = os.path.ismount(self.mount_point)
        predator_collegato = find_predator_mount() is not None
        img = find_img_path()

        if loop_montato:
            self.status.set_markup(
                '<span foreground="green"><b>Predator montato.</b></span> '
                "Smonta l'immagine prima di staccare il disco." + conf_mancante
            )
            self.monta_btn.set_visible(False)
            self.smonta_btn.set_visible(True)
        elif predator_collegato and img and os.path.isfile(img):
            self.status.set_markup(
                '<span foreground="orange"><b>Predator collegato ma non montato.</b></span> '
                "Clicca Monta il Predator." + conf_mancante
            )
            self.monta_btn.set_visible(True)
            self.smonta_btn.set_visible(False)
        else:
            self.status.set_markup(
                '<span foreground="red"><b>Predator non collegato.</b></span> '
                "Collega il disco e clicca Aggiorna." + conf_mancante
            )
            self.monta_btn.set_visible(False)
            self.smonta_btn.set_visible(False)
        self.espelli_btn.set_visible(predator_collegato or loop_montato)

    def on_aggiorna_predator_clicked(self, btn):
        if not os.path.ismount(self.mount_point):
            self._warning("Predator non montato", "Collega il disco, montalo, poi riprova.")
            return
        cmd = f"flatpak update --installation={shlex.quote(self.installation)} -y"
        self._terminale("Aggiorna app sul Predator", cmd)

    def on_monta_clicked(self, btn):
        img = find_img_path()
        if not img:
            self._warning("Errore", "Non trovo il Predator. E' collegato?")
            return
        if not os.path.isfile(img):
            self._warning("Errore", f"File immagine non trovato:\n{img}")
            return
        mount = shlex.quote(self.mount_point)
        image = shlex.quote(img)
        cmd = f"sudo mkdir -p {mount} && sudo mount -o loop {image} {mount}"
        self._terminale("Monta Predator", cmd)

    def on_smonta_clicked(self, btn):
        if not os.path.ismount(self.mount_point):
            self._warning("Già smontato", "L'immagine non è montata.")
            return
        mount = shlex.quote(self.mount_point)
        cmd = (
            f"sync && sudo umount {mount} && "
            "echo \"Immagine smontata. I file sulla partizione exFAT restano aperti. "
            "Per staccare il disco usa Espelli, poi clicca Aggiorna.\""
        )
        self._terminale("Smonta immagine", cmd)

    def on_espelli_clicked(self, btn):
        mount = shlex.quote(self.mount_point)
        uuid = shlex.quote(PREDATOR_UUID)
        cmd = (
            "set -eu\n"
            f"if mountpoint -q {mount}; then sync; sudo umount {mount}; fi\n"
            f"part=$(findmnt -n -o SOURCE -S UUID={uuid} || true)\n"
            'if [ -z "$part" ]; then echo "Il disco non risulta montato."; exit 0; fi\n'
            'udisksctl unmount -b "$part"\n'
            'disk=$(lsblk -no PKNAME "$part")\n'
            'if [ -n "$disk" ]; then udisksctl power-off -b "/dev/$disk"; fi\n'
            'echo "Disco espulso. Puoi staccarlo. Torna su Swichy SSD e clicca Aggiorna."\n'
        )
        self._terminale("Espelli disco", cmd)

    def pulisci(self, lista):
        while True:
            r = lista.get_first_child()
            if r is None:
                break
            lista.remove(r)

    def aggiorna(self):
        self.check_prerequisiti()
        self.pulisci(self.lista_interno)
        self.pulisci(self.lista_predator)

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
                extra = orig
                if app_id in pred:
                    extra = f"{orig}  [copia già sul Predator]"
                self.lista_interno.append(self._row(
                    app_id, nome, extra, "Sposta su Predator ->",
                    self.sposta_su_predator, "suggested-action"))

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
            self._dialog("Errore", "Nessun terminale trovato. Installa GNOME Terminal o Ptyxis.", error=True)
            return
        full = build_full_command(comando)
        # CORREZIONE: stesso fix del ramo on_monta_clicked.
        if term == "gnome-terminal":
            subprocess.Popen([term, "--window", "--title", titolo, "--", "bash", "-c", full])
        elif term in ("kgx", "ptyxis"):
            subprocess.Popen([term, "--", "bash", "-c", full])
        else:
            subprocess.Popen([term, "-e", "bash", "-c", full])

    def _comando_sposta(self, flag, app_id):
        script = shlex.quote(os.path.abspath(__file__))
        return f"python3 {script} {flag} {shlex.quote(app_id)}"

    def sposta_su_predator(self, app_id, nome):
        if not os.path.ismount(self.mount_point):
            self._warning("Predator non montato", "Collega il disco e clicca 'Monta il Predator', poi riprova.")
            return
        self._terminale(f"Sposto {nome} sul Predator", self._comando_sposta("--move-to-predator", app_id))

    def sposta_su_interno(self, app_id, nome):
        if not os.path.ismount(self.mount_point):
            self._warning("Predator non montato", "Collega il disco e clicca 'Monta il Predator', poi riprova.")
            return
        self._terminale(f"Sposto {nome} sul disco interno", self._comando_sposta("--move-to-internal", app_id))

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
    bin_dir = os.path.expanduser("~/.local/bin")
    app_dir = os.path.expanduser("~/.local/share/applications")
    os.makedirs(bin_dir, exist_ok=True)
    os.makedirs(app_dir, exist_ok=True)

    src = os.path.abspath(__file__)
    dst = os.path.join(bin_dir, "sposta-app.py")
    shutil.copy2(src, dst)

    desktop = (
        "[Desktop Entry]\n"
        "Name=Swichy SSD\n"
        "Comment=Sposta le app Flatpak tra disco interno e SSD esterno\n"
        f"Exec=/usr/bin/python3 {dst}\n"
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
    for flag, direction in (("--move-to-predator", "to-predator"), ("--move-to-internal", "to-internal")):
        if flag in sys.argv:
            index = sys.argv.index(flag)
            if index + 1 >= len(sys.argv):
                sys.exit("Manca l'id dell'app.")
            move_app(direction, sys.argv[index + 1])
            sys.exit(0)

    try:
        app = Gtk.Application(application_id="com.bitfarmy.swichyssd")
        app.connect("activate", on_activate)
        app.run()
    except Exception:
        traceback.print_exc()
        input("Errore all'avvio (vedi sopra). Premi Invio per chiudere...")
