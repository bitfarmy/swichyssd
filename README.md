# SwichySSD

Sposta le app Flatpak tra il disco interno e un SSD esterno su Fedora Linux,
con una custom installation di Flatpak (in italiano: niente complicazioni, solo bottoni).

## Come funziona

1. Installi le app normalmente da GNOME Software (finiscono sul disco interno)
2. Apri **Swichy SSD**: elenca tutte le tue app
3. Un click su **"Sposta su Predator"** → l'app viene reinstallata sull'SSD esterno
   e rimossa dal disco interno. Dati e impostazioni delle app restano intatti
   (vivono in `~/.var/app/`, non vengono toccati).

Viceversa, le app sull'SSD esterno hanno il bottone **"Sposta sul disco interno"**
per quando devi usare il PC senza il disco.

## Novita: Impostazioni

Clicca il bottone **"Impostazioni"** in alto per:
- Vedere il **percorso attuale** dove finiscono le app
- Cambiare il **nome installation** Flatpak
- Cambiare il **mount point** e il **percorso programs**
- Cambiare il **file di configurazione**

Tutto viene salvato in `~/.config/swichyssd/config.json`.

## Prerequisiti (una tantum)

Il programma richiede che l'SSD esterno sia configurato come custom installation
Flatpak. Riassunto per Fedora:

```bash
# 1. file immagine ext4 dentro la partizione exFAT (mantiene compatibilita' Windows)
dd if=/dev/zero of=/mnt/predator-ssd/asus-linux/fedora-apps.img bs=1M count=51200
mkfs.ext4 -L fedora-apps /mnt/predator-ssd/asus-linux/fedora-apps.img

# 2. montaggio automatico (adatta UUID e percorsi al tuo disco)
sudo mkdir /mnt/predator-fedora
# aggiungere a /etc/fstab:
#   UUID=XXXX-XXXX  /mnt/predator-ssd  exfat  defaults,nofail  0  0
#   /mnt/predator-ssd/asus-linux/fedora-apps.img  /mnt/predator-fedora  ext4  loop,defaults,x-systemd.requires-mounts-for=/mnt/predator-ssd  0  2
sudo mount -a

# 3. custom installation Flatpak
sudo mkdir -p /etc/flatpak/installations.d
sudo tee /etc/flatpak/installations.d/predator.conf > /dev/null <<'CONF'
[Installation "predator"]
Path=/mnt/predator-fedora/programs
DisplayName=Predator SSD
StorageType=ssd
CONF
sudo flatpak remote-add --installation=predator --if-not-exists flathub https://flathub.org/repo/flathub.flatpakrepo
```

## Installazione

```bash
git clone https://github.com/bitfarmy/swichyssd.git
cd swichyssd
chmod +x install.sh   # solo se da' "Permesso negato"
./install.sh
```

Poi cerca **"Swichy SSD"** nel menu delle applicazioni (icona disco).

## Requisiti

- Fedora (o altra distro) con GNOME e Flatpak
- `python3-gobject` e GTK4 (gia' presenti su Fedora Workstation)
- GNOME Terminal (o kgx) per mostrare il progresso degli spostamenti

## Regole d'oro con un SSD esterno

- **Espelli sempre il disco in sicurezza** prima di scollegarlo
- Se Windows propone di formattare il disco o il file `.img`, annulla sempre
- Senza disco collegato, le app sull'SSD non sono disponibili (e il programma
  te lo segnala)

## Licenza

MIT - vedi LICENSE
