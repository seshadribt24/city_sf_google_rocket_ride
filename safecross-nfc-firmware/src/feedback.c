/**
 * @file feedback.c
 * @brief LED ring and buzzer feedback implementation
 */

#include "feedback.h"
#include "ws2812b.h"
#include "pin_config.h"

#ifndef UNIT_TEST
#include "stm32f4xx_hal.h"

/* ============================================================================
 * Sine Lookup Table for Breathing Effect
 * ============================================================================ */

/**
 * @brief 64-entry sine table scaled 0-255 for breathing brightness
 *
 * Maps a phase (0-63) to a brightness level using a sine wave.
 */
static const uint8_t sine_lut[64] = {
    128, 140, 153, 165, 177, 188, 199, 209,
    218, 226, 234, 240, 245, 250, 253, 254,
    255, 254, 253, 250, 245, 240, 234, 226,
    218, 209, 199, 188, 177, 165, 153, 140,
    128, 115, 102,  90,  78,  67,  56,  46,
     37,  29,  21,  15,  10,   5,   2,   1,
      0,   1,   2,   5,  10,  15,  21,  29,
     37,  46,  56,  67,  78,  90, 102, 115
};

/* ============================================================================
 * Private State
 * ============================================================================ */

/** Current feedback state */
static feedback_state_t fb_state = FEEDBACK_STATE_IDLE;

/** Timestamp when current state was entered */
static uint32_t fb_state_start = 0;

/** TIM3 handle for buzzer PWM */
static TIM_HandleTypeDef htim_buzzer;

/** Buzzer stop time (0 = not active) */
static uint32_t buzzer_stop_time = 0;

/** Double-beep state: second tone start time */
static uint32_t buzzer_second_tone_time = 0;
static bool buzzer_second_tone_pending = false;

/* ============================================================================
 * Private Helpers — Buzzer
 * ============================================================================ */

/**
 * @brief Initialize TIM3 for buzzer PWM on PB5
 */
static void buzzer_init(void)
{
    GPIO_InitTypeDef gpio = {0};

    /* Enable TIM3 clock */
    __HAL_RCC_TIM3_CLK_ENABLE();

    /* PB5 — TIM3_CH2, AF2 */
    gpio.Pin       = BUZZER_PIN;
    gpio.Mode      = GPIO_MODE_AF_PP;
    gpio.Pull      = GPIO_NOPULL;
    gpio.Speed     = GPIO_SPEED_FREQ_LOW;
    gpio.Alternate = BUZZER_TIM_AF;
    HAL_GPIO_Init(BUZZER_PORT, &gpio);

    /* TIM3 base configuration — will be reconfigured per tone */
    htim_buzzer.Instance               = BUZZER_TIM_INSTANCE;
    htim_buzzer.Init.Prescaler         = 0;
    htim_buzzer.Init.CounterMode       = TIM_COUNTERMODE_UP;
    htim_buzzer.Init.Period            = 0xFFFF;
    htim_buzzer.Init.ClockDivision     = TIM_CLOCKDIVISION_DIV1;
    htim_buzzer.Init.AutoReloadPreload = TIM_AUTORELOAD_PRELOAD_ENABLE;
    HAL_TIM_PWM_Init(&htim_buzzer);

    /* PWM channel config */
    TIM_OC_InitTypeDef oc = {0};
    oc.OCMode    = TIM_OCMODE_PWM1;
    oc.Pulse     = 0;
    oc.OCPolarity = TIM_OCPOLARITY_HIGH;
    HAL_TIM_PWM_ConfigChannel(&htim_buzzer, &oc, BUZZER_TIM_CHANNEL);
}

/**
 * @brief Start a buzzer tone at the given frequency
 * @param freq_hz Tone frequency in Hz
 */
