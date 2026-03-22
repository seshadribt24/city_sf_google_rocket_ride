/**
 * @file rs485.c
 * @brief RS-485 communication implementation
 */

#include "rs485.h"
#include "pin_config.h"
#include <string.h>

/* ============================================================================
 * CRC-16/MODBUS Lookup Table
 * ============================================================================ */

/**
 * @brief CRC-16/MODBUS lookup table
 *
 * Polynomial: 0x8005, reflected, init: 0xFFFF
 */
static const uint16_t crc16_table[256] = {
    0x0000, 0xC0C1, 0xC181, 0x0140, 0xC301, 0x03C0, 0x0280, 0xC241,
    0xC601, 0x06C0, 0x0780, 0xC741, 0x0500, 0xC5C1, 0xC481, 0x0440,
    0xCC01, 0x0CC0, 0x0D80, 0xCD41, 0x0F00, 0xCFC1, 0xCE81, 0x0E40,
    0x0A00, 0xCAC1, 0xCB81, 0x0B40, 0xC901, 0x09C0, 0x0880, 0xC841,
    0xD801, 0x18C0, 0x1980, 0xD941, 0x1B00, 0xDBC1, 0xDA81, 0x1A40,
    0x1E00, 0xDEC1, 0xDF81, 0x1F40, 0xDD01, 0x1DC0, 0x1C80, 0xDC41,
    0x1400, 0xD4C1, 0xD581, 0x1540, 0xD701, 0x17C0, 0x1680, 0xD641,
    0xD201, 0x12C0, 0x1380, 0xD341, 0x1100, 0xD1C1, 0xD081, 0x1040,
    0xF001, 0x30C0, 0x3180, 0xF141, 0x3300, 0xF3C1, 0xF281, 0x3240,
    0x3600, 0xF6C1, 0xF781, 0x3740, 0xF501, 0x35C0, 0x3480, 0xF441,
    0x3C00, 0xFCC1, 0xFD81, 0x3D40, 0xFF01, 0x3FC0, 0x3E80, 0xFE41,
    0xFA01, 0x3AC0, 0x3B80, 0xFB41, 0x3900, 0xF9C1, 0xF881, 0x3840,
    0x2800, 0xE8C1, 0xE981, 0x2940, 0xEB01, 0x2BC0, 0x2A80, 0xEA41,
    0xEE01, 0x2EC0, 0x2F80, 0xEF41, 0x2D00, 0xEDC1, 0xEC81, 0x2C40,
    0xE401, 0x24C0, 0x2580, 0xE541, 0x2700, 0xE7C1, 0xE681, 0x2640,
    0x2200, 0xE2C1, 0xE381, 0x2340, 0xE101, 0x21C0, 0x2080, 0xE041,
    0xA001, 0x60C0, 0x6180, 0xA141, 0x6300, 0xA3C1, 0xA281, 0x6240,
    0x6600, 0xA6C1, 0xA781, 0x6740, 0xA501, 0x65C0, 0x6480, 0xA441,
    0x6C00, 0xACC1, 0xAD81, 0x6D40, 0xAF01, 0x6FC0, 0x6E80, 0xAE41,
    0xAA01, 0x6AC0, 0x6B80, 0xAB41, 0x6900, 0xA9C1, 0xA881, 0x6840,
    0x7800, 0xB8C1, 0xB981, 0x7940, 0xBB01, 0x7BC0, 0x7A80, 0xBA41,
    0xBE01, 0x7EC0, 0x7F80, 0xBF41, 0x7D00, 0xBDC1, 0xBC81, 0x7C40,
    0xB401, 0x74C0, 0x7580, 0xB541, 0x7700, 0xB7C1, 0xB681, 0x7640,
    0x7200, 0xB2C1, 0xB381, 0x7340, 0xB101, 0x71C0, 0x7080, 0xB041,
    0x5000, 0x90C1, 0x9181, 0x5140, 0x9301, 0x53C0, 0x5280, 0x9241,
    0x9601, 0x56C0, 0x5780, 0x9741, 0x5500, 0x95C1, 0x9481, 0x5440,
    0x9C01, 0x5CC0, 0x5D80, 0x9D41, 0x5F00, 0x9FC1, 0x9E81, 0x5E40,
    0x5A00, 0x9AC1, 0x9B81, 0x5B40, 0x9901, 0x59C0, 0x5880, 0x9841,
    0x8801, 0x48C0, 0x4980, 0x8941, 0x4B00, 0x8BC1, 0x8A81, 0x4A40,
    0x4E00, 0x8EC1, 0x8F81, 0x4F40, 0x8D01, 0x4DC0, 0x4C80, 0x8C41,
    0x4400, 0x84C1, 0x8581, 0x4540, 0x8701, 0x47C0, 0x4680, 0x8641,
    0x8201, 0x42C0, 0x4380, 0x8341, 0x4100, 0x81C1, 0x8081, 0x4040
};

