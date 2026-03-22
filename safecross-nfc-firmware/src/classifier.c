/**
 * @file classifier.c
 * @brief Card type classification implementation
 *
 * Pure logic module — no hardware dependencies. Classifies NFC cards
 * based on DESFire application data, UID prefix matching, or simple
 * DESFire detection depending on the active classification mode.
 */

#include "classifier.h"
#include <string.h>

/* ============================================================================
 * Default UID Prefix Table
 * ============================================================================ */

/**
 * @brief Default UID prefix entries — placeholder values.
 *
 * Real values would be determined by analyzing actual Clipper card UIDs
 * from the field. This table can be updated at runtime via RS-485.
 */
static const uid_prefix_entry_t default_uid_table[] = {
    { {0x04, 0xA2, 0x00}, 2, CARD_TYPE_SENIOR_RTC },
    { {0x04, 0xA3, 0x00}, 2, CARD_TYPE_SENIOR_RTC },
    { {0x04, 0xB1, 0x00}, 2, CARD_TYPE_DISABLED_RTC },
    { {0x04, 0xB2, 0x00}, 2, CARD_TYPE_DISABLED_RTC },
    { {0x04, 0xC0, 0x00}, 2, CARD_TYPE_YOUTH },
};

#define DEFAULT_UID_TABLE_SIZE \
    (sizeof(default_uid_table) / sizeof(default_uid_table[0]))

/* ============================================================================
 * Runtime State
 * ============================================================================ */

/** Runtime UID prefix table (copy in RAM, updateable) */
static uid_prefix_entry_t uid_table[CLASSIFIER_MAX_UID_ENTRIES];

/** Current number of entries in the runtime table */
static uint8_t uid_table_count = 0;

/* ============================================================================
 * Private Classification Functions
 * ============================================================================ */

/**
 * @brief Classify using DESFire application directory data (Approach A)
 */
static card_type_t classify_appdir(const nfc_card_info_t *card)
{
    if (!card->is_desfire) {
        return CARD_TYPE_UNKNOWN;
    }

    /* If we have card data from a file read, check the card type byte */
    if (card->card_data_len >= 1) {
        switch (card->card_data[0]) {
        case CLIPPER_TYPE_BYTE_SENIOR:
            return CARD_TYPE_SENIOR_RTC;
        case CLIPPER_TYPE_BYTE_DISABLED:
            return CARD_TYPE_DISABLED_RTC;
        case CLIPPER_TYPE_BYTE_STANDARD:
            return CARD_TYPE_STANDARD;
        case CLIPPER_TYPE_BYTE_YOUTH:
            return CARD_TYPE_YOUTH;
        default:
            break;
        }
    }

    /* Fallback: analyze AID list for known patterns */
    if (card->num_aids == 0) {
        return CARD_TYPE_UNKNOWN;
    }

    /* Check for presence of known Clipper AIDs
     * The number of applications can hint at card type:
     * - Senior/Disabled RTC cards often have additional benefit AIDs
     * - Standard cards typically have fewer applications
     */
    for (uint8_t i = 0; i < card->num_aids; i++) {
        uint8_t aid_hi  = card->aid_list[i * 3 + 2];
        uint8_t aid_mid = card->aid_list[i * 3 + 1];

        /* Look for specific AID ranges indicating card category */
        if (aid_hi == 0x00 && aid_mid == 0x00) {
            uint8_t aid_lo = card->aid_list[i * 3 + 0];
            if (aid_lo >= 0x05 && aid_lo <= 0x08) {
                return CARD_TYPE_SENIOR_RTC;
            }
            if (aid_lo >= 0x09 && aid_lo <= 0x0C) {
                return CARD_TYPE_DISABLED_RTC;
            }
        }
    }

    /* DESFire card with AIDs but no recognized pattern */
    return CARD_TYPE_STANDARD;
}

/**
 * @brief Classify using UID prefix matching (Approach B)
 */
