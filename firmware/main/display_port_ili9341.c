/* display_port_ili9341.c — the 2.8" CYD (Freenove ESP32-S3 Display 2.8, FNK0104B; 2026-11-18): an ILI9341V IPS panel
 * over 4-wire SPI via esp_lcd, 240 x 320 glass scanned LANDSCAPE as 320 x 240 (MADCTL swap_xy, the vendor's rotation 1).
 *
 * The tank renders row-major TANK_W x TANK_H (320 x 240) into a frame that is already in the panel's byte order
 * (PT_FB_SWAP, render.h). So there is no transpose here: the panel's own scan does the turn, the flip is the two
 * mirrors (MADCTL MX|MY = 180 degrees, the picture's rows and columns both reversed), and a frame goes out as stripes
 * of whole rows. Without PT_FB_SWAP the stripes are byte-swapped on the way (the same two pixels a word).
 *
 * The flush is the sh8601 port's asynchronous one: a flush task owns the frame once it is drawn, copies each stripe out
 * of PSRAM with the CPU into one of two internal-RAM DMA stripes, and the SPI DMA sends it while the tank task renders
 * the next frame. The copy is the CPU's (the GDMA copies lost to the PSRAM bus on the AMOLEDs; the same bus here).
 *
 * Brightness is the backlight's PWM on GPIO45 (LEDC, active high). The panel's own brightness command is not used.
 * The panel's reset is the chip's (no pin); it is reset by software at init. The panel is dark until the first whole
 * frame is in, as the AMOLED's (its memory holds whatever it held before the reset).
 *
 * The chips are asked here (display_port_init), and the board is decided by board_probe.h's table: this image is the
 * CYD's (board_port_hw reads cyd28 once the chips agree). This port also owns the board's I2C bus (touch, codec, the
 * I2C socket), as the AMOLED port does - board_i2c_bus() is how everything else reaches it. */
#include "display_port.h"
#include "board_pins.h"
#include "board_probe.h"
#include "tank.h"
#include "render.h"
#include "driver/spi_master.h"
#include "driver/i2c_master.h"
#include "driver/ledc.h"
#include "driver/gpio.h"
#include "esp_lcd_panel_io.h"
#include "esp_lcd_panel_ops.h"
#include "esp_lcd_ili9341.h"
#include "esp_log.h"
#include "esp_heap_caps.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/semphr.h"
#include "freertos/task.h"
#include <string.h>

static const char *TAG = "ili9341";
#define LCD_HOST    SPI2_HOST
#define STRIPE_ROWS 8                                   /* rows per DMA stripe: 320 x 8 x 2 = 5 KB, two in internal RAM (the app is short of it) */
#define STRIPE_BYTES (TANK_W * STRIPE_ROWS * 2)
/* 40 MHz: the vendor's setting. The community port's bench found 80 MHz stripes the panel (2026-09-26). */
#define LCD_PCLK_HZ (40 * 1000 * 1000)

/* How the glass is mounted: the vendor's TFT_eSPI rotation 1 (MV | BGR) is swap_xy with no mirror, and the
 * colour order and inversion are the two things the CYD clones differ in (both as the vendor's and the port's). */
#define LCD_SWAP_XY   true
#define LCD_MIRROR_X  false
#define LCD_MIRROR_Y  false
#define LCD_BGR       true
#define LCD_INVERT    true                              /* the IPS ILI9341V panel wants inversion on */

#define BL_TIMER   LEDC_TIMER_0
#define BL_CHANNEL LEDC_CHANNEL_0

static esp_lcd_panel_io_handle_t s_io;
static esp_lcd_panel_handle_t    s_panel;
static i2c_master_bus_handle_t   s_i2c;
static uint16_t *s_stripe[2];                           /* STRIPE_BYTES each, DMA-capable: ping-pong */
static SemaphoreHandle_t s_stripe_free;                 /* counts the stripe buffers not in DMA flight */
static int64_t s_prof_wait, s_prof_send;                /* where a flush's time goes (display_port_flush_prof) */
static uint8_t s_brightness = 0xFF;                     /* the level wanted: the backlight shows it once the panel is lit */
static bool s_dark = true;                              /* no whole frame in the panel's memory yet: the backlight stays off */
static bool s_asleep;                                   /* display_port_sleep: the backlight off, the panel in sleep-in */
static volatile bool s_inverted;                        /* the 180-degree flip wanted (display_port_set_inverted) */
static bool s_applied_inverted;                         /* the one MADCTL has */
/* the board, as the chips said at init (board_probe.h): NULL-able identity for the release and the installer */
static volatile bool s_probed;
static board_kind_t s_kind;
static uint8_t s_es7210;

