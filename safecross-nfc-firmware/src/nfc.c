/**
 * @file nfc.c
 * @brief NFC card polling and DESFire reading implementation
 */

#include "nfc.h"
#include "classifier.h"
#include "pn5180.h"

#ifndef UNIT_TEST
#include "stm32f4xx_hal.h"
#endif

#include <string.h>

/* ============================================================================
 * Private State
 * ============================================================================ */

/** Current NFC module status */
static nfc_status_t nfc_status = NFC_STATUS_OK;

/** Consecutive poll failure counter */
static uint8_t nfc_fail_count = 0;

/* ============================================================================
 * DESFire Command Helpers
 * ============================================================================ */

#ifndef UNIT_TEST

/**
 * @brief Send a DESFire command and receive response via ISO-DEP
 * @param cmd DESFire command byte
 * @param params Command parameters (NULL if none)
 * @param params_len Length of parameters
 * @param resp Response buffer
 * @param resp_max Maximum response size
 * @param resp_len Actual response length (output, excluding status byte)
 * @param status_byte DESFire status byte (output)
 * @return true if communication succeeded (check status_byte for DESFire errors)
 */
static bool nfc_desfire_command(uint8_t cmd, const uint8_t *params,
                                uint16_t params_len,
                                uint8_t *resp, uint16_t resp_max,
                                uint16_t *resp_len, uint8_t *status_byte)
{
    /* Build DESFire command frame */
    uint8_t tx_buf[64];
    tx_buf[0] = cmd;
    if (params != NULL && params_len > 0) {
        memcpy(&tx_buf[1], params, params_len);
    }

    uint8_t rx_buf[258];
    uint16_t rx_len = 0;

    if (!pn5180_transceive(tx_buf, 1 + params_len, rx_buf, 256, &rx_len)) {
        *resp_len = 0;
        *status_byte = 0xFF;
        return false;
    }

    if (rx_len < 1) {
        *resp_len = 0;
        *status_byte = 0xFF;
        return false;
    }

    /* First byte of DESFire response is the status byte */
    *status_byte = rx_buf[0];
    *resp_len = rx_len - 1;

    if (*resp_len > 0 && resp != NULL) {
        uint16_t copy_len = (*resp_len > resp_max) ? resp_max : *resp_len;
        memcpy(resp, &rx_buf[1], copy_len);
        *resp_len = copy_len;
    }

    return true;
}

/**
 * @brief Read DESFire application IDs
 * @param card_info Card info structure to populate
 * @return true on success
 */
static bool nfc_desfire_read_app_ids(nfc_card_info_t *card_info)
{
    uint8_t resp[NFC_MAX_AIDS * 3];
    uint16_t resp_len = 0;
    uint8_t status = 0;

    if (!nfc_desfire_command(DESFIRE_CMD_GET_APP_IDS, NULL, 0,
                            resp, sizeof(resp), &resp_len, &status)) {
        return false;
    }

    if (status == DESFIRE_STATUS_AUTH_ERROR) {
        /* Authentication required — cannot read, fallback needed */
        card_info->num_aids = 0;
        return true;  /* Not a communication error, just access denied */
    }

    if (status != DESFIRE_STATUS_OK && status != DESFIRE_STATUS_MORE_FRAMES) {
        return false;
    }

    /* AIDs are 3 bytes each */
    card_info->num_aids = (uint8_t)(resp_len / 3);
    if (card_info->num_aids > NFC_MAX_AIDS) {
        card_info->num_aids = NFC_MAX_AIDS;
    }

    memcpy(card_info->aid_list, resp, card_info->num_aids * 3);
    return true;
}

/**
 * @brief Select a DESFire application by AID
 * @param aid 3-byte Application ID
 * @return true on success
 */
static bool nfc_desfire_select_app(const uint8_t *aid)
{
    uint8_t resp[16];
    uint16_t resp_len = 0;
    uint8_t status = 0;

    if (!nfc_desfire_command(DESFIRE_CMD_SELECT_APP, aid, 3,
                            resp, sizeof(resp), &resp_len, &status)) {
        return false;
    }

    return (status == DESFIRE_STATUS_OK);
}

/**
 * @brief Read data from a DESFire file
 * @param file_id File ID to read
 * @param offset Read offset
 * @param length Bytes to read
 * @param data Output buffer
 * @param data_len Actual bytes read (output)
 * @return true on success, false on error or auth required
 */
static bool nfc_desfire_read_file(uint8_t file_id, uint16_t offset,
                                  uint16_t length, uint8_t *data,
                                  uint16_t *data_len)
{
    uint8_t params[7];
    params[0] = file_id;
    params[1] = (uint8_t)(offset >> 0);
    params[2] = (uint8_t)(offset >> 8);
    params[3] = 0x00;  /* Offset high byte */
    params[4] = (uint8_t)(length >> 0);
    params[5] = (uint8_t)(length >> 8);
    params[6] = 0x00;  /* Length high byte */

    uint8_t status = 0;

    if (!nfc_desfire_command(DESFIRE_CMD_READ_DATA, params, 7,
                            data, length, data_len, &status)) {
        return false;
    }

    if (status == DESFIRE_STATUS_AUTH_ERROR) {
        /* File requires authentication — skip */
        *data_len = 0;
        return false;
    }

    return (status == DESFIRE_STATUS_OK);
}