static card_type_t classify_uid(const nfc_card_info_t *card)
{
    if (card->uid_len == 0) {
        return CARD_TYPE_UNKNOWN;
    }

    /* Search the UID prefix table */
    for (uint8_t i = 0; i < uid_table_count; i++) {
        const uid_prefix_entry_t *entry = &uid_table[i];

        if (entry->prefix_len == 0 || entry->prefix_len > card->uid_len) {
            continue;
        }

        bool match = true;
        for (uint8_t j = 0; j < entry->prefix_len; j++) {
            if (card->uid[j] != entry->prefix[j]) {
                match = false;
                break;
            }
        }

        if (match) {
            return entry->card_type;
        }
    }

    /* No prefix match — assume standard card */
    return CARD_TYPE_STANDARD;
}

/**
 * @brief Classify using simple DESFire detection (Approach C)
 */
static card_type_t classify_any(const nfc_card_info_t *card)
{
    if (card->is_desfire) {
        return CARD_TYPE_DESFIRE_DETECTED;
    }
    return CARD_TYPE_UNKNOWN;
}

/**
 * @brief Internal classification dispatcher
 */
static card_type_t classify_with_mode(const nfc_card_info_t *card, int mode)
{
    if (card == NULL) {
        return CARD_TYPE_NONE;
    }

    switch (mode) {
    case CLASSIFY_MODE_APPDIR:
        return classify_appdir(card);
    case CLASSIFY_MODE_UID:
        return classify_uid(card);
    case CLASSIFY_MODE_ANY:
        return classify_any(card);
    default:
        return CARD_TYPE_UNKNOWN;
    }
}

/* ============================================================================
 * Public API
 * ============================================================================ */

void classifier_init(void)
{
    /* Copy default table into RAM */
    uid_table_count = (uint8_t)DEFAULT_UID_TABLE_SIZE;
    if (uid_table_count > CLASSIFIER_MAX_UID_ENTRIES) {
        uid_table_count = CLASSIFIER_MAX_UID_ENTRIES;
    }

    memcpy(uid_table, default_uid_table,
           uid_table_count * sizeof(uid_prefix_entry_t));
}

card_type_t classifier_classify(const nfc_card_info_t *card)
{
    return classify_with_mode(card, ACTIVE_CLASSIFY_MODE);
}

bool classifier_update_uid_table(const uint8_t *data, uint16_t len)
{
    if (data == NULL || len == 0) {
        return false;
    }

    /* Table format: repeated entries of:
     *   [prefix_len: 1 byte] [prefix: 3 bytes] [card_type: 1 byte]
     * Total: 5 bytes per entry */
    const uint16_t entry_size = 5;

    if (len % entry_size != 0) {
        return false;
    }

    uint16_t new_count = len / entry_size;
    if (new_count > CLASSIFIER_MAX_UID_ENTRIES) {
        return false;
    }

    /* Parse and validate entries */
    for (uint16_t i = 0; i < new_count; i++) {
        const uint8_t *entry_data = &data[i * entry_size];
        uint8_t prefix_len = entry_data[0];

        /* Validate prefix length */
        if (prefix_len == 0 || prefix_len > 3) {
            return false;
        }

        /* Validate card type */
        uint8_t card_type = entry_data[4];
        if (card_type > CARD_TYPE_DESFIRE_DETECTED && card_type != CARD_TYPE_UNKNOWN) {
            return false;
        }

        uid_table[i].prefix_len = prefix_len;
        uid_table[i].prefix[0] = entry_data[1];
        uid_table[i].prefix[1] = entry_data[2];
        uid_table[i].prefix[2] = entry_data[3];
        uid_table[i].card_type = (card_type_t)card_type;
    }

    uid_table_count = (uint8_t)new_count;
    return true;
}

#ifdef UNIT_TEST
card_type_t classifier_classify_with_mode(const nfc_card_info_t *card, int mode)
{
    return classify_with_mode(card, mode);
}
#endif
