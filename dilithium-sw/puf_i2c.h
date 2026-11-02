#ifndef PUF_I2C_H
#define PUF_I2C_H
/* HD13HS10K SRAM PUF（普安信）I2C 裸机驱动
 * 芯片：I2C 从机，7 位地址 0x64（写 0xC8 / 读 0xC9），寄存器地址固定 0x00
 * PUF_WORK：C8 + 00 + 50 + 32B 挑战 → STOP → 等 ≥15ms → C9 读回 32B 响应
 * 上电默认 PUF_ON，无需使能命令。
 *
 * E203 侧：I2C1 @ 0x1003_5000（apb_i2c），IOF 复用 gpioB[14]=SCL / gpioB[15]=SDA
 * 寄存器（PADDR[5:2] 译码，字地址步进 4）：
 *   +0x00 PRE   预分频（0x1F @16MHz 外设时钟 ≈ 100kHz，芯片上限 400kHz）
 *   +0x04 CTRL  [7]=EN [6]=IEN
 *   +0x08 RX    接收数据（只读）
 *   +0x0C SR    [7]=RxACK(0=收到ACK) [6]=BUSY [5]=AL [1]=TIP [0]=IF
 *   +0x10 TX    发送数据
 *   +0x14 CMD   [7]=STA [6]=STO [5]=RD [4]=WR [3]=ACK(读时置1=回NACK) [0]=IACK
 */
#include <stdint.h>
#include "uart_drv.h"

#define I2C1_BASE     0x10035000u
#define I2C_PRE_REG   (*(volatile uint32_t*)(I2C1_BASE + 0x00))
#define I2C_CTRL_REG  (*(volatile uint32_t*)(I2C1_BASE + 0x04))
#define I2C_RX_REG    (*(volatile uint32_t*)(I2C1_BASE + 0x08))
#define I2C_SR_REG    (*(volatile uint32_t*)(I2C1_BASE + 0x0C))
#define I2C_TX_REG    (*(volatile uint32_t*)(I2C1_BASE + 0x10))
#define I2C_CMD_REG   (*(volatile uint32_t*)(I2C1_BASE + 0x14))

#define I2C_CMD_STA   0x80u
#define I2C_CMD_STO   0x40u
#define I2C_CMD_RD    0x20u
#define I2C_CMD_WR    0x10u
#define I2C_CMD_NACK  0x08u

#define I2C_SR_RXACK  0x80u
#define I2C_SR_BUSY   0x40u
#define I2C_SR_TIP    0x02u

#define PUF_ADDR_W    0xC8u
#define PUF_ADDR_R    0xC9u
#define PUF_REG_ADDR  0x00u
#define PUF_CMD_WORK  0x50u
#define PUF_CMD_ON    0x20u
#define PUF_CMD_OFF   0x10u

/* 粗延时：外设时钟 16MHz，1ms ≈ 16000 拍 */
static void puf_delay_ms(uint32_t ms) {
    for (volatile uint32_t i = 0; i < ms * 16000u; i++) ;
}

/* 等待 TIP 清零；0=完成，-1=超时 */
static int i2c_wait_tip(void) {
    uint32_t t = 2000000u;
    while (I2C_SR_REG & I2C_SR_TIP) if (!--t) return -1;
    return 0;
}

/* 写一个字节并确认从机 ACK；0=成功，-1=超时，-2=NACK */
static int i2c_wr(uint8_t b, uint8_t cmd) {
    I2C_TX_REG = b;
    I2C_CMD_REG = cmd;
    if (i2c_wait_tip()) return -1;
    return (I2C_SR_REG & I2C_SR_RXACK) ? -2 : 0;
}

static void puf_i2c_init(void) {
    GPIOB_IOFCFG |= (1u << 14) | (1u << 15);   // gpioB[14]SCL/[15]SDA → I2C1
    I2C_PRE_REG  = 0x1Fu;                       // ≈100kHz
    I2C_CTRL_REG = 0x80u;                       // EN=1，轮询模式不开中断
}

/* PUF_WORK 挑战-响应：chal[32] → resp[32]；0=成功，非 0=失败 */
static int puf_work(const uint8_t *chal, uint8_t *resp) {
    if (i2c_wr(PUF_ADDR_W, I2C_CMD_STA | I2C_CMD_WR)) return -1;
    if (i2c_wr(PUF_REG_ADDR, I2C_CMD_WR)) return -2;
    if (i2c_wr(PUF_CMD_WORK, I2C_CMD_WR)) return -3;
    for (int i = 0; i < 32; i++)
        if (i2c_wr(chal[i], I2C_CMD_WR)) return -4;
    I2C_CMD_REG = I2C_CMD_STO;
    if (i2c_wait_tip()) return -5;
    /* 等 STOP 生效、总线释放 */
    {
        uint32_t t = 2000000u;
        while ((I2C_SR_REG & I2C_SR_BUSY) && --t) ;
        if (!t) return -6;
    }

    puf_delay_ms(20);                           // 手册要求 ≥15ms

    /* 读地址轮询直到 ACK（芯片忙时会 NACK），50 次 ×1ms ≈ 50ms 上限 */
    for (int retry = 0; retry < 50; retry++) {
        if (i2c_wr(PUF_ADDR_R, I2C_CMD_STA | I2C_CMD_WR) == 0) goto rd;
        puf_delay_ms(1);
    }
    return -7;
rd:
    for (int i = 0; i < 32; i++) {
        I2C_CMD_REG = (i == 31) ? (I2C_CMD_RD | I2C_CMD_NACK | I2C_CMD_STO)
                                : I2C_CMD_RD;   // 前 31 字节回 ACK，末字节 NACK+STOP
        if (i2c_wait_tip()) return -8;
        resp[i] = (uint8_t)(I2C_RX_REG & 0xFF);
    }
    return 0;
}

/* PUF_ON / PUF_OFF：上电默认 ON，一般用不到；0=成功 */
static int puf_set_power(uint8_t on_off) {
    if (i2c_wr(PUF_ADDR_W, I2C_CMD_STA | I2C_CMD_WR)) return -1;
    if (i2c_wr(PUF_REG_ADDR, I2C_CMD_WR)) return -2;
    if (i2c_wr(on_off, I2C_CMD_WR)) return -3;
    I2C_CMD_REG = I2C_CMD_STO;
    return i2c_wait_tip();
}
#endif
