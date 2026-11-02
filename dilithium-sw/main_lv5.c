#include <stdint.h>
#include "dilithium_drv.h"
#include "kat_lv5.h"

#define RESULT_ADDR  (*(volatile uint32_t*)0x9000FF00)
#define PASS_CNT     (*(volatile uint32_t*)0x9000FF04)
#define FAIL_CNT     (*(volatile uint32_t*)0x9000FF08)

int main(void) {
    int pass = 0, fail = 0;
    for (int tv = 0; tv < 5; tv++) {
        int r = dilithium_verify(2, kat_rho_lv5[tv], kat_c_lv5[tv],
                kat_z_lv5[tv], kat_t1_lv5[tv], kat_mlen_lv5[tv],
                kat_m_lv5[tv], kat_h_lv5[tv]);
        if (r == 0) pass++; else fail++;
    }
    PASS_CNT = pass;
    FAIL_CNT = fail;
    RESULT_ADDR = 0x1A2B3C4D;
    uint32_t r = (fail == 0) ? 1u : 0u;
    asm volatile ("mv x3, %0" :: "r"(r));   // 全过=1 → tb 打印 TEST_PASS
    while (1);
    return 0;
}
