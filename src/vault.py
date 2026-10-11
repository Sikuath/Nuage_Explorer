import json
import os
import sys
import tempfile
from pathlib import Path

from argon2.low_level import Type, hash_secret_raw
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


MAGIC = b"NUAGEVAULT\x01"
SALT_SIZE = 16
NONCE_SIZE = 12
KEY_SIZE = 32

ARGON_TIME_COST = 3
ARGON_MEMORY_COST = 65536  # 64 Mio
ARGON_PARALLELISM = 2


class VaultError(Exception):
    """Erreur liée au coffre."""


class VaultExistsError(VaultError):
    """Un coffre existe déjà."""


class InvalidVaultError(VaultError):
    """Le coffre est invalide, endommagé ou le mot de passe est incorrect."""


def get_vault_path() -> Path:
    """Chemin portable, relatif au dossier de l'application."""
    if getattr(sys, "frozen", False):
        base = Path(sys.executable).resolve().parent
    else:
        base = Path(__file__).resolve().parent.parent

    return base / "data" / "nuage.vault"


def _derive_key(password: str, salt: bytes) -> bytes:
    if not isinstance(password, str) or not password:
        raise VaultError("Le mot de passe maître ne peut pas être vide.")

    return hash_secret_raw(
        secret=password.encode("utf-8"),
        salt=salt,
        time_cost=ARGON_TIME_COST,
        memory_cost=ARGON_MEMORY_COST,
        parallelism=ARGON_PARALLELISM,
        hash_len=KEY_SIZE,
        type=Type.ID,
    )


def _validate_data(data: dict) -> None:
    if not isinstance(data, dict) or data.get("version") != 1:
        raise VaultError("Structure de coffre invalide.")

    if not isinstance(data.get("profiles"), list):
        raise VaultError("La liste des profils est invalide.")


def _write_encrypted(path: Path, password: str, data: dict) -> None:
    _validate_data(data)

    salt = os.urandom(SALT_SIZE)
    nonce = os.urandom(NONCE_SIZE)
    key = _derive_key(password, salt)

    plaintext = json.dumps(
        data, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")

    associated_data = MAGIC + salt
    ciphertext = AESGCM(key).encrypt(nonce, plaintext, associated_data)
    content = MAGIC + salt + nonce + ciphertext

    path.parent.mkdir(parents=True, exist_ok=True)

    # Écriture temporaire puis remplacement atomique du coffre.
    fd, temporary_name = tempfile.mkstemp(
        prefix=".nuage-vault-", suffix=".tmp", dir=path.parent
    )
    temporary_path = Path(temporary_name)

    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())

        os.replace(temporary_path, path)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


def create_vault(path: Path, password: str) -> dict:
    """Crée un coffre vide sans écraser un coffre existant."""
    path = Path(path)

    if path.exists():
        raise VaultExistsError("Un coffre existe déjà à cet emplacement.")

    data = {"version": 1, "profiles": []}
    _write_encrypted(path, password, data)
    return data


def unlock_vault(path: Path, password: str) -> dict:
    """Déchiffre et vérifie un coffre existant."""
    path = Path(path)

    try:
        content = path.read_bytes()
    except OSError as exc:
        raise InvalidVaultError("Impossible de lire le coffre.") from exc

    header_size = len(MAGIC) + SALT_SIZE + NONCE_SIZE

    if len(content) <= header_size or not content.startswith(MAGIC):
        raise InvalidVaultError("Format de coffre invalide.")

    offset = len(MAGIC)
    salt = content[offset:offset + SALT_SIZE]
    offset += SALT_SIZE

    nonce = content[offset:offset + NONCE_SIZE]
    offset += NONCE_SIZE

    ciphertext = content[offset:]

    try:
        key = _derive_key(password, salt)
        plaintext = AESGCM(key).decrypt(
            nonce, ciphertext, MAGIC + salt
        )
        data = json.loads(plaintext.decode("utf-8"))
        _validate_data(data)
        return data
    except (InvalidTag, ValueError, UnicodeDecodeError, json.JSONDecodeError,
            VaultError) as exc:
        raise InvalidVaultError(
            "Mot de passe incorrect ou coffre endommagé."
        ) from exc



def save_vault(path: Path, password: str, data: dict) -> None:
    """Enregistre les données dans le coffre après validation."""
    path = Path(path)

    if not path.is_file():
        raise InvalidVaultError("Le coffre n'existe pas.")

    # Vérifie le mot de passe et l'intégrité du coffre existant.
    current_data = unlock_vault(path, password)

    _validate_data(data)

    # Évite de remplacer le coffre par une structure d'une autre version.
    if data.get("version") != current_data.get("version"):
        raise InvalidVaultError(
            "La version des données ne correspond pas au coffre."
        )

    _write_encrypted(path, password, data)
