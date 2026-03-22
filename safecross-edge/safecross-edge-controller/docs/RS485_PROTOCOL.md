# RS-485 Protocol Specification

## Overview

Binary frame protocol for communication between the NFC reader (Layer 1) and the edge controller over RS-485.

## Frame Format

See `src/message_protocol.py` for the full frame format and message type definitions.

## Physical Layer

- **Baud rate**: 115200 (configurable)
- **Data bits**: 8
- **Parity**: None
- **Stop bits**: 1
- **Flow control**: None
