/**
 * @file main.c
 * @brief SafeCross NFC Reader Firmware — Entry point and main loop
 *
 * Initializes all peripherals and runs the main polling loop:
 * NFC card detection → classification → LED/buzzer feedback → RS-485 reporting.
 */

#include "pin_config.h"
#include "watchdog.h"
#include "nfc.h"
#include "classifier.h"
#include "rs485.h"
#include "feedback.h"

#ifndef UNIT_TEST
#include "stm32f4xx_hal.h"

/* ============================================================================
 * Configuration
 * ============================================================================ */

/** NFC polling interval (ms) */
#define NFC_POLL_INTERVAL_MS        100

/** Heartbeat transmission interval (ms) */
#define HEARTBEAT_INTERVAL_MS       10000

/** Cooldown after a card tap (ms) — prevents double-reads */
#define COOLDOWN_PERIOD_MS          2000

/** NFC chip recovery attempt interval when in error state (ms) */
#define NFC_RECOVERY_INTERVAL_MS    5000

/* ============================================================================
 * Global State
 * ============================================================================ */

/** Total card taps since boot */
static uint32_t tap_count = 0;

/** Cooldown state */
static bool in_cooldown = false;
static uint32_t cooldown_start = 0;

/** Timing trackers */
static uint32_t last_nfc_poll = 0;
static uint32_t last_heartbeat = 0;
static uint32_t last_nfc_recovery = 0;

/* ============================================================================
 * System Clock Configuration
 * ============================================================================ */

/**
 * @brief Configure system clocks
 *
 * HSE 8MHz → PLL → SYSCLK 168MHz
 * AHB = 168MHz, APB1 = 42MHz, APB2 = 84MHz
 */
static void SystemClock_Config(void)
{
    RCC_OscInitTypeDef osc = {0};
    RCC_ClkInitTypeDef clk = {0};

    /* Enable PWR clock and set voltage regulator scale */
    __HAL_RCC_PWR_CLK_ENABLE();
    __HAL_PWR_VOLTAGESCALING_CONFIG(PWR_REGULATOR_VOLTAGE_SCALE1);

    /* HSE oscillator → PLL */
    osc.OscillatorType = RCC_OSCILLATORTYPE_HSE;
    osc.HSEState       = RCC_HSE_ON;
    osc.PLL.PLLState   = RCC_PLL_ON;
    osc.PLL.PLLSource  = RCC_PLLSOURCE_HSE;
    osc.PLL.PLLM       = 8;      /* HSE / 8 = 1 MHz */
    osc.PLL.PLLN       = 336;    /* 1 MHz * 336 = 336 MHz VCO */
    osc.PLL.PLLP       = RCC_PLLP_DIV2; /* 336 / 2 = 168 MHz SYSCLK */
    osc.PLL.PLLQ       = 7;      /* 336 / 7 = 48 MHz (USB, not used) */
    HAL_RCC_OscConfig(&osc);

    /* System clock, AHB, APB1, APB2 */
    clk.ClockType      = RCC_CLOCKTYPE_HCLK | RCC_CLOCKTYPE_SYSCLK |
                          RCC_CLOCKTYPE_PCLK1 | RCC_CLOCKTYPE_PCLK2;
    clk.SYSCLKSource   = RCC_SYSCLKSOURCE_PLLCLK;
    clk.AHBCLKDivider  = RCC_SYSCLK_DIV1;    /* 168 MHz */
    clk.APB1CLKDivider = RCC_HCLK_DIV4;      /* 42 MHz */
    clk.APB2CLKDivider = RCC_HCLK_DIV2;      /* 84 MHz */
    HAL_RCC_ClockConfig(&clk, FLASH_LATENCY_5);

    /* SysTick at 1kHz (1ms ticks) */
    HAL_SYSTICK_Config(HAL_RCC_GetHCLKFreq() / 1000);
    HAL_SYSTICK_CLKSourceConfig(SYSTICK_CLKSOURCE_HCLK);
}

/* ============================================================================
 * RS-485 Config Message Handler
 * ============================================================================ */