i2c_master_bus_handle_t board_i2c_bus(void) { return s_i2c; }
bool board_is_v2(void) { return false; }                /* the AMOLED's revision question; never asked here */
bool board_is_round(void) { return false; }
bool board_is_175(void) { return false; }
bool board_is_watch(void) { return false; }
bool board_is_square(void) { return false; }
bool board_has_expander(void) { return false; }
uint8_t board_es7210_addr(void) { return s_es7210; }
void board_sd_select(bool on) { (void)on; }             /* the CYD's socket has no card select: nothing to drive */
int  board_pwr_sense_pin(void) { return -1; }           /* no PWR key sense line: BOOT is the key here */
bool board_port_probed(void) { return s_probed; }
const char *board_port_hw(void) { return board_kind_id(s_kind, false); }   /* "cyd28" once the chips agree; NULL before, or if they don't */

/* ---- the backlight: LEDC PWM on GPIO45, 8-bit. Dark until the first frame, and asleep; the level waits for those ---- */
static void backlight_init(void) {
    ledc_timer_config_t timer = { .speed_mode = LEDC_LOW_SPEED_MODE, .duty_resolution = LEDC_TIMER_8_BIT,
                                  .timer_num = BL_TIMER, .freq_hz = 5000, .clk_cfg = LEDC_AUTO_CLK };
    ESP_ERROR_CHECK(ledc_timer_config(&timer));
    ledc_channel_config_t channel = { .gpio_num = PIN_LCD_BL, .speed_mode = LEDC_LOW_SPEED_MODE,
                                      .channel = BL_CHANNEL, .timer_sel = BL_TIMER, .duty = 0, .hpoint = 0 };
    ESP_ERROR_CHECK(ledc_channel_config(&channel));
}
static void light(void) {
    uint32_t duty = (s_asleep || s_dark) ? 0 : s_brightness;
    ledc_set_duty(LEDC_LOW_SPEED_MODE, BL_CHANNEL, duty);
    ledc_update_duty(LEDC_LOW_SPEED_MODE, BL_CHANNEL);
}

static bool on_trans_done(esp_lcd_panel_io_handle_t io, esp_lcd_panel_io_event_data_t *ev, void *ctx) {
    (void)io; (void)ev; (void)ctx;
    BaseType_t woken = pdFALSE;
    xSemaphoreGiveFromISR(s_stripe_free, &woken);
    return woken == pdTRUE;
}
static inline void stripe_take(void) {
    int64_t t = esp_timer_get_time();
    xSemaphoreTake(s_stripe_free, portMAX_DELAY);
    s_prof_wait += esp_timer_get_time() - t;
}

/* MADCTL for the current flip: the mounting above, with both mirrors toggled for upside down (a 180-degree turn of the scan) */
static void apply_orientation(void) {
    esp_lcd_panel_swap_xy(s_panel, LCD_SWAP_XY);
    esp_lcd_panel_mirror(s_panel, LCD_MIRROR_X ^ s_inverted, LCD_MIRROR_Y ^ s_inverted);
    s_applied_inverted = s_inverted;
}

static bool probe(uint8_t addr) {                       /* three tries: a board is not chosen on one glitch */
    for (int i = 0; i < 3; i++) if (i2c_master_probe(s_i2c, addr, 50) == ESP_OK) return true;
    return false;
}
static uint8_t probe_es7210(void) {                     /* the ES7210 at 0x40 + 0..3: the CYD has none, so this answers 0 */
    for (int i = 0; i < ES7210_ADDR_COUNT; i++) if (probe((uint8_t)(ES7210_ADDR_FIRST + i))) return (uint8_t)(ES7210_ADDR_FIRST + i);
    return 0;
}

