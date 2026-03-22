/**
 * @file pn5180.c
 * @brief NXP PN5180 NFC transceiver SPI driver implementation
 */

#include "pn5180.h"
#include "pin_config.h"

#ifndef UNIT_TEST
#include "stm32f4xx_hal.h"

/* ============================================================================
 * Private State
 * ============================================================================ */

/** SPI handle for PN5180 communication */
static SPI_HandleTypeDef hspi_pn5180;

/** ISO-DEP block number toggle (0 or 1) */
static uint8_t iso_dep_block_number = 0;

/* ============================================================================
 * Private Helpers — GPIO
 * ============================================================================ */

/**
 * @brief Assert CS (active low)
 */
static inline void pn5180_cs_low(void)
{
    HAL_GPIO_WritePin(PN5180_CS_PORT, PN5180_CS_PIN, GPIO_PIN_RESET);
}

/**
 * @brief Deassert CS
 */
static inline void pn5180_cs_high(void)
{
    HAL_GPIO_WritePin(PN5180_CS_PORT, PN5180_CS_PIN, GPIO_PIN_SET);
}

/**
 * @brief Read the BUSY pin state
 * @return true if BUSY is asserted (high)
 */
static inline bool pn5180_is_busy(void)
{
    return HAL_GPIO_ReadPin(PN5180_BUSY_PORT, PN5180_BUSY_PIN) == GPIO_PIN_SET;
}

/**
 * @brief Wait for BUSY pin to deassert
 * @return true if BUSY went low, false on timeout
 */
static bool pn5180_wait_busy(void)
{
    uint32_t start = HAL_GetTick();
    while (pn5180_is_busy()) {
        if ((HAL_GetTick() - start) >= PN5180_BUSY_TIMEOUT_MS) {
            return false;
        }
    }
    return true;
}

/**
 * @brief Hard reset the PN5180
 */
static void pn5180_hard_reset(void)
{
    HAL_GPIO_WritePin(PN5180_RST_PORT, PN5180_RST_PIN, GPIO_PIN_RESET);
    HAL_Delay(10);
    HAL_GPIO_WritePin(PN5180_RST_PORT, PN5180_RST_PIN, GPIO_PIN_SET);
    HAL_Delay(2);
    /* Wait for BUSY to deassert after reset */
    pn5180_wait_busy();
}

/* ============================================================================
 * Private Helpers — SPI Transfer
 * ============================================================================ */

/**
 * @brief Send a raw SPI command and optionally read response
 * @param tx_buf Transmit buffer
 * @param tx_len Transmit length
 * @param rx_buf Receive buffer (NULL if no response expected)
 * @param rx_len Receive length
 * @return true on success
 */
static bool pn5180_spi_transfer(const uint8_t *tx_buf, uint16_t tx_len,
                                uint8_t *rx_buf, uint16_t rx_len)
{
    /* Wait for any previous operation to complete */
    if (!pn5180_wait_busy()) {
        return false;
    }

    /* Send command */
    pn5180_cs_low();
    HAL_StatusTypeDef status = HAL_SPI_Transmit(&hspi_pn5180,
                                                (uint8_t *)tx_buf, tx_len, 100);
    pn5180_cs_high();

    if (status != HAL_OK) {
        return false;
    }

    /* If a response is expected, wait for BUSY then read */
    if (rx_buf != NULL && rx_len > 0) {
        if (!pn5180_wait_busy()) {
            return false;
        }

        pn5180_cs_low();
        status = HAL_SPI_Receive(&hspi_pn5180, rx_buf, rx_len, 100);
        pn5180_cs_high();

        if (status != HAL_OK) {
            return false;
        }
    }

    return true;
}

/* ============================================================================
 * GPIO and SPI Initialization
 * ============================================================================ */

/**
 * @brief Configure GPIO pins for PN5180
 */
