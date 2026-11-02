#ifndef UART_DRV_H
#define UART_DRV_H
#include <stdint.h>

/* PC↔FPGA 通道 UART 选择：0 = UART0(0x1001_3000, gpioA[16]/[17]，DDR200T 板载 USB 串口)
 *                        2 = UART2(0x1003_3000, gpioA[18]/[19]，MCU200T 的 CH340 / DDR200T 的 Lora 引脚)
 * 编译时可用 -DPC_UART_SEL=0 覆盖（板级 UART0 版固件） */
#ifndef PC_UART_SEL
#define PC_UART_SEL  2
#endif

/* E203 perips 内嵌 UART0（16550 兼容 apb_uart），基址 0x1001_3000，寄存器步长 4B */
#define UART0_BASE   0x10013000u
/* UART2（板上 MCU200T 的 CH340 USB-UART 通道），基址 0x1003_3000 */
#define UART2_BASE   0x10033000u

/* GPIO IOF 复用配置：IOFCFG(+0x1C) 写 1<<n 使能 gpio[n] 外设功能，
 * TX 到引脚必须置位；RX 输入通路恒通 */
#define GPIOA_BASE   0x10012000u
#define GPIOB_BASE   0x10040000u
#define GPIO_IOFCFG_OFF 0x1Cu
#define GPIOA_IOFCFG (*(volatile uint32_t*)(GPIOA_BASE + GPIO_IOFCFG_OFF))
#define GPIOB_IOFCFG (*(volatile uint32_t*)(GPIOB_BASE + GPIO_IOFCFG_OFF))

#if PC_UART_SEL == 0
#define UART_PC_BASE UART0_BASE
#elif PC_UART_SEL == 2
#define UART_PC_BASE UART2_BASE
#else
#error "PC_UART_SEL must be 0 or 2"
#endif

#define UART_RBR     (*(volatile uint32_t*)(UART_PC_BASE + 0x00)) // 读接收缓冲 (DLAB=0)
#define UART_THR     (*(volatile uint32_t*)(UART_PC_BASE + 0x00)) // 写发送保持 (DLAB=0)
#define UART_DLL     (*(volatile uint32_t*)(UART_PC_BASE + 0x00)) // 分频低字节 (DLAB=1)
#define UART_IER     (*(volatile uint32_t*)(UART_PC_BASE + 0x04))
#define UART_DLM     (*(volatile uint32_t*)(UART_PC_BASE + 0x04)) // 分频高字节 (DLAB=1)
#define UART_FCR     (*(volatile uint32_t*)(UART_PC_BASE + 0x08)) // 写 FIFO 控制
#define UART_LCR     (*(volatile uint32_t*)(UART_PC_BASE + 0x0C))
#define UART_LSR     (*(volatile uint32_t*)(UART_PC_BASE + 0x14))
#define UART_LSR_DR  0x01u   // 接收数据就绪
#define UART_LSR_THRE 0x20u  // 发送保持寄存器空
#define UART_LSR_TEMT 0x40u  // 发送器空

/* 外设时钟 hfclk：仿真 tb 为 250MHz（tb #2 翻转），板上 mmcm clk_out2 = 16MHz
 * 本 16550-like 核的分频语义：位周期 = (DLL+1) 个外设时钟（无 16 倍采样，
 * RX 在 div/2 处采起始位中点），与标准 16550 的 16x 不同。
 * 真机协议参数: 115200 8N1 → div = 16e6/115200 - 1 ≈ 138（误差 -0.08%）
 * 仿真加速档:    div = 15 → 位周期 64ns（等效 15.625Mbaud，帧格式不变）
 * 四场景演示用 UART_BAUD_DIV_SIM，板级编译用 -DUART_BAUD_DIV=UART_BAUD_DIV_HW */
#define UART_BAUD_DIV_HW   138u
#define UART_BAUD_DIV_SIM  15u
#ifndef UART_BAUD_DIV
#define UART_BAUD_DIV UART_BAUD_DIV_SIM
#endif

static inline void uart_init(uint32_t div) {
#if PC_UART_SEL == 0
    GPIOA_IOFCFG |= (1u << 16) | (1u << 17);   // gpioA[16]RX/[17]TX → UART0
#elif PC_UART_SEL == 2
    GPIOA_IOFCFG |= (1u << 18) | (1u << 19);   // gpioA[18]RX/[19]TX → UART2
#endif
    UART_LCR = 0x80u;                 // DLAB=1
    UART_DLL = div & 0xFFu;
    UART_DLM = (div >> 8) & 0xFFu;
    UART_LCR = 0x03u;                 // 8N1
    UART_FCR = 0x07u;                 // 使能并清零 TX/RX FIFO
    UART_IER = 0x00u;                 // 轮询模式，不开中断
}

