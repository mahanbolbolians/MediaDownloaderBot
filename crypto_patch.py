"""
Native C crypto acceleration for Hydrogram on Windows without MSVC build tools.
Injects cryptg (C IGE AES) and pycryptodome (C CTR AES) as a drop-in tgcrypto replacement.
"""
import sys
import types

try:
    import cryptg
    from Crypto.Cipher import AES

    mod = types.ModuleType("tgcrypto")
    mod.ige256_encrypt = lambda data, key, iv: cryptg.encrypt_ige(data, key, iv)
    mod.ige256_decrypt = lambda data, key, iv: cryptg.decrypt_ige(data, key, iv)

    def ctr256_encrypt(data: bytes, key: bytes, iv: bytearray, state=None) -> bytes:
        cipher = AES.new(key, AES.MODE_CTR, initial_value=bytes(iv[:16]), nonce=b"")
        return cipher.encrypt(data)

    def ctr256_decrypt(data: bytes, key: bytes, iv: bytearray, state=None) -> bytes:
        cipher = AES.new(key, AES.MODE_CTR, initial_value=bytes(iv[:16]), nonce=b"")
        return cipher.decrypt(data)

    def xor(a: bytes, b: bytes) -> bytes:
        return int.to_bytes(
            int.from_bytes(a, "big") ^ int.from_bytes(b, "big"),
            len(a),
            "big",
        )

    mod.ctr256_encrypt = ctr256_encrypt
    mod.ctr256_decrypt = ctr256_decrypt
    mod.xor = xor

    sys.modules["tgcrypto"] = mod
except Exception:
    pass
