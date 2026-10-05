# SwichySSD

Versione 2.0. Sposta le app Flatpak tra il disco interno e un SSD esterno su Fedora Linux.
Niente fstab pericoloso, niente blocchi all'avvio: il disco si monta e si smonta dai bottoni.

## Versione 2.0

- **Smonta immagine** chiude solo il file `.img` delle app. I documenti sulla partizione exFAT restano aperti.
- **Espelli disco** smonta prima l'immagine, poi l'exFAT, e spegne il disco. Usalo prima di staccare il cavo.
- **Aggiorna** rilegge se il disco è collegato e se l'immagine è montata, e aggiorna i bottoni.
- Lo spostamento copia l'app già installata, dal remote da cui proviene, senza riscaricarla da Flathub. La voce di menu e le icone si creano solo se la copia riesce. Se la disinstallazione fallisce, l'errore resta nel terminale e l'app non viene nascosta.

## Come funziona

1. Installi le app normalmente da GNOME Software (finiscono sul disco interno)
2. Collega il tuo SSD esterno
3. Apri **Swichy SSD**: se il disco non è ancora montato, clicca **"Monta il Predator"**
4. Un click su **"Sposta su Predator"** copia l'app sull'SSD e la toglie dal disco interno
5. Per chiudere solo le app e tenere i file: **Smonta immagine**
6. Per staccare il disco: **Espelli disco**, poi clicca **Aggiorna**

Viceversa, le app sull'SSD hanno il bottone **"<- Sposta sul disco interno"**
per quando devi usare il PC senza il disco. Lo spostamento chiede la password di amministrazione perché il repository Flatpak sul Predator è di root.

**I tuoi dati e impostazioni delle app restano sempre intatti:** vivono in `~/.var/app/`
e non vengono toccati quando sposti un'app.

## Requisiti hardware (una tantum)

Il tuo SSD esterno deve contenere un **file immagine ext4** (`.img`) dentro una
partizione exFAT. Questo permette a Flatpak di funzionare correttamente mantenendo
la compatibilita' con Windows.

### Se parti da zero

```bash
# 1. Crea il file immagine da 50 GB dentro la cartella dedicata
sudo mkdir -p /run/media/$USER/NOME_SSD/asus-linux
dd if=/dev/zero of=/run/media/$USER/NOME_SSD/asus-linux/fedora-apps.img bs=1M count=51200
mkfs.ext4 -L fedora-apps /run/media/$USER/NOME_SSD/asus-linux/fedora-apps.img

# 2. Montalo una volta per creare la struttura
sudo mkdir -p /mnt/predator-fedora
sudo mount -o loop /run/media/$USER/NOME_SSD/asus-linux/fedora-apps.img /mnt/predator-fedora
sudo mkdir -p /mnt/predator-fedora/programs
sudo umount /mnt/predator-fedora
```

### Se hai gia' il file immagine (es. dopo una reinstallazione)

Non devi rifarlo. Basta montarlo:

```bash
sudo mkdir -p /mnt/predator-fedora
sudo mount -o loop "/run/media/$USER/PSSD GP30/asus-linux/fedora-apps.img" /mnt/predator-fedora
```

(Adatta il percorso in base a dove GNOME monta il tuo SSD.)

## Configurazione Flatpak (una tantum)

```bash
sudo mkdir -p /etc/flatpak/installations.d
sudo tee /etc/flatpak/installations.d/predator.conf > /dev/null <<'CONF'
[Installation "predator"]
Path=/mnt/predator-fedora/programs
DisplayName=Predator SSD
StorageType=ssd
CONF
sudo flatpak remote-add --installation=predator --if-not-exists flathub https://flathub.org/repo/flathub.flatpakrepo
```

## Installazione Swichy SSD

```bash
git clone https://github.com/bitfarmy/swichyssd.git
cd swichyssd
python3 sposta-app.py --install
```

Poi cerca **"Swichy SSD"** nel menu delle applicazioni (icona disco).

Per aggiornare (stessi comandi, sovrascrive automaticamente):

```bash
cd swichyssd
git pull
python3 sposta-app.py --install
```

## Come si comporta il sistema

| Situazione | Cosa succede |
|---|---|
| **PC senza SSD collegato** | Fedora avvia normalmente. Lo store installa sul disco interno. Swichy SSD mostra "Predator non collegato". |
| **SSD collegato, non montato** | Swichy SSD rileva il disco e mostra **"Monta il Predator"**. Il bottone **Aggiorna** rilegge anche questo stato. |
| **SSD montato** | Vedi le app sul Predator e puoi spostarle avanti e indietro. **Smonta immagine** chiude solo il file `.img`. **Espelli disco** smonta prima l'immagine, poi la partizione exFAT, e spegne il disco. |

**Niente fstab, niente blocchi all'avvio.** Il montaggio e' manuale o tramite bottone.

## Installare da terminale direttamente sul Predator

```bash
# Prima monta il file immagine (se non e' gia' montato)
sudo mount -o loop "/run/media/$USER/PSSD GP30/asus-linux/fedora-apps.img" /mnt/predator-fedora

# Poi installa con --installation
flatpak install --installation=predator flathub nomeapp
```

Per installare sul disco interno (default):

```bash
flatpak install flathub nomeapp
```

## File e repository personali

**Non usare il file immagine `.img` per i tuoi file.** Montalo solo per le app Flatpak.

Per i tuoi documenti, codice, repository: usa la partizione **exFAT** del Predator
direttamente, ad esempio:

```
/run/media/$USER/NOME_SSD/progetti
/run/media/$USER/NOME_SSD/repository
```

Windows legge queste cartelle normalmente.

## Requisiti software

- Fedora (o altra distro) con GNOME e Flatpak
- `python3-gobject` e GTK4 (gia' presenti su Fedora Workstation)
- Ptyxis, GNOME Terminal o kgx, per mostrare il progresso degli spostamenti e chiedere la password

## Regole d'oro con un SSD esterno

- **Espelli sempre il disco** con il bottone **Espelli disco** prima di scollegarlo. Staccare il cavo con l'immagine ancora montata lascia l'exFAT sporco.
- Se Windows propone di formattare il disco o il file `.img`, annulla sempre
- Senza disco collegato, le app sull'SSD non sono disponibili (e il programma te lo segnala)
- Se reinstalli Fedora, il file `.img` e le app dentro restano intatti sul SSD

## Licenza

MIT - vedi LICENSE