uint16_t rs485_crc16_modbus(const uint8_t *data, uint16_t len)
{
    uint16_t crc = 0xFFFF;

    for (uint16_t i = 0; i < len; i++) {
        uint8_t index = (uint8_t)(crc ^ data[i]);
        crc = (crc >> 8) ^ crc16_table[index];
    }

    return crc;
}

/* ============================================================================
 * Frame Building and Parsing (hardware-independent)
 * ============================================================================ */

bool rs485_build_frame(uint8_t msg_type, const uint8_t *payload,
                       uint8_t payload_len, uint8_t *frame,
                       uint16_t *frame_len)
{
    if (payload_len > RS485_MAX_PAYLOAD) {
        return false;
    }

    uint16_t pos = 0;

    /* SYNC bytes */
    frame[pos++] = RS485_SYNC_BYTE_1;
    frame[pos++] = RS485_SYNC_BYTE_2;

    /* LENGTH = msg_type(1) + payload_len */
    uint8_t length = 1 + payload_len;
    frame[pos++] = length;

    /* MSG_TYPE */
    frame[pos++] = msg_type;

    /* PAYLOAD */
    if (payload != NULL && payload_len > 0) {
        memcpy(&frame[pos], payload, payload_len);
        pos += payload_len;
    }

    /* CRC-16/MODBUS over MSG_TYPE + PAYLOAD */
    uint16_t crc = rs485_crc16_modbus(&frame[3], length);
    frame[pos++] = (uint8_t)(crc & 0xFF);        /* CRC low byte */
    frame[pos++] = (uint8_t)((crc >> 8) & 0xFF); /* CRC high byte */

    *frame_len = pos;
    return true;
}

bool rs485_parse_frame(const uint8_t *frame, uint16_t frame_len,
                       rs485_message_t *msg)
{
    /* Minimum frame: SYNC(2) + LENGTH(1) + MSG_TYPE(1) + CRC(2) = 6 */
    if (frame_len < 6) {
        return false;
    }

    /* Verify SYNC */
    if (frame[0] != RS485_SYNC_BYTE_1 || frame[1] != RS485_SYNC_BYTE_2) {
        return false;
    }

    /* Extract LENGTH */
    uint8_t length = frame[2];
    if (length < 1 || length > (RS485_MAX_PAYLOAD + 1)) {
        return false;
    }

    /* Verify total frame length */
    uint16_t expected_len = 2 + 1 + length + 2;  /* SYNC + LENGTH + data + CRC */
    if (frame_len < expected_len) {
        return false;
    }

    /* Verify CRC over MSG_TYPE + PAYLOAD */
    uint16_t crc_calc = rs485_crc16_modbus(&frame[3], length);
    uint16_t crc_recv = (uint16_t)frame[3 + length] |
                        ((uint16_t)frame[3 + length + 1] << 8);

    if (crc_calc != crc_recv) {
        return false;
    }

    /* Parse message */
    msg->msg_type = frame[3];
    msg->payload_len = length - 1;
    if (msg->payload_len > 0) {
        memcpy(msg->payload, &frame[4], msg->payload_len);
    }

    return true;
}

/* ============================================================================
 * Hardware-Dependent Code (guarded for unit tests)
 * ============================================================================ */

#ifndef UNIT_TEST

#include "stm32f4xx_hal.h"

/** UART handle */
static UART_HandleTypeDef huart_rs485;

/** Config message callback */
static rs485_config_callback_t config_callback = NULL;

/** TX retry buffer */
static uint8_t tx_buffer[RS485_TX_BUFFER_DEPTH][RS485_MAX_FRAME_SIZE];
static uint16_t tx_buffer_len[RS485_TX_BUFFER_DEPTH];
static uint8_t tx_buffer_head = 0;
static uint8_t tx_buffer_tail = 0;
static uint8_t tx_buffer_count = 0;

/** RX state machine */
typedef enum {
    RX_STATE_WAIT_SYNC1,
    RX_STATE_WAIT_SYNC2,
    RX_STATE_READ_LENGTH,
    RX_STATE_READ_DATA,
} rx_state_t;

static rx_state_t rx_state = RX_STATE_WAIT_SYNC1;
static uint8_t rx_frame[RS485_MAX_FRAME_SIZE];
static uint16_t rx_pos = 0;
static uint8_t rx_expected_len = 0;

/* ============================================================================
 * Private Helpers
 * ============================================================================ */

/**
 * @brief Set RS-485 direction to transmit
 */
static inline void rs485_de_enable(void)
{
    HAL_GPIO_WritePin(RS485_DE_PORT, RS485_DE_PIN, GPIO_PIN_SET);
}

/**
 * @brief Set RS-485 direction to receive
 */
static inline void rs485_de_disable(void)
{
    HAL_GPIO_WritePin(RS485_DE_PORT, RS485_DE_PIN, GPIO_PIN_RESET);
}

/**
 * @brief Transmit a frame over UART with DE control
 * @return true on success
 */
static bool rs485_transmit_frame(const uint8_t *frame, uint16_t len)
{
    rs485_de_enable();

    HAL_StatusTypeDef status = HAL_UART_Transmit(&huart_rs485,
                                                  (uint8_t *)frame, len, 100);

    /* Wait for transmission complete flag before disabling DE */
    uint32_t start = HAL_GetTick();
    while (__HAL_UART_GET_FLAG(&huart_rs485, UART_FLAG_TC) == RESET) {
        if ((HAL_GetTick() - start) > 10) {
            break;
        }
    }

    rs485_de_disable();

    return (status == HAL_OK);
}

/**
 * @brief Add a frame to the retry buffer
 */
static void rs485_buffer_frame(const uint8_t *frame, uint16_t len)
{
    if (tx_buffer_count >= RS485_TX_BUFFER_DEPTH) {
        /* Buffer full — drop oldest */
        tx_buffer_tail = (tx_buffer_tail + 1) % RS485_TX_BUFFER_DEPTH;
        tx_buffer_count--;
    }

    memcpy(tx_buffer[tx_buffer_head], frame, len);
    tx_buffer_len[tx_buffer_head] = len;
    tx_buffer_head = (tx_buffer_head + 1) % RS485_TX_BUFFER_DEPTH;
    tx_buffer_count++;
}

/**
 * @brief Build and send (or buffer) a message
 */
static bool rs485_send_message(uint8_t msg_type, const uint8_t *payload,
                               uint8_t payload_len)
{
    uint8_t frame[RS485_MAX_FRAME_SIZE];
    uint16_t frame_len = 0;

    if (!rs485_build_frame(msg_type, payload, payload_len, frame, &frame_len)) {
        return false;
    }

    if (rs485_transmit_frame(frame, frame_len)) {
        return true;
    }

    /* Transmission failed — buffer for retry */
    rs485_buffer_frame(frame, frame_len);
    return false;
}