static void buzzer_start(uint16_t freq_hz)
{
    if (freq_hz == 0) {
        return;
    }

    /* Calculate timer period: TIM3 clock = 84 MHz
     * For freq_hz, need ARR such that 84MHz / (PSC+1) / (ARR+1) = freq_hz
     * Use PSC=0: ARR = 84MHz / freq_hz - 1 */
    uint32_t arr = (BUZZER_TIM_CLK_HZ / freq_hz) - 1;
    if (arr > 0xFFFF) {
        /* Frequency too low for no prescaler — use prescaler */
        htim_buzzer.Init.Prescaler = 83;  /* 84MHz / 84 = 1MHz */
        arr = (1000000 / freq_hz) - 1;
    } else {
        htim_buzzer.Init.Prescaler = 0;
    }

    htim_buzzer.Init.Period = (uint16_t)arr;
    HAL_TIM_PWM_Init(&htim_buzzer);

    /* 50% duty cycle */
    TIM_OC_InitTypeDef oc = {0};
    oc.OCMode    = TIM_OCMODE_PWM1;
    oc.Pulse     = (uint16_t)(arr / 2);
    oc.OCPolarity = TIM_OCPOLARITY_HIGH;
    HAL_TIM_PWM_ConfigChannel(&htim_buzzer, &oc, BUZZER_TIM_CHANNEL);

    HAL_TIM_PWM_Start(&htim_buzzer, BUZZER_TIM_CHANNEL);
}

/**
 * @brief Stop the buzzer
 */
static void buzzer_stop(void)
{
    HAL_TIM_PWM_Stop(&htim_buzzer, BUZZER_TIM_CHANNEL);
}

/* ============================================================================
 * Private Helpers — LED Patterns
 * ============================================================================ */

/**
 * @brief Apply breathing effect with given color and period
 */
static void led_breathing(uint8_t r, uint8_t g, uint8_t b,
                          uint32_t period_ms, uint32_t now)
{
    uint32_t elapsed = (now - fb_state_start) % period_ms;
    uint32_t phase = (elapsed * 64) / period_ms;
    uint8_t brightness = sine_lut[phase & 63];

    /* Scale color by brightness */
    uint8_t sr = (uint8_t)((uint16_t)r * brightness / 255);
    uint8_t sg = (uint8_t)((uint16_t)g * brightness / 255);
    uint8_t sb = (uint8_t)((uint16_t)b * brightness / 255);

    ws2812b_set_all(sr, sg, sb);
    ws2812b_update();
}

/* ============================================================================
 * Public API
 * ============================================================================ */

void feedback_init(void)
{
    ws2812b_init();
    buzzer_init();

    fb_state = FEEDBACK_STATE_IDLE;
    fb_state_start = HAL_GetTick();
    buzzer_stop_time = 0;
    buzzer_second_tone_pending = false;
}

void feedback_update(void)
{
    uint32_t now = HAL_GetTick();

    /* Handle buzzer timing */
    if (buzzer_stop_time != 0 && (now >= buzzer_stop_time)) {
        buzzer_stop();
        buzzer_stop_time = 0;

        /* Check if double-beep second tone is pending */
        if (buzzer_second_tone_pending) {
            buzzer_second_tone_time = now + FEEDBACK_BUZZER_GAP_MS;
        }
    }

    /* Start second tone of double-beep after gap */
    if (buzzer_second_tone_pending && buzzer_second_tone_time != 0 &&
        now >= buzzer_second_tone_time) {
        buzzer_start(FEEDBACK_BUZZER_TEST_HZ);
        buzzer_stop_time = now + FEEDBACK_BUZZER_TEST_MS;
        buzzer_second_tone_pending = false;
        buzzer_second_tone_time = 0;
    }

    /* Skip LED update if DMA is busy */
    if (ws2812b_is_busy()) {
        return;
    }

    switch (fb_state) {
    case FEEDBACK_STATE_IDLE:
        /* Dim white breathing pulse, 3-second cycle */
        led_breathing(FEEDBACK_COLOR_WHITE_R, FEEDBACK_COLOR_WHITE_G,
                      FEEDBACK_COLOR_WHITE_B, FEEDBACK_IDLE_PERIOD_MS, now);
        break;

    case FEEDBACK_STATE_GREEN_SOLID:
        /* All green, solid for duration then return to idle */
        if ((now - fb_state_start) < FEEDBACK_GREEN_DURATION_MS) {
            ws2812b_set_all(FEEDBACK_COLOR_GREEN_R, FEEDBACK_COLOR_GREEN_G,
                            FEEDBACK_COLOR_GREEN_B);
            ws2812b_update();
        } else {
            fb_state = FEEDBACK_STATE_IDLE;
            fb_state_start = now;
        }
        break;

    case FEEDBACK_STATE_AMBER_FLASH:
        /* Single amber flash for duration then return to idle */
        if ((now - fb_state_start) < FEEDBACK_AMBER_DURATION_MS) {
            ws2812b_set_all(FEEDBACK_COLOR_AMBER_R, FEEDBACK_COLOR_AMBER_G,
                            FEEDBACK_COLOR_AMBER_B);
            ws2812b_update();
        } else {
            fb_state = FEEDBACK_STATE_IDLE;
            fb_state_start = now;
        }
        break;

    case FEEDBACK_STATE_BLUE_SOLID:
        /* All blue, solid for duration then return to idle */
        if ((now - fb_state_start) < FEEDBACK_BLUE_DURATION_MS) {
            ws2812b_set_all(FEEDBACK_COLOR_BLUE_R, FEEDBACK_COLOR_BLUE_G,
                            FEEDBACK_COLOR_BLUE_B);
            ws2812b_update();
        } else {
            fb_state = FEEDBACK_STATE_IDLE;
            fb_state_start = now;
        }
        break;

    case FEEDBACK_STATE_RED_FLASH:
        /* Single red flash for duration then return to idle */
        if ((now - fb_state_start) < FEEDBACK_RED_DURATION_MS) {
            ws2812b_set_all(FEEDBACK_COLOR_RED_R, FEEDBACK_COLOR_RED_G,
                            FEEDBACK_COLOR_RED_B);
            ws2812b_update();
        } else {
            fb_state = FEEDBACK_STATE_IDLE;
            fb_state_start = now;
        }
        break;

    case FEEDBACK_STATE_ERROR_BREATHING:
        /* Red breathing pulse, 1-second cycle — stays until cleared */
        led_breathing(FEEDBACK_COLOR_RED_R, FEEDBACK_COLOR_RED_G,
                      FEEDBACK_COLOR_RED_B, FEEDBACK_ERROR_PERIOD_MS, now);
        break;
    }
}

void feedback_trigger(card_type_t card_type)
{
    uint32_t now = HAL_GetTick();
    fb_state_start = now;

    switch (card_type) {
    case CARD_TYPE_SENIOR_RTC:
    case CARD_TYPE_DISABLED_RTC:
        fb_state = FEEDBACK_STATE_GREEN_SOLID;
        /* Single 100ms tone at 2kHz */
        buzzer_start(FEEDBACK_BUZZER_FREQ_HZ);
        buzzer_stop_time = now + FEEDBACK_BUZZER_TONE_MS;
        buzzer_second_tone_pending = false;
        break;

    case CARD_TYPE_STANDARD:
    case CARD_TYPE_YOUTH:
        fb_state = FEEDBACK_STATE_AMBER_FLASH;
        /* No buzzer */
        break;

    case CARD_TYPE_DESFIRE_DETECTED:
        fb_state = FEEDBACK_STATE_BLUE_SOLID;
        /* Double 80ms tone at 1.5kHz */
        buzzer_start(FEEDBACK_BUZZER_TEST_HZ);
        buzzer_stop_time = now + FEEDBACK_BUZZER_TEST_MS;
        buzzer_second_tone_pending = true;
        break;

    case CARD_TYPE_UNKNOWN:
    default:
        fb_state = FEEDBACK_STATE_RED_FLASH;
        /* No buzzer for errors */
        break;

    case CARD_TYPE_NONE:
        /* No feedback */
        break;
    }
}

void feedback_set_error(void)
{
    fb_state = FEEDBACK_STATE_ERROR_BREATHING;
    fb_state_start = HAL_GetTick();
}

void feedback_set_idle(void)
{
    fb_state = FEEDBACK_STATE_IDLE;
    fb_state_start = HAL_GetTick();
}

feedback_state_t feedback_get_state(void)
{
    return fb_state;
}

#endif /* UNIT_TEST */
