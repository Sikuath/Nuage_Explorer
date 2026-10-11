import getpass

from webdav import list_directory, WebDAVError

url = input(
    "Adresse WebDAV [Entrée pour utiliser l'adresse NUAGE connue] : "
).strip()

if not url:
    url = (
        "https://nuage12.apps.education.fr/"
        "remote.php/dav/files/johancanovas/"
    )

username = input("Identifiant WebDAV [johancanovas] : ").strip()
if not username:
    username = "johancanovas"

password = getpass.getpass("Mot de passe d'application : ")

try:
    entries = list_directory(url, username, password)
    print("\nConnexion WebDAV réussie.")
    print(f"Nombre d'éléments retournés : {len(entries)}")

    for entry in entries:
        kind = "[DOSSIER]" if entry["is_directory"] else "[FICHIER]"
        print(f'{kind} {entry["name"]}')

except WebDAVError as exc:
    print(f"\nÉchec de la connexion : {exc}")
