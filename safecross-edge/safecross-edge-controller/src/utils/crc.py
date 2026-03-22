"""CRC-16/MODBUS implementation.

Computes CRC-16 using the MODBUS variant:
  - Polynomial: 0xA001 (bit-reflected form of 0x8005)
  - Initial value: 0xFFFF
  - No final XOR

Known test vectors:
  crc16_modbus(b"")             -> 0xFFFF
  crc16_modbus(b"123456789")    -> 0x4B37
  crc16_modbus(b"\\x01\\x02\\x03\\x04") -> 0x2BA1
"""

from __future__ import annotations


def crc16_modbus(data: bytes) -> int:
    """Compute CRC-16/MODBUS over *data*.

    Algorithm: for each byte, XOR into the low byte of the CRC register,
    then shift right 8 times, XORing with 0xA001 whenever the LSB is 1.

    Args:
        data: Bytes to checksum.

    Returns:
        16-bit unsigned CRC value.
    """
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x0001:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
    return crc
