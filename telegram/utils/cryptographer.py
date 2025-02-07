from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
import base64

from telegram.config.consts import SECRET_KEY


def encrypt_telegram_id(telegram_id: int) -> str:
    """
    Детерминированно шифрует telegram_id, чтобы один и тот же ID всегда давал одинаковый результат.
    """
    data = str(telegram_id).zfill(16).encode()  # Делаем 16-байтовую строку
    cipher = Cipher(algorithms.AES(SECRET_KEY), modes.ECB(), backend=default_backend())
    encryptor = cipher.encryptor()
    encrypted_data = encryptor.update(data) + encryptor.finalize()

    return base64.urlsafe_b64encode(encrypted_data).decode()


def decrypt_telegram_id(encrypted_telegram_id: str) -> int:
    """
    Дешифрует зашифрованный telegram_id обратно в int.
    """
    cipher = Cipher(algorithms.AES(SECRET_KEY), modes.ECB(), backend=default_backend())
    decryptor = cipher.decryptor()
    decrypted_data = decryptor.update(base64.urlsafe_b64decode(encrypted_telegram_id)) + decryptor.finalize()

    return int(decrypted_data.decode().lstrip("0"))
