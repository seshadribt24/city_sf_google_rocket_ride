/**
 * @file test_rs485_framing.c
 * @brief Unit tests for RS-485 message framing and CRC-16/MODBUS
 *
 * Tests frame construction, parsing, CRC calculation, and
 * byte ordering. Compiles and runs on x86 with no embedded dependencies.
 */

#include <assert.h>
#include <stdio.h>
#include <string.h>
#include <stdint.h>

/* Build with -DUNIT_TEST to exclude HAL code */
#include "../src/rs485.h"

/* ============================================================================
 * Test Helpers
 * ============================================================================ */

static int tests_run = 0;
static int tests_passed = 0;

#define TEST(name) \
    do { \
        tests_run++; \
        printf("  TEST: %-50s ", #name); \
    } while (0)

#define PASS() \
    do { \
        tests_passed++; \
        printf("[PASS]\n"); \
    } while (0)

/* ============================================================================
 * CRC-16/MODBUS Tests
 * ============================================================================ */

static void test_crc_empty(void)
{
    TEST(crc16_modbus_empty_data);

    uint16_t crc = rs485_crc16_modbus(NULL, 0);
    /* CRC of empty data with init=0xFFFF should be 0xFFFF */
    assert(crc == 0xFFFF);

    PASS();
}

static void test_crc_single_byte(void)
{
    TEST(crc16_modbus_single_byte);

    uint8_t data[] = {0x01};
    uint16_t crc = rs485_crc16_modbus(data, 1);
    /* Known CRC-16/MODBUS for {0x01} = 0x807E */
    assert(crc == 0x807E);

    PASS();
}

static void test_crc_known_vector_1(void)
{
    TEST(crc16_modbus_known_vector_123456789);

    /* Standard test vector: "123456789" → CRC = 0x4B37 */
    uint8_t data[] = {'1', '2', '3', '4', '5', '6', '7', '8', '9'};
    uint16_t crc = rs485_crc16_modbus(data, 9);
    assert(crc == 0x4B37);

    PASS();
}

static void test_crc_known_vector_2(void)
{
    TEST(crc16_modbus_known_vector_0x01_0x02);

    /* CRC-16/MODBUS for {0x01, 0x02} */
    uint8_t data[] = {0x01, 0x02};
    uint16_t crc = rs485_crc16_modbus(data, 2);
    /* Known value: 0xE181 */
    assert(crc == 0xE181);

    PASS();
}

static void test_crc_modbus_example(void)
{
    TEST(crc16_modbus_real_modbus_frame);

    /* Typical Modbus RTU request: slave=0x01, func=0x03, addr=0x0000, qty=0x000A
     * CRC-16/MODBUS register value = 0xCDC5 (wire order: 0xC5, 0xCD) */
    uint8_t data[] = {0x01, 0x03, 0x00, 0x00, 0x00, 0x0A};
    uint16_t crc = rs485_crc16_modbus(data, 6);
    assert(crc == 0xCDC5);

    PASS();
}

/* ============================================================================
 * Frame Building Tests
 * ============================================================================ */

static void test_frame_sync_bytes(void)
{
    TEST(frame_build_sync_bytes);

    uint8_t payload[] = {0x42};
    uint8_t frame[RS485_MAX_FRAME_SIZE];
    uint16_t frame_len = 0;

    bool ok = rs485_build_frame(0x01, payload, 1, frame, &frame_len);
    assert(ok == true);
    assert(frame[0] == RS485_SYNC_BYTE_1);
    assert(frame[1] == RS485_SYNC_BYTE_2);

    PASS();
}

static void test_frame_length_field(void)
{
    TEST(frame_build_length_field);

    uint8_t payload[] = {0x01, 0x02, 0x03, 0x04, 0x05};
    uint8_t frame[RS485_MAX_FRAME_SIZE];
    uint16_t frame_len = 0;

    bool ok = rs485_build_frame(0x01, payload, 5, frame, &frame_len);
    assert(ok == true);
    /* LENGTH = 1 (msg_type) + 5 (payload) = 6 */
    assert(frame[2] == 6);

    PASS();
}

static void test_frame_msg_type(void)
{
    TEST(frame_build_msg_type_position);

    uint8_t payload[] = {0xAA};
    uint8_t frame[RS485_MAX_FRAME_SIZE];
    uint16_t frame_len = 0;

    rs485_build_frame(0x02, payload, 1, frame, &frame_len);
    assert(frame[3] == 0x02);

    PASS();
}

static void test_frame_total_length(void)
{
    TEST(frame_build_total_length);

    uint8_t payload[] = {0x01, 0x02, 0x03};
    uint8_t frame[RS485_MAX_FRAME_SIZE];
    uint16_t frame_len = 0;

    rs485_build_frame(0x01, payload, 3, frame, &frame_len);
    /* Total: SYNC(2) + LENGTH(1) + MSG_TYPE(1) + PAYLOAD(3) + CRC(2) = 9 */
    assert(frame_len == 9);

    PASS();
}

static void test_frame_crc_position(void)
{
    TEST(frame_build_crc_at_end);

    uint8_t payload[] = {0x42};
    uint8_t frame[RS485_MAX_FRAME_SIZE];
    uint16_t frame_len = 0;

    rs485_build_frame(0x01, payload, 1, frame, &frame_len);

    /* CRC is over frame[3..4] (msg_type + payload) */
    uint16_t expected_crc = rs485_crc16_modbus(&frame[3], 2);
    uint16_t frame_crc = (uint16_t)frame[5] | ((uint16_t)frame[6] << 8);
    assert(frame_crc == expected_crc);

    PASS();
}

static void test_frame_empty_payload(void)
{
    TEST(frame_build_empty_payload);

    uint8_t frame[RS485_MAX_FRAME_SIZE];
    uint16_t frame_len = 0;

    bool ok = rs485_build_frame(0x02, NULL, 0, frame, &frame_len);
    assert(ok == true);
    assert(frame[2] == 1);  /* LENGTH = just msg_type */
    /* Total: SYNC(2) + LENGTH(1) + MSG_TYPE(1) + CRC(2) = 6 */
    assert(frame_len == 6);

    PASS();
}

static void test_frame_payload_too_large(void)
{
    TEST(frame_build_payload_too_large);

    uint8_t big_payload[RS485_MAX_PAYLOAD + 1];
    memset(big_payload, 0xAA, sizeof(big_payload));
    uint8_t frame[RS485_MAX_FRAME_SIZE + 10];
    uint16_t frame_len = 0;

    bool ok = rs485_build_frame(0x01, big_payload, RS485_MAX_PAYLOAD + 1,
                                frame, &frame_len);
    assert(ok == false);

    PASS();
}

/* ============================================================================
 * Frame Parsing Tests
 * ============================================================================ */

static void test_parse_valid_frame(void)
{
    TEST(frame_parse_valid_roundtrip);

    /* Build a frame, then parse it */
    uint8_t payload[] = {0x01, 0x07, 0x04, 0x11, 0x22, 0x33, 0x44,
                         0x55, 0x66, 0x77, 0x00, 0x01, 0x00, 0x00};
    uint8_t frame[RS485_MAX_FRAME_SIZE];
    uint16_t frame_len = 0;

    rs485_build_frame(RS485_MSG_TAP_EVENT, payload, 14, frame, &frame_len);

    rs485_message_t msg;
    bool ok = rs485_parse_frame(frame, frame_len, &msg);
    assert(ok == true);
    assert(msg.msg_type == RS485_MSG_TAP_EVENT);
    assert(msg.payload_len == 14);
    assert(msg.payload[0] == 0x01);
    assert(msg.payload[1] == 0x07);

    PASS();
}

static void test_parse_bad_sync(void)
{
    TEST(frame_parse_bad_sync_bytes);

    uint8_t frame[] = {0xBB, 0x55, 0x02, 0x01, 0x42, 0x00, 0x00};
    rs485_message_t msg;

    bool ok = rs485_parse_frame(frame, sizeof(frame), &msg);
    assert(ok == false);

    PASS();
}

static void test_parse_bad_crc(void)
{
    TEST(frame_parse_bad_crc);

    /* Build a valid frame, then corrupt the CRC */
    uint8_t payload[] = {0x42};
    uint8_t frame[RS485_MAX_FRAME_SIZE];
    uint16_t frame_len = 0;

    rs485_build_frame(0x01, payload, 1, frame, &frame_len);

    /* Corrupt CRC */
    frame[frame_len - 1] ^= 0xFF;

    rs485_message_t msg;
    bool ok = rs485_parse_frame(frame, frame_len, &msg);
    assert(ok == false);

    PASS();
}

static void test_parse_truncated_frame(void)
{
    TEST(frame_parse_truncated);

    uint8_t frame[] = {0xAA, 0x55, 0x03};  /* Too short */
    rs485_message_t msg;

    bool ok = rs485_parse_frame(frame, sizeof(frame), &msg);
    assert(ok == false);

    PASS();
}

static void test_parse_config_message(void)
{
    TEST(frame_parse_config_update);

    /* Build a config update message: key=0x02, data=0x03 (set classify mode) */
    uint8_t payload[] = {RS485_CONFIG_CLASSIFY_MODE, 0x03};
    uint8_t frame[RS485_MAX_FRAME_SIZE];
    uint16_t frame_len = 0;

    rs485_build_frame(RS485_MSG_CONFIG_UPDATE, payload, 2, frame, &frame_len);

    rs485_message_t msg;
    bool ok = rs485_parse_frame(frame, frame_len, &msg);
    assert(ok == true);
    assert(msg.msg_type == RS485_MSG_CONFIG_UPDATE);
    assert(msg.payload_len == 2);
    assert(msg.payload[0] == RS485_CONFIG_CLASSIFY_MODE);
    assert(msg.payload[1] == 0x03);

    PASS();
}

/* ============================================================================
 * Byte Ordering Tests
 * ============================================================================ */

static void test_heartbeat_byte_order(void)
{
    TEST(heartbeat_frame_little_endian);

    /* Build a heartbeat frame and verify little-endian encoding */
    uint8_t payload[11];
    uint8_t pos = 0;

    uint8_t status = 0x00;
    uint32_t uptime = 0x12345678;
    uint32_t taps = 0xAABBCCDD;
    int16_t temp = 0x0123;  /* 29.1°C */

    payload[pos++] = status;
    payload[pos++] = (uint8_t)(uptime >>  0);
    payload[pos++] = (uint8_t)(uptime >>  8);
    payload[pos++] = (uint8_t)(uptime >> 16);
    payload[pos++] = (uint8_t)(uptime >> 24);
    payload[pos++] = (uint8_t)(taps >>  0);
    payload[pos++] = (uint8_t)(taps >>  8);
    payload[pos++] = (uint8_t)(taps >> 16);
    payload[pos++] = (uint8_t)(taps >> 24);
    payload[pos++] = (uint8_t)((uint16_t)temp >>  0);
    payload[pos++] = (uint8_t)((uint16_t)temp >>  8);

    uint8_t frame[RS485_MAX_FRAME_SIZE];
    uint16_t frame_len = 0;
    rs485_build_frame(RS485_MSG_HEARTBEAT, payload, 11, frame, &frame_len);

    /* Parse and verify */
    rs485_message_t msg;
    bool ok = rs485_parse_frame(frame, frame_len, &msg);
    assert(ok == true);
    assert(msg.msg_type == RS485_MSG_HEARTBEAT);

    /* Verify little-endian uptime at offset 1 */
    uint32_t parsed_uptime = (uint32_t)msg.payload[1] |
                             ((uint32_t)msg.payload[2] << 8) |
                             ((uint32_t)msg.payload[3] << 16) |
                             ((uint32_t)msg.payload[4] << 24);
    assert(parsed_uptime == 0x12345678);

    /* Verify little-endian tap_count at offset 5 */
    uint32_t parsed_taps = (uint32_t)msg.payload[5] |
                           ((uint32_t)msg.payload[6] << 8) |
                           ((uint32_t)msg.payload[7] << 16) |
                           ((uint32_t)msg.payload[8] << 24);
    assert(parsed_taps == 0xAABBCCDD);

    /* Verify little-endian temperature at offset 9 */
    int16_t parsed_temp = (int16_t)((uint16_t)msg.payload[9] |
                                    ((uint16_t)msg.payload[10] << 8));
    assert(parsed_temp == 0x0123);

    PASS();
}

static void test_tap_event_byte_order(void)
{
    TEST(tap_event_frame_little_endian);

    /* Build a tap event payload manually */
    uint8_t payload[14];
    uint8_t pos = 0;

    payload[pos++] = CARD_TYPE_SENIOR_RTC;
    payload[pos++] = 7;  /* uid_len */
    payload[pos++] = 0x04;
    payload[pos++] = 0xA2;
    payload[pos++] = 0x11;
    payload[pos++] = 0x22;
    payload[pos++] = 0x33;
    payload[pos++] = 0x44;
    payload[pos++] = 0x55;

    uint32_t timestamp = 0xDEADBEEF;
    payload[pos++] = (uint8_t)(timestamp >>  0);
    payload[pos++] = (uint8_t)(timestamp >>  8);
    payload[pos++] = (uint8_t)(timestamp >> 16);
    payload[pos++] = (uint8_t)(timestamp >> 24);

    payload[pos++] = CLASSIFY_MODE_UID;

    uint8_t frame[RS485_MAX_FRAME_SIZE];
    uint16_t frame_len = 0;
    rs485_build_frame(RS485_MSG_TAP_EVENT, payload, pos, frame, &frame_len);

    rs485_message_t msg;
    bool ok = rs485_parse_frame(frame, frame_len, &msg);
    assert(ok == true);
    assert(msg.payload[0] == CARD_TYPE_SENIOR_RTC);
    assert(msg.payload[1] == 7);

    /* Verify timestamp is little-endian at offset 9 */
    uint32_t parsed_ts = (uint32_t)msg.payload[9] |
                         ((uint32_t)msg.payload[10] << 8) |
                         ((uint32_t)msg.payload[11] << 16) |
                         ((uint32_t)msg.payload[12] << 24);
    assert(parsed_ts == 0xDEADBEEF);

    assert(msg.payload[13] == CLASSIFY_MODE_UID);

    PASS();
}

/* ============================================================================
 * Main
 * ============================================================================ */

int main(void)
{
    printf("=== SafeCross RS-485 Framing Unit Tests ===\n\n");

    /* CRC tests */
    printf("[CRC-16/MODBUS]\n");
    test_crc_empty();
    test_crc_single_byte();
    test_crc_known_vector_1();
    test_crc_known_vector_2();
    test_crc_modbus_example();

    /* Frame building tests */
    printf("\n[Frame building]\n");
    test_frame_sync_bytes();
    test_frame_length_field();
    test_frame_msg_type();
    test_frame_total_length();
    test_frame_crc_position();
    test_frame_empty_payload();
    test_frame_payload_too_large();

    /* Frame parsing tests */
    printf("\n[Frame parsing]\n");
    test_parse_valid_frame();
    test_parse_bad_sync();
    test_parse_bad_crc();
    test_parse_truncated_frame();
    test_parse_config_message();

    /* Byte ordering tests */
    printf("\n[Byte ordering]\n");
    test_heartbeat_byte_order();
    test_tap_event_byte_order();

    printf("\n=== Results: %d/%d tests passed ===\n", tests_passed, tests_run);

    return (tests_passed == tests_run) ? 0 : 1;
}
