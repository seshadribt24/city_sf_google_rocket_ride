PILOT_INTERSECTIONS = [
    {"intersection_id": "INT-2025-0001", "device_id": "EDGE-0001", "name": "Market St & 5th St", "lat": 37.7837, "lng": -122.4073, "crossings": [{"crossing_id": "NS", "width_ft": 72, "base_walk_sec": 7, "max_extension_sec": 13}, {"crossing_id": "EW", "width_ft": 48, "base_walk_sec": 7, "max_extension_sec": 8}]},
    {"intersection_id": "INT-2025-0002", "device_id": "EDGE-0002", "name": "Geary Blvd & Masonic Ave", "lat": 37.7842, "lng": -122.4462, "crossings": [{"crossing_id": "NS", "width_ft": 80, "max_extension_sec": 13}, {"crossing_id": "EW", "width_ft": 60, "max_extension_sec": 10}]},
    {"intersection_id": "INT-2025-0003", "device_id": "EDGE-0003", "name": "Mission St & 16th St", "lat": 37.7650, "lng": -122.4194, "crossings": [{"crossing_id": "NS", "width_ft": 65, "max_extension_sec": 11}, {"crossing_id": "EW", "width_ft": 50, "max_extension_sec": 8}]},
    {"intersection_id": "INT-2025-0004", "device_id": "EDGE-0004", "name": "Van Ness Ave & Eddy St", "lat": 37.7836, "lng": -122.4213, "crossings": [{"crossing_id": "NS", "width_ft": 95, "max_extension_sec": 13}, {"crossing_id": "EW", "width_ft": 45, "max_extension_sec": 8}]},
    {"intersection_id": "INT-2025-0005", "device_id": "EDGE-0005", "name": "Stockton St & Clay St", "lat": 37.7934, "lng": -122.4082, "crossings": [{"crossing_id": "NS", "width_ft": 50, "max_extension_sec": 8}, {"crossing_id": "EW", "width_ft": 50, "max_extension_sec": 8}]},
    {"intersection_id": "INT-2025-0006", "device_id": "EDGE-0006", "name": "3rd St & Evans Ave", "lat": 37.7432, "lng": -122.3872, "crossings": [{"crossing_id": "NS", "width_ft": 70, "max_extension_sec": 12}, {"crossing_id": "EW", "width_ft": 55, "max_extension_sec": 9}]},
    {"intersection_id": "INT-2025-0007", "device_id": "EDGE-0007", "name": "Taraval St & 19th Ave", "lat": 37.7434, "lng": -122.4756, "crossings": [{"crossing_id": "NS", "width_ft": 90, "max_extension_sec": 13}, {"crossing_id": "EW", "width_ft": 45, "max_extension_sec": 7}]},
    {"intersection_id": "INT-2025-0008", "device_id": "EDGE-0008", "name": "Polk St & Turk St", "lat": 37.7824, "lng": -122.4186, "crossings": [{"crossing_id": "NS", "width_ft": 55, "max_extension_sec": 9}, {"crossing_id": "EW", "width_ft": 50, "max_extension_sec": 8}]},
    {"intersection_id": "INT-2025-0009", "device_id": "EDGE-0009", "name": "Ocean Ave & Geneva Ave", "lat": 37.7235, "lng": -122.4419, "crossings": [{"crossing_id": "NS", "width_ft": 75, "max_extension_sec": 12}, {"crossing_id": "EW", "width_ft": 60, "max_extension_sec": 10}]},
    {"intersection_id": "INT-2025-0010", "device_id": "EDGE-0010", "name": "Sutter St & Larkin St", "lat": 37.7876, "lng": -122.4182, "crossings": [{"crossing_id": "NS", "width_ft": 55, "max_extension_sec": 9}, {"crossing_id": "EW", "width_ft": 50, "max_extension_sec": 8}]},
]

# Quick lookup by intersection_id
INTERSECTIONS_BY_ID = {i["intersection_id"]: i for i in PILOT_INTERSECTIONS}
