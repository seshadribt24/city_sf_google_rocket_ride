# SafeCross NFC Reader Firmware — Claude Code Spec

## What you are building

Embedded C firmware for the SafeCross NFC reader module — a pole-mounted device that reads Bay Area Clipper transit cards (NFC/MIFARE DESFire) at pedestrian crossings, classifies the card type (Senior, Disabled, or other), provides user feedback (LED + buzzer), and sends the classification to a downstream edge controller over RS-485.

This firmware runs on a bare-metal ARM Cortex-M4 microcontroller inside a weatherproof housing mounted on a traffic signal pole. It is part of a system that extends pedestrian walk signal time for seniors and people with disabilities.

## Target hardware

- **MCU:** STM32F407 (ARM Cortex-M4, 168 MHz, 192KB SRAM, 1MB Flash)
  - Use STM32 HAL drivers (not bare register access) for portability
  - If you prefer a different STM32F4xx variant, that's fine — keep the HAL layer
- **NFC transceiver:** NXP PN5180 (13.56 MHz, ISO 14443A, MIFARE DESFire support)
  - Connected to MCU via SPI (SPI1)
  - IRQ pin connected to PA4 (EXTI4)
  - NSS/CS pin on PA3 (active low)
  - BUSY pin on PA5
  - Reset pin on PA6
- **RS-485 transceiver:** MAX485 or equivalent
  - Connected to MCU USART2 (TX=PA2, RX=PA3 — note: reassign CS to PB0 if conflict)
  - Direction control pin (DE/RE) on PB1
- **LED ring:** WS2812B-compatible (8 LEDs), single data line on PB6 (TIM4_CH1 for DMA-based driving)
- **Buzzer:** Piezo on PB7, driven via TIM4_CH2 PWM
- **Power:** 12VDC input from signal cabinet via conduit, onboard 3.3V regulator (assume already present on PCB)

> **Note to Claude Code:** If the exact pin assignments create conflicts in your implementation, you may reassign pins — just document the changes clearly in a `pin_config.h` header. The pin assignments above are a starting reference, not hard constraints.

## Project structure

Create the following file structure:

```
safecross-nfc-firmware/
├── README.md                  # Build instructions, pin mapping, flashing guide
├── Makefile                   # ARM GCC cross-compilation (arm-none-eabi-gcc)
├── linker.ld                  # STM32F407 linker script (Flash + RAM layout)
├── src/
│   ├── main.c                 # Entry point, init sequence, main loop
│   ├── nfc.h / nfc.c          # NFC polling, anti-collision, card read
│   ├── classifier.h / .c      # Card type classification logic
│   ├── rs485.h / rs485.c      # RS-485 message framing and transmission
│   ├── feedback.h / feedback.c # LED ring + buzzer control
│   ├── watchdog.h / watchdog.c # IWDG (independent watchdog) setup
│   └── pin_config.h           # All pin definitions in one place
├── drivers/
│   ├── pn5180.h / pn5180.c    # PN5180 SPI driver (register-level commands)
│   └── ws2812b.h / ws2812b.c  # WS2812B LED driver (DMA-based bit-bang via timer)
└── tests/
    ├── test_classifier.c       # Unit tests for card type classification
    └── test_rs485_framing.c    # Unit tests for message framing
```

## Behavior specification

### Main loop

The firmware runs a simple polling loop (not RTOS):

```
1. Initialize all peripherals (SPI, USART, timers, GPIO, watchdog)
2. Set LED ring to idle state (dim white pulse, 1 cycle/3 sec)
3. Loop forever:
   a. Kick the watchdog
   b. Poll for NFC card presence (RF field on, check for ATQA response)
   c. If no card detected: continue loop (polling interval ~100ms)
   d. If card detected:
      i.   Run ISO 14443A anti-collision to get card UID (4 or 7 bytes)
      ii.  Select the card (RATS exchange for DESFire)
      iii. Read the card type (see Card Classification below)
      iv.  Determine classification result
      v.   Trigger appropriate LED + buzzer feedback
      vi.  Send classification message over RS-485
      vii. Enter cooldown period (2 seconds — ignore further taps to prevent
           double-reads of the same card)
      viii. Return to idle LED state
```

