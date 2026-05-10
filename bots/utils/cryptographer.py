import base64

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from bots.config.consts import SECRET_KEY


def encrypt_platform_user_id(platform_user_id: int | str) -> str:
    normalized_value = str(platform_user_id).strip()

    if not normalized_value:
        raise ValueError("platform_user_id не может быть пустым")

    data = normalized_value.zfill(16).encode()

    cipher = Cipher(
        algorithms.AES(SECRET_KEY),
        modes.ECB(),
        backend=default_backend(),
    )
    encryptor = cipher.encryptor()
    encrypted_data = encryptor.update(data) + encryptor.finalize()

    return base64.urlsafe_b64encode(encrypted_data).decode()


def decrypt_platform_user_id(encrypted_platform_user_id: str) -> int:
    cipher = Cipher(
        algorithms.AES(SECRET_KEY),
        modes.ECB(),
        backend=default_backend(),
    )
    decryptor = cipher.decryptor()
    decrypted_data = (
        decryptor.update(base64.urlsafe_b64decode(encrypted_platform_user_id))
        + decryptor.finalize()
    )

    return int(decrypted_data.decode().lstrip("0"))


def encrypt_telegram_id(telegram_id: int) -> str:
    return encrypt_platform_user_id(telegram_id)


def decrypt_telegram_id(encrypted_telegram_id: str) -> int:
    return decrypt_platform_user_id(encrypted_telegram_id)


def encrypt_vk_id(vk_id: int) -> str:
    return encrypt_platform_user_id(vk_id)


def decrypt_vk_id(encrypted_vk_id: str) -> int:
    return decrypt_platform_user_id(encrypted_vk_id)