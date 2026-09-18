# -*- coding: utf-8 -*-
"""Bluetooth/BLE attack tools -- scan, enumerate, GATT interaction.

Requires: bleak (pip install bleak), pybluez (Linux)
Author: zxwn
"""
import asyncio
from typing import Optional


async def ble_scan(duration: float = 10.0) -> list:
    """Scan for BLE devices. Returns list of {name, address, rssi}."""
    try:
        from bleak import BleakScanner
    except ImportError:
        return [{"error": "pip install bleak"}]

    devices = {}

    def callback(device, advertisement_data):
        devices[device.address] = {
            "name": device.name or advertisement_data.local_name or "Unknown",
            "address": device.address,
            "rssi": device.rssi if hasattr(device, 'rssi') else advertisement_data.rssi,
            "tx_power": getattr(advertisement_data, 'tx_power', None),
        }

    scanner = BleakScanner(callback)
    await scanner.start()
    await asyncio.sleep(duration)
    await scanner.stop()

    return list(devices.values())


async def ble_services(address: str) -> list:
    """Enumerate GATT services of BLE device."""
    try:
        from bleak import BleakClient
    except ImportError:
        return [{"error": "pip install bleak"}]

    services_list = []

    async def _enum():
        async with BleakClient(address, timeout=10.0) as client:
            for service in client.services:
                svc = {
                    "uuid": service.uuid,
                    "description": service.description,
                    "characteristics": [],
                }
                for char in service.characteristics:
                    svc["characteristics"].append({
                        "uuid": char.uuid,
                        "properties": char.properties,
                        "description": char.description,
                    })
                services_list.append(svc)

    await _enum()
    return services_list


async def ble_read_char(address: str, char_uuid: str) -> Optional[bytes]:
    """Read BLE characteristic value."""
    try:
        from bleak import BleakClient
    except ImportError:
        return None

    value = None

    async def _read():
        nonlocal value
        async with BleakClient(address, timeout=10.0) as client:
            value = await client.read_gatt_char(char_uuid)

    await _read()
    return value


async def ble_write_char(address: str, char_uuid: str, data: bytes) -> bool:
    """Write to BLE characteristic."""
    try:
        from bleak import BleakClient
    except ImportError:
        return False

    try:
        async with BleakClient(address, timeout=10.0) as client:
            await client.write_gatt_char(char_uuid, data)
        return True
    except:
        return False


def classic_bluetooth_scan(duration: int = 10) -> list:
    """Scan for classic Bluetooth devices (requires pybluez + Linux)."""
    try:
        import bluetooth
    except ImportError:
        return [{"error": "pip install pybluez (Linux only)"}]

    devices = bluetooth.discover_devices(duration=duration, lookup_names=True, lookup_class=True)
    return [
        {"address": addr, "name": name, "device_class": cls}
        for addr, name, cls in devices
    ]


# Common BLE UUIDs
BLE_UUIDS = {
    "device_name": "00002a00-0000-1000-8000-00805f9b34fb",
    "appearance": "00002a01-0000-1000-8000-00805f9b34fb",
    "battery_level": "00002a19-0000-1000-8000-00805f9b34fb",
    "firmware_revision": "00002a26-0000-1000-8000-00805f9b34fb",
    "hardware_revision": "00002a27-0000-1000-8000-00805f9b34fb",
    "software_revision": "00002a28-0000-1000-8000-00805f9b34fb",
    "manufacturer_name": "00002a29-0000-1000-8000-00805f9b34fb",
}


if __name__ == "__main__":
    print("[bluetooth_tools] Loaded.")

    async def main():
        print("Scanning BLE devices...")
        devices = await ble_scan(5)
        for d in devices:
            print("  {} ({}) RSSI: {}".format(d.get("name", "?"), d["address"], d.get("rssi", "?")))

    try:
        asyncio.run(main())
    except:
        print("  (BLE scan requires actual hardware + bleak)")