/**
 * @brief Process a complete received frame
 */
static void rs485_process_rx_frame(void)
{
    rs485_message_t msg;

    if (!rs485_parse_frame(rx_frame, rx_pos, &msg)) {
        return;
    }

    /* Only handle config update messages */
    if (msg.msg_type == RS485_MSG_CONFIG_UPDATE && msg.payload_len >= 1) {
        uint8_t config_key = msg.payload[0];
        uint8_t *config_data = (msg.payload_len > 1) ? &msg.payload[1] : NULL;
        uint8_t config_data_len = (msg.payload_len > 1) ? (msg.payload_len - 1) : 0;

        if (config_callback != NULL) {
            config_callback(config_key, config_data, config_data_len);
        }
    }
}

/* ============================================================================
 * Public API Implementation
 * ============================================================================ */

void rs485_init(void)
{
    GPIO_InitTypeDef gpio = {0};

    /* Enable USART2 clock */
    __HAL_RCC_USART2_CLK_ENABLE();

    /* USART2 GPIO: TX (PA2), RX (PA3) */
    gpio.Pin       = RS485_TX_PIN | RS485_RX_PIN;
    gpio.Mode      = GPIO_MODE_AF_PP;
    gpio.Pull      = GPIO_PULLUP;
    gpio.Speed     = GPIO_SPEED_FREQ_HIGH;
    gpio.Alternate = RS485_USART_AF;
    HAL_GPIO_Init(RS485_USART_PORT, &gpio);

    /* DE/RE pin — output, default low (receive mode) */
    gpio.Pin   = RS485_DE_PIN;
    gpio.Mode  = GPIO_MODE_OUTPUT_PP;
    gpio.Pull  = GPIO_NOPULL;
    gpio.Speed = GPIO_SPEED_FREQ_HIGH;
    HAL_GPIO_Init(RS485_DE_PORT, &gpio);
    rs485_de_disable();

    /* USART2 configuration */
    huart_rs485.Instance        = RS485_USART_INSTANCE;
    huart_rs485.Init.BaudRate   = RS485_BAUDRATE;
    huart_rs485.Init.WordLength = UART_WORDLENGTH_8B;
    huart_rs485.Init.StopBits   = UART_STOPBITS_1;
    huart_rs485.Init.Parity     = UART_PARITY_NONE;
    huart_rs485.Init.Mode       = UART_MODE_TX_RX;
    huart_rs485.Init.HwFlowCtl  = UART_HWCONTROL_NONE;

    HAL_UART_Init(&huart_rs485);

    /* Initialize state */
    rx_state = RX_STATE_WAIT_SYNC1;
    rx_pos = 0;
    tx_buffer_head = 0;
    tx_buffer_tail = 0;
    tx_buffer_count = 0;
    config_callback = NULL;
}

bool rs485_send_tap_event(card_type_t card_type, const uint8_t *uid,
                          uint8_t uid_len, uint32_t timestamp_ms,
                          uint8_t read_method)
{
    uint8_t payload[14];  /* Max: 1 + 1 + 7 + 4 + 1 = 14 */
    uint8_t pos = 0;

    payload[pos++] = (uint8_t)card_type;
    payload[pos++] = uid_len;

    for (uint8_t i = 0; i < uid_len && i < 7; i++) {
        payload[pos++] = uid[i];
    }

    /* timestamp_ms — little-endian */
    payload[pos++] = (uint8_t)(timestamp_ms >>  0);
    payload[pos++] = (uint8_t)(timestamp_ms >>  8);
    payload[pos++] = (uint8_t)(timestamp_ms >> 16);
    payload[pos++] = (uint8_t)(timestamp_ms >> 24);

    payload[pos++] = read_method;

    return rs485_send_message(RS485_MSG_TAP_EVENT, payload, pos);
}

