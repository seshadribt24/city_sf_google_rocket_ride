/**
 * Linker script for STM32F407VGT6
 * Flash: 1024K @ 0x08000000
 * SRAM:  128K  @ 0x20000000
 * CCM:   64K   @ 0x10000000 (not DMA-accessible)
 */

/* Entry point */
ENTRY(Reset_Handler)

/* Top of stack — end of 128K SRAM */
_estack = ORIGIN(SRAM) + LENGTH(SRAM);

/* Minimum heap and stack sizes */
_Min_Heap_Size  = 0x000;  /* No heap — no dynamic allocation */
_Min_Stack_Size = 0x800;  /* 2KB stack */

MEMORY
{
    FLASH (rx)  : ORIGIN = 0x08000000, LENGTH = 1024K
    SRAM  (rwx) : ORIGIN = 0x20000000, LENGTH = 128K
    CCM   (rw)  : ORIGIN = 0x10000000, LENGTH = 64K
}

SECTIONS
{
    /* Vector table — must be at start of flash */
    .isr_vector :
    {
        . = ALIGN(4);
        KEEP(*(.isr_vector))
        . = ALIGN(4);
    } >FLASH

    /* Code */
    .text :
    {
        . = ALIGN(4);
        *(.text)
        *(.text*)
        *(.glue_7)
        *(.glue_7t)
        *(.eh_frame)

        KEEP(*(.init))
        KEEP(*(.fini))

        . = ALIGN(4);
        _etext = .;
    } >FLASH

    /* Read-only data (const tables, string literals) */
    .rodata :
    {
        . = ALIGN(4);
        *(.rodata)
        *(.rodata*)
        . = ALIGN(4);
    } >FLASH

    /* ARM exception table */
    .ARM.extab :
    {
        *(.ARM.extab* .gnu.linkonce.armextab.*)
    } >FLASH

    .ARM :
    {
        __exidx_start = .;
        *(.ARM.exidx*)
        __exidx_end = .;
    } >FLASH

    /* Pre-initialization array */
    .preinit_array :
    {
        PROVIDE_HIDDEN(__preinit_array_start = .);
        KEEP(*(.preinit_array*))
        PROVIDE_HIDDEN(__preinit_array_end = .);
    } >FLASH

    .init_array :
    {
        PROVIDE_HIDDEN(__init_array_start = .);
        KEEP(*(SORT(.init_array.*)))
        KEEP(*(.init_array*))
        PROVIDE_HIDDEN(__init_array_end = .);
    } >FLASH

    .fini_array :
    {
        PROVIDE_HIDDEN(__fini_array_start = .);
        KEEP(*(SORT(.fini_array.*)))
        KEEP(*(.fini_array*))
        PROVIDE_HIDDEN(__fini_array_end = .);
    } >FLASH

    /* Initialized data — loaded from flash, copied to SRAM by startup code */
    _sidata = LOADADDR(.data);

    .data :
    {
        . = ALIGN(4);
        _sdata = .;
        *(.data)
        *(.data*)
        . = ALIGN(4);
        _edata = .;
    } >SRAM AT> FLASH

    /* Zero-initialized data */
    .bss :
    {
        . = ALIGN(4);
        _sbss = .;
        __bss_start__ = _sbss;
        *(.bss)
        *(.bss*)
        *(COMMON)
        . = ALIGN(4);
        _ebss = .;
        __bss_end__ = _ebss;
    } >SRAM

    /* No-init section — survives soft resets (for watchdog reset counter) */
    .noinit (NOLOAD) :
    {
        . = ALIGN(4);
        *(.noinit)
        *(.noinit*)
        . = ALIGN(4);
    } >SRAM

    /* Stack check */
    ._user_heap_stack :
    {
        . = ALIGN(8);
        . = . + _Min_Heap_Size;
        . = . + _Min_Stack_Size;
        . = ALIGN(8);
    } >SRAM

    /* Discard debug sections in release builds */
    /DISCARD/ :
    {
        libc.a(*)
        libm.a(*)
        libgcc.a(*)
    }

    .ARM.attributes 0 : { *(.ARM.attributes) }
}