/**
 * @brief Handle incoming RS-485 configuration messages
 */
static void config_handler(uint8_t config_key, const uint8_t *data, uint8_t len)
{
    uint8_t result = RS485_CONFIG_RESULT_OK;

    switch (config_key) {
    case RS485_CONFIG_UID_TABLE:
        if (!classifier_update_uid_table(data, len)) {
            result = RS485_CONFIG_RESULT_BAD_DATA;
        }
        break;

    case RS485_CONFIG_CLASSIFY_MODE:
        /* Runtime mode change not supported (compile-time define) */
        /* Acknowledge but note: this has no effect in current build */
        if (len < 1 || data[0] < 1 || data[0] > 3) {
            result = RS485_CONFIG_RESULT_BAD_DATA;
        }
        break;

    case RS485_CONFIG_COOLDOWN:
        /* Cooldown period update — not implemented in this build */
        if (len < 2) {
            result = RS485_CONFIG_RESULT_BAD_DATA;
        }
        break;

    default:
        result = RS485_CONFIG_RESULT_BAD_KEY;
        break;
    }

    rs485_send_config_ack(config_key, result);
}

/* ============================================================================
 * MCU Temperature Reading
 * ============================================================================ */

/**
 * @brief Read the MCU internal die temperature
 * @return Temperature in 0.1°C units
 */
static int16_t read_mcu_temperature(void)
{
    ADC_HandleTypeDef hadc;
    ADC_ChannelConfTypeDef adc_ch = {0};

    __HAL_RCC_ADC1_CLK_ENABLE();

    hadc.Instance                   = ADC1;
    hadc.Init.Resolution            = ADC_RESOLUTION_12B;
    hadc.Init.ScanConvMode          = DISABLE;
    hadc.Init.ContinuousConvMode    = DISABLE;
    hadc.Init.ExternalTrigConvEdge  = ADC_EXTERNALTRIGCONVEDGE_NONE;
    hadc.Init.DataAlign             = ADC_DATAALIGN_RIGHT;
    hadc.Init.NbrOfConversion       = 1;
    HAL_ADC_Init(&hadc);

    /* Internal temperature sensor on ADC1 Channel 16 */
    adc_ch.Channel      = ADC_CHANNEL_TEMPSENSOR;
    adc_ch.Rank         = 1;
    adc_ch.SamplingTime = ADC_SAMPLETIME_480CYCLES;
    HAL_ADC_ConfigChannel(&hadc, &adc_ch);

    HAL_ADC_Start(&hadc);
    HAL_ADC_PollForConversion(&hadc, 10);
    uint32_t raw = HAL_ADC_GetValue(&hadc);
    HAL_ADC_Stop(&hadc);

    /* Convert raw ADC to temperature (0.1°C units)
     * STM32F4 formula: T(°C) = ((V_sense - V_25) / Avg_Slope) + 25
     * V_sense = raw * 3300 / 4096 (mV)
     * V_25 = 760 mV, Avg_Slope = 2.5 mV/°C
     * T(°C) = ((raw * 3300 / 4096 - 760) * 10) / 25 + 250 (in 0.1°C) */
    int32_t v_sense = (int32_t)(raw * 3300 / 4096);
    int16_t temp_01c = (int16_t)(((v_sense - 760) * 10) / 25 + 250);

    return temp_01c;
}

/* ============================================================================
 * Error Handler
 * ============================================================================ */

/**
 * @brief Called on unrecoverable HAL errors
 *
 * Sets LED to error state and enters an infinite loop.
 * The watchdog will eventually reset the MCU.
 */
void Error_Handler(void)
{
    feedback_set_error();
    while (1) {
        /* Watchdog will reset us */
    }
}

/* ============================================================================
 * DMA IRQ Handler
 * ============================================================================ */

/**
 * @brief DMA1 Stream 0 IRQ handler (WS2812B)
 */
void DMA1_Stream0_IRQHandler(void)
{
    extern void ws2812b_dma_complete_handler(void);

    /* Check transfer complete flag (Stream 0 uses LISR/LIFCR bits 4-5) */
    if (DMA1->LISR & DMA_FLAG_TCIF0_4) {
        DMA1->LIFCR = DMA_FLAG_TCIF0_4;
        ws2812b_dma_complete_handler();
    }
}

