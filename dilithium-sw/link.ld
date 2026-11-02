MEMORY {
    ITCM (rx)  : ORIGIN = 0x80000000, LENGTH = 64K
    DTCM (rwx) : ORIGIN = 0x90000000, LENGTH = 64K
}
SECTIONS {
    .text   : { *(.text*)                     } > ITCM
    .rodata : { *(.rodata*) *(.srodata*) *(.rodata.cst*) *(.srodata.*) } > ITCM
    .data   : { *(.data*)  *(.sdata*)  *(.sdata.*) } > DTCM
    .bss    : { *(.bss*)   *(.sbss*)   *(.sbss.*)  } > DTCM
    . = ALIGN(16);
    _stack_top = 0x9000FFF0;
}