### NFC card reading — what to read from the Clipper card

Clipper cards are NXP MIFARE DESFire EV1 (MF3ICD41) smartcards. They operate under ISO 14443A and the DESFire protocol.

**Approach A (preferred): Read DESFire Application Directory**

1. After card selection, send `GET_APPLICATION_IDS` (DESFire command 0x6A)
2. The response contains a list of 3-byte Application IDs (AIDs) present on the card
3. Clipper cards have a known AID structure. Look for the presence of specific AIDs that identify the card's fare product configuration:
   - AID `0x000001` to `0x000010` (range — exact values TBD from card analysis)
   - The **number and type of AIDs** present can indicate card category

4. Alternatively, after selecting a Clipper application (SELECT_APPLICATION, command 0x5A with the AID), send `GET_FILE_IDS` (command 0x6F) to list files, then `READ_DATA` (command 0xBD) on a specific file ID to read the card type byte

**Important:** Do NOT attempt to authenticate or read encrypted data. The firmware should only read data in the card's **public/free-read** area. If a read requires authentication (returns 0xAE = "authentication error"), skip that file and fall back to Approach B.

**Approach B (fallback): UID prefix classification**

If the DESFire application directory doesn't reveal card type without authentication:

1. Use the card's 7-byte UID obtained during anti-collision
2. Senior RTC and Disabled RTC Clipper cards are issued in known UID serial number ranges
3. Classify based on a lookup table of UID prefixes:

```c
// Example prefix table — these are placeholders.
// Real values would be determined by analyzing actual Clipper card UIDs.
// This table would be stored in flash and updateable via RS-485 config command.
typedef struct {
    uint8_t prefix[3];     // First 3 bytes of 7-byte UID
    uint8_t prefix_len;    // How many bytes to match
    card_type_t card_type; // Classification result
} uid_prefix_entry_t;

static const uid_prefix_entry_t uid_table[] = {
    { {0x04, 0xA2, 0x00}, 2, CARD_TYPE_SENIOR_RTC },
    { {0x04, 0xB1, 0x00}, 2, CARD_TYPE_DISABLED_RTC },
    // ... more entries
    // If no prefix matches → CARD_TYPE_STANDARD
};
```

**Approach C (simplest, for initial development): Any DESFire card = trigger**

For initial lab testing before real Clipper card analysis is done:
1. If the card responds to DESFire selection (ATS contains DESFire identifier bytes)
2. Classify as `CARD_TYPE_DESFIRE_DETECTED`
3. This lets you test the full pipeline without needing real Clipper card data

> **Implement all three approaches behind a `#define` toggle:**
> ```c
> #define CLASSIFY_MODE_APPDIR   1   // Approach A
> #define CLASSIFY_MODE_UID      2   // Approach B  
> #define CLASSIFY_MODE_ANY      3   // Approach C (dev/test)
>
> #define ACTIVE_CLASSIFY_MODE   CLASSIFY_MODE_ANY  // Change for deployment
> ```

### Card type classification — output enum

```c
typedef enum {
    CARD_TYPE_NONE = 0x00,           // No card present
    CARD_TYPE_SENIOR_RTC = 0x01,     // Senior (65+) reduced fare card
    CARD_TYPE_DISABLED_RTC = 0x02,   // Disabled reduced fare card
    CARD_TYPE_STANDARD = 0x03,       // Standard adult Clipper
    CARD_TYPE_YOUTH = 0x04,          // Youth card
    CARD_TYPE_DESFIRE_DETECTED = 0x05, // DESFire card, type unknown (test mode)
    CARD_TYPE_UNKNOWN = 0xFF         // Card detected but not classifiable
} card_type_t;
```

### LED + buzzer feedback