static void pn5180_gpio_init(void)
{
    GPIO_InitTypeDef gpio = {0};

    /* CS pin — output push-pull, default high (deasserted) */
    gpio.Pin   = PN5180_CS_PIN;
    gpio.Mode  = GPIO_MODE_OUTPUT_PP;
    gpio.Pull  = GPIO_NOPULL;
    gpio.Speed = GPIO_SPEED_FREQ_HIGH;
    HAL_GPIO_Init(PN5180_CS_PORT, &gpio);
    pn5180_cs_high();

    /* BUSY pin — input */
    gpio.Pin   = PN5180_BUSY_PIN;
    gpio.Mode  = GPIO_MODE_INPUT;
    gpio.Pull  = GPIO_PULLDOWN;
    HAL_GPIO_Init(PN5180_BUSY_PORT, &gpio);

    /* RST pin — output push-pull, default high */
    gpio.Pin   = PN5180_RST_PIN;
    gpio.Mode  = GPIO_MODE_OUTPUT_PP;
    gpio.Pull  = GPIO_NOPULL;
    gpio.Speed = GPIO_SPEED_FREQ_LOW;
    HAL_GPIO_Init(PN5180_RST_PORT, &gpio);
    HAL_GPIO_WritePin(PN5180_RST_PORT, PN5180_RST_PIN, GPIO_PIN_SET);

    /* IRQ pin — input with falling-edge interrupt */
    gpio.Pin   = PN5180_IRQ_PIN;
    gpio.Mode  = GPIO_MODE_IT_FALLING;
    gpio.Pull  = GPIO_PULLUP;
    HAL_GPIO_Init(PN5180_IRQ_PORT, &gpio);
}

/**
 * @brief Configure SPI1 for PN5180 communication
 */
static void pn5180_spi_init(void)
{
    GPIO_InitTypeDef gpio = {0};

    /* Enable SPI1 clock */
    __HAL_RCC_SPI1_CLK_ENABLE();

    /* SPI1 GPIO: SCK (PA5), MISO (PA6), MOSI (PA7) */
    gpio.Pin       = PN5180_SPI_SCK_PIN | PN5180_SPI_MISO_PIN | PN5180_SPI_MOSI_PIN;
    gpio.Mode      = GPIO_MODE_AF_PP;
    gpio.Pull      = GPIO_NOPULL;
    gpio.Speed     = GPIO_SPEED_FREQ_HIGH;
    gpio.Alternate = PN5180_SPI_AF;
    HAL_GPIO_Init(PN5180_SPI_PORT, &gpio);

    /* SPI1 configuration */
    hspi_pn5180.Instance               = PN5180_SPI_INSTANCE;
    hspi_pn5180.Init.Mode              = SPI_MODE_MASTER;
    hspi_pn5180.Init.Direction         = SPI_DIRECTION_2LINES;
    hspi_pn5180.Init.DataSize          = SPI_DATASIZE_8BIT;
    hspi_pn5180.Init.CLKPolarity       = SPI_POLARITY_LOW;   /* CPOL = 0 */
    hspi_pn5180.Init.CLKPhase          = SPI_PHASE_1EDGE;    /* CPHA = 0 */
    hspi_pn5180.Init.NSS               = SPI_NSS_SOFT;
    hspi_pn5180.Init.BaudRatePrescaler = SPI_BAUDRATEPRESCALER_16; /* 84MHz/16 = 5.25MHz */
    hspi_pn5180.Init.FirstBit          = SPI_FIRSTBIT_MSB;
    hspi_pn5180.Init.TIMode            = SPI_TIMODE_DISABLE;
    hspi_pn5180.Init.CRCCalculation    = SPI_CRCCALCULATION_DISABLE;

    HAL_SPI_Init(&hspi_pn5180);
}

/* ============================================================================
 * Public API — Register Access
 * ============================================================================ */

void pn5180_write_register(uint8_t reg, uint32_t value)
{
    uint8_t cmd[6];
    cmd[0] = PN5180_CMD_WRITE_REGISTER;
    cmd[1] = reg;
    cmd[2] = (uint8_t)(value >>  0);
    cmd[3] = (uint8_t)(value >>  8);
    cmd[4] = (uint8_t)(value >> 16);
    cmd[5] = (uint8_t)(value >> 24);

    pn5180_spi_transfer(cmd, 6, NULL, 0);
}

void pn5180_write_register_or(uint8_t reg, uint32_t mask)
{
    uint8_t cmd[6];
    cmd[0] = PN5180_CMD_WRITE_REGISTER_OR;
    cmd[1] = reg;
    cmd[2] = (uint8_t)(mask >>  0);
    cmd[3] = (uint8_t)(mask >>  8);
    cmd[4] = (uint8_t)(mask >> 16);
    cmd[5] = (uint8_t)(mask >> 24);

    pn5180_spi_transfer(cmd, 6, NULL, 0);
}

