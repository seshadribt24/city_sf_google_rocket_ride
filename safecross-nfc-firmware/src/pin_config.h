/**
 * @file pin_config.h
 * @brief Central pin assignment definitions for SafeCross NFC Reader
 *
 * All GPIO pin assignments, alternate function mappings, and peripheral
 * configurations are defined here. This file resolves the following
 * conflicts from the original hardware reference:
 *
 * - PA3 conflict: SPI1 CS moved to PB0 (PA3 needed for USART2 RX)
 * - PA5 conflict: PN5180 BUSY moved to PC0 (PA5 needed for SPI1 SCK)
 * - PA6 conflict: PN5180 RST moved to PC1 (PA6 needed for SPI1 MISO)
 * - TIM4 conflict: Buzzer moved to PB5/TIM3_CH2 (TIM4 used by WS2812B at 800kHz)
 */

#ifndef PIN_CONFIG_H
#define PIN_CONFIG_H

/* ============================================================================
 * SPI1 — PN5180 NFC Transceiver
 * ============================================================================ */

/** SPI1 SCK — PA5, AF5 */
#define PN5180_SPI_PORT             GPIOA
#define PN5180_SPI_SCK_PIN          GPIO_PIN_5
#define PN5180_SPI_MISO_PIN         GPIO_PIN_6
#define PN5180_SPI_MOSI_PIN         GPIO_PIN_7
#define PN5180_SPI_AF               GPIO_AF5_SPI1
#define PN5180_SPI_INSTANCE         SPI1

/** PN5180 Chip Select — PB0, GPIO output, active low */
#define PN5180_CS_PORT              GPIOB
#define PN5180_CS_PIN               GPIO_PIN_0

/** PN5180 IRQ — PA4, EXTI4, falling edge */
#define PN5180_IRQ_PORT             GPIOA
#define PN5180_IRQ_PIN              GPIO_PIN_4
#define PN5180_IRQ_EXTI_LINE        EXTI_LINE_4
#define PN5180_IRQ_IRQn             EXTI4_IRQn

/** PN5180 BUSY — PC0, GPIO input */
#define PN5180_BUSY_PORT            GPIOC
#define PN5180_BUSY_PIN             GPIO_PIN_0

/** PN5180 Reset — PC1, GPIO output, active low */
#define PN5180_RST_PORT             GPIOC
#define PN5180_RST_PIN              GPIO_PIN_1

/* ============================================================================
 * USART2 — RS-485 Transceiver (MAX485)
 * ============================================================================ */

/** USART2 TX — PA2, AF7 */
#define RS485_USART_PORT            GPIOA
#define RS485_TX_PIN                GPIO_PIN_2
#define RS485_RX_PIN                GPIO_PIN_3
#define RS485_USART_AF              GPIO_AF7_USART2
#define RS485_USART_INSTANCE        USART2

/** RS-485 Direction Enable (DE/RE) — PB1, GPIO output */
#define RS485_DE_PORT               GPIOB
#define RS485_DE_PIN                GPIO_PIN_1

/** RS-485 baud rate */
#define RS485_BAUDRATE              115200

/* ============================================================================
 * TIM4_CH1 — WS2812B LED Ring (8 LEDs)
 * ============================================================================ */

/** WS2812B Data — PB6, AF2 (TIM4_CH1) */
#define WS2812B_PORT                GPIOB
#define WS2812B_PIN                 GPIO_PIN_6
#define WS2812B_TIM_AF              GPIO_AF2_TIM4
#define WS2812B_TIM_INSTANCE        TIM4
#define WS2812B_TIM_CHANNEL         TIM_CHANNEL_1

/** Number of LEDs in the ring */
#define WS2812B_LED_COUNT           8

/** TIM4 clock: APB1 timer clock = 84 MHz */
#define WS2812B_TIM_CLK_HZ         84000000
/** WS2812B bit period: 1.25 us = 800 kHz */
#define WS2812B_TIM_ARR            104
/** Duty cycle for logic "1": ~0.8 us */
#define WS2812B_DUTY_HIGH          67
/** Duty cycle for logic "0": ~0.4 us */
#define WS2812B_DUTY_LOW           33

/* DMA for WS2812B: DMA1 Stream 0, Channel 2 (TIM4_UP) */
#define WS2812B_DMA_STREAM         DMA1_Stream0
#define WS2812B_DMA_CHANNEL        DMA_CHANNEL_2
#define WS2812B_DMA_IRQn           DMA1_Stream0_IRQn

/* ============================================================================
 * TIM3_CH2 — Piezo Buzzer
 * ============================================================================ */

/** Buzzer — PB5, AF2 (TIM3_CH2) */
#define BUZZER_PORT                 GPIOB
#define BUZZER_PIN                  GPIO_PIN_5
#define BUZZER_TIM_AF               GPIO_AF2_TIM3
#define BUZZER_TIM_INSTANCE         TIM3
#define BUZZER_TIM_CHANNEL          TIM_CHANNEL_2

/** TIM3 clock: APB1 timer clock = 84 MHz */
#define BUZZER_TIM_CLK_HZ          84000000

/* ============================================================================
 * System Clock Configuration
 * ============================================================================ */

#define SYSCLK_FREQ_HZ             168000000
#define HCLK_FREQ_HZ               168000000
#define APB1_FREQ_HZ               42000000
#define APB1_TIM_FREQ_HZ           84000000
#define APB2_FREQ_HZ               84000000
#define APB2_TIM_FREQ_HZ           168000000

/* ============================================================================
 * GPIO Clock Enable Masks
 * ============================================================================ */

#define GPIO_CLK_ENABLE_ALL() do { \
    __HAL_RCC_GPIOA_CLK_ENABLE(); \
    __HAL_RCC_GPIOB_CLK_ENABLE(); \
    __HAL_RCC_GPIOC_CLK_ENABLE(); \
} while (0)

#endif /* PIN_CONFIG_H */
