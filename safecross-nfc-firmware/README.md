# SafeCross NFC Reader Firmware

Bare-metal ARM Cortex-M4 firmware for the SafeCross NFC reader module. Reads Bay Area Clipper transit cards (NFC/MIFARE DESFire) at pedestrian crossings, classifies the card type (Senior, Disabled, or Standard), provides visual/audio feedback, and sends classification data to a downstream edge controller over RS-485.

## Hardware

- **MCU:** STM32F407VGT6 (ARM Cortex-M4, 168 MHz)
- **NFC:** NXP PN5180 (SPI1)
- **Comms:** RS-485 via MAX485 (USART2, 115200 baud)
- **Feedback:** WS2812B 8-LED ring (TIM4/DMA) + piezo buzzer (TIM3 PWM)

## Pin Mapping

| Signal         | Pin  | Mode/AF         | Notes                          |
|----------------|------|-----------------|--------------------------------|
| SPI1 SCK       | PA5  | AF5             | PN5180 clock                   |
| SPI1 MISO      | PA6  | AF5             | PN5180 data in                 |
| SPI1 MOSI      | PA7  | AF5             | PN5180 data out                |
| PN5180 CS      | PB0  | GPIO out        | Active low                     |
| PN5180 IRQ     | PA4  | EXTI4 input     | Falling edge                   |
| PN5180 BUSY    | PC0  | GPIO input      | Moved from PA5 (SPI conflict)  |
| PN5180 RST     | PC1  | GPIO out        | Moved from PA6 (SPI conflict)  |
| USART2 TX      | PA2  | AF7             | RS-485 transmit                |
| USART2 RX      | PA3  | AF7             | RS-485 receive                 |
| RS-485 DE/RE   | PB1  | GPIO out        | Direction control              |
| WS2812B Data   | PB6  | AF2 (TIM4_CH1)  | DMA-driven LED ring            |
| Buzzer         | PB5  | AF2 (TIM3_CH2)  | Moved from PB7 (TIM4 conflict) |

## Build

### Prerequisites

- `arm-none-eabi-gcc` toolchain
- STM32F4xx HAL Driver (set `HAL_DIR` in Makefile or environment)
- CMSIS headers (set `CMSIS_DIR` in Makefile or environment)
- `st-flash` for programming via ST-Link

### Compile Firmware

```bash
make firmware          # Release build
make firmware DEBUG=1  # Debug build with symbols
```

### Flash to Target

```bash
make flash
```

### Run Unit Tests (x86)

```bash
make test
```

Tests compile with native GCC and require no embedded toolchain or hardware.

## Classification Modes

Set `ACTIVE_CLASSIFY_MODE` in `src/classifier.h`:

| Mode | Value | Description |
|------|-------|-------------|
| `CLASSIFY_MODE_APPDIR` | 1 | Read DESFire application directory (production) |
| `CLASSIFY_MODE_UID`    | 2 | Match UID prefix table (fallback) |
| `CLASSIFY_MODE_ANY`    | 3 | Any DESFire card triggers (development/test) |

## RS-485 Protocol

Frame format: `[0xAA 0x55] [LENGTH] [MSG_TYPE] [PAYLOAD...] [CRC16-MODBUS]`

- **0x01** — Card tap event (reader → edge controller)
- **0x02** — Heartbeat every 10 seconds (reader → edge controller)
- **0x80** — Config update (edge controller → reader)
- **0x81** — Config ACK (reader → edge controller)

## Project Structure

```
├── Makefile              # Dual-target build (ARM firmware + x86 tests)
├── linker.ld             # STM32F407 memory layout
├── src/
│   ├── main.c            # Entry point, init, main loop
│   ├── nfc.h / nfc.c     # NFC polling and DESFire card reading
│   ├── classifier.h / .c # Card type classification logic
│   ├── rs485.h / rs485.c # RS-485 framing and communication
│   ├── feedback.h / .c   # LED ring + buzzer control
│   ├── watchdog.h / .c   # IWDG watchdog timer
│   └── pin_config.h      # Central pin definitions
├── drivers/
│   ├── pn5180.h / .c     # PN5180 NFC transceiver SPI driver
│   └── ws2812b.h / .c    # WS2812B LED driver (DMA)
└── tests/
    ├── test_classifier.c  # Classifier unit tests
    └── test_rs485_framing.c # RS-485 framing unit tests
```
