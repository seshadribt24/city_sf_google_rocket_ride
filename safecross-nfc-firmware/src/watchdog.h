/**
 * @file watchdog.h
 * @brief Independent Watchdog (IWDG) management for SafeCross NFC Reader
 *
 * Configures the STM32 IWDG with a ~4 second timeout. The main loop
 * must call watchdog_kick() on every iteration. If the firmware hangs,
 * the MCU will hard-reset after the timeout expires.
 */

#ifndef WATCHDOG_H
#define WATCHDOG_H

#include <stdint.h>
#include <stdbool.h>

/** IWDG prescaler — divides 32kHz LSI */
#define WATCHDOG_PRESCALER          IWDG_PRESCALER_256

/** IWDG reload value — 256 * 500 / 32000 = 4.0 seconds */
#define WATCHDOG_RELOAD_VALUE       500

/** Sentinel value to validate noinit region across resets */
#define WATCHDOG_NOINIT_MAGIC       0xDEAD1234

/**
 * @brief Persistent reset counter — survives soft resets
 *
 * Placed in .noinit section so it is not zero-initialized on reset.
 * The magic field validates that the data is not garbage after power-on.
 */
typedef struct {
    uint32_t magic;
    uint32_t watchdog_reset_count;
} watchdog_noinit_t;

/**
 * @brief Check if the previous reset was caused by the watchdog
 * @return true if the last reset was a watchdog reset
 *
 * Call this BEFORE watchdog_init(). Reads RCC reset flags and
 * updates the persistent counter if a watchdog reset is detected.
 */
bool watchdog_check_reset_cause(void);

/**
 * @brief Get the number of watchdog resets since power-on
 * @return Watchdog reset count from the noinit region
 */
uint32_t watchdog_get_reset_count(void);

/**
 * @brief Initialize the Independent Watchdog (IWDG)
 *
 * Once started, the IWDG cannot be stopped. The main loop must
 * call watchdog_kick() at least every 4 seconds.
 */
void watchdog_init(void);

/**
 * @brief Reload the watchdog timer (kick the dog)
 *
 * Must be called in the main loop to prevent a watchdog reset.
 */
void watchdog_kick(void);

#endif /* WATCHDOG_H */
