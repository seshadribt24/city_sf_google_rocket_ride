/**
 * @file classifier.h
 * @brief Card type classification logic
 *
 * Classifies NFC cards based on DESFire application data or UID
 * prefix matching. Three classification modes are supported,
 * selectable at compile time via ACTIVE_CLASSIFY_MODE.
 */

#ifndef CLASSIFIER_H
#define CLASSIFIER_H

#include <stdint.h>
#include <stdbool.h>
#include "nfc.h"

/* ============================================================================
 * Classification Modes
 * ============================================================================ */

/** Read DESFire application directory to determine card type */
#define CLASSIFY_MODE_APPDIR    1
/** Match UID prefix against known table */
#define CLASSIFY_MODE_UID       2
/** Any DESFire card triggers (development/test mode) */
#define CLASSIFY_MODE_ANY       3

/** Active classification mode — change for deployment */
#ifndef ACTIVE_CLASSIFY_MODE
#define ACTIVE_CLASSIFY_MODE    CLASSIFY_MODE_ANY
#endif

/* ============================================================================
 * Card Types
 * ============================================================================ */

/**
 * @brief Card classification result
 */
typedef enum {
    CARD_TYPE_NONE              = 0x00,  /**< No card present */
    CARD_TYPE_SENIOR_RTC        = 0x01,  /**< Senior (65+) reduced fare card */
    CARD_TYPE_DISABLED_RTC      = 0x02,  /**< Disabled reduced fare card */
    CARD_TYPE_STANDARD          = 0x03,  /**< Standard adult Clipper */
    CARD_TYPE_YOUTH             = 0x04,  /**< Youth card */
    CARD_TYPE_DESFIRE_DETECTED  = 0x05,  /**< DESFire card, type unknown (test) */
    CARD_TYPE_UNKNOWN           = 0xFF   /**< Card detected but unclassifiable */
} card_type_t;

/* ============================================================================
 * UID Prefix Table
 * ============================================================================ */

/** Maximum entries in the UID prefix lookup table */
#define CLASSIFIER_MAX_UID_ENTRIES  32

/**
 * @brief UID prefix table entry
 */
typedef struct {
    uint8_t     prefix[3];      /**< First N bytes of 7-byte UID */
    uint8_t     prefix_len;     /**< How many bytes to match (1-3) */
    card_type_t card_type;      /**< Classification result */
} uid_prefix_entry_t;

/* ============================================================================
 * Known DESFire AIDs for Clipper Card Classification
 * ============================================================================ */

/** Clipper application AID — primary transit application */
#define CLIPPER_AID_TRANSIT_0       0x00, 0x00, 0x01
#define CLIPPER_AID_TRANSIT_1       0x00, 0x00, 0x02

/** File ID within the Clipper application that contains card type */
#define CLIPPER_CARD_TYPE_FILE_ID   0x01
/** Offset of the card type byte within the file */
#define CLIPPER_CARD_TYPE_OFFSET    0
/** Length to read for card type */
#define CLIPPER_CARD_TYPE_LENGTH    1

/** Card type byte values in the DESFire file (Approach A) */
#define CLIPPER_TYPE_BYTE_SENIOR    0x01
#define CLIPPER_TYPE_BYTE_DISABLED  0x02
#define CLIPPER_TYPE_BYTE_STANDARD  0x03
#define CLIPPER_TYPE_BYTE_YOUTH     0x04

/* ============================================================================
 * Public API
 * ============================================================================ */

/**
 * @brief Initialize the classifier module
 *
 * Loads default UID prefix table into RAM.
 */
void classifier_init(void);

/**
 * @brief Classify a card based on the active classification mode
 * @param card Card information from NFC read
 * @return Card type classification result
 */
card_type_t classifier_classify(const nfc_card_info_t *card);

/**
 * @brief Update the UID prefix table at runtime (from RS-485 config)
 * @param data Serialized table data
 * @param len Length of data
 * @return true on success, false if data is invalid
 *
 * Table format: repeated entries of [prefix_len(1)] [prefix(3)] [card_type(1)]
 */
bool classifier_update_uid_table(const uint8_t *data, uint16_t len);

#ifdef UNIT_TEST
/**
 * @brief Classify with an explicit mode (for testing)
 * @param card Card information
 * @param mode Classification mode (CLASSIFY_MODE_*)
 * @return Card type classification result
 */
card_type_t classifier_classify_with_mode(const nfc_card_info_t *card, int mode);
#endif

#endif /* CLASSIFIER_H */
