/**
 * @file pn5180.h
 * @brief NXP PN5180 NFC transceiver SPI driver
 *
 * Low-level driver for the PN5180 NFC frontend IC. Provides SPI register
 * access, RF field control, and ISO 14443A operations (polling, anti-collision,
 * card selection, and RATS exchange).
 */

#ifndef PN5180_H
#define PN5180_H

#include <stdint.h>
#include <stdbool.h>

/* ============================================================================
 * PN5180 SPI Command Codes
 * ============================================================================ */

#define PN5180_CMD_WRITE_REGISTER       0x00
#define PN5180_CMD_WRITE_REGISTER_OR    0x01
#define PN5180_CMD_WRITE_REGISTER_AND   0x02
#define PN5180_CMD_READ_REGISTER        0x04
#define PN5180_CMD_WRITE_EEPROM         0x06
#define PN5180_CMD_READ_EEPROM          0x07
#define PN5180_CMD_SEND_DATA            0x09
#define PN5180_CMD_READ_DATA            0x0A
#define PN5180_CMD_SWITCH_MODE          0x0B
#define PN5180_CMD_LOAD_RF_CONFIG       0x11
#define PN5180_CMD_RF_ON                0x16
#define PN5180_CMD_RF_OFF               0x17

/* ============================================================================
 * PN5180 Register Addresses
 * ============================================================================ */

#define PN5180_REG_SYSTEM_CONFIG        0x00
#define PN5180_REG_IRQ_ENABLE           0x01
#define PN5180_REG_IRQ_STATUS           0x02
#define PN5180_REG_IRQ_CLEAR            0x03
#define PN5180_REG_TRANSCEIVE_CONTROL   0x04
#define PN5180_REG_TIMER0_STATUS        0x08
#define PN5180_REG_TIMER1_STATUS        0x09
#define PN5180_REG_TIMER2_STATUS        0x0A
#define PN5180_REG_RX_STATUS            0x13
#define PN5180_REG_RF_STATUS            0x1D
#define PN5180_REG_TEMP_CONTROL         0x21

/* ============================================================================
 * PN5180 IRQ Flags
 * ============================================================================ */

#define PN5180_IRQ_RX_DONE              (1U << 0)
#define PN5180_IRQ_TX_DONE              (1U << 1)
#define PN5180_IRQ_IDLE                 (1U << 2)
#define PN5180_IRQ_RFOFF_DET            (1U << 6)
#define PN5180_IRQ_RFON_DET             (1U << 7)
#define PN5180_IRQ_GENERAL_ERROR        (1U << 17)

/* ============================================================================
 * PN5180 RF Configuration IDs
 * ============================================================================ */

/** ISO 14443A 106 kbps TX configuration */
#define PN5180_RF_TX_ISO14443A_106      0x00
/** ISO 14443A 106 kbps RX configuration */
#define PN5180_RF_RX_ISO14443A_106      0x80

/* ============================================================================
 * PN5180 EEPROM Addresses
 * ============================================================================ */

#define PN5180_EEPROM_VERSION           0x10
#define PN5180_EEPROM_PRODUCT_VERSION   0x12
#define PN5180_EEPROM_FIRMWARE_VERSION  0x14

/* ============================================================================
 * ISO 14443A Constants
 * ============================================================================ */

/** REQA command byte */
#define ISO14443A_CMD_REQA              0x26
/** WUPA command byte */
#define ISO14443A_CMD_WUPA              0x52
/** Anti-collision cascade level 1 */
#define ISO14443A_CMD_ANTICOLL_CL1      0x93
/** Anti-collision cascade level 2 */
#define ISO14443A_CMD_ANTICOLL_CL2      0x95
/** Anti-collision cascade level 3 */
#define ISO14443A_CMD_ANTICOLL_CL3      0x97
/** NVB for anti-collision (request all bits) */
#define ISO14443A_NVB_ANTICOLL          0x20
/** NVB for select (all 4 bytes + BCC) */
#define ISO14443A_NVB_SELECT            0x70
/** RATS command */
#define ISO14443A_CMD_RATS              0xE0
/** Cascade tag in UID */
#define ISO14443A_CASCADE_TAG           0x88

/** SAK bit indicating ISO 14443-4 (ISO-DEP) support */
#define ISO14443A_SAK_ISO_DEP           (1U << 5)

/* ============================================================================
 * Timeouts
 * ============================================================================ */

