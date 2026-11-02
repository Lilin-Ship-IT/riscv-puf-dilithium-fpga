// 阶段 1 keygen 单独自测 lv2：keygen(KAT seed) -> 与官方 KAT 逐字比对（不含 sign）
#include <stdint.h>
#include "dilithium_drv.h"
#include "kat_kg_lv2.h"

#define LVL_I    0
#define KGW      952

#define RESULT_ADDR  (*(volatile uint32_t*)0x9000FF00)
#define PASS_CNT     (*(volatile uint32_t*)0x9000FF04)
#define FAIL_CNT     (*(volatile uint32_t*)0x9000FF08)

static uint32_t kg_buf[KGW];

int main(void) {
    int pass = 0, fail = 0;
    for (int tv = 0; tv < 5; tv++) {
        dilithium_keygen(LVL_I, kat_seed_lv2[tv]);
        dil_read(kg_buf, KGW);
        int ok = 1;
        for (int i = 0; i < KGW; i++)
            if (kg_buf[i] != kat_kgexp_lv2[tv][i]) { ok = 0; break; }
        if (ok) pass++; else fail++;
    }
    PASS_CNT = pass;
    FAIL_CNT = fail;
    RESULT_ADDR = 0x1A2B3C4D;
    uint32_t r = (fail == 0) ? 1u : 0u;
    asm volatile ("mv x3, %0" :: "r"(r));
    while (1);
    return 0;
}