bool rs485_send_heartbeat(uint8_t status, uint32_t uptime_sec,
                          uint32_t tap_count, int16_t temperature)
{
    uint8_t payload[11];
    uint8_t pos = 0;

    payload[pos++] = status;

    /* uptime_sec — little-endian */
    payload[pos++] = (uint8_t)(uptime_sec >>  0);
    payload[pos++] = (uint8_t)(uptime_sec >>  8);
    payload[pos++] = (uint8_t)(uptime_sec >> 16);
    payload[pos++] = (uint8_t)(uptime_sec >> 24);

    /* tap_count — little-endian */
    payload[pos++] = (uint8_t)(tap_count >>  0);
    payload[pos++] = (uint8_t)(tap_count >>  8);
    payload[pos++] = (uint8_t)(tap_count >> 16);
    payload[pos++] = (uint8_t)(tap_count >> 24);

    /* temperature — little-endian int16 */
    payload[pos++] = (uint8_t)((uint16_t)temperature >>  0);
    payload[pos++] = (uint8_t)((uint16_t)temperature >>  8);

    return rs485_send_message(RS485_MSG_HEARTBEAT, payload, pos);
}

bool rs485_send_config_ack(uint8_t config_key, uint8_t result)
{
    uint8_t payload[2];
    payload[0] = config_key;
    payload[1] = result;

    return rs485_send_message(RS485_MSG_CONFIG_ACK, payload, 2);
}

void rs485_receive_poll(void)
{
    uint8_t byte;

    /* Check if a byte is available */
    if (HAL_UART_Receive(&huart_rs485, &byte, 1, 0) != HAL_OK) {
        return;
    }

    switch (rx_state) {
    case RX_STATE_WAIT_SYNC1:
        if (byte == RS485_SYNC_BYTE_1) {
            rx_frame[0] = byte;
            rx_pos = 1;
            rx_state = RX_STATE_WAIT_SYNC2;
        }
        break;

    case RX_STATE_WAIT_SYNC2:
        if (byte == RS485_SYNC_BYTE_2) {
            rx_frame[1] = byte;
            rx_pos = 2;
            rx_state = RX_STATE_READ_LENGTH;
        } else {
            rx_state = RX_STATE_WAIT_SYNC1;
        }
        break;

    case RX_STATE_READ_LENGTH:
        rx_frame[2] = byte;
        rx_pos = 3;
        rx_expected_len = byte;  /* Data length (MSG_TYPE + PAYLOAD) */
        if (rx_expected_len < 1 || rx_expected_len > (RS485_MAX_PAYLOAD + 1)) {
            rx_state = RX_STATE_WAIT_SYNC1;
        } else {
            rx_state = RX_STATE_READ_DATA;
        }
        break;

    case RX_STATE_READ_DATA:
        if (rx_pos < RS485_MAX_FRAME_SIZE) {
            rx_frame[rx_pos++] = byte;
        }

        /* Expected total after LENGTH: data bytes + 2 CRC bytes */
        if (rx_pos >= (uint16_t)(3 + rx_expected_len + 2)) {
            rs485_process_rx_frame();
            rx_state = RX_STATE_WAIT_SYNC1;
        }
        break;
    }
}

void rs485_set_config_callback(rs485_config_callback_t callback)
{
    config_callback = callback;
}

void rs485_retry_pending(void)
{
    while (tx_buffer_count > 0) {
        if (!rs485_transmit_frame(tx_buffer[tx_buffer_tail],
                                  tx_buffer_len[tx_buffer_tail])) {
            /* Still failing — stop retrying */
            return;
        }

        tx_buffer_tail = (tx_buffer_tail + 1) % RS485_TX_BUFFER_DEPTH;
        tx_buffer_count--;
    }
}

uint8_t rs485_get_pending_count(void)
{
    return tx_buffer_count;
}

#endif /* UNIT_TEST */