/**
 * @brief Check if ATS indicates a DESFire card
 * @param ats ATS buffer
 * @param ats_len ATS length
 * @return true if DESFire markers are present
 */
static bool nfc_is_desfire_ats(const uint8_t *ats, uint8_t ats_len)
{
    /* DESFire EV1 ATS typically contains:
     * - TL (length), T0, TA, TB, TC, historical bytes
     * - Historical bytes often contain 0x75 0x77 0x81 0x02 for DESFire
     * - Or we can check for bytes 0xC1 (DESFire identifier) in historical bytes
     *
     * Simple heuristic: look for DESFire-characteristic bytes in ATS */
    if (ats_len < 5) {
        return false;
    }

    /* Check historical bytes for DESFire EV1 patterns */
    for (uint8_t i = 3; i < ats_len - 1; i++) {
        /* DESFire cards often have 0x75 0x77 or 0xC1 in historical bytes */
        if (ats[i] == 0x75 && (i + 1) < ats_len && ats[i + 1] == 0x77) {
            return true;
        }
        if (ats[i] == 0xC1) {
            return true;
        }
    }

    /* Fallback: if SAK indicates ISO-DEP and card responded to RATS,
     * it could be DESFire — return true to attempt DESFire commands */
    return true;
}

/* ============================================================================
 * Public API
 * ============================================================================ */

bool nfc_init(void)
{
    nfc_status = NFC_STATUS_OK;
    nfc_fail_count = 0;

    if (!pn5180_init()) {
        nfc_status = NFC_STATUS_CHIP_ERROR;
        return false;
    }

    /* Turn on RF field */
    if (!pn5180_rf_on()) {
        nfc_status = NFC_STATUS_CHIP_ERROR;
        return false;
    }

    return true;
}

bool nfc_poll(void)
{
    if (nfc_status != NFC_STATUS_OK) {
        return false;
    }

    uint8_t atqa[2];

    if (pn5180_iso14443a_poll(atqa)) {
        nfc_fail_count = 0;
        return true;
    }

    /* Track consecutive failures */
    nfc_fail_count++;
    if (nfc_fail_count >= NFC_MAX_CONSECUTIVE_FAILURES) {
        /* Check if it's a chip error vs just no card present */
        /* Try reading a register to verify SPI is working */
        uint32_t reg = pn5180_read_register(0x1D);  /* RF_STATUS */
        if (reg == 0xFFFFFFFF) {
            nfc_status = NFC_STATUS_CHIP_ERROR;
        }
        nfc_fail_count = 0;
    }

    return false;
}

bool nfc_read_card(nfc_card_info_t *card_info)
{
    memset(card_info, 0, sizeof(nfc_card_info_t));

    /* Step 1: Anti-collision and selection */
    if (!pn5180_iso14443a_select(card_info->uid, &card_info->uid_len,
                                 &card_info->sak)) {
        return false;
    }

    /* Step 2: Check if card supports ISO-DEP (ISO 14443-4) */
    if (!(card_info->sak & ISO14443A_SAK_ISO_DEP)) {
        /* Not an ISO-DEP card — can't be DESFire */
        card_info->is_desfire = false;
        return true;
    }

    /* Step 3: RATS exchange to activate ISO-DEP */
    if (!pn5180_iso14443a_rats(card_info->ats, &card_info->ats_len)) {
        /* RATS failed but we have the UID */
        card_info->is_desfire = false;
        return true;
    }

    /* Step 4: Check ATS for DESFire indicators */
    card_info->is_desfire = nfc_is_desfire_ats(card_info->ats, card_info->ats_len);

    if (!card_info->is_desfire) {
        return true;
    }

    /* Step 5: Read DESFire application IDs */
    nfc_desfire_read_app_ids(card_info);

    /* Step 6: If we found AIDs, try to select the first Clipper app and read data */
    if (card_info->num_aids > 0) {
        /* Try to select the first application and read card type data */
        if (nfc_desfire_select_app(card_info->aid_list)) {
            uint16_t data_len = 0;
            nfc_desfire_read_file(CLIPPER_CARD_TYPE_FILE_ID,
                                  CLIPPER_CARD_TYPE_OFFSET,
                                  CLIPPER_CARD_TYPE_LENGTH,
                                  card_info->card_data, &data_len);
            card_info->card_data_len = (uint8_t)data_len;
        }
    }

    return true;
}

nfc_status_t nfc_get_status(void)
{
    return nfc_status;
}

bool nfc_attempt_recovery(void)
{
    /* Turn off RF, re-initialize */
    pn5180_rf_off();

    if (!pn5180_init()) {
        return false;
    }

    if (!pn5180_rf_on()) {
        return false;
    }

    nfc_status = NFC_STATUS_OK;
    nfc_fail_count = 0;
    return true;
}

#endif /* UNIT_TEST */
