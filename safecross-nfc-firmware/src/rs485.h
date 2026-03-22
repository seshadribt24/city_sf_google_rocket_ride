/**
 * @file rs485.h
 * @brief RS-485 communication interface
 *
 * Handles message framing, CRC-16/MODBUS calculation, and half-duplex
 * RS-485 communication with the downstream edge controller.
 */

#ifndef RS485_H
#define RS485_H

#include <stdint.h>
#include <stdbool.h>
#include "classifier.h"

/* ============================================================================
 * Protocol Constants
 * ============================================================================ */

/** Frame synchronization bytes */
#define RS485_SYNC_BYTE_1           0xAA
#define RS485_SYNC_BYTE_2           0x55

/** Maximum payload size */
#define RS485_MAX_PAYLOAD           64

/** Maximum frame size: SYNC(2) + LENGTH(1) + MSG_TYPE(1) + PAYLOAD(64) + CRC(2) */
#define RS485_MAX_FRAME_SIZE        70

/** Message retry buffer depth */
#define RS485_TX_BUFFER_DEPTH       16

/* ============================================================================
 * Message Types
 * ============================================================================ */

/** Card tap event (reader → edge controller) */
#define RS485_MSG_TAP_EVENT         0x01
/** Heartbeat (reader → edge controller) */
#define RS485_MSG_HEARTBEAT         0x02
/** Config update (edge controller → reader) */
#define RS485_MSG_CONFIG_UPDATE     0x80
/** Config ACK (reader → edge controller) */
#define RS485_MSG_CONFIG_ACK        0x81

/* ============================================================================
 * Config Keys
 * ============================================================================ */

/** Update UID prefix table */
#define RS485_CONFIG_UID_TABLE      0x01
/** Set classification mode */
#define RS485_CONFIG_CLASSIFY_MODE  0x02
/** Set cooldown period (ms) */
#define RS485_CONFIG_COOLDOWN       0x03

/* ============================================================================
 * Config Result Codes
 * ============================================================================ */

#define RS485_CONFIG_RESULT_OK      0x00
#define RS485_CONFIG_RESULT_BAD_KEY 0x01
#define RS485_CONFIG_RESULT_BAD_DATA 0x02

/* ============================================================================
 * Data Types
 * ============================================================================ */

/**
 * @brief Parsed incoming message
 */
typedef struct {
    uint8_t  msg_type;
    uint8_t  payload[RS485_MAX_PAYLOAD];
    uint8_t  payload_len;
} rs485_message_t;

/**
 * @brief Callback type for received config messages
 */
typedef void (*rs485_config_callback_t)(uint8_t config_key,
                                        const uint8_t *data, uint8_t len);

/* ============================================================================
 * Public API
 * ============================================================================ */

/**
 * @brief Initialize RS-485 communication
 *
 * Configures USART2, GPIO pins, and the DE/RE direction control pin.
 */
void rs485_init(void);

/**
 * @brief Calculate CRC-16/MODBUS over a data buffer
 * @param data Input data
 * @param len Data length
 * @return CRC-16 value
 *
 * Uses the standard MODBUS polynomial 0x8005 with reflected I/O
 * and initial value 0xFFFF.
 */
uint16_t rs485_crc16_modbus(const uint8_t *data, uint16_t len);

/**
 * @brief Build a complete RS-485 frame
 * @param msg_type Message type byte
 * @param payload Payload data
 * @param payload_len Payload length
 * @param frame Output frame buffer (must be at least RS485_MAX_FRAME_SIZE)
 * @param frame_len Output: actual frame length
 * @return true on success
 */
bool rs485_build_frame(uint8_t msg_type, const uint8_t *payload,
                       uint8_t payload_len, uint8_t *frame,
                       uint16_t *frame_len);

/**
 * @brief Parse an incoming RS-485 frame
 * @param frame Raw frame data (starting from SYNC bytes)
 * @param frame_len Frame length
 * @param msg Output: parsed message
 * @return true if frame is valid (correct SYNC, LENGTH, and CRC)
 */
bool rs485_parse_frame(const uint8_t *frame, uint16_t frame_len,
                       rs485_message_t *msg);

/**
 * @brief Send a card tap event to the edge controller
 * @param card_type Classification result
 * @param uid Card UID
 * @param uid_len UID length (4 or 7)
 * @param timestamp_ms Milliseconds since boot
 * @param read_method Classification method used (1, 2, or 3)
 * @return true on successful transmission
 */
bool rs485_send_tap_event(card_type_t card_type, const uint8_t *uid,
                          uint8_t uid_len, uint32_t timestamp_ms,
                          uint8_t read_method);

/**
 * @brief Send a heartbeat message to the edge controller
 * @param status System status byte (0x00=OK, 0x01=NFC error, 0x02=LED error)
 * @param uptime_sec Seconds since boot
 * @param tap_count Total taps since boot
 * @param temperature MCU die temperature in 0.1°C units
 * @return true on successful transmission
 */
bool rs485_send_heartbeat(uint8_t status, uint32_t uptime_sec,
                          uint32_t tap_count, int16_t temperature);

/**
 * @brief Send a config ACK to the edge controller
 * @param config_key Echoed config key
 * @param result Result code
 * @return true on successful transmission
 */
bool rs485_send_config_ack(uint8_t config_key, uint8_t result);

/**
 * @brief Poll for incoming RS-485 messages
 *
 * Feeds received bytes into the RX state machine. If a complete
 * valid frame is received, invokes the config callback.
 */
void rs485_receive_poll(void);

/**
 * @brief Register a callback for incoming config messages
 * @param callback Function to call when a config message is received
 */
void rs485_set_config_callback(rs485_config_callback_t callback);

/**
 * @brief Retry sending any buffered messages
 *
 * Called periodically (e.g., on heartbeat tick) to flush the retry buffer.
 */
void rs485_retry_pending(void);

/**
 * @brief Get the number of pending messages in the retry buffer
 * @return Number of unsent messages
 */
uint8_t rs485_get_pending_count(void);

#endif /* RS485_H */
