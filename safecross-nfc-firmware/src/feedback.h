/**
 * @file feedback.h
 * @brief LED ring and buzzer feedback control
 *
 * Manages user feedback via WS2812B LED ring and piezo buzzer.
 * Uses a non-blocking state machine driven by HAL_GetTick().
 */

#ifndef FEEDBACK_H
#define FEEDBACK_H

#include <stdint.h>
#include <stdbool.h>
#include "classifier.h"

/* ============================================================================
 * Color Definitions (RGB)
 * ============================================================================ */

#define FEEDBACK_COLOR_GREEN_R      0
#define FEEDBACK_COLOR_GREEN_G      180
#define FEEDBACK_COLOR_GREEN_B      0

#define FEEDBACK_COLOR_AMBER_R      255
#define FEEDBACK_COLOR_AMBER_G      160
#define FEEDBACK_COLOR_AMBER_B      0

#define FEEDBACK_COLOR_BLUE_R       0
#define FEEDBACK_COLOR_BLUE_G       80
#define FEEDBACK_COLOR_BLUE_B       255

#define FEEDBACK_COLOR_RED_R        255
#define FEEDBACK_COLOR_RED_G        0
#define FEEDBACK_COLOR_RED_B        0

#define FEEDBACK_COLOR_WHITE_R      40
#define FEEDBACK_COLOR_WHITE_G      40
#define FEEDBACK_COLOR_WHITE_B      40

/* ============================================================================
 * Timing Constants (milliseconds)
 * ============================================================================ */

/** Idle breathing cycle period */
#define FEEDBACK_IDLE_PERIOD_MS     3000
/** Green solid duration (Senior/Disabled RTC) */
#define FEEDBACK_GREEN_DURATION_MS  1500
/** Amber flash duration (Standard/Youth) */
#define FEEDBACK_AMBER_DURATION_MS  500
/** Blue solid duration (DESFire test mode) */
#define FEEDBACK_BLUE_DURATION_MS   1500
/** Red flash duration (read error) */
#define FEEDBACK_RED_DURATION_MS    500
/** Error breathing cycle period */
#define FEEDBACK_ERROR_PERIOD_MS    1000

/** Buzzer tone duration for Senior/Disabled */
#define FEEDBACK_BUZZER_TONE_MS     100
/** Buzzer frequency for Senior/Disabled (Hz) */
#define FEEDBACK_BUZZER_FREQ_HZ     2000
/** Buzzer tone duration for DESFire test (double beep) */
#define FEEDBACK_BUZZER_TEST_MS     80
/** Buzzer frequency for DESFire test (Hz) */
#define FEEDBACK_BUZZER_TEST_HZ     1500
/** Gap between double-beep tones */
#define FEEDBACK_BUZZER_GAP_MS      60

/* ============================================================================
 * Feedback States
 * ============================================================================ */

/**
 * @brief Feedback state machine states
 */
typedef enum {
    FEEDBACK_STATE_IDLE,            /**< Dim white breathing pulse */
    FEEDBACK_STATE_GREEN_SOLID,     /**< All green (Senior/Disabled RTC) */
    FEEDBACK_STATE_AMBER_FLASH,     /**< Single amber flash (Standard/Youth) */
    FEEDBACK_STATE_BLUE_SOLID,      /**< All blue (DESFire test mode) */
    FEEDBACK_STATE_RED_FLASH,       /**< Single red flash (read error) */
    FEEDBACK_STATE_ERROR_BREATHING, /**< Red breathing (system error) */
} feedback_state_t;

/* ============================================================================
 * Public API
 * ============================================================================ */

/**
 * @brief Initialize the feedback module (LEDs + buzzer)
 */
void feedback_init(void);

/**
 * @brief Update the feedback state machine (call every main loop iteration)
 *
 * Handles LED animations (breathing, flashing) and buzzer timing
 * using HAL_GetTick() for non-blocking operation.
 */
void feedback_update(void);

/**
 * @brief Trigger feedback for a card classification result
 * @param card_type The classification result to show feedback for
 */
void feedback_trigger(card_type_t card_type);

/**
 * @brief Set the feedback to system error state
 *
 * Shows a red breathing LED pattern. Stays active until
 * feedback_set_idle() is called.
 */
void feedback_set_error(void);

/**
 * @brief Return to idle state (dim white breathing)
 */
void feedback_set_idle(void);

/**
 * @brief Get the current feedback state
 * @return Current state
 */
feedback_state_t feedback_get_state(void);

#endif /* FEEDBACK_H */
