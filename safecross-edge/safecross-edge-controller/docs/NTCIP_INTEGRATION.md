# NTCIP 1202 Signal Controller Integration Notes

## Overview

The SafeCross edge controller communicates with the traffic signal controller using SNMP v2c per the NTCIP 1202 v02 standard.

## Key OIDs

See `src/ntcip_client.py` for the full OID reference.

## Vendor Compatibility

- **Econolite Cobalt**: Standard NTCIP 1202 OIDs, no overrides needed.
- **McCain**: May require OID adjustments — to be determined during field testing.

## Testing

Use an SNMP simulator (e.g., `snmpsim`) for local development and integration testing.
