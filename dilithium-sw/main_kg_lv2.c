// 阶段 1 自测 lv2：keygen(KAT seed) 逐字比对 KAT；sign(kg 输出=KAT sk, m) -> verify(KAT pk) 必须 PASS
// 确定性签名（无外部 rnd，FIPS 204 deterministic 模式）；与官方 hedged KAT 签名向量不做逐字节判据
#include <stdint.h>
#include "dilithium_drv.h"
#include "kat_kg_lv2.h"

#define LVL_I    0
#define KGW      952               // keygen 输出 32b 字数 = 2*476
#define SIGW     606               // sign 输出 32b 字数 = 2*303
#define HDR      kat_kg_lv2.h

#define RESULT_ADDR  (*(volatile uint32_t*)0x9000FF00)
#define PASS_CNT     (*(volatile uint32_t*)0x9000FF04)
#define FAIL_CNT     (*(volatile uint32_t*)0x9000FF08)

static uint32_t kg_buf[KGW];
static uint32_t sig_buf[SIGW];

int main(void) {
    int pass = 0, fail = 0;
    for (int tv = 0; tv < 5; tv++) {
        // ① keygen(seed) → 与官方 KAT 逐字比对
        dilithium_keygen(LVL_I, kat_seed_lv2[tv]);
        dil_read(kg_buf, KGW);
        int kg_ok = 1;
        for (int i = 0; i < KGW; i++)
            if (kg_buf[i] != kat_kgexp_lv2[tv][i]) { kg_ok = 0; break; }

        // 段切片（32b 字）：rho|k|s1|s2|t1|t0|tr
        uint32_t *rho = kg_buf, *k = kg_buf + 8, *s1 = kg_buf + 16;
        uint32_t *s2 = s1 + 2*DIL_NS1[LVL_I];
        uint32_t *t1 = s2 + 2*DIL_NS2[LVL_I];
        uint32_t *t0 = t1 + 2*DIL_NT1[LVL_I];
        uint32_t *tr = t0 + 2*DIL_NT0[LVL_I];

        // ② sign(sk 段, m) → 读出签名 z|h|c
        dilithium_sign(LVL_I, rho, kat_mglen_lv2[tv], tr, kat_mg_lv2[tv], k, s1, s2, t0);
        dil_read(sig_buf, SIGW);
        uint32_t *z = sig_buf;
        uint32_t *h = z + 2*DIL_NZ[LVL_I];
        uint32_t *c = h + 2*DIL_NH[LVL_I];

        // ③ verify(pk=(rho,t1), sig, m) → 0=PASS 为 sign 自测主判据
        int r = dilithium_verify(LVL_I, rho, c, z, t1, kat_mglen_lv2[tv], kat_mg_lv2[tv], h);
        if (kg_ok && r == 0) pass++; else fail++;
    }
    PASS_CNT = pass;
    FAIL_CNT = fail;
    RESULT_ADDR = 0x1A2B3C4D;
    uint32_t r = (fail == 0) ? 1u : 0u;
    asm volatile ("mv x3, %0" :: "r"(r));   // 全过=1 → tb 打印 TEST_PASS
    while (1);
    return 0;
}