bool display_port_init(void) {
    i2c_master_bus_config_t bus = { .i2c_port = I2C_NUM_0, .sda_io_num = PIN_I2C_SDA, .scl_io_num = PIN_I2C_SCL,
        .clk_source = I2C_CLK_SRC_DEFAULT, .glitch_ignore_cnt = 7, .flags.enable_internal_pullup = true };
    ESP_ERROR_CHECK(i2c_new_master_bus(&bus, &s_i2c));

    /* which board: the chips that answer decide it (board_decide, table-tested on the host). The CYD has no expander, no
       ES7210 and no PMIC; it has an FT6336 at 0x38 and an ES8311 at 0x18. The panel is driven either way (this image is
       the CYD's), but the release identity is only claimed when the chips say so. */
    board_chips_t chips = { 0 };
    chips.expander = probe(I2C_ADDR_EXPANDER);
    chips.es7210 = s_es7210 = probe_es7210();
    chips.pmic = probe(0x34);
    chips.ft6336 = probe(I2C_ADDR_FT6336);
    chips.es8311 = probe(0x18) || probe(0x19);
    s_kind = board_decide(chips);
    s_probed = true;
    ESP_LOGI(TAG, "chips: expander %d, ES7210 0x%02x, PMIC %d, FT6336 %d, ES8311 %d -> %s", chips.expander, chips.es7210, chips.pmic,
             chips.ft6336, chips.es8311, board_kind_id(s_kind, false) ? board_kind_id(s_kind, false) : "not the CYD by its chips (the panel runs anyway)");

    /* the backlight pins: a deep sleep held them; the boot takes them back (the touch port configures its reset after this) */
    gpio_hold_dis(PIN_LCD_BL); gpio_hold_dis(PIN_LCD_CS); gpio_hold_dis(PIN_TP_RST);
    backlight_init();                                   /* dark until the first frame is in */

    for (int i = 0; i < 2; i++) {
        s_stripe[i] = heap_caps_malloc(STRIPE_BYTES, MALLOC_CAP_DMA | MALLOC_CAP_INTERNAL);
        if (!s_stripe[i]) { ESP_LOGE(TAG, "no internal RAM for a %d-byte stripe", (int)STRIPE_BYTES); return false; }
    }
    s_stripe_free = xSemaphoreCreateCounting(2, 2);

    const spi_bus_config_t spi = { .sclk_io_num = PIN_LCD_SCLK, .mosi_io_num = PIN_LCD_MOSI, .miso_io_num = PIN_LCD_MISO,
                                   .quadwp_io_num = -1, .quadhd_io_num = -1, .max_transfer_sz = STRIPE_BYTES };
    ESP_ERROR_CHECK(spi_bus_initialize(LCD_HOST, &spi, SPI_DMA_CH_AUTO));
    const esp_lcd_panel_io_spi_config_t io_cfg = { .cs_gpio_num = PIN_LCD_CS, .dc_gpio_num = PIN_LCD_DC,
        .spi_mode = 0, .pclk_hz = LCD_PCLK_HZ, .trans_queue_depth = 4, .on_color_trans_done = on_trans_done,
        .lcd_cmd_bits = 8, .lcd_param_bits = 8 };
    ESP_ERROR_CHECK(esp_lcd_new_panel_io_spi((esp_lcd_spi_bus_handle_t)LCD_HOST, &io_cfg, &s_io));
    const esp_lcd_panel_dev_config_t pcfg = { .reset_gpio_num = -1,   /* the reset is the chip's: a software reset below */
        .rgb_ele_order = LCD_BGR ? LCD_RGB_ELEMENT_ORDER_BGR : LCD_RGB_ELEMENT_ORDER_RGB, .bits_per_pixel = 16 };
    ESP_ERROR_CHECK(esp_lcd_new_panel_ili9341(s_io, &pcfg, &s_panel));
    ESP_ERROR_CHECK(esp_lcd_panel_reset(s_panel));
    ESP_ERROR_CHECK(esp_lcd_panel_init(s_panel));
    esp_lcd_panel_invert_color(s_panel, LCD_INVERT);
    apply_orientation();
    ESP_ERROR_CHECK(esp_lcd_panel_disp_on_off(s_panel, true));
    ESP_LOGI(TAG, "panel up: %dx%d landscape (MADCTL swap_xy) at %d MHz, the backlight on GPIO%d after the first frame",
             TANK_W, TANK_H, LCD_PCLK_HZ / 1000000, PIN_LCD_BL);
    return true;
}

/* ---- sleep and wake: the panel in sleep-in (0x10), the backlight off. Its memory keeps the last frame, so a wake
 * lights it at once (display_port_wake's SLPOUT takes 120 ms to settle, as the datasheet has it) ---- */
