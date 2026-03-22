/**
 * @file nfc.h
 * @brief NFC card polling and DESFire reading interface
 *
 * High-level module for detecting NFC cards, running anti-collision,
 * and reading DESFire application data from Clipper transit cards.
 */

#ifndef NFC_H
#define NFC_H

#include <stdint.h>
#include <stdbool.h>

/* ============================================================================
 * DESFire Protocol Constants
 * ============================================================================ */

/** DESFire command: Get Application IDs */
#define DESFIRE_CMD_GET_APP_IDS         0x6A
/** DESFire command: Select Application */
#define DESFIRE_CMD_SELECT_APP          0x5A
/** DESFire command: Get File IDs */
#define DESFIRE_CMD_GET_FILE_IDS        0x6F
/** DESFire command: Read Data */
#define DESFIRE_CMD_READ_DATA           0xBD

/** DESFire response: Operation OK */
#define DESFIRE_STATUS_OK               0x00
/** DESFire response: Additional frames pending */
#define DESFIRE_STATUS_MORE_FRAMES      0xAF
/** DESFire response: Authentication error (requires key) */
#define DESFIRE_STATUS_AUTH_ERROR        0xAE

/** Maximum number of AIDs to store */
#define NFC_MAX_AIDS                    10
/** Maximum card data buffer size */
#define NFC_MAX_CARD_DATA               64
/** Maximum ATS buffer size */
#define NFC_MAX_ATS_LEN                 32

/** Consecutive NFC failures before error state */
#define NFC_MAX_CONSECUTIVE_FAILURES    3

/* ============================================================================
 * Data Types
 * ============================================================================ */

/**
 * @brief NFC card information structure
 *
 * Populated by nfc_read_card() after a successful card read.
 */
typedef struct {
    uint8_t uid[7];             /**< Card UID (4 or 7 bytes) */
    uint8_t uid_len;            /**< Actual UID length */
    uint8_t sak;                /**< SAK byte from selection */
    bool    is_desfire;         /**< Card supports DESFire protocol */

    uint8_t ats[NFC_MAX_ATS_LEN]; /**< Answer To Select data */
    uint8_t ats_len;            /**< ATS length */

    uint8_t aid_list[NFC_MAX_AIDS * 3]; /**< Application ID list (3 bytes each) */
    uint8_t num_aids;           /**< Number of AIDs found */

    uint8_t card_data[NFC_MAX_CARD_DATA]; /**< Raw card data from file read */
    uint8_t card_data_len;      /**< Length of card data */
} nfc_card_info_t;

/**
 * @brief NFC module status
 */
typedef enum {
    NFC_STATUS_OK           = 0x00,  /**< Operating normally */
    NFC_STATUS_CHIP_ERROR   = 0x01,  /**< PN5180 communication failure */
} nfc_status_t;

/* ============================================================================
 * Public API
 * ============================================================================ */

/**
 * @brief Initialize the NFC module and PN5180 transceiver
 * @return true on success, false if chip initialization fails
 */
bool nfc_init(void);

/**
 * @brief Poll for NFC card presence
 * @return true if a card is detected in the RF field
 *
 * Performs a single REQA poll. Call this at ~100ms intervals from
 * the main loop. Does not perform anti-collision or card reading.
 */
bool nfc_poll(void);

/**
 * @brief Read a detected NFC card
 * @param card_info Output structure populated with card details
 * @return true on successful read, false on error
 *
 * Must be called after nfc_poll() returns true. Performs the full
 * card read sequence: anti-collision, selection, RATS, and DESFire
 * application directory read.
 */
bool nfc_read_card(nfc_card_info_t *card_info);

/**
 * @brief Get the current NFC module status
 * @return NFC_STATUS_OK or NFC_STATUS_CHIP_ERROR
 */
nfc_status_t nfc_get_status(void);

/**
 * @brief Attempt recovery from NFC chip error
 * @return true if recovery succeeded
 *
 * Re-initializes the PN5180. Called periodically (every 5s) when
 * in error state.
 */
bool nfc_attempt_recovery(void);

#endif /* NFC_H */