void pn5180_write_register_and(uint8_t reg, uint32_t mask)
{
    uint8_t cmd[6];
    cmd[0] = PN5180_CMD_WRITE_REGISTER_AND;
    cmd[1] = reg;
    cmd[2] = (uint8_t)(mask >>  0);
    cmd[3] = (uint8_t)(mask >>  8);
    cmd[4] = (uint8_t)(mask >> 16);
    cmd[5] = (uint8_t)(mask >> 24);

    pn5180_spi_transfer(cmd, 6, NULL, 0);
}

uint32_t pn5180_read_register(uint8_t reg)
{
    uint8_t cmd[2];
    uint8_t resp[4] = {0};

    cmd[0] = PN5180_CMD_READ_REGISTER;
    cmd[1] = reg;

    pn5180_spi_transfer(cmd, 2, resp, 4);

    return ((uint32_t)resp[3] << 24) |
           ((uint32_t)resp[2] << 16) |
           ((uint32_t)resp[1] <<  8) |
           ((uint32_t)resp[0] <<  0);
}

/* ============================================================================
 * Public API — RF Data Operations
 * ============================================================================ */

bool pn5180_send_data(const uint8_t *data, uint16_t len, uint8_t num_valid_bits)
{
    if (len == 0 || len > 260) {
        return false;
    }

    /* Clear IRQ status */
    pn5180_clear_irq();

    /* Build SEND_DATA command: [cmd] [valid_bits] [data...] */
    uint8_t cmd_buf[262];
    cmd_buf[0] = PN5180_CMD_SEND_DATA;
    cmd_buf[1] = num_valid_bits;  /* 0 = all 8 bits valid in last byte */
    for (uint16_t i = 0; i < len; i++) {
        cmd_buf[2 + i] = data[i];
    }

    if (!pn5180_spi_transfer(cmd_buf, len + 2, NULL, 0)) {
        return false;
    }

    /* Wait for TX_DONE IRQ */
    return pn5180_wait_irq(PN5180_IRQ_TX_DONE, PN5180_IRQ_TIMEOUT_MS);
}

bool pn5180_read_data(uint8_t *buffer, uint16_t max_len, uint16_t *actual_len)
{
    /* Read RX_STATUS register to get received byte count */
    uint32_t rx_status = pn5180_read_register(PN5180_REG_RX_STATUS);
    uint16_t rx_bytes = (uint16_t)(rx_status & 0x01FF);  /* Bits [8:0] */

    if (rx_bytes == 0) {
        *actual_len = 0;
        return false;
    }

    if (rx_bytes > max_len) {
        rx_bytes = max_len;
    }

    /* Send READ_DATA command */
    uint8_t cmd[2];
    cmd[0] = PN5180_CMD_READ_DATA;
    cmd[1] = 0x00;

    if (!pn5180_spi_transfer(cmd, 2, buffer, rx_bytes)) {
        *actual_len = 0;
        return false;
    }

    *actual_len = rx_bytes;
    return true;
}

void pn5180_load_rf_config(uint8_t tx_config, uint8_t rx_config)
{
    uint8_t cmd[3];
    cmd[0] = PN5180_CMD_LOAD_RF_CONFIG;
    cmd[1] = tx_config;
    cmd[2] = rx_config;

    pn5180_spi_transfer(cmd, 3, NULL, 0);
}

bool pn5180_rf_on(void)
{
    uint8_t cmd[2];
    cmd[0] = PN5180_CMD_RF_ON;
    cmd[1] = 0x00;  /* Collision avoidance mode: none */

    if (!pn5180_spi_transfer(cmd, 2, NULL, 0)) {
        return false;
    }

    /* Verify RF field is active */
    HAL_Delay(5);
    uint32_t rf_status = pn5180_read_register(PN5180_REG_RF_STATUS);
    return (rf_status & 0x01) != 0;  /* Bit 0 = RF field on */
}

void pn5180_rf_off(void)
{
    uint8_t cmd[2];
    cmd[0] = PN5180_CMD_RF_OFF;
    cmd[1] = 0x00;

    pn5180_spi_transfer(cmd, 2, NULL, 0);
}

/* ============================================================================
 * Public API — IRQ Management
 * ============================================================================ */

void pn5180_clear_irq(void)
{
    pn5180_write_register(PN5180_REG_IRQ_CLEAR, 0xFFFFFFFF);
}

