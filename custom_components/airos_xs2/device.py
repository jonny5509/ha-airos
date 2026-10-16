"""Helpers for normalizing legacy airOS device metadata."""


def normalize_device_metadata(raw_name):
    """Split a legacy UBNT metadata string into readable device fields."""
    if not isinstance(raw_name, str) or not raw_name.startswith("UBNT,"):
        return {"name": raw_name or "Ubiquiti AirOS"}

    metadata = {}
    for item in raw_name.split(",")[1:]:
        key, separator, value = item.partition("=")
        if separator and key and value:
            metadata[key.strip()] = value.strip()

    return {
        "name": "Ubiquiti AirOS",
        "device_id": metadata.get("deviceId"),
        "firmware_version": metadata.get("firmwareVersion"),
        "platform": metadata.get("platform"),
        "device_ip": metadata.get("deviceIp"),
    }
