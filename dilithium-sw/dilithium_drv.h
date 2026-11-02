#ifndef DILITHIUM_DRV_H
#define DILITHIUM_DRV_H
#include <stdint.h>

// PPI 基址（来自 config.v: E203_CFG_PPI_ADDR_BASE）
#define DIL_BASE    0x11000000u

#define DIL_CTRL    (*(volatile uint32_t*)(DIL_BASE + 0x00)) // [0]start [2:1]mode [6:4]sec_lvl
#define DIL_STATUS  (*(volatile uint32_t*)(DIL_BASE + 0x04)) // [0]busy [1]done [2]reject
#define DIL_MLEN    (*(volatile uint32_t*)(DIL_BASE + 0x08))
#define DIL_IEN     (*(volatile uint32_t*)(DIL_BASE + 0x0C))
#define DIL_PTR     (*(volatile uint32_t*)(DIL_BASE + 0x10)) // 输入缓冲写指针
#define DIL_WDATA   (*(volatile uint32_t*)(DIL_BASE + 0x14)) // 写数据(指针自增)
#define DIL_RDATA   (*(volatile uint32_t*)(DIL_BASE + 0x1C)) // 读数据(指针自增)

#define MODE_VERIFY 1u
#define DIL_DONE    2u
#define DIL_REJECT  4u

// 各等级固定 64-bit 字数（z / t1 / h）
static const int DIL_NZ[3]  = {288, 400, 560};
static const int DIL_NT1[3] = {160, 240, 320};
static const int DIL_NH[3]  = {11,  8,   11};

static inline void dil_load(const uint32_t *w, int n32) {
    for (int i = 0; i < n32; i++) DIL_WDATA = w[i];
}

// 输入流顺序: rho(8) | c(8) | z | t1 | {0,mlen}(2) | m | h —— 与 KAT hex 同序
static int dilithium_verify(int lvl_i, const uint32_t *rho, const uint32_t *c,
                            const uint32_t *z, const uint32_t *t1, uint32_t mlen,
                            const uint32_t *m, const uint32_t *h)
{
    int nm = (mlen + 7) / 8;
    DIL_PTR = 0;
    dil_load(rho, 8);  dil_load(c, 8);
    dil_load(z,  2*DIL_NZ[lvl_i]);  dil_load(t1, 2*DIL_NT1[lvl_i]);
    DIL_WDATA = 0;      DIL_WDATA = mlen;              // {48'd0, mlen}
    dil_load(m,  2*nm); dil_load(h, 2*DIL_NH[lvl_i]);
    DIL_MLEN = mlen;
    DIL_CTRL = ((uint32_t)(lvl_i==0?2:lvl_i==1?3:5) << 4) | (MODE_VERIFY << 1) | 1u;
    (void)DIL_STATUS;                                  // 哑读冲掉首拍（APB 读首拍返回 X）
    while (!(DIL_STATUS & DIL_DONE));
    return (DIL_STATUS & DIL_REJECT) ? -1 : 0;
}

// ---------------- keygen/sign ----------------
#define DIL_RPTR    (*(volatile uint32_t*)(DIL_BASE + 0x18)) // 输出缓冲读指针
#define MODE_KEYGEN 0u
#define MODE_SIGN   2u

// 各等级固定 64-bit 字数（s1 / s2 / t0），及 keygen/sign 输出 64b 字数
static const int DIL_NS1[3]   = {48,  80,  84};
static const int DIL_NS2[3]   = {48,  96,  96};
static const int DIL_NT0[3]   = {208, 312, 416};
static const int DIL_KG64[3]  = {476, 740, 928};   // rho|k|s1|s2|t1|t0|tr
static const int DIL_SIG64[3] = {303, 412, 575};   // z|h|c

static inline void dil_read(uint32_t *w, int n32) {
    DIL_RPTR = 0;
    (void)DIL_RDATA;   // 哑读冲掉首拍（PRDATA 注册式晚一拍）
    for (int i = 0; i < n32; i++) w[i] = DIL_RDATA;
}

static inline void dil_start(int lvl_i, uint32_t mode) {
    DIL_CTRL = ((uint32_t)(lvl_i==0?2:lvl_i==1?3:5) << 4) | (mode << 1) | 1u;
    (void)DIL_STATUS;                                  // 哑读冲掉首拍
    while (!(DIL_STATUS & DIL_DONE));
}

// keygen: inbuf = seed(8 字)；outbuf = rho|k|s1|s2|t1|t0|tr（2*DIL_KG64 字）
static void dilithium_keygen(int lvl_i, const uint32_t *seed) {
    DIL_PTR = 0;
    dil_load(seed, 8);
    dil_start(lvl_i, MODE_KEYGEN);
}

// sign: inbuf = rho(8) | {0,mlen} | tr(8) | m | k(8) | s1 | s2 | t0
// （确定性签名，无外部 rnd，对应 FIPS 204 deterministic 模式）
static void dilithium_sign(int lvl_i, const uint32_t *rho, uint32_t mlen,
                           const uint32_t *tr, const uint32_t *m,
                           const uint32_t *k, const uint32_t *s1,
                           const uint32_t *s2, const uint32_t *t0)
{
    int nm = (mlen + 7) / 8;
    DIL_PTR = 0;
    dil_load(rho, 8);
    DIL_WDATA = 0;      DIL_WDATA = mlen;              // {48'd0, mlen}，低 16 位有效
    dil_load(tr, 8);
    dil_load(m,  2*nm);
    dil_load(k,  8);
    dil_load(s1, 2*DIL_NS1[lvl_i]);
    dil_load(s2, 2*DIL_NS2[lvl_i]);
    dil_load(t0, 2*DIL_NT0[lvl_i]);
    DIL_MLEN = mlen;
    dil_start(lvl_i, MODE_SIGN);
}
#endif