bool pn5180_wait_irq(uint32_t irq_mask, uint32_t timeout_ms)
{
    uint32_t start = HAL_GetTick();

    while ((HAL_GetTick() - start) < timeout_ms) {
        uint32_t irq_status = pn5180_read_register(PN5180_REG_IRQ_STATUS);
        if (irq_status & irq_mask) {
            return true;
        }
        if (irq_status & PN5180_IRQ_GENERAL_ERROR) {
            return false;
        }
    }

    return false;
}

/* ============================================================================
 * Public API — ISO 14443A Operations
 * ============================================================================ */

/**
 * @brief Helper: transceive raw ISO 14443A data and wait for response
 */
static bool pn5180_transceive_raw(const uint8_t *tx, uint16_t tx_len,
                                  uint8_t num_valid_bits,
                                  uint8_t *rx, uint16_t rx_max,
                                  uint16_t *rx_len)
{
    /* Configure transceiver for ISO 14443A */
    pn5180_write_register(PN5180_REG_SYSTEM_CONFIG, 0x03);  /* Transceive mode */
    pn5180_clear_irq();

    if (!pn5180_send_data(tx, tx_len, num_valid_bits)) {
        *rx_len = 0;
        return false;
    }

    /* Wait for RX_DONE */
    if (!pn5180_wait_irq(PN5180_IRQ_RX_DONE, PN5180_CARD_TIMEOUT_MS)) {
        *rx_len = 0;
        return false;
    }

    return pn5180_read_data(rx, rx_max, rx_len);
}

bool pn5180_iso14443a_poll(uint8_t *atqa)
{
    /* Send REQA (short frame, 7 bits) */
    uint8_t reqa = ISO14443A_CMD_REQA;
    uint16_t rx_len = 0;
    uint8_t rx_buf[2];

    if (!pn5180_transceive_raw(&reqa, 1, 7, rx_buf, 2, &rx_len)) {
        return false;
    }

    if (rx_len < 2) {
        return false;
    }

    atqa[0] = rx_buf[0];
    atqa[1] = rx_buf[1];

    return true;
}

/**
 * @brief Run anti-collision for one cascade level
 * @param cascade_cmd CL1 (0x93), CL2 (0x95), or CL3 (0x97)
 * @param uid_part Output: 4 UID bytes + BCC
 * @param sak Output: SAK byte
 * @return true on success
 */
static bool pn5180_anticollision_level(uint8_t cascade_cmd,
                                       uint8_t *uid_part, uint8_t *sak)
{
    uint8_t cmd[2];
    uint8_t resp[5];
    uint16_t rx_len = 0;

    /* Anti-collision command */
    cmd[0] = cascade_cmd;
    cmd[1] = ISO14443A_NVB_ANTICOLL;

    if (!pn5180_transceive_raw(cmd, 2, 0, resp, 5, &rx_len)) {
        return false;
    }

    if (rx_len < 5) {
        return false;
    }

    /* Verify BCC (XOR of 4 UID bytes) */
    uint8_t bcc = resp[0] ^ resp[1] ^ resp[2] ^ resp[3];
    if (bcc != resp[4]) {
        return false;
    }

    /* Copy UID part */
    for (int i = 0; i < 5; i++) {
        uid_part[i] = resp[i];
    }

    /* Select command with the resolved UID */
    uint8_t select_cmd[7];
    select_cmd[0] = cascade_cmd;
    select_cmd[1] = ISO14443A_NVB_SELECT;
    select_cmd[2] = resp[0];
    select_cmd[3] = resp[1];
    select_cmd[4] = resp[2];
    select_cmd[5] = resp[3];
    select_cmd[6] = resp[4];  /* BCC */

    uint8_t sak_buf[1];
    rx_len = 0;

    if (!pn5180_transceive_raw(select_cmd, 7, 0, sak_buf, 1, &rx_len)) {
        return false;
    }

    if (rx_len < 1) {
        return false;
    }

    *sak = sak_buf[0];
    return true;
}