void display_port_sleep(void) {
    display_port_flush_wait(NULL);                      /* a frame on its way out first */
    s_asleep = true; light();
    if (s_io) esp_lcd_panel_io_tx_param(s_io, 0x10, NULL, 0);
    vTaskDelay(pdMS_TO_TICKS(5));
}
void display_port_wake(void) {
    display_port_flush_wait(NULL);
    if (!s_panel) return;
    if (s_io) { esp_lcd_panel_io_tx_param(s_io, 0x11, NULL, 0); vTaskDelay(pdMS_TO_TICKS(120)); }
    s_asleep = false; light();
}
void display_port_deep_sleep_pins(bool tp_awake_high) {
    /* the backlight dark, the panel not selected (its chip select held high) and the touch chip's reset held as the touch
       port left it (high if it took its own sleep). Every other digital pad is isolated by the deep-sleep hold. A boot's
       display_port_init lets these go. */
    static const gpio_num_t dark[] = { PIN_LCD_BL, PIN_LCD_CS, PIN_TP_RST };
    const int levels[] = { 0, 1, tp_awake_high ? 1 : 0 };
    for (size_t i = 0; i < sizeof dark / sizeof dark[0]; i++) {
        gpio_reset_pin(dark[i]);                        /* off the LEDC / SPI routing, a GPIO again */
        gpio_set_direction(dark[i], GPIO_MODE_OUTPUT);
        gpio_set_level(dark[i], levels[i]);
        gpio_hold_en(dark[i]);
    }
}
void display_port_deep_sleep_bus(void) { }              /* the chip select is held high: the panel ignores its SPI lines */
void display_port_deep_standby(void) { }                /* the panel was put in sleep-in by display_port_sleep: no deep standby command here */

/* ---- brightness: the backlight's duty, 0..255 ---- */
void display_port_set_brightness(uint8_t level) {
    s_brightness = level;
    light();
}
uint8_t display_port_brightness(void) { return s_brightness; }

/* ---- orientation: the flip (MADCTL mirrors), applied between frames. The CYD's picture stands on its long edge only:
 * the quarter turns are not the panel's (display_port_quarters is false), so a side is ignored ---- */
void display_port_set_inverted(bool inverted) { s_inverted = inverted; }
void display_port_set_quarter(int q) { s_inverted = (q & 2) != 0; }
bool display_port_quarters(void) { return false; }
void display_port_side_tune(int madctl, int gx, int gy) { (void)madctl; (void)gx; (void)gy; }
void display_port_side_info(int *madctl, int *gx, int *gy, bool *on) { *madctl = 0; *gx = *gy = 0; *on = false; }
void display_port_probe(bool on) { (void)on; }          /* the AMOLED's edge-colour bands: nothing on this panel */
void display_port_set_madctl(uint8_t v) { (void)v; }    /* the square's way-up register: not this panel's */
uint8_t display_port_madctl(void) { return 0; }
void display_port_frame_origin(int *px, int *py) { *px = 0; *py = 0; }   /* the frame IS the panel */
void display_port_set_view(int view) { (void)view; }
int  display_port_view(void) { return DISPLAY_VIEW_FULL; }
void display_port_panel_to_tank(int px, int py, float *tx, float *ty) { *tx = (float)px; *ty = (float)py; }

/* ---- the panel's power rail: the watch's only ---- */
bool display_port_panel_power_check(void) { return false; }
uint32_t display_port_panel_heals(void) { return 0; }
void display_port_panel_rail_test_off(void) { }

/* ---- flushes ---- */
/* the copy of one stripe into a DMA buffer: the frame is in the panel's byte order (PT_FB_SWAP), so a plain copy; without
 * it the two bytes of each pixel swap on the way (a word of two pixels at a time) */
static void stripe_fill(uint16_t *dst, const uint16_t *src, size_t n) {
    if (PT_FB_SWAP) { memcpy(dst, src, n * sizeof *dst); return; }
    uint32_t *d = (uint32_t *)dst; const uint32_t *s = (const uint32_t *)src;
    for (size_t i = 0; i < n / 2; i++) { uint32_t v = s[i]; d[i] = ((v & 0x00FF00FFu) << 8) | ((v >> 8) & 0x00FF00FFu); }
}

/* the frame, whole: stripes of whole rows, sent in order. The flip is in MADCTL, so the rows go out as drawn. */
static void flush_now(const uint16_t *fb) {
    if (!s_panel) return;
    if (s_inverted != s_applied_inverted) {             /* a flip lands between frames: MADCTL is a command on the same bus */
        xSemaphoreTake(s_stripe_free, portMAX_DELAY); xSemaphoreTake(s_stripe_free, portMAX_DELAY);
        apply_orientation();
        xSemaphoreGive(s_stripe_free); xSemaphoreGive(s_stripe_free);
    }
    int cur = 0;
    for (int y0 = 0; y0 < TANK_H; y0 += STRIPE_ROWS) {
        const int rows = TANK_H - y0 < STRIPE_ROWS ? TANK_H - y0 : STRIPE_ROWS;
        stripe_take();
        uint16_t *stripe = s_stripe[cur];
        stripe_fill(stripe, fb + y0 * TANK_W, (size_t)rows * TANK_W);
        int64_t t = esp_timer_get_time();
        esp_err_t err = esp_lcd_panel_draw_bitmap(s_panel, 0, y0, TANK_W, y0 + rows, stripe);
        s_prof_send += esp_timer_get_time() - t;
        if (err != ESP_OK) {
            xSemaphoreGive(s_stripe_free);              /* no transfer, so no completion will return it */
            static int logged;
            if (logged++ < 3) ESP_LOGE(TAG, "draw_bitmap y0=%d: %s", y0, esp_err_to_name(err));
        }
        cur ^= 1;
    }
    s_dark = false;                                     /* the first whole frame is in: the backlight may show the level */
    light();
}

void display_port_flush(const uint16_t *fb) {           /* the plain flush, whole, here and now */
    display_port_flush_wait(NULL);
    flush_now(fb);
}
void display_port_flush_prof(int64_t *wait_us, int64_t *send_us) { *wait_us = s_prof_wait; *send_us = s_prof_send; s_prof_wait = s_prof_send = 0; }

/* The asynchronous flush (the sh8601 port's, 2026-10-23): a flush task sends one frame at a time. The tank task hands it
 * a drawn frame (display_port_flush_async) and, before it draws into a buffer again, waits for the flush (flush_wait).
 * `done` runs on the flush task once the frame has left the copy (the stripes are the task's until then). It must not
 * call display_port_flush_wait: the flush is still marked in flight while it runs. */
static TaskHandle_t s_fl_task;
static SemaphoreHandle_t s_fl_req, s_fl_idle;           /* idle: given while no flush is in flight */
static const uint16_t *volatile s_fl_fb;
static void (*s_fl_cb)(const uint16_t *fb, void *arg); static void *s_fl_arg;
static int64_t s_fl_us; static int s_fl_frames;
static void fl_task(void *arg) {
    (void)arg;
    for (;;) {
        xSemaphoreTake(s_fl_req, portMAX_DELAY);
        const uint16_t *fb = s_fl_fb;
        int64_t t0 = esp_timer_get_time();
        flush_now(fb);
        s_fl_us += esp_timer_get_time() - t0; s_fl_frames++;
        s_fl_fb = NULL;
        void (*cb)(const uint16_t *, void *) = s_fl_cb; void *a = s_fl_arg;
        if (cb) cb(fb, a);
        xSemaphoreGive(s_fl_idle);
    }
}
bool display_port_flush_async(const uint16_t *fb, void (*done)(const uint16_t *fb, void *arg), void *arg) {
    if (!s_panel) return false;
    if (!s_fl_task) {                                   /* the first call sets the task up (after the SPI has its DMA) */
        s_fl_req = xSemaphoreCreateBinary(); s_fl_idle = xSemaphoreCreateBinary();
        if (!s_fl_req || !s_fl_idle) return false;
        xSemaphoreGive(s_fl_idle);
        if (xTaskCreatePinnedToCore(fl_task, "flush", 4096, NULL, 5, &s_fl_task, 0) != pdPASS) { s_fl_task = NULL; return false; }
        ESP_LOGI(TAG, "flush: asynchronous, the stripes copied on the flush task");
    }
    xSemaphoreTake(s_fl_idle, portMAX_DELAY);           /* one frame on its way at a time */
    s_fl_fb = fb; s_fl_cb = done; s_fl_arg = arg;
    xSemaphoreGive(s_fl_req);
    return true;
}
void display_port_flush_wait(const uint16_t *fb) {      /* until no flush is in flight (any frame: that covers fb's too) */
    (void)fb;
    if (!s_fl_task) return;
    xSemaphoreTake(s_fl_idle, portMAX_DELAY);
    xSemaphoreGive(s_fl_idle);
}
void display_port_flush_async_prof(int64_t *task_us, int *frames, int64_t *copy_us) {
    *task_us = s_fl_us; *frames = s_fl_frames; *copy_us = 0; s_fl_us = 0; s_fl_frames = 0;   /* (the copies are the task's own: no GDMA) */
}
