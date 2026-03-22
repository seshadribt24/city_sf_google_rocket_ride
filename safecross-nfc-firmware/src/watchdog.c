/**
 * @file watchdog.c
 * @brief Independent Watchdog (IWDG) implementation
 */

#include "watchdog.h"

#ifndef UNIT_TEST
#include "stm32f4xx_hal.h"

/** IWDG handle */
static IWDG_HandleTypeDef hiwdg;

/** Persistent data in .noinit section — not zeroed on reset */
static watchdog_noinit_t watchdog_noinit __attribute__((section(".noinit")));

bool watchdog_check_reset_cause(void)
{
    bool was_watchdog_reset = false;

    /* Check if the IWDG caused the last reset */
    if (__HAL_RCC_GET_FLAG(RCC_FLAG_IWDGRST)) {
        was_watchdog_reset = true;

        /* Validate the noinit region */
        if (watchdog_noinit.magic == WATCHDOG_NOINIT_MAGIC) {
            watchdog_noinit.watchdog_reset_count++;
        } else {
            /* First time or power-on — initialize */
            watchdog_noinit.magic = WATCHDOG_NOINIT_MAGIC;
            watchdog_noinit.watchdog_reset_count = 1;
        }
    } else {
        /* Normal power-on reset — initialize the noinit region */
        if (watchdog_noinit.magic != WATCHDOG_NOINIT_MAGIC) {
            watchdog_noinit.magic = WATCHDOG_NOINIT_MAGIC;
            watchdog_noinit.watchdog_reset_count = 0;
        }
    }

    /* Clear all reset flags */
    __HAL_RCC_CLEAR_RESET_FLAGS();

    return was_watchdog_reset;
}

uint32_t watchdog_get_reset_count(void)
{
    if (watchdog_noinit.magic == WATCHDOG_NOINIT_MAGIC) {
        return watchdog_noinit.watchdog_reset_count;
    }
    return 0;
}

void watchdog_init(void)
{
    hiwdg.Instance       = IWDG;
    hiwdg.Init.Prescaler = WATCHDOG_PRESCALER;
    hiwdg.Init.Reload    = WATCHDOG_RELOAD_VALUE;

    HAL_IWDG_Init(&hiwdg);
}

void watchdog_kick(void)
{
    HAL_IWDG_Refresh(&hiwdg);
}

#endif /* UNIT_TEST */
