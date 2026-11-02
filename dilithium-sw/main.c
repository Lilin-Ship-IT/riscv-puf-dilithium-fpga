/*
 * main_demo.c — E203+Dilithium+PUF 全链路演示固件
 *
 * 命令（PC↔FPGA 串口；PUF 通道仿真走 UART1、真板走 I2C1，由 PUF_I2C 宏切换）：
 *   CHAL <64hex>   挑战 C → PUF → 响应 R 作 keygen 种子生成密钥对
 *   SEED <64hex>   直接喂种子（旁路 PUF 调试用）
 *   FW <4096hex>   收 2KB 固件，软件 SHA3-256 求摘要作待签消息
 *   SIGN           对摘要签名，回 SIG <hex>
 *   VER <hex>      验签，回 OK / FAIL
 *   PUBK / PRIV    回传公钥 / 私钥
 *   WIPE           清零驻留私钥
 *   DONE           结束，x3=1 通知 tb
 *   HELP           帮助
 *
 * hex 文本为自然字节序；打包进 32bit 字时高字节在前。确定性签名（无外部 rnd）。
 */
#include <stdint.h>
#include "dilithium_drv.h"
#include "uart_drv.h"
#include "sha3_sw.c"
#ifdef PUF_I2C
#include "puf_i2c.h"
#endif

#define LVL_I     0                  // 演示固定 Dilithium lv2
#define KGW       952                // keygen 输出 32b 字数 (lv2)
#define SIGW      606                // sign 输出 32b 字数 (lv2)
#define PKW       (8 + 2*160)        // pk = rho(8) | t1(320)
#define LINE_MAX  4920               // 最大请求帧: "VER "+4848hex+"\r\n"

static uint32_t kg_buf[KGW];         // rho|k|s1|s2|t1|t0|tr（sk 段驻留 DTCM）
static uint32_t sig_buf[SIGW];       // z|h|c
static uint8_t  fw_buf[2048];
static uint8_t  digest[32];
static uint8_t  line_buf[LINE_MAX];
static int      key_ready = 0, msg_ready = 0;

/* sk 组成: rho,k,tr,s1,s2,t0；pk 组成: rho,t1 */
#define P_RHO (kg_buf)
#define P_K   (kg_buf + 8)
#define P_S1  (kg_buf + 16)
#define P_S2  (P_S1 + 2*DIL_NS1[LVL_I])
#define P_T1  (P_S2 + 2*DIL_NS2[LVL_I])
#define P_T0  (P_T1 + 2*DIL_NT1[LVL_I])
#define P_TR  (P_T0 + 2*DIL_NT0[LVL_I])

static int hexval(int c) {
    if (c >= '0' && c <= '9') return c - '0';
    if (c >= 'a' && c <= 'f') return c - 'a' + 10;
    if (c >= 'A' && c <= 'F') return c - 'A' + 10;
    return -1;
}

static int read_line(uint8_t *buf, int max) {
    int n = 0;
    for (;;) {
        int c = uart_getc();
        if (c == '\n') break;
        if (c != '\r' && n < max - 1) buf[n++] = (uint8_t)c;
    }
    buf[n] = 0;
    return n;
}

static int read_line1(uint8_t *buf, int max) {
    int n = 0;
    for (;;) {
        int c = uart1_getc();
        if (c == '\n') break;
        if (c != '\r' && n < max - 1) buf[n++] = (uint8_t)c;
    }
    buf[n] = 0;
    return n;
}

/* hex 文本 → 32bit 字流（8 hex/字，高 nibble 在前） */
static void hex2words(const uint8_t *hex, uint32_t *w, int n32) {
    for (int i = 0; i < n32; i++) {
        uint32_t v = 0;
        for (int j = 0; j < 8; j++) v = (v << 4) | (uint32_t)hexval(hex[8*i + j]);
        w[i] = v;
    }
}

static void hex2bytes(const uint8_t *hex, uint8_t *b, int nb) {
    for (int i = 0; i < nb; i++)
        b[i] = (uint8_t)((hexval(hex[2*i]) << 4) | hexval(hex[2*i+1]));
}

static void put_words_hex(const uint32_t *w, int n32) {
    for (int i = 0; i < n32; i++) uart_puthex32(w[i]);
}

static void put_bhex(uint8_t v) {
    int hi = (v >> 4) & 0xF, lo = v & 0xF;
    uart_putc(hi < 10 ? '0'+hi : 'a'+(hi-10));
    uart_putc(lo < 10 ? '0'+lo : 'a'+(lo-10));
}

