/**
 * @file ws2812b.h
 * @brief WS2812B LED ring driver (DMA-based via TIM4_CH1)
 *
 * Drives a ring of WS2812B addressable LEDs using DMA transfers
 * through TIM4 Channel 1 PWM output on PB6.
 */

#ifndef WS2812B_H
#define WS2812B_H

#include <stdint.h>
#include <stdbool.h>

/** Number of LEDs in the ring */
#define WS2812B_NUM_LEDS        8

/** Bits per LED (8 green + 8 red + 8 blue) */
#define WS2812B_BITS_PER_LED    24

/** Reset pulse length in zero-bits (50us / 1.25us ≈ 40, use 50 for margin) */
#define WS2812B_RESET_SLOTS     50

/** Total DMA buffer size */
#define WS2812B_DMA_BUF_SIZE    (WS2812B_NUM_LEDS * WS2812B_BITS_PER_LED + WS2812B_RESET_SLOTS)

/* ============================================================================
 * Public API
 * ============================================================================ */

/**
 * @brief Initialize the WS2812B driver
 *
 * Configures TIM4_CH1, DMA1 Stream 0, and GPIO PB6.
 */
void ws2812b_init(void);

/**
 * @brief Set the color of a specific LED
 * @param index LED index (0 to WS2812B_NUM_LEDS-1)
 * @param r Red component (0-255)
 * @param g Green component (0-255)
 * @param b Blue component (0-255)
 */
void ws2812b_set_pixel(uint8_t index, uint8_t r, uint8_t g, uint8_t b);

/**
 * @brief Set all LEDs to the same color
 * @param r Red component (0-255)
 * @param g Green component (0-255)
 * @param b Blue component (0-255)
 */
void ws2812b_set_all(uint8_t r, uint8_t g, uint8_t b);

/**
 * @brief Clear all LEDs (turn off)
 */
void ws2812b_clear(void);

/**
 * @brief Push pixel data to the LED ring via DMA
 *
 * Triggers a DMA transfer. Non-blocking — the transfer completes
 * in the background (~300us for 8 LEDs). Do not call again until
 * the previous transfer is complete.
 */
void ws2812b_update(void);

/**
 * @brief Check if a DMA transfer is currently in progress
 * @return true if DMA is busy
 */
bool ws2812b_is_busy(void);

#endif /* WS2812B_H */
