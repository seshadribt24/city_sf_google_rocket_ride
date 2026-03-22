/**
 * @file test_classifier.c
 * @brief Unit tests for the card type classifier module
 *
 * Tests all three classification modes (APPDIR, UID, ANY) with
 * various card data scenarios. Compiles and runs on x86 with no
 * embedded dependencies.
 */

#include <assert.h>
#include <stdio.h>
#include <string.h>
#include <stdint.h>

/* Build with -DUNIT_TEST to exclude HAL code */
#include "../src/classifier.h"

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

/**
 * @brief Create a blank card info struct
 */
static nfc_card_info_t make_card(void)
{
    nfc_card_info_t card;
    memset(&card, 0, sizeof(card));
    return card;
}

/* ============================================================================
 * Mode ANY Tests
 * ============================================================================ */

static void test_any_desfire_detected(void)
{
    TEST(any_mode_desfire_card);

    nfc_card_info_t card = make_card();
    card.is_desfire = true;
    card.uid_len = 7;
    card.uid[0] = 0x04; card.uid[1] = 0x11; card.uid[2] = 0x22;

    card_type_t result = classifier_classify_with_mode(&card, CLASSIFY_MODE_ANY);
    assert(result == CARD_TYPE_DESFIRE_DETECTED);

    PASS();
}

static void test_any_non_desfire(void)
{
    TEST(any_mode_non_desfire_card);

    nfc_card_info_t card = make_card();
    card.is_desfire = false;
    card.uid_len = 4;

    card_type_t result = classifier_classify_with_mode(&card, CLASSIFY_MODE_ANY);
    assert(result == CARD_TYPE_UNKNOWN);

    PASS();
}

static void test_any_null_card(void)
{
    TEST(any_mode_null_card);

    card_type_t result = classifier_classify_with_mode(NULL, CLASSIFY_MODE_ANY);
    assert(result == CARD_TYPE_NONE);

    PASS();
}

/* ============================================================================
 * Mode UID Tests
 * ============================================================================ */

static void test_uid_senior_match(void)
{
    TEST(uid_mode_senior_prefix_match);

    classifier_init();  /* Load default UID table */

    nfc_card_info_t card = make_card();
    card.uid_len = 7;
    card.uid[0] = 0x04;
    card.uid[1] = 0xA2;
    card.uid[2] = 0x33;
    card.uid[3] = 0x44;
    card.uid[4] = 0x55;
    card.uid[5] = 0x66;
    card.uid[6] = 0x77;

    card_type_t result = classifier_classify_with_mode(&card, CLASSIFY_MODE_UID);
    assert(result == CARD_TYPE_SENIOR_RTC);

    PASS();
}

static void test_uid_disabled_match(void)
{
    TEST(uid_mode_disabled_prefix_match);

    classifier_init();

    nfc_card_info_t card = make_card();
    card.uid_len = 7;
    card.uid[0] = 0x04;
    card.uid[1] = 0xB1;
    card.uid[2] = 0xAA;
    card.uid[3] = 0xBB;
    card.uid[4] = 0xCC;
    card.uid[5] = 0xDD;
    card.uid[6] = 0xEE;

    card_type_t result = classifier_classify_with_mode(&card, CLASSIFY_MODE_UID);
    assert(result == CARD_TYPE_DISABLED_RTC);

    PASS();
}

static void test_uid_youth_match(void)
{
    TEST(uid_mode_youth_prefix_match);

    classifier_init();

    nfc_card_info_t card = make_card();
    card.uid_len = 7;
    card.uid[0] = 0x04;
    card.uid[1] = 0xC0;
    card.uid[2] = 0x11;

    card_type_t result = classifier_classify_with_mode(&card, CLASSIFY_MODE_UID);
    assert(result == CARD_TYPE_YOUTH);

    PASS();
}

static void test_uid_no_match(void)
{
    TEST(uid_mode_unknown_prefix);

    classifier_init();

    nfc_card_info_t card = make_card();
    card.uid_len = 7;
    card.uid[0] = 0x04;
    card.uid[1] = 0xFF;
    card.uid[2] = 0xFF;

    card_type_t result = classifier_classify_with_mode(&card, CLASSIFY_MODE_UID);
    assert(result == CARD_TYPE_STANDARD);

    PASS();
}

