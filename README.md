# Nuage Explorer

Petit gestionnaire de fichiers pour accéder à son espace NUAGE de l'Éducation nationale via WebDAV, avec aperçu des documents.

## Structure du projet

```text
src/
├── main.py
└── nuage_explorer/
    ├── __init__.py
    ├── common.py       # imports, accès au coffre, chemins et helpers partagés
    ├── style.py        # feuille de style Qt
    ├── workers.py      # workers Qt de transfert et documents Office
    ├── dialogs.py      # ProfileDialog, PreviewDialog, RemoteFolderDialog
    ├── widgets.py      # widgets de glisser-déposer
    ├── main_window.py        # construction de la fenêtre principale
    ├── profile_navigation.py # profil, arborescence et navigation
    ├── preview_office.py     # aperçus et fonctions LibreOffice
    ├── printing.py           # Module impression des pdf
    ├── remote_operations.py  # menu contextuel, couper/copier, renommer/supprimer
    ├── transfers.py          # téléchargements, envois et glisser-déposer
    ├── folder_operations.py  # création de dossiers distants
    ├── storage.py            # récupération du quota
    └── storage_widget.py      # affichage du quota
```

Le dossier `.venv` peut être recréé. **Le fichier `requirements.txt`, lui, doit être conservé avec le projet** : il permet de réinstaller les dépendances Python si l'environnement disparaît.

## Important : préparer la récupération pendant que tout fonctionne

Depuis la racine du projet, dans PowerShell, exécuter :

```powershell
.\.venv\Scripts\python.exe --version
.\.venv\Scripts\python.exe -m pip freeze > .\requirements.txt
```

La première commande affiche la version de Python utilisée. La seconde enregistre dans `requirements.txt` les paquets installés dans l'environnement actuel, avec leurs versions. Vérifier que le fichier a bien été créé à la racine, puis **le conserver sur la clé USB avec le code source**.

Cette opération doit être faite avant une panne de l'environnement. Si les dépendances changent ensuite, régénérer `requirements.txt` depuis l'environnement fonctionnel.

## Recréer l'environnement Python après une panne

Ces commandes sont à exécuter depuis la racine du projet dans PowerShell. Elles recréent `.venv` et y réinstallent les dépendances listées dans `requirements.txt`.

1. Vérifier que Python est installé :

   ```powershell
   py --version
   py -0p
   ```

   Si Python n'est plus installé, le réinstaller d'abord. Utiliser de préférence la même version majeure/mineure que celle affichée dans la section précédente.

2. Si l'ancien environnement `.venv` existe encore mais est endommagé, le supprimer. Cette commande efface uniquement l'environnement Python du projet :

   ```powershell
   Remove-Item -Recurse -Force .\.venv
   ```

   Si `.venv` n'existe déjà plus, passer à l'étape suivante.

3. Recréer l'environnement :

   ```powershell
   py -m venv .venv
   ```

4. Mettre `pip` à jour et installer les dépendances :

   ```powershell
   .\.venv\Scripts\python.exe -m pip install --upgrade pip
   .\.venv\Scripts\python.exe -m pip install -r .\requirements.txt
   ```

5. Vérifier la syntaxe des fichiers principaux :

   ```powershell
   .\.venv\Scripts\python.exe -m py_compile .\src\main.py .\src\webdav.py .\src\vault.py
   ```

6. Lancer Nuage Explorer :

   ```powershell
   .\.venv\Scripts\python.exe .\src\main.py
   ```

> Si `requirements.txt` est absent ou vide, ne pas supposer que `PySide6` et `httpx` suffisent : le module `vault.py` peut avoir ses propres dépendances. Reconstituer le fichier depuis une copie fonctionnelle du projet ou réinstaller les paquets réellement nécessaires.

## Lancement habituel

Depuis la racine du projet, dans PowerShell :

```powershell
.\.venv\Scripts\python.exe .\src\main.py
```

Vérification de syntaxe :

```powershell
.\.venv\Scripts\python.exe -m py_compile .\src\main.py .\src\webdav.py .\src\vault.py
```

Au premier lancement, l'application propose de créer un coffre protégé par un mot de passe maître. Les informations de connexion sont conservées dans ce coffre chiffré.

## Fonctions

- Connexion à NUAGE par WebDAV HTTPS.
- Navigation dans les dossiers, création de dossiers et import de fichiers.
- Menu au clic droit : ouvrir, couper, copier, déplacer, copier vers, renommer, coller, supprimer et télécharger.
- Aperçu des images et des PDF dans une fenêtre intégrée.
- Aperçu des documents LibreOffice par conversion temporaire en PDF.

## Aperçus et dossier temporaire

Les fichiers utilisés pour les aperçus sont placés dans le dossier `temp` à la racine du projet, par exemple sur la clé USB :

```text
Nuage_Explorer/
├── src/
├── temp/
└── README.md
```

- Le dossier `temp` est vidé au démarrage de l'application.
- Les fichiers d'aperçu sont normalement supprimés lorsque la fenêtre d'aperçu se ferme.
- Les documents bureautiques nécessitent LibreOffice installé sur le PC et autorisé à s'exécuter.
- Ne pas utiliser `temp` pour stocker des fichiers personnels : son contenu est supprimé au lancement.
- Si le nettoyage échoue, certains fichiers peuvent rester temporairement dans ce dossier ; fermer l'application et vérifier les fichiers avant de les supprimer manuellement.

## Compiler la version portable pour Windows

La version portable est construite avec **PyInstaller**. Il faut effectuer cette compilation sur Windows : PyInstaller produit une application pour le système sur lequel il tourne. Le mode `--onedir` est volontairement utilisé ; il crée un dossier autonome contenant l'exécutable et ses bibliothèques Qt.

### Prérequis

- Python installé sur le PC de compilation ;
- le code source du projet, notamment `src/main.py`, `src/webdav.py` et `src/vault.py` ;
- `requirements.txt` à jour ;
- une clé USB disposant d'assez d'espace libre.

### Compiler depuis la clé USB

Dans l'exemple ci-dessous, le projet source se trouve dans `F:\Nuage_Explorer`. Adapter la lettre du lecteur et le chemin si nécessaire. Ouvrir PowerShell et exécuter les commandes depuis la racine du projet :

```powershell
cd F:\Nuage_Explorer

# Recréer l'environnement si nécessaire (voir la section précédente).
# Installer les dépendances de l'application.
.\.venv\Scripts\python.exe -m pip install -r .\requirements.txt

# Installer l'outil de compilation.
.\.venv\Scripts\python.exe -m pip install --upgrade pyinstaller

# Vérifier la syntaxe avant la compilation.
.\.venv\Scripts\python.exe -m py_compile .\src\main.py .\src\webdav.py .\src\vault.py

# Construire l'application portable.
.\.venv\Scripts\python.exe -m PyInstaller `
    --noconfirm `
    --clean `
    --windowed `
    --onedir `
    --name NuageExplorer `
    --hidden-import PySide6.QtPdf `
    --hidden-import PySide6.QtPdfWidgets `
    .\src\main.py
```

À la fin, l'application compilée se trouve dans :

```text
F:\Nuage_Explorer\dist\NuageExplorer\
├── NuageExplorer.exe
└── _internal\
    └── bibliothèques Python, composants Qt et dépendances
```

**Ne copiez pas uniquement `NuageExplorer.exe`** : l'exécutable a besoin des fichiers du dossier `_internal`. Pour distribuer l'application, copier le dossier `dist\NuageExplorer` en entier sur la clé USB ou à l'emplacement souhaité. On peut lancer `NuageExplorer.exe` directement depuis ce dossier.

Le dossier `build` et le fichier `NuageExplorer.spec` sont des produits de compilation ; ils ne sont pas nécessaires pour lancer l'application. Ils peuvent être recréés lors d'une prochaine compilation.

### Fichiers temporaires et aperçus

En mode compilé, Nuage Explorer utilise le dossier `temp` situé à côté de `NuageExplorer.exe`. Il est créé automatiquement s'il n'existe pas, vidé au démarrage, et les aperçus sont normalement supprimés quand leur fenêtre se ferme. Ne pas y conserver de fichiers personnels.

### Limites à connaître

- PyInstaller embarque Python et les dépendances détectées, mais **n'embarque pas LibreOffice**. Pour prévisualiser les documents bureautiques via conversion en PDF, LibreOffice doit être installé et autorisé sur le PC utilisé.
- Il est conseillé de tester la version compilée après chaque modification du code, notamment l'ouverture d'images, de PDF et de documents LibreOffice, ainsi que les opérations WebDAV.
- La compilation portable ne contourne pas les règles informatiques du lycée : Windows Defender, les stratégies de sécurité ou le filtrage réseau peuvent bloquer l'exécutable ou la connexion WebDAV.
- **Vérifier l'emplacement du coffre chiffré avant de déplacer l'application vers une autre clé ou un autre PC.** Il est déterminé par `get_vault_path()` dans `src/vault.py` ; ne pas supposer que le coffre se trouve automatiquement à côté de l'exécutable.

## À savoir

- Une connexion HTTPS valide et des identifiants WebDAV sont nécessaires.
- La copie, le déplacement et le renommage dépendent des opérations autorisées par le serveur NUAGE.
- Avant d'utiliser les suppressions ou les déplacements sur des documents importants, effectuer un essai avec des fichiers sans importance.
- Au lycée, vérifier que les règles de sécurité du poste autorisent l'exécution de Python, de l'application et, si nécessaire, de LibreOffice.
- Le nettoyage de `temp` efface tout ce qu'il contient au lancement. Ne pas y placer d'autres données.
