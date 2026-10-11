import getpass
import tempfile
from pathlib import Path

from vault import (
    create_vault,
    unlock_vault,
    save_vault,
    VaultExistsError,
    InvalidVaultError,
)

with tempfile.TemporaryDirectory(prefix="nuage-vault-test-") as folder:
    path = Path(folder) / "test.vault"

    password = getpass.getpass("Choisis un mot de passe maître temporaire : ")
    confirmation = getpass.getpass("Confirme ce mot de passe : ")

    if not password or password != confirmation:
        raise SystemExit("Test annulé : mot de passe vide ou différent.")

    create_vault(path, password)
    print("1. Création du coffre : OK")

    data = unlock_vault(path, password)
    assert data == {"version": 1, "profiles": []}
    print("2. Déverrouillage : OK")

    try:
        unlock_vault(path, "mot-de-passe-incorrect")
    except InvalidVaultError:
        print("3. Refus du mauvais mot de passe : OK")
    else:
        raise AssertionError("Un mauvais mot de passe a été accepté.")

    try:
        create_vault(path, password)
    except VaultExistsError:
        print("4. Protection contre l'écrasement : OK")
    else:
        raise AssertionError("Le coffre existant a été écrasé.")

    data["profiles"].append({
        "name": "Profil de test",
        "url": "https://example.invalid/remote.php/dav/",
        "username": "test",
    })
    save_vault(path, password, data)

    restored = unlock_vault(path, password)
    assert restored["profiles"][0]["name"] == "Profil de test"
    print("5. Enregistrement et relecture : OK")

    print("6. Taille du fichier chiffré :", path.stat().st_size, "octets")
    print("Tous les tests ont réussi.")
