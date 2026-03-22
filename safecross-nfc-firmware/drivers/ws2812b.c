/**
 * @file ws2812b.c
 * @brief WS2812B LED ring driver implementation (DMA-based via TIM4_CH1)
 */

#include "ws2812b.h"
#include "pin_config.h"

#ifndef UNIT_TEST
#include "stm32f4xx_hal.h"
#include <string.h>

/* ============================================================================
 * Private State
 * ============================================================================ */

/** Pixel color buffer: [LED_index][G, R, B] — WS2812B uses GRB order */
static uint8_t pixel_buf[WS2812B_NUM_LEDS][3];

/** DMA buffer: one uint16_t per bit, plus reset slots */
static uint16_t dma_buf[WS2812B_DMA_BUF_SIZE];

/** TIM4 handle */
static TIM_HandleTypeDef htim_ws2812b;

/** DMA handle */
static DMA_HandleTypeDef hdma_ws2812b;

/** Flag indicating DMA transfer in progress */
static volatile bool dma_busy = false;

/* ============================================================================
 * DMA Callback
 * ============================================================================ */

/**
 * @brief DMA transfer complete callback
 */
void ws2812b_dma_complete_handler(void)
{
    HAL_TIM_PWM_Stop_DMA(&htim_ws2812b, WS2812B_TIM_CHANNEL);
    dma_busy = false;
}

/* ============================================================================
 * Private Helpers
 * ============================================================================ */

/**
 * @brief Convert pixel buffer to DMA bit-stream buffer
 */
static void ws2812b_fill_dma_buffer(void)
{
    uint16_t pos = 0;

    for (uint8_t led = 0; led < WS2812B_NUM_LEDS; led++) {
        /* GRB order, MSB first */
        for (uint8_t color = 0; color < 3; color++) {
            uint8_t byte = pixel_buf[led][color];
            for (int8_t bit = 7; bit >= 0; bit--) {
                if (byte & (1 << bit)) {
                    dma_buf[pos] = WS2812B_DUTY_HIGH;
                } else {
                    dma_buf[pos] = WS2812B_DUTY_LOW;
                }
                pos++;
            }
        }
    }

    /* Reset period: all zero duty cycles (line held low) */
    for (uint16_t i = 0; i < WS2812B_RESET_SLOTS; i++) {
        dma_buf[pos++] = 0;
    }
}

/* ============================================================================
 * Public API
 * ============================================================================ */

void ws2812b_init(void)
{
    GPIO_InitTypeDef gpio = {0};

    /* Enable clocks */
    __HAL_RCC_TIM4_CLK_ENABLE();
    __HAL_RCC_DMA1_CLK_ENABLE();

    /* Configure PB6 as TIM4_CH1 AF */
    gpio.Pin       = WS2812B_PIN;
    gpio.Mode      = GPIO_MODE_AF_PP;
    gpio.Pull      = GPIO_NOPULL;
    gpio.Speed     = GPIO_SPEED_FREQ_HIGH;
    gpio.Alternate = WS2812B_TIM_AF;
    HAL_GPIO_Init(WS2812B_PORT, &gpio);

    /* Configure TIM4 for 800kHz PWM */
    htim_ws2812b.Instance               = WS2812B_TIM_INSTANCE;
    htim_ws2812b.Init.Prescaler         = 0;  /* No prescaler */
    htim_ws2812b.Init.CounterMode       = TIM_COUNTERMODE_UP;
    htim_ws2812b.Init.Period            = WS2812B_TIM_ARR;
    htim_ws2812b.Init.ClockDivision     = TIM_CLOCKDIVISION_DIV1;
    htim_ws2812b.Init.AutoReloadPreload = TIM_AUTORELOAD_PRELOAD_DISABLE;
    HAL_TIM_PWM_Init(&htim_ws2812b);

    /* PWM channel configuration */
    TIM_OC_InitTypeDef oc_config = {0};
    oc_config.OCMode     = TIM_OCMODE_PWM1;
    oc_config.Pulse      = 0;
    oc_config.OCPolarity  = TIM_OCPOLARITY_HIGH;
    oc_config.OCFastMode  = TIM_OCFAST_DISABLE;
    HAL_TIM_PWM_ConfigChannel(&htim_ws2812b, &oc_config, WS2812B_TIM_CHANNEL);

    /* Configure DMA1 Stream 0 Channel 2 for TIM4_UP */
    hdma_ws2812b.Instance                 = WS2812B_DMA_STREAM;
    hdma_ws2812b.Init.Channel             = WS2812B_DMA_CHANNEL;
    hdma_ws2812b.Init.Direction           = DMA_MEMORY_TO_PERIPH;
    hdma_ws2812b.Init.PeriphInc           = DMA_PINC_DISABLE;
    hdma_ws2812b.Init.MemInc              = DMA_MINC_ENABLE;
    hdma_ws2812b.Init.PeriphDataAlignment = DMA_PDATAALIGN_HALFWORD;
    hdma_ws2812b.Init.MemDataAlignment    = DMA_MDATAALIGN_HALFWORD;
    hdma_ws2812b.Init.Mode                = DMA_NORMAL;
    hdma_ws2812b.Init.Priority            = DMA_PRIORITY_HIGH;
    hdma_ws2812b.Init.FIFOMode            = DMA_FIFOMODE_DISABLE;
    HAL_DMA_Init(&hdma_ws2812b);

    /* Link DMA to timer */
    __HAL_LINKDMA(&htim_ws2812b, hdma[TIM_DMA_ID_CC1], hdma_ws2812b);

    /* Enable DMA interrupt */
    HAL_NVIC_SetPriority(WS2812B_DMA_IRQn, 5, 0);
    HAL_NVIC_EnableIRQ(WS2812B_DMA_IRQn);

    /* Clear pixel buffer */
    ws2812b_clear();
    dma_busy = false;
}

void ws2812b_set_pixel(uint8_t index, uint8_t r, uint8_t g, uint8_t b)
{
    if (index >= WS2812B_NUM_LEDS) {
        return;
    }

    /* GRB order */
    pixel_buf[index][0] = g;
    pixel_buf[index][1] = r;
    pixel_buf[index][2] = b;
}

void ws2812b_set_all(uint8_t r, uint8_t g, uint8_t b)
{
    for (uint8_t i = 0; i < WS2812B_NUM_LEDS; i++) {
        pixel_buf[i][0] = g;
        pixel_buf[i][1] = r;
        pixel_buf[i][2] = b;
    }
}

void ws2812b_clear(void)
{
    memset(pixel_buf, 0, sizeof(pixel_buf));
}

void ws2812b_update(void)
{
    if (dma_busy) {
        return;
    }

    ws2812b_fill_dma_buffer();

    dma_busy = true;
    HAL_TIM_PWM_Start_DMA(&htim_ws2812b, WS2812B_TIM_CHANNEL,
                           (uint32_t *)dma_buf, WS2812B_DMA_BUF_SIZE);
}

bool ws2812b_is_busy(void)
{
    return dma_busy;
}

#endif /* UNIT_TEST */