bool pn5180_iso14443a_select(uint8_t *uid, uint8_t *uid_len, uint8_t *sak)
{
    uint8_t uid_part[5];
    uint8_t level_sak = 0;

    /* Cascade Level 1 */
    if (!pn5180_anticollision_level(ISO14443A_CMD_ANTICOLL_CL1, uid_part, &level_sak)) {
        return false;
    }

    /* Check if UID is complete (no cascade) or needs more levels */
    if (uid_part[0] != ISO14443A_CASCADE_TAG) {
        /* Single-size UID (4 bytes) */
        uid[0] = uid_part[0];
        uid[1] = uid_part[1];
        uid[2] = uid_part[2];
        uid[3] = uid_part[3];
        *uid_len = 4;
        *sak = level_sak;
        return true;
    }

    /* Cascade Level 2 — first byte was cascade tag, real UID starts at bytes 1-3 */
    uid[0] = uid_part[1];
    uid[1] = uid_part[2];
    uid[2] = uid_part[3];

    if (!pn5180_anticollision_level(ISO14443A_CMD_ANTICOLL_CL2, uid_part, &level_sak)) {
        return false;
    }

    if (uid_part[0] != ISO14443A_CASCADE_TAG) {
        /* Double-size UID (7 bytes) */
        uid[3] = uid_part[0];
        uid[4] = uid_part[1];
        uid[5] = uid_part[2];
        uid[6] = uid_part[3];
        *uid_len = 7;
        *sak = level_sak;
        return true;
    }

    /* Cascade Level 3 (10-byte UID — rare, but handle for completeness) */
    uid[3] = uid_part[1];
    uid[4] = uid_part[2];
    uid[5] = uid_part[3];

    if (!pn5180_anticollision_level(ISO14443A_CMD_ANTICOLL_CL3, uid_part, &level_sak)) {
        return false;
    }

    uid[6] = uid_part[0];
    /* Only return 7 bytes max as per spec */
    *uid_len = 7;
    *sak = level_sak;
    return true;
}

bool pn5180_iso14443a_rats(uint8_t *ats, uint8_t *ats_len)
{
    uint8_t cmd[2];
    cmd[0] = ISO14443A_CMD_RATS;
    cmd[1] = 0x50;  /* FSD = 64 bytes, CID = 0 */

    uint16_t rx_len = 0;

    if (!pn5180_transceive_raw(cmd, 2, 0, ats, 64, &rx_len)) {
        return false;
    }

    if (rx_len < 1) {
        return false;
    }

    *ats_len = (uint8_t)rx_len;

    /* Reset ISO-DEP block number for new card session */
    iso_dep_block_number = 0;

    return true;
}

bool pn5180_transceive(const uint8_t *tx_data, uint16_t tx_len,
                       uint8_t *rx_data, uint16_t rx_max, uint16_t *rx_len)
{
    /* Wrap in ISO-DEP I-block */
    uint8_t i_block[258];
    uint8_t pcb = 0x02 | (iso_dep_block_number & 0x01);  /* I-block PCB */
    i_block[0] = pcb;

    for (uint16_t i = 0; i < tx_len && i < 256; i++) {
        i_block[1 + i] = tx_data[i];
    }

    uint8_t rx_buf[258];
    uint16_t raw_rx_len = 0;

    if (!pn5180_transceive_raw(i_block, tx_len + 1, 0,
                               rx_buf, rx_max + 1, &raw_rx_len)) {
        return false;
    }

    if (raw_rx_len < 2) {
        *rx_len = 0;
        return false;
    }

    /* Toggle block number for next exchange */
    iso_dep_block_number ^= 1;

    /* Strip I-block header (1 byte PCB) from response */
    *rx_len = raw_rx_len - 1;
    for (uint16_t i = 0; i < *rx_len && i < rx_max; i++) {
        rx_data[i] = rx_buf[i + 1];
    }

    return true;
}

/* ============================================================================
 * Public API — Initialization
 * ============================================================================ */

bool pn5180_init(void)
{
    /* Enable GPIO clocks */
    GPIO_CLK_ENABLE_ALL();

    /* Initialize GPIO and SPI */
    pn5180_gpio_init();
    pn5180_spi_init();

    /* Hard reset the PN5180 */
    pn5180_hard_reset();

    /* Verify chip communication by reading a known register */
    uint32_t version = pn5180_read_register(PN5180_REG_RF_STATUS);
    /* Just check that SPI is responding (register read doesn't return 0xFFFFFFFF) */
    if (version == 0xFFFFFFFF) {
        return false;
    }

    /* Load ISO 14443A 106 kbps RF configuration */
    pn5180_load_rf_config(PN5180_RF_TX_ISO14443A_106, PN5180_RF_RX_ISO14443A_106);

    /* Clear all IRQ flags */
    pn5180_clear_irq();

    return true;
}

#endif /* UNIT_TEST */
