/*
 * sha3_sw.c - 软件 SHA3-256（E203 演示固件用，求 2KB 固件摘要）
 *
 * 来源: 基于 Markku-Juhani O. Saarinen 的 tiny_sha3 改写
 *       https://github.com/mjosaarinen/tiny_sha3
 * 许可证: CC0 / Public Domain（原作者声明），本文件同样置于公有领域
 *
 * 仅保留 SHA3-256 需要的 keccak-f[1600] 与吸收/挤压流程，
 * 32bit 平台友好（无 64bit 除法、无动态内存）。
 */

#include <stdint.h>
#include <string.h>

/* -nostdlib 环境无 libgcc/libc：自供 64bit 移位与 memset/memcpy
 * （rv32 下 64bit 移位会被编译为 __ashldi3/__lshrdi3 调用） */
typedef union { uint64_t u64; uint32_t u32[2]; } u64u_t;   // 小端: u32[0]=低32位

uint64_t __ashldi3(uint64_t x, int n) {
    u64u_t r, v; v.u64 = x;
    if (n <= 0) return x;
    if (n < 32) { r.u32[1] = (v.u32[1] << n) | (v.u32[0] >> (32 - n)); r.u32[0] = v.u32[0] << n; }
    else if (n < 64) { r.u32[1] = v.u32[0] << (n - 32); r.u32[0] = 0; }
    else { r.u32[0] = 0; r.u32[1] = 0; }
    return r.u64;
}

uint64_t __lshrdi3(uint64_t x, int n) {
    u64u_t r, v; v.u64 = x;
    if (n <= 0) return x;
    if (n < 32) { r.u32[0] = (v.u32[0] >> n) | (v.u32[1] << (32 - n)); r.u32[1] = v.u32[1] >> n; }
    else if (n < 64) { r.u32[0] = v.u32[1] >> (n - 32); r.u32[1] = 0; }
    else { r.u32[0] = 0; r.u32[1] = 0; }
    return r.u64;
}

void *memset(void *d, int c, unsigned n) {
    uint8_t *p = (uint8_t *)d;
    while (n--) *p++ = (uint8_t)c;
    return d;
}

void *memcpy(void *d, const void *s, unsigned n) {
    uint8_t *p = (uint8_t *)d;
    const uint8_t *q = (const uint8_t *)s;
    while (n--) *p++ = *q++;
    return d;
}

static uint64_t keccakf_rndc[24] = {
    0x0000000000000001ULL, 0x0000000000008082ULL, 0x800000000000808aULL,
    0x8000000080008000ULL, 0x000000000000808bULL, 0x0000000080000001ULL,
    0x8000000080008081ULL, 0x8000000000008009ULL, 0x000000000000008aULL,
    0x0000000000000088ULL, 0x0000000080008009ULL, 0x000000008000000aULL,
    0x000000008000808bULL, 0x800000000000008bULL, 0x8000000000008089ULL,
    0x8000000000008003ULL, 0x8000000000008002ULL, 0x8000000000000080ULL,
    0x000000000000800aULL, 0x800000008000000aULL, 0x8000000080008081ULL,
    0x8000000000008080ULL, 0x0000000080000001ULL, 0x8000000080008008ULL
};

static const int keccakf_rotc[24] = {
    1, 3, 6, 10, 15, 21, 28, 36, 45, 55, 2, 14,
    27, 41, 56, 8, 25, 43, 62, 18, 39, 61, 20, 44
};

static const int keccakf_piln[24] = {
    10, 7, 11, 17, 18, 3, 5, 16, 8, 21, 24, 4,
    15, 23, 19, 13, 12, 2, 20, 14, 22, 9, 6, 1
};

static inline uint64_t rol64(uint64_t x, int n)
{
    return (x << n) | (x >> (64 - n));
}

static void keccakf(uint64_t st[25])
{
    int i, j, r;
    uint64_t t, bc[5];

    for (r = 0; r < 24; r++) {
        /* Theta */
        for (i = 0; i < 5; i++)
            bc[i] = st[i] ^ st[i + 5] ^ st[i + 10] ^ st[i + 15] ^ st[i + 20];
        for (i = 0; i < 5; i++) {
            t = bc[(i + 4) % 5] ^ rol64(bc[(i + 1) % 5], 1);
            for (j = 0; j < 25; j += 5)
                st[j + i] ^= t;
        }
        /* Rho Pi */
        t = st[1];
        for (i = 0; i < 24; i++) {
            j = keccakf_piln[i];
            bc[0] = st[j];
            st[j] = rol64(t, keccakf_rotc[i]);
            t = bc[0];
        }
        /* Chi */
        for (j = 0; j < 25; j += 5) {
            for (i = 0; i < 5; i++)
                bc[i] = st[j + i];
            for (i = 0; i < 5; i++)
                st[j + i] ^= (~bc[(i + 1) % 5]) & bc[(i + 2) % 5];
        }
        /* Iota */
        st[0] ^= keccakf_rndc[r];
    }
}

/* 吸收模式上下文: rate = 136 字节 (1088 bit) for SHA3-256 */
#define SHA3_256_RATE 136

typedef struct {
    uint64_t st[25];
    uint32_t pos;              /* 当前块内字节偏移 */
} sha3_256_ctx;

static void sha3_256_init(sha3_256_ctx *c)
{
    memset(c, 0, sizeof(*c));
}

static void sha3_256_update(sha3_256_ctx *c, const uint8_t *in, uint32_t len)
{
    uint32_t i;
    for (i = 0; i < len; i++) {
        ((uint8_t *)c->st)[c->pos] ^= in[i];   /* 小端序吸收 */
        if (++c->pos == SHA3_256_RATE) {
            keccakf(c->st);
            c->pos = 0;
        }
    }
}

static void sha3_256_final(sha3_256_ctx *c, uint8_t md[32])
{
    /* SHA3 域分隔 0x06 + 结尾 0x80 */
    ((uint8_t *)c->st)[c->pos] ^= 0x06;
    ((uint8_t *)c->st)[SHA3_256_RATE - 1] ^= 0x80;
    keccakf(c->st);
    memcpy(md, c->st, 32);
}

/* 一次性接口: 对 len 字节数据求 SHA3-256 */
void sha3_256(const uint8_t *in, uint32_t len, uint8_t md[32])
{
    sha3_256_ctx c;
    sha3_256_init(&c);
    sha3_256_update(&c, in, len);
    sha3_256_final(&c, md);
}