static void test_uid_empty_uid(void)
{
    TEST(uid_mode_empty_uid);

    classifier_init();

    nfc_card_info_t card = make_card();
    card.uid_len = 0;

    card_type_t result = classifier_classify_with_mode(&card, CLASSIFY_MODE_UID);
    assert(result == CARD_TYPE_UNKNOWN);

    PASS();
}

static void test_uid_4byte_uid(void)
{
    TEST(uid_mode_4byte_uid_match);

    classifier_init();

    nfc_card_info_t card = make_card();
    card.uid_len = 4;
    card.uid[0] = 0x04;
    card.uid[1] = 0xA2;
    card.uid[2] = 0x99;
    card.uid[3] = 0x88;

    card_type_t result = classifier_classify_with_mode(&card, CLASSIFY_MODE_UID);
    assert(result == CARD_TYPE_SENIOR_RTC);

    PASS();
}

/* ============================================================================
 * Mode APPDIR Tests
 * ============================================================================ */

static void test_appdir_card_data_senior(void)
{
    TEST(appdir_mode_card_data_senior);

    nfc_card_info_t card = make_card();
    card.is_desfire = true;
    card.card_data_len = 1;
    card.card_data[0] = CLIPPER_TYPE_BYTE_SENIOR;
    card.num_aids = 1;

    card_type_t result = classifier_classify_with_mode(&card, CLASSIFY_MODE_APPDIR);
    assert(result == CARD_TYPE_SENIOR_RTC);

    PASS();
}

static void test_appdir_card_data_disabled(void)
{
    TEST(appdir_mode_card_data_disabled);

    nfc_card_info_t card = make_card();
    card.is_desfire = true;
    card.card_data_len = 1;
    card.card_data[0] = CLIPPER_TYPE_BYTE_DISABLED;
    card.num_aids = 1;

    card_type_t result = classifier_classify_with_mode(&card, CLASSIFY_MODE_APPDIR);
    assert(result == CARD_TYPE_DISABLED_RTC);

    PASS();
}

static void test_appdir_card_data_standard(void)
{
    TEST(appdir_mode_card_data_standard);

    nfc_card_info_t card = make_card();
    card.is_desfire = true;
    card.card_data_len = 1;
    card.card_data[0] = CLIPPER_TYPE_BYTE_STANDARD;
    card.num_aids = 1;

    card_type_t result = classifier_classify_with_mode(&card, CLASSIFY_MODE_APPDIR);
    assert(result == CARD_TYPE_STANDARD);

    PASS();
}

static void test_appdir_card_data_youth(void)
{
    TEST(appdir_mode_card_data_youth);

    nfc_card_info_t card = make_card();
    card.is_desfire = true;
    card.card_data_len = 1;
    card.card_data[0] = CLIPPER_TYPE_BYTE_YOUTH;
    card.num_aids = 1;

    card_type_t result = classifier_classify_with_mode(&card, CLASSIFY_MODE_APPDIR);
    assert(result == CARD_TYPE_YOUTH);

    PASS();
}

static void test_appdir_empty_aids(void)
{
    TEST(appdir_mode_empty_aid_list);

    nfc_card_info_t card = make_card();
    card.is_desfire = true;
    card.num_aids = 0;
    card.card_data_len = 0;

    card_type_t result = classifier_classify_with_mode(&card, CLASSIFY_MODE_APPDIR);
    assert(result == CARD_TYPE_UNKNOWN);

    PASS();
}

static void test_appdir_not_desfire(void)
{
    TEST(appdir_mode_non_desfire);

    nfc_card_info_t card = make_card();
    card.is_desfire = false;

    card_type_t result = classifier_classify_with_mode(&card, CLASSIFY_MODE_APPDIR);
    assert(result == CARD_TYPE_UNKNOWN);

    PASS();
}

static void test_appdir_aid_pattern_senior(void)
{
    TEST(appdir_mode_aid_pattern_senior);

    nfc_card_info_t card = make_card();
    card.is_desfire = true;
    card.card_data_len = 0;  /* No file data — use AID analysis */
    card.num_aids = 2;
    /* AID 0x000005 — in Senior range */
    card.aid_list[0] = 0x05;
    card.aid_list[1] = 0x00;
    card.aid_list[2] = 0x00;
    /* AID 0x000001 */
    card.aid_list[3] = 0x01;
    card.aid_list[4] = 0x00;
    card.aid_list[5] = 0x00;

    card_type_t result = classifier_classify_with_mode(&card, CLASSIFY_MODE_APPDIR);
    assert(result == CARD_TYPE_SENIOR_RTC);

    PASS();
}

/* ============================================================================
 * UID Table Update Tests
 * ============================================================================ */

static void test_table_update_valid(void)
{
    TEST(uid_table_update_valid);

    classifier_init();

    /* Create a new table with 2 entries:
     * Entry 1: prefix_len=2, prefix=0x04 0xDD 0x00, type=SENIOR
     * Entry 2: prefix_len=2, prefix=0x04 0xEE 0x00, type=DISABLED */
    uint8_t table_data[] = {
        2, 0x04, 0xDD, 0x00, CARD_TYPE_SENIOR_RTC,
        2, 0x04, 0xEE, 0x00, CARD_TYPE_DISABLED_RTC,
    };

    bool ok = classifier_update_uid_table(table_data, sizeof(table_data));
    assert(ok == true);

    /* Verify new table works */
    nfc_card_info_t card = make_card();
    card.uid_len = 7;
    card.uid[0] = 0x04;
    card.uid[1] = 0xDD;
    card.uid[2] = 0x11;

    card_type_t result = classifier_classify_with_mode(&card, CLASSIFY_MODE_UID);
    assert(result == CARD_TYPE_SENIOR_RTC);

    /* Verify old table entry no longer matches */
    card.uid[1] = 0xA2;
    result = classifier_classify_with_mode(&card, CLASSIFY_MODE_UID);
    assert(result == CARD_TYPE_STANDARD);  /* No match → standard */

    PASS();
}

static void test_table_update_invalid_size(void)
{
    TEST(uid_table_update_invalid_size);

    classifier_init();

    /* 7 bytes is not a multiple of 5 */
    uint8_t bad_data[] = {2, 0x04, 0xDD, 0x00, CARD_TYPE_SENIOR_RTC, 0x00, 0x00};
    bool ok = classifier_update_uid_table(bad_data, sizeof(bad_data));
    assert(ok == false);

    PASS();
}

static void test_table_update_null(void)
{
    TEST(uid_table_update_null_data);

    bool ok = classifier_update_uid_table(NULL, 0);
    assert(ok == false);

    PASS();
}

static void test_table_update_bad_prefix_len(void)
{
    TEST(uid_table_update_bad_prefix_len);

    classifier_init();

    /* prefix_len=0 is invalid */
    uint8_t bad_data[] = {0, 0x04, 0xDD, 0x00, CARD_TYPE_SENIOR_RTC};
    bool ok = classifier_update_uid_table(bad_data, sizeof(bad_data));
    assert(ok == false);

    PASS();
}

/* ============================================================================
 * Invalid Mode Test
 * ============================================================================ */

static void test_invalid_mode(void)
{
    TEST(invalid_classify_mode);

    nfc_card_info_t card = make_card();
    card.is_desfire = true;

    card_type_t result = classifier_classify_with_mode(&card, 99);
    assert(result == CARD_TYPE_UNKNOWN);

    PASS();
}

/* ============================================================================
 * Main
 * ============================================================================ */

int main(void)
{
    printf("=== SafeCross Classifier Unit Tests ===\n\n");

    /* ANY mode tests */
    printf("[ANY mode]\n");
    test_any_desfire_detected();
    test_any_non_desfire();
    test_any_null_card();

    /* UID mode tests */
    printf("\n[UID mode]\n");
    test_uid_senior_match();
    test_uid_disabled_match();
    test_uid_youth_match();
    test_uid_no_match();
    test_uid_empty_uid();
    test_uid_4byte_uid();

    /* APPDIR mode tests */
    printf("\n[APPDIR mode]\n");
    test_appdir_card_data_senior();
    test_appdir_card_data_disabled();
    test_appdir_card_data_standard();
    test_appdir_card_data_youth();
    test_appdir_empty_aids();
    test_appdir_not_desfire();
    test_appdir_aid_pattern_senior();

    /* UID table update tests */
    printf("\n[UID table updates]\n");
    test_table_update_valid();
    test_table_update_invalid_size();
    test_table_update_null();
    test_table_update_bad_prefix_len();

    /* Edge cases */
    printf("\n[Edge cases]\n");
    test_invalid_mode();

    printf("\n=== Results: %d/%d tests passed ===\n", tests_passed, tests_run);

    return (tests_passed == tests_run) ? 0 : 1;
}