| Event | LED ring | Buzzer |
|-------|----------|--------|
| Idle / no card | Slow dim white breathing pulse (3 sec cycle) | Silent |
| Senior RTC detected | All green, solid, 1.5 sec | Single 100ms tone at 2kHz |
| Disabled RTC detected | All green, solid, 1.5 sec | Single 100ms tone at 2kHz |
| Standard / Youth card | Single amber flash, 0.5 sec | Silent (no extension granted) |
| DESFire detected (test mode) | All blue, solid, 1.5 sec | Double 80ms tone at 1.5kHz |
| Read error / unknown | Single red flash, 0.5 sec | Silent |
| System error | Red breathing pulse (1 sec cycle) | Silent |

For the WS2812B LED ring:
- Green: RGB(0, 180, 0)
- Amber: RGB(255, 160, 0)
- Blue: RGB(0, 80, 255)
- Red: RGB(255, 0, 0)
- White (idle): RGB(40, 40, 40) breathing

### RS-485 message protocol

The edge controller (downstream device) listens on RS-485 at **115200 baud, 8N1**.

**Message frame format:**

```
| SYNC (2 bytes) | LENGTH (1 byte) | MSG_TYPE (1 byte) | PAYLOAD (N bytes) | CRC16 (2 bytes) |
| 0xAA 0x55      | N + 2            | see below         | varies             | CRC-16/MODBUS   |
```

- SYNC: `0xAA 0x55` — frame start delimiter
- LENGTH: number of bytes from MSG_TYPE through end of PAYLOAD (inclusive), not counting CRC
- CRC16: CRC-16/MODBUS over all bytes from MSG_TYPE through end of PAYLOAD

**Message types:**

**0x01 — Card tap event (reader → edge controller)**
```
PAYLOAD:
  card_type:     1 byte (card_type_t enum value)
  uid_length:    1 byte (4 or 7)
  uid:           4 or 7 bytes
  timestamp_ms:  4 bytes (uint32, milliseconds since boot, little-endian)
  read_method:   1 byte (1=APPDIR, 2=UID_PREFIX, 3=ANY_DESFIRE)
```

**0x02 — Heartbeat (reader → edge controller, every 10 seconds)**
```
PAYLOAD:
  status:        1 byte (0x00 = OK, 0x01 = NFC chip error, 0x02 = LED error)
  uptime_sec:    4 bytes (uint32, seconds since boot, little-endian)
  tap_count:     4 bytes (uint32, total taps since boot, little-endian)
  temperature:   2 bytes (int16, MCU die temperature in 0.1°C units, little-endian)
```

**0x80 — Config update (edge controller → reader)**
```
PAYLOAD:
  config_key:    1 byte
    0x01 = Update UID prefix table (followed by table data)
    0x02 = Set classify mode (followed by 1 byte: 1, 2, or 3)
    0x03 = Set cooldown period (followed by 2 bytes: milliseconds, little-endian)
  config_data:   variable length
```

**0x81 — Config ACK (reader → edge controller)**
```
PAYLOAD:
  config_key:    1 byte (echo of received key)
  result:        1 byte (0x00 = success, 0x01 = invalid key, 0x02 = invalid data)
```

### Watchdog

Use the STM32 Independent Watchdog (IWDG) with a 4-second timeout. The main loop kicks the watchdog on every iteration. If the NFC polling loop or any other operation hangs, the MCU will hard reset after 4 seconds.

After a watchdog reset, the firmware should:
1. Detect that the reset was caused by IWDG (check RCC reset flags)
2. Log the event in a small circular buffer in battery-backed SRAM (if available) or a designated flash sector
3. Resume normal operation

### Error handling

- **NFC chip communication failure:** If the PN5180 doesn't respond to SPI commands for 3 consecutive attempts, set system status to `NFC_CHIP_ERROR`, switch LED to red breathing, and continue attempting recovery every 5 seconds
- **RS-485 transmission failure:** Buffer up to 16 unsent messages in RAM. If buffer is full, drop oldest messages. Retry transmission every heartbeat interval
- **Unexpected card response:** If DESFire protocol returns unexpected status bytes, log the raw status code in the tap event message (for debugging) and classify as `CARD_TYPE_UNKNOWN`

## PN5180 driver — key commands needed

The PN5180 communicates over SPI using a command/response protocol. You'll need to implement these operations:

```c
// Core SPI commands
void pn5180_write_register(uint8_t reg, uint32_t value);
uint32_t pn5180_read_register(uint8_t reg);
void pn5180_send_data(uint8_t *data, uint16_t len);
void pn5180_read_data(uint8_t *buffer, uint16_t len);
void pn5180_load_rf_config(uint8_t tx_config, uint8_t rx_config);

// ISO 14443A operations
bool pn5180_iso14443a_poll(uint8_t *atqa, uint8_t *sak, uint8_t *uid, uint8_t *uid_len);
bool pn5180_iso14443a_select(uint8_t *uid, uint8_t uid_len);
bool pn5180_iso14443a_rats(uint8_t *ats, uint8_t *ats_len);

// DESFire operations (built on top of ISO 14443A transceive)
bool desfire_get_application_ids(uint8_t *aid_list, uint8_t *num_aids);
bool desfire_select_application(uint8_t *aid);  // 3-byte AID
bool desfire_get_file_ids(uint8_t *file_list, uint8_t *num_files);
bool desfire_read_data(uint8_t file_id, uint16_t offset, uint16_t length, uint8_t *data);
```

Reference the NXP PN5180 datasheet (publicly available) for the SPI command set. The ISO 14443A and DESFire command bytes are standard:
- DESFire GET_APPLICATION_IDS: 0x6A
- DESFire SELECT_APPLICATION: 0x5A
- DESFire GET_FILE_IDS: 0x6F
- DESFire READ_DATA: 0xBD
- DESFire response OK: 0x00
- DESFire response AUTHENTICATION_ERROR: 0xAE

## Build system

Use ARM GCC cross-compiler (`arm-none-eabi-gcc`). The Makefile should:
- Compile all `.c` files in `src/` and `drivers/`
- Link against CMSIS and STM32F4xx HAL (assume these are available as a submodule or system package)
- Produce a `.elf` and `.bin` file for flashing via ST-Link
- Have a `make test` target that compiles and runs the unit tests in `tests/` using the native GCC compiler (x86, no hardware dependencies — the test files should mock the hardware interfaces)

## Unit tests

Write unit tests for:

1. **Card type classifier** — test all three classification approaches with mock card data:
   - Known Senior RTC UID prefix → `CARD_TYPE_SENIOR_RTC`
   - Known Disabled RTC UID prefix → `CARD_TYPE_DISABLED_RTC`
   - Unknown UID prefix → `CARD_TYPE_STANDARD`
   - Empty AID list → `CARD_TYPE_UNKNOWN`
   - DESFire card in ANY mode → `CARD_TYPE_DESFIRE_DETECTED`

2. **RS-485 message framing** — verify frame construction:
   - Correct SYNC bytes
   - Correct LENGTH field
   - Correct CRC-16/MODBUS calculation (test against known vectors)
   - Correct byte ordering (little-endian for multi-byte fields)
   - Correct parsing of incoming config messages

Use a simple test framework — `assert()` macros are fine, no need for a heavy test library. Tests should compile and run on x86 without any embedded dependencies (mock all HAL calls).

## What NOT to build

- Do not implement DESFire authenticated read (requires Clipper encryption keys we don't have)
- Do not implement any write operations to the Clipper card (this is read-only)
- Do not implement OTA firmware updates on the reader MCU (that's handled by the edge controller, which reflashes the reader if needed)
- Do not implement an RTOS — the polling loop is sufficient for this workload
- Do not implement USB or JTAG debug output in the production build (use `#ifdef DEBUG` guards)

## Code style

- C11 standard
- 4-space indentation, no tabs
- All public functions prefixed with their module name: `nfc_poll()`, `classifier_get_type()`, `rs485_send()`, `feedback_set_green()`
- All hardware register access goes through HAL — no direct register manipulation
- Every function has a doxygen-style comment block
- No dynamic memory allocation (`malloc` / `free`) — all buffers are statically allocated
- All magic numbers get named constants in the relevant header file