static inline void uart_putc(char c) {
    while (!(UART_LSR & UART_LSR_THRE));
    UART_THR = (uint8_t)c;
}

static inline int uart_getc(void) {
    while (!(UART_LSR & UART_LSR_DR));
    return UART_RBR & 0xFF;
}

static inline void uart_puts(const char *s) {
    while (*s) uart_putc(*s++);
}

static inline void uart_puthex32(uint32_t v) {
    for (int i = 7; i >= 0; i--) {
        uint32_t n = (v >> (4*i)) & 0xF;
        uart_putc(n < 10 ? '0'+n : 'a'+(n-10));
    }
}

/* ---------------- UART2（板上 CH340 USB-UART 通道）0x1003_3000，同一 16550 寄存器组 ---------------- */
#define UART2_RBR    (*(volatile uint32_t*)(UART2_BASE + 0x00))
#define UART2_THR    (*(volatile uint32_t*)(UART2_BASE + 0x00))
#define UART2_DLL    (*(volatile uint32_t*)(UART2_BASE + 0x00))
#define UART2_IER    (*(volatile uint32_t*)(UART2_BASE + 0x04))
#define UART2_DLM    (*(volatile uint32_t*)(UART2_BASE + 0x04))
#define UART2_FCR    (*(volatile uint32_t*)(UART2_BASE + 0x08))
#define UART2_LCR    (*(volatile uint32_t*)(UART2_BASE + 0x0C))
#define UART2_LSR    (*(volatile uint32_t*)(UART2_BASE + 0x14))

static inline void uart2_init(uint32_t div) {
    UART2_LCR = 0x80u;
    UART2_DLL = div & 0xFFu;
    UART2_DLM = (div >> 8) & 0xFFu;
    UART2_LCR = 0x03u;
    UART2_FCR = 0x07u;
    UART2_IER = 0x00u;
}

static inline void uart2_putc(char c) {
    while (!(UART2_LSR & UART_LSR_THRE));
    UART2_THR = (uint8_t)c;
}

static inline int uart2_getc(void) {
    while (!(UART2_LSR & UART_LSR_DR));
    return UART2_RBR & 0xFF;
}

static inline void uart2_puts(const char *s) {
    while (*s) uart2_putc(*s++);
}

/* ---------------- UART1（串口 A：PUF 通道）0x1002_3000，同一 16550 寄存器组 ---------------- */
#define UART1_BASE   0x10023000u
#define UART1_RBR    (*(volatile uint32_t*)(UART1_BASE + 0x00))
#define UART1_THR    (*(volatile uint32_t*)(UART1_BASE + 0x00))
#define UART1_DLL    (*(volatile uint32_t*)(UART1_BASE + 0x00))
#define UART1_IER    (*(volatile uint32_t*)(UART1_BASE + 0x04))
#define UART1_DLM    (*(volatile uint32_t*)(UART1_BASE + 0x04))
#define UART1_FCR    (*(volatile uint32_t*)(UART1_BASE + 0x08))
#define UART1_LCR    (*(volatile uint32_t*)(UART1_BASE + 0x0C))
#define UART1_LSR    (*(volatile uint32_t*)(UART1_BASE + 0x14))

static inline void uart1_init(uint32_t div) {
    GPIOB_IOFCFG |= (1u << 16) | (1u << 17);   // gpioB[16]RX/[17]TX → UART1
    UART1_LCR = 0x80u;
    UART1_DLL = div & 0xFFu;
    UART1_DLM = (div >> 8) & 0xFFu;
    UART1_LCR = 0x03u;
    UART1_FCR = 0x07u;
    UART1_IER = 0x00u;
}

static inline void uart1_putc(char c) {
    while (!(UART1_LSR & UART_LSR_THRE));
    UART1_THR = (uint8_t)c;
}

static inline int uart1_getc(void) {
    while (!(UART1_LSR & UART_LSR_DR));
    return UART1_RBR & 0xFF;
}

static inline void uart1_puts(const char *s) {
    while (*s) uart1_putc(*s++);
}
#endif