static void do_keygen(const uint8_t *seed32) {
    uint32_t sw[8];
    for (int i = 0; i < 8; i++)
        sw[i] = ((uint32_t)seed32[4*i] << 24) | ((uint32_t)seed32[4*i+1] << 16) |
                ((uint32_t)seed32[4*i+2] << 8) | (uint32_t)seed32[4*i+3];
    dilithium_keygen(LVL_I, sw);
    dil_read(kg_buf, KGW);
    key_ready = 1;
}

static int starts_with(const uint8_t *s, const char *p) {
    while (*p) if (*s++ != (uint8_t)*p++) return 0;
    return 1;
}

/* 容忍行首幻影垃圾前缀（UART 首帧异常规避） */
static uint8_t *find_sub(uint8_t *s, const char *p) {
    for (; *s; s++) {
        const char *q = p; uint8_t *t = s;
        while (*q && *t == (uint8_t)*q) { t++; q++; }
        if (!*q) return s;
    }
    return 0;
}

static int hex_ok(const uint8_t *p, int n) {
    for (int i = 0; i < n; i++) if (hexval(p[i]) < 0) return 0;
    return 1;
}

int main(void) {
    uart_init(UART_BAUD_DIV);
#ifdef PUF_I2C
    puf_i2c_init();                 // I2C1：gpioB[14]SCL/[15]SDA
    puf_delay_ms(10);
    puf_set_power(PUF_CMD_ON);      // 首笔 I2C 事务实测易 NACK，丢弃结果
    puf_delay_ms(5);
    puf_set_power(PUF_CMD_ON);
    puf_delay_ms(5);
#else
    uart1_init(UART_BAUD_DIV);
#endif
    uart_puts("E203+Dilithium+PUF demo ready. HELP for cmds.\r\n");

    for (;;) {
        int n = read_line(line_buf, LINE_MAX);
        uint8_t *cmd;

        if ((cmd = find_sub(line_buf, "CHAL ")) && hex_ok(cmd + 5, 64)) {
#ifdef PUF_I2C
            /* C → PUF_WORK(0x50)+32B挑战 → 等≥15ms → 读回 R → keygen(R) */
            uint8_t chal32[32], r[32];
            hex2bytes(cmd + 5, chal32, 32);
            int rc = -1;
            for (int att = 0; att < 3 && rc != 0; att++) {   // 冷启动首笔事务易 NACK，重试
                rc = puf_work(chal32, r);
                if (rc != 0) {
                    puf_set_power(PUF_CMD_ON);   // 重试前补一发 PUF_ON，救 OFF 态
                    puf_delay_ms(5);
                }
            }
            if (rc == 0) {
                uart_puts("RES PUF R ");
                for (int i = 0; i < 32; i++) put_bhex(r[i]);
                uart_puts("\r\n");
                do_keygen(r);
                uart_puts("RES KEYGEN OK (seed=PUF R)\r\n");
            } else {
                uart_puts("RES PUF TIMEOUT/ERR rc=-");
                uart_putc('0' + (-rc));
                uart_puts("\r\n");
            }
#else
            /* C → UART1 转发给 PUF 模型 → 收 R → keygen(R) */
            uart1_puts((const char *)cmd); uart1_puts("\r\n");
            int found = 0, tries = 0;
            while (!found && ++tries < 10) {
                int rn = read_line1(line_buf + 2048, 256);
                uint8_t *rp = find_sub(line_buf + 2048, "R ");
                if (rp && hex_ok(rp + 2, 64)) {
                    uint8_t r[32];
                    hex2bytes(rp + 2, r, 32);
                    do_keygen(r);
                    uart_puts("RES KEYGEN OK (seed=PUF R)\r\n");
                    found = 1;
                }
            }
            if (!found) uart_puts("RES PUF TIMEOUT/ERR\r\n");
#endif
        } else if ((cmd = find_sub(line_buf, "SEED ")) && hex_ok(cmd + 5, 64)) {
            uint8_t r[32];
            hex2bytes(cmd + 5, r, 32);
            do_keygen(r);
            uart_puts("RES KEYGEN OK (seed=direct)\r\n");
#ifdef PUF_I2C
        } else if (find_sub(line_buf, "PON")) {
            uart_puts(puf_set_power(PUF_CMD_ON) == 0 ? "RES PUF ON OK\r\n" : "RES PUF ON ERR\r\n");
            puf_delay_ms(5);
        } else if (find_sub(line_buf, "POFF")) {
            uart_puts(puf_set_power(PUF_CMD_OFF) == 0 ? "RES PUF OFF OK\r\n" : "RES PUF OFF ERR\r\n");
#endif
        } else if ((cmd = find_sub(line_buf, "FW ")) && hex_ok(cmd + 3, 4096)) {
            hex2bytes(cmd + 3, fw_buf, 2048);
            sha3_256(fw_buf, 2048, digest);
            msg_ready = 1;
            uart_puts("RES FW SHA3 ");
            for (int i = 0; i < 32; i++) put_bhex(digest[i]);
            uart_puts("\r\n");
        } else if (find_sub(line_buf, "SIGN")) {
            if (!key_ready || !msg_ready) { uart_puts("RES NOT READY\r\n"); continue; }
            uint32_t mw[8];
            for (int i = 0; i < 8; i++)
                mw[i] = ((uint32_t)digest[4*i] << 24) | ((uint32_t)digest[4*i+1] << 16) |
                        ((uint32_t)digest[4*i+2] << 8) | (uint32_t)digest[4*i+3];
            dilithium_sign(LVL_I, P_RHO, 32, P_TR, mw, P_K, P_S1, P_S2, P_T0);
            dil_read(sig_buf, SIGW);
            uart_puts("SIG ");
            put_words_hex(sig_buf, SIGW);
            uart_puts("\r\n");
        } else if ((cmd = find_sub(line_buf, "VER ")) && hex_ok(cmd + 4, 8*SIGW)) {
            if (!key_ready || !msg_ready) { uart_puts("RES NOT READY\r\n"); continue; }
            hex2words(cmd + 4, sig_buf, SIGW);
            uint32_t *z = sig_buf;
            uint32_t *h = z + 2*DIL_NZ[LVL_I];
            uint32_t *c = h + 2*DIL_NH[LVL_I];
            uint32_t mw[8];
            for (int i = 0; i < 8; i++)
                mw[i] = ((uint32_t)digest[4*i] << 24) | ((uint32_t)digest[4*i+1] << 16) |
                        ((uint32_t)digest[4*i+2] << 8) | (uint32_t)digest[4*i+3];
            int rc = dilithium_verify(LVL_I, P_RHO, c, z, P_T1, 32, mw, h);
            uart_puts(rc == 0 ? "OK\r\n" : "FAIL\r\n");
        } else if (find_sub(line_buf, "PUBK")) {
            if (!key_ready) { uart_puts("RES NOT READY\r\n"); continue; }
            uart_puts("PUBK ");
            put_words_hex(P_RHO, 8);
            put_words_hex(P_T1, 2*DIL_NT1[LVL_I]);
            uart_puts("\r\n");
        } else if (find_sub(line_buf, "PRIV")) {
            if (!key_ready) { uart_puts("RES NOT READY\r\n"); continue; }
            uart_puts("PRIV ");
            put_words_hex(P_RHO, 8);   put_words_hex(P_K, 8);
            put_words_hex(P_TR, 8);    put_words_hex(P_S1, 2*DIL_NS1[LVL_I]);
            put_words_hex(P_S2, 2*DIL_NS2[LVL_I]); put_words_hex(P_T0, 2*DIL_NT0[LVL_I]);
            uart_puts("\r\n");
        } else if (find_sub(line_buf, "WIPE")) {
            /* 覆写清零驻留 sk 段（k/s1/s2/t0/tr） */
            for (int i = 8; i < 16; i++) kg_buf[i] = 0;
            for (int i = 16; i < 16 + 2*DIL_NS1[LVL_I]; i++) kg_buf[i] = 0;
            for (int i = 0; i < 2*DIL_NS2[LVL_I]; i++) P_S2[i] = 0;
            for (int i = 0; i < 2*DIL_NT0[LVL_I]; i++) P_T0[i] = 0;
            for (int i = 0; i < 8; i++) P_TR[i] = 0;
            key_ready = 0;
            uart_puts("RES WIPED\r\n");
        } else if (find_sub(line_buf, "DONE")) {
            uart_puts("RES DONE\r\n");
            asm volatile ("mv x3, %0" :: "r"(1u));
            while (1);
        } else if (find_sub(line_buf, "HELP")) {
            uart_puts("cmds: CHAL <64hex> | SEED <64hex> | FW <4096hex> | SIGN | VER <hex> | PUBK | PRIV | WIPE | DONE | HELP"
#ifdef PUF_I2C
                      " | PON | POFF"
#endif
                      "\r\n");
        } else if (n >= 3) {   // 碎帧静默丢弃
            uart_puts("RES UNKNOWN CMD n=");
            put_bhex((uint8_t)n);
            uart_puts(" head=");
            for (int i = 0; i < 8 && i < n; i++) put_bhex(line_buf[i]);
            uart_puts("\r\n");
        }
    }
    return 0;
}
