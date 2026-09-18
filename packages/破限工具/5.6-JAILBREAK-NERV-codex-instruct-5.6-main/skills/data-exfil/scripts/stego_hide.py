# -*- coding: utf-8 -*-
"""Steganography -- LSB hiding in PNG/WAV, metadata embedding.

Author: zxwn
"""
import struct, os


def lsb_hide_png(png_path: str, data: bytes, output_path: str) -> int:
    """Hide data in PNG using LSB of pixel bytes (after IDAT chunk).

    Returns bytes hidden.
    """
    with open(png_path, "rb") as f:
        png = bytearray(f.read())

    # Find IDAT chunk
    idat_start = png.find(b"IDAT")
    if idat_start == -1:
        return 0

    # Pixel data starts after IDAT header (4 bytes length + 4 bytes "IDAT")
    pixel_start = idat_start + 8
    pixel_data = png[pixel_start:]

    # Calculate capacity (1 bit per byte)
    capacity = len(pixel_data) // 8
    if len(data) * 8 > len(pixel_data):
        raise ValueError("Data too large: {} bytes, capacity: {} bits".format(len(data), capacity))

    # Encode length prefix (4 bytes)
    length_bytes = struct.pack(">I", len(data))
    bits = "".join("{:08b}".format(b) for b in length_bytes + data)

    for i, bit in enumerate(bits):
        if bit == "1":
            png[pixel_start + i] |= 1
        else:
            png[pixel_start + i] &= 0xFE

    with open(output_path, "wb") as f:
        f.write(png)
    return len(data)


def lsb_extract_png(png_path: str) -> bytes:
    """Extract LSB-hidden data from PNG."""
    with open(png_path, "rb") as f:
        png = f.read()

    idat_start = png.find(b"IDAT")
    if idat_start == -1:
        return b""

    pixel_start = idat_start + 8
    pixel_data = png[pixel_start:]

    # Read length prefix (32 bits = 4 bytes)
    bits = ""
    for i in range(32):
        bits += str(pixel_data[i] & 1)
    data_len = int(bits, 2)

    # Read data
    bits = ""
    for i in range(32, 32 + data_len * 8):
        if i >= len(pixel_data):
            break
        bits += str(pixel_data[i] & 1)

    return int(bits, 2).to_bytes(data_len, "big")


def lsb_hide_wav(wav_path: str, data: bytes, output_path: str) -> int:
    """Hide data in WAV using LSB of sample bytes."""
    with open(wav_path, "rb") as f:
        wav = bytearray(f.read())

    # Find "data" chunk (sample data)
    data_start = wav.find(b"data")
    if data_start == -1:
        return 0

    # Sample data starts after "data" + 4-byte size
    sample_start = data_start + 8
    samples = wav[sample_start:]

    length_bytes = struct.pack(">I", len(data))
    bits = "".join("{:08b}".format(b) for b in length_bytes + data)

    if len(bits) > len(samples):
        raise ValueError("WAV too small for {} bytes".format(len(data)))

    for i, bit in enumerate(bits):
        if bit == "1":
            wav[sample_start + i] |= 1
        else:
            wav[sample_start + i] &= 0xFE

    with open(output_path, "wb") as f:
        f.write(wav)
    return len(data)


def embed_in_exif(jpg_path: str, data: bytes, output_path: str) -> int:
    """Embed data in JPEG EXIF comment field."""
    with open(jpg_path, "rb") as f:
        jpg = bytearray(f.read())

    # Find EXIF APP1 marker
    app1_pos = jpg.find(b"Exif\x00\x00")
    if app1_pos == -1:
        return 0

    encoded = data.hex()
    marker = b"COMMENT:" + encoded.encode() + b";"
    # Insert after EXIF header
    insert_pos = app1_pos + 8
    jpg[insert_pos:insert_pos] = marker

    with open(output_path, "wb") as f:
        f.write(jpg)
    return len(data)


def text_to_binary_noise(text: str, noise_ratio: float = 0.7) -> str:
    """Embed text as random-looking binary string with noise.

    Output looks like random hex/binary data.
    """
    encoded = text.encode().hex()
    noise_bytes = os.urandom(int(len(encoded) * noise_ratio))
    result = []
    for i, ch in enumerate(encoded):
        result.append(ch)
        if i < len(noise_bytes):
            result.append("{:02x}".format(noise_bytes[i]))
    return "".join(result)


def binary_noise_to_text(noise: str) -> str:
    """Extract text from binary_noise output (every other hex pair)."""
    pairs = [noise[i:i+2] for i in range(0, len(noise), 2)]
    extracted = "".join(pairs[::2])
    return bytes.fromhex(extracted).decode("utf-8", errors="replace")


if __name__ == "__main__":
    print("[stego_hide] Loaded.")
    print("  lsb_hide_png(in.png, data, out.png)")
    print("  lsb_hide_wav(in.wav, data, out.wav)")
    print("  embed_in_exif(in.jpg, data, out.jpg)")