/** Maximum time to wait for BUSY pin deassert (ms) */
#define PN5180_BUSY_TIMEOUT_MS          10
/** Maximum time to wait for IRQ (ms) */
#define PN5180_IRQ_TIMEOUT_MS           50
/** Maximum time to wait for card response (ms) */
#define PN5180_CARD_TIMEOUT_MS          100

/* ============================================================================
 * Public API
 * ============================================================================ */

/**
 * @brief Initialize the PN5180 transceiver
 * @return true on success, false if chip communication fails
 *
 * Configures SPI1, GPIO pins, performs a hard reset, verifies the
 * product version register, and loads ISO 14443A RF configuration.
 */
bool pn5180_init(void);

/**
 * @brief Write a 32-bit value to a PN5180 register
 * @param reg Register address
 * @param value 32-bit value to write
 */
void pn5180_write_register(uint8_t reg, uint32_t value);

/**
 * @brief Set bits in a PN5180 register (OR mask)
 * @param reg Register address
 * @param mask Bits to set
 */
void pn5180_write_register_or(uint8_t reg, uint32_t mask);

/**
 * @brief Clear bits in a PN5180 register (AND mask)
 * @param reg Register address
 * @param mask Bits to keep (inverted clear mask)
 */
void pn5180_write_register_and(uint8_t reg, uint32_t mask);

/**
 * @brief Read a 32-bit value from a PN5180 register
 * @param reg Register address
 * @return 32-bit register value
 */
uint32_t pn5180_read_register(uint8_t reg);

/**
 * @brief Send data through the RF field
 * @param data Data buffer to transmit
 * @param len Length in bytes
 * @param num_valid_bits Number of valid bits in the last byte (0 = all 8)
 * @return true on success
 */
bool pn5180_send_data(const uint8_t *data, uint16_t len, uint8_t num_valid_bits);

/**
 * @brief Read data received from the RF field
 * @param buffer Output buffer
 * @param max_len Maximum bytes to read
 * @param actual_len Actual bytes read (output)
 * @return true on success
 */
bool pn5180_read_data(uint8_t *buffer, uint16_t max_len, uint16_t *actual_len);

/**
 * @brief Load an RF TX/RX configuration
 * @param tx_config TX configuration ID
 * @param rx_config RX configuration ID
 */
void pn5180_load_rf_config(uint8_t tx_config, uint8_t rx_config);

/**
 * @brief Turn on the RF field
 * @return true on success
 */
bool pn5180_rf_on(void);

/**
 * @brief Turn off the RF field
 */
void pn5180_rf_off(void);

/**
 * @brief Clear all pending IRQ flags
 */
void pn5180_clear_irq(void);

/**
 * @brief Wait for a specific IRQ flag to be set
 * @param irq_mask IRQ flag(s) to wait for
 * @param timeout_ms Maximum wait time in milliseconds
 * @return true if IRQ occurred, false on timeout
 */
bool pn5180_wait_irq(uint32_t irq_mask, uint32_t timeout_ms);

/* ============================================================================
 * ISO 14443A Operations
 * ============================================================================ */

/**
 * @brief Poll for an ISO 14443A card (send REQA)
 * @param atqa Output buffer for 2-byte ATQA response
 * @return true if a card responded
 */
bool pn5180_iso14443a_poll(uint8_t *atqa);

/**
 * @brief Run full anti-collision and selection to get UID
 * @param uid Output buffer for UID (7 bytes max)
 * @param uid_len Output: actual UID length (4 or 7)
 * @param sak Output: SAK byte from the card
 * @return true on success
 */
bool pn5180_iso14443a_select(uint8_t *uid, uint8_t *uid_len, uint8_t *sak);

/**
 * @brief Send RATS and receive ATS (activate ISO 14443-4 / ISO-DEP)
 * @param ats Output buffer for ATS
 * @param ats_len Output: ATS length
 * @return true on success
 */
bool pn5180_iso14443a_rats(uint8_t *ats, uint8_t *ats_len);

/**
 * @brief Transceive data via ISO-DEP (ISO 14443-4 I-block)
 * @param tx_data Command data to send
 * @param tx_len Length of command data
 * @param rx_data Response buffer
 * @param rx_max Maximum response size
 * @param rx_len Actual response length (output)
 * @return true on success
 */
bool pn5180_transceive(const uint8_t *tx_data, uint16_t tx_len,
                       uint8_t *rx_data, uint16_t rx_max, uint16_t *rx_len);

#endif /* PN5180_H */
