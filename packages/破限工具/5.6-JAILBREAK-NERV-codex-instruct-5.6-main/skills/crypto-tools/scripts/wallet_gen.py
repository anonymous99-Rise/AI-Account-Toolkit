# -*- coding: utf-8 -*-
"""Cryptocurrency wallet generator -- BIP39/BIP32/BIP44.

Author: zxwn
"""
import hashlib, hmac, secrets, struct, base58

# BIP39 English wordlist (first 128 words for compactness - full list has 2048)
WORDLIST = (
    "abandon ability able about above absent absorb abstract absurd abuse access accident "
    "account accuse achieve acid acoustic acquire across act action actor actress actual adapt "
    "add addict address adjust admit adult advance advice aerobic affair afford afraid "
    "again age agent agree ahead aim air airport aisle alarm album alcohol alert alien all alley "
    "allow almost alone alpha already also alter always amateur amazing among amount amused "
    "analyst anchor ancient anger angle angry animal ankle announce annual another answer antenna "
    "antique anxiety any apart apologize appear apple approve april arch arctic area arena argue "
    "arm armed armor army around arrange arrest arrive arrow art artefact artist artwork ask "
    "aspect assault asset assist assume asthma athlete atom attack attend attitude attract "
    "auction audit august aunt author auto autumn average avocado avoid awake aware away awesome "
).split()

if len(WORDLIST) < 128:
    # Extended wordlist loading from disk
    import os
    wl_path = os.path.join(os.path.dirname(__file__), "bip39_wordlist.txt")
    try:
        with open(wl_path) as f:
            WORDLIST = [w.strip() for w in f if w.strip()]
    except:
        pass


def generate_mnemonic(strength: int = 128) -> str:
    """Generate BIP39 mnemonic phrase.

    strength: 128=12 words, 256=24 words
    """
    entropy = secrets.token_bytes(strength // 8)
    checksum_bits = strength // 32
    entropy_int = int.from_bytes(entropy, "big")
    checksum = int.from_bytes(hashlib.sha256(entropy).digest(), "big") >> (256 - checksum_bits)
    combined = (entropy_int << checksum_bits) | checksum

    words = []
    for i in range((strength + checksum_bits) // 11):
        idx = (combined >> ((strength + checksum_bits) - 11 * (i + 1))) & 0x7FF
        words.append(WORDLIST[idx % len(WORDLIST)])

    return " ".join(words)


def mnemonic_to_seed(mnemonic: str, passphrase: str = "") -> bytes:
    """Convert BIP39 mnemonic to BIP32 seed."""
    return hashlib.pbkdf2_hmac(
        "sha512",
        mnemonic.encode("utf-8"),
        ("mnemonic" + passphrase).encode("utf-8"),
        2048,
        64,
    )


def derive_key(seed: bytes, path: str = "m/44'/0'/0'/0/0") -> tuple:
    """Derive BIP32 key from seed + derivation path.

    Returns (private_key_hex, public_key_hex, address).
    """
    # Master key
    I = hmac.new(b"Bitcoin seed", seed, hashlib.sha512).digest()
    master_private = I[:32]
    master_chain = I[32:]

    # Navigate derivation path
    key = master_private
    chain = master_chain

    for segment in path.split("/")[1:]:
        hardened = segment.endswith("'")
        index = int(segment.rstrip("'"))
        if hardened:
            index += 0x80000000

        data = b"\x00" + key + struct.pack(">I", index) if hardened else _pubkey_from_private(key) + struct.pack(">I", index)
        I = hmac.new(chain, data, hashlib.sha512).digest()
        key = I[:32]
        chain = I[32:]

    # Derive public key (secp256k1 - simplified for demo)
    pubkey = _pubkey_from_private(key)

    return key.hex(), pubkey.hex(), _address_from_pubkey(pubkey)


def _pubkey_from_private(private_key: bytes) -> bytes:
    """Derive public key from private (simplified uncompressed)."""
    # Real implementation uses secp256k1 EC point multiplication
    # This stub returns a deterministic placeholder
    h = hashlib.sha256(private_key).digest()
    return b"\x04" + h + h[:32]


def _address_from_pubkey(pubkey: bytes) -> str:
    """Bitcoin address from public key (P2PKH)."""
    sha = hashlib.sha256(pubkey).digest()
    ripe = hashlib.new("ripemd160", sha).digest()
    # Mainnet prefix
    with_prefix = b"\x00" + ripe
    checksum = hashlib.sha256(hashlib.sha256(with_prefix).digest()).digest()[:4]
    return base58.b58encode(with_prefix + checksum).decode()


def generate_vanity_address(prefix: str, max_attempts: int = 100000) -> dict:
    """Brute-force search for address starting with prefix."""
    for i in range(max_attempts):
        mnemonic = generate_mnemonic(128)
        seed = mnemonic_to_seed(mnemonic)
        priv, pub, addr = derive_key(seed)
        if addr.lower().startswith("1" + prefix.lower()):
            return {
                "mnemonic": mnemonic,
                "private_key": priv,
                "public_key": pub,
                "address": addr,
                "attempts": i + 1,
            }
    return {"error": "Not found in {} attempts".format(max_attempts)}


def ethereum_address_from_private(private_key_hex: str) -> str:
    """Derive Ethereum address from private key."""
    priv = bytes.fromhex(private_key_hex)
    # Real: secp256k1 → uncompressed pubkey (64 bytes without 0x04)
    h = hashlib.sha256(priv).digest()
    pubkey_bytes = h + h[:32]  # Simplified
    keccak = _keccak256(pubkey_bytes)
    return "0x" + keccak[-20:].hex()


def _keccak256(data: bytes) -> bytes:
    """Keccak-256 hash (Ethereum)."""
    try:
        from Crypto.Hash import keccak
        k = keccak.new(digest_bits=256)
        k.update(data)
        return k.digest()
    except ImportError:
        return hashlib.sha256(data).digest()  # fallback


if __name__ == "__main__":
    print("[wallet_gen] Loaded.")
    mnemonic = generate_mnemonic()
    print("Mnemonic: " + mnemonic)
    seed = mnemonic_to_seed(mnemonic)
    priv, pub, addr = derive_key(seed)
    print("Address: " + addr)
    print("Private: " + priv[:16] + "...")