/* ============================================================================
 * Main Entry Point
 * ============================================================================ */

/**
 * @brief Firmware entry point
 */
int main(void)
{
    /* Initialize HAL */
    HAL_Init();

    /* Configure system clocks */
    SystemClock_Config();

    /* Enable GPIO clocks */
    GPIO_CLK_ENABLE_ALL();

    /* Check for watchdog reset before initializing IWDG */
    bool was_wdg_reset = watchdog_check_reset_cause();

    /* Initialize watchdog */
    watchdog_init();

    /* Initialize all modules */
    rs485_init();
    rs485_set_config_callback(config_handler);

    classifier_init();

    feedback_init();
    feedback_set_idle();

    /* Initialize NFC — if it fails, enter error state but continue */
    bool nfc_ok = nfc_init();
    if (!nfc_ok) {
        feedback_set_error();
    }

    /* If we recovered from a watchdog reset, send a heartbeat with error info */
    if (was_wdg_reset) {
        /* Brief delay to let RS-485 bus settle */
        HAL_Delay(10);
    }

    /* Initialize timing */
    uint32_t now = HAL_GetTick();
    last_nfc_poll     = now;
    last_heartbeat    = now;
    last_nfc_recovery = now;

    /* ====================================================================
     * Main Loop
     * ==================================================================== */
    while (1) {
        watchdog_kick();
        now = HAL_GetTick();

        /* ---- Heartbeat (every 10 seconds) ---- */
        if ((now - last_heartbeat) >= HEARTBEAT_INTERVAL_MS) {
            nfc_status_t nfc_stat = nfc_get_status();
            uint8_t sys_status = (nfc_stat == NFC_STATUS_CHIP_ERROR) ? 0x01 : 0x00;
            uint32_t uptime_sec = now / 1000;
            int16_t temperature = read_mcu_temperature();

            rs485_send_heartbeat(sys_status, uptime_sec, tap_count, temperature);

            /* Retry any pending messages */
            rs485_retry_pending();

            last_heartbeat = now;
        }

        /* ---- RS-485 RX poll ---- */
        rs485_receive_poll();

        /* ---- Feedback animation update ---- */
        feedback_update();

        /* ---- NFC error recovery ---- */
        if (nfc_get_status() == NFC_STATUS_CHIP_ERROR) {
            if ((now - last_nfc_recovery) >= NFC_RECOVERY_INTERVAL_MS) {
                if (nfc_attempt_recovery()) {
                    feedback_set_idle();
                }
                last_nfc_recovery = now;
            }
            continue;  /* Skip NFC polling while in error state */
        }

        /* ---- NFC polling (every 100ms) ---- */
        if ((now - last_nfc_poll) >= NFC_POLL_INTERVAL_MS) {
            last_nfc_poll = now;

            /* Check cooldown */
            if (in_cooldown) {
                if ((now - cooldown_start) < COOLDOWN_PERIOD_MS) {
                    continue;
                }
                in_cooldown = false;
                feedback_set_idle();
            }

            /* Poll for card */
            if (nfc_poll()) {
                nfc_card_info_t card;

                if (nfc_read_card(&card)) {
                    /* Classify */
                    card_type_t type = classifier_classify(&card);

                    /* Feedback */
                    feedback_trigger(type);

                    /* Report over RS-485 */
                    rs485_send_tap_event(type, card.uid, card.uid_len,
                                         now, ACTIVE_CLASSIFY_MODE);

                    /* Update counters */
                    tap_count++;

                    /* Enter cooldown */
                    in_cooldown = true;
                    cooldown_start = now;
                } else {
                    /* Read failed — brief red flash */
                    feedback_trigger(CARD_TYPE_UNKNOWN);
                }
            }
        }
    }
}

/* ============================================================================
 * SysTick Handler (required by HAL)
 * ============================================================================ */

void SysTick_Handler(void)
{
    HAL_IncTick();
}

#endif /* UNIT_TEST */
