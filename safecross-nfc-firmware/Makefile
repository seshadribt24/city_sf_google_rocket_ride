# SafeCross NFC Reader Firmware — Build System
# Dual-target: ARM cross-compilation (firmware) and x86 native (tests)

# ==============================================================================
# ARM Cross-Compilation Toolchain
# ==============================================================================
ARM_CC      = arm-none-eabi-gcc
ARM_OBJCOPY = arm-none-eabi-objcopy
ARM_SIZE    = arm-none-eabi-size

# ==============================================================================
# Paths
# ==============================================================================
BUILD_DIR   = build
SRC_DIR     = src
DRV_DIR     = drivers
TEST_DIR    = tests

# STM32 HAL and CMSIS paths
HAL_DIR       ?= ../STM32F4xx_HAL_Driver
CMSIS_DEV_DIR ?= ../cmsis_device_f4
CMSIS_DIR     ?= ../CMSIS/CMSIS/Core

# ==============================================================================
# Source Files
# ==============================================================================
SRC_FILES   = $(wildcard $(SRC_DIR)/*.c)
DRV_FILES   = $(wildcard $(DRV_DIR)/*.c)

# HAL source files needed by the firmware
HAL_SOURCES = \
	$(HAL_DIR)/Src/stm32f4xx_hal.c \
	$(HAL_DIR)/Src/stm32f4xx_hal_cortex.c \
	$(HAL_DIR)/Src/stm32f4xx_hal_rcc.c \
	$(HAL_DIR)/Src/stm32f4xx_hal_rcc_ex.c \
	$(HAL_DIR)/Src/stm32f4xx_hal_pwr.c \
	$(HAL_DIR)/Src/stm32f4xx_hal_pwr_ex.c \
	$(HAL_DIR)/Src/stm32f4xx_hal_gpio.c \
	$(HAL_DIR)/Src/stm32f4xx_hal_spi.c \
	$(HAL_DIR)/Src/stm32f4xx_hal_uart.c \
	$(HAL_DIR)/Src/stm32f4xx_hal_tim.c \
	$(HAL_DIR)/Src/stm32f4xx_hal_tim_ex.c \
	$(HAL_DIR)/Src/stm32f4xx_hal_dma.c \
	$(HAL_DIR)/Src/stm32f4xx_hal_dma_ex.c \
	$(HAL_DIR)/Src/stm32f4xx_hal_iwdg.c \
	$(HAL_DIR)/Src/stm32f4xx_hal_adc.c \
	$(HAL_DIR)/Src/stm32f4xx_hal_adc_ex.c \
	$(HAL_DIR)/Src/stm32f4xx_hal_flash.c \
	$(HAL_DIR)/Src/stm32f4xx_hal_flash_ex.c

# CMSIS startup and system
CMSIS_SOURCES = \
	$(CMSIS_DEV_DIR)/Source/Templates/system_stm32f4xx.c

# Startup assembly (use GCC variant)
STARTUP_ASM = startup/startup_stm32f407xx.s

FW_SOURCES  = $(SRC_FILES) $(DRV_FILES) $(HAL_SOURCES) $(CMSIS_SOURCES)
FW_OBJECTS  = $(patsubst %.c,$(BUILD_DIR)/%.o,$(FW_SOURCES))
FW_OBJECTS += $(patsubst %.s,$(BUILD_DIR)/%.o,$(STARTUP_ASM))

# ==============================================================================
# ARM Compiler Flags
# ==============================================================================
ARM_CFLAGS  = -mcpu=cortex-m4 -mthumb -mfloat-abi=hard -mfpu=fpv4-sp-d16
ARM_CFLAGS += -std=c11 -Wall -Wextra
ARM_CFLAGS += -Os -ffunction-sections -fdata-sections
ARM_CFLAGS += -DSTM32F407xx -DUSE_HAL_DRIVER
ARM_CFLAGS += -I$(SRC_DIR) -I$(DRV_DIR)
ARM_CFLAGS += -I$(HAL_DIR)/Inc
ARM_CFLAGS += -I$(CMSIS_DEV_DIR)/Include
ARM_CFLAGS += -I$(CMSIS_DIR)/Include

ARM_ASFLAGS = -mcpu=cortex-m4 -mthumb -mfloat-abi=hard -mfpu=fpv4-sp-d16

ARM_LDFLAGS = -mcpu=cortex-m4 -mthumb -mfloat-abi=hard -mfpu=fpv4-sp-d16
ARM_LDFLAGS += -Tlinker.ld -Wl,--gc-sections -Wl,-Map=$(BUILD_DIR)/firmware.map
ARM_LDFLAGS += --specs=nosys.specs --specs=nano.specs -lc -lm -lnosys

# Debug build flags
ifdef DEBUG
ARM_CFLAGS += -g3 -gdwarf-2 -DDEBUG -Og
else
ARM_CFLAGS += -DNDEBUG
endif

# ==============================================================================
# Native Test Compiler Flags
# ==============================================================================
TEST_CC     = gcc
TEST_CFLAGS = -std=c11 -Wall -Wextra -g -DUNIT_TEST
TEST_CFLAGS += -I$(SRC_DIR) -I$(DRV_DIR)

# ==============================================================================
# Targets
# ==============================================================================

.PHONY: all firmware test clean flash

all: firmware

# --- Firmware Build -----------------------------------------------------------

firmware: $(BUILD_DIR)/firmware.elf $(BUILD_DIR)/firmware.bin
	@$(ARM_SIZE) $(BUILD_DIR)/firmware.elf

$(BUILD_DIR)/firmware.elf: $(FW_OBJECTS)
	@mkdir -p $(dir $@)
	$(ARM_CC) $(FW_OBJECTS) $(ARM_LDFLAGS) -o $@

$(BUILD_DIR)/firmware.bin: $(BUILD_DIR)/firmware.elf
	$(ARM_OBJCOPY) -O binary $< $@

$(BUILD_DIR)/%.o: %.c
	@mkdir -p $(dir $@)
	$(ARM_CC) $(ARM_CFLAGS) -c $< -o $@

$(BUILD_DIR)/%.o: %.s
	@mkdir -p $(dir $@)
	$(ARM_CC) $(ARM_ASFLAGS) -c $< -o $@

# --- Test Build ---------------------------------------------------------------

test: $(BUILD_DIR)/test_classifier $(BUILD_DIR)/test_rs485_framing
	@echo "=== Running classifier tests ==="
	./$(BUILD_DIR)/test_classifier
	@echo ""
	@echo "=== Running RS-485 framing tests ==="
	./$(BUILD_DIR)/test_rs485_framing
	@echo ""
	@echo "All tests passed."

$(BUILD_DIR)/test_classifier: $(TEST_DIR)/test_classifier.c $(SRC_DIR)/classifier.c
	@mkdir -p $(BUILD_DIR)
	$(TEST_CC) $(TEST_CFLAGS) $^ -o $@

$(BUILD_DIR)/test_rs485_framing: $(TEST_DIR)/test_rs485_framing.c $(SRC_DIR)/rs485.c
	@mkdir -p $(BUILD_DIR)
	$(TEST_CC) $(TEST_CFLAGS) $^ -o $@

# --- Flash via ST-Link --------------------------------------------------------

flash: $(BUILD_DIR)/firmware.bin
	st-flash write $(BUILD_DIR)/firmware.bin 0x08000000

# --- Clean --------------------------------------------------------------------

clean:
	rm -rf $(BUILD_DIR)
