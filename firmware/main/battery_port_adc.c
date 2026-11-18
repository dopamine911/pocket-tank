/* battery_port_adc.c — the CYD's battery (2026-11-18): NO PMIC, so no fuel gauge, no charger, no PWR key to ask (battery_port.h).
 *
 * The cell's voltage reaches GPIO9 through the board's divider. The vendor's own battery sketch
 * (Sketch_05.1_Battery_Voltage) reads GPIO9 with analogReadMilliVolts and multiplies by 2.0; that ratio is taken as it
 * stands. UNCALIBRATED: the divider and the 2:1 ratio are not measured on a board yet, so the percent below is a straight
 * line between 3.3 V and 4.2 V of the cell, and the voltage is the ADC's own curve fit (or its raw scale if eFuse has no
 * calibration). Both are for the bench to check before the pill or the battery page is trusted.
 *
 * No charge detection: the TP4054 charger has no status line to the ESP32 on this board, so the cable is not sensed. The
 * tank reports not charging, on battery (BAT_ON_BATTERY), and never claims a charge. The PWR key is BOOT on this board
 * (main.c), so the key calls answer nothing, and there is no power-off: a night is a deep sleep (main.c). */
#include "battery_port.h"
#include "board_pins.h"
#include "esp_adc/adc_oneshot.h"
#include "esp_adc/adc_cali.h"
#include "esp_adc/adc_cali_scheme.h"
#include "esp_log.h"
#include "esp_timer.h"

static const char *TAG = "battery";
#define BAT_ADC_CHANNEL  ADC_CHANNEL_8        /* GPIO9 on the ESP32-S3 (ADC1: GPIO1..10 are channels 0..9) */
#define BAT_DIVIDER_X    2.0f                 /* the vendor's cell = pin x 2 (UNCALIBRATED: not measured here) */
#define BAT_EMPTY_MV     3300                 /* the percent's ends, as a LiPo cell's (uncalibrated) */
#define BAT_FULL_MV      4200
#define BAT_SAMPLES      8                    /* averaged per read: the divider's own noise is most of it */
#define BAT_CACHE_US     900000               /* a read at most this often (as the AXP port's ~1 s) */

static adc_oneshot_unit_handle_t s_adc;
static adc_cali_handle_t s_cali;
static bool s_cali_ok;
static bool s_valid;
static int  s_mv;                              /* the cell's voltage, mV (the divider undone) */
static int64_t s_last_us = -1;

static bool read_mv(int *mv) {
    int sum = 0;
    for (int i = 0; i < BAT_SAMPLES; i++) {
        int raw = 0;
        if (adc_oneshot_read(s_adc, BAT_ADC_CHANNEL, &raw) != ESP_OK) return false;
        sum += raw;
    }
    int raw = sum / BAT_SAMPLES, pin_mv = 0;
    if (s_cali_ok) { if (adc_cali_raw_to_voltage(s_cali, raw, &pin_mv) != ESP_OK) return false; }
    else pin_mv = raw * 3100 / 4095;           /* uncalibrated: 12 dB attenuation spans ~3.1 V */
    *mv = (int)(pin_mv * BAT_DIVIDER_X);
    return true;
}

static void refresh(void) {
    if (!s_adc) return;
    int64_t now = esp_timer_get_time();
    if (s_last_us >= 0 && now - s_last_us <= BAT_CACHE_US) return;
    s_last_us = now;
    int mv = 0;
    s_valid = read_mv(&mv) && mv > 0;
    if (s_valid) s_mv = mv;
}

bool battery_port_init(i2c_master_bus_handle_t bus) {
    (void)bus;                                 /* no PMIC: the battery is not on the I2C bus */
    adc_oneshot_unit_init_cfg_t unit = { .unit_id = ADC_UNIT_1, .ulp_mode = ADC_ULP_MODE_DISABLE };
    if (adc_oneshot_new_unit(&unit, &s_adc) != ESP_OK) { ESP_LOGW(TAG, "no ADC unit: the battery is not read"); s_adc = NULL; return false; }
    adc_oneshot_chan_cfg_t ch = { .atten = ADC_ATTEN_DB_12, .bitwidth = ADC_BITWIDTH_DEFAULT };
    if (adc_oneshot_config_channel(s_adc, BAT_ADC_CHANNEL, &ch) != ESP_OK) { ESP_LOGW(TAG, "GPIO%d: no ADC channel", PIN_BAT_ADC); s_adc = NULL; return false; }
    adc_cali_curve_fitting_config_t cal = { .unit_id = ADC_UNIT_1, .chan = BAT_ADC_CHANNEL, .atten = ADC_ATTEN_DB_12, .bitwidth = ADC_BITWIDTH_DEFAULT };
    s_cali_ok = adc_cali_create_scheme_curve_fitting(&cal, &s_cali) == ESP_OK;
    ESP_LOGW(TAG, "battery: GPIO%d through the divider (x%.1f, UNCALIBRATED: the vendor's ratio) - ADC %s, the reading is not trusted until measured",
             PIN_BAT_ADC, BAT_DIVIDER_X, s_cali_ok ? "curve-fit calibrated" : "raw scale (no calibration)");
    refresh();
    ESP_LOGI(TAG, "battery: %s (%d mV)", s_valid ? "read" : "not read yet", s_mv);
    return false;                              /* false: no PMIC (main.c's night is a deep sleep, the PWR key is BOOT) */
}

/* the meter: a straight line between the cell's ends, uncalibrated. The cable is not sensed: never charging */
bool battery_port_read(float *frac, bool *charging) {
    refresh();
    if (!s_valid) return false;
    float f = (float)(s_mv - BAT_EMPTY_MV) / (float)(BAT_FULL_MV - BAT_EMPTY_MV);
    *frac = f < 0 ? 0 : f > 1 ? 1 : f;
    *charging = false;
    return true;
}
int battery_port_state(void) { return BAT_ON_BATTERY; }   /* no charger status on this board: the cable is not sensed */
int battery_port_vbat_mv(void) { refresh(); return s_valid ? s_mv : 0; }

/* no PMIC: nothing to power off, no rails, no charger, no PWR key (the calls answer as the port has nothing to ask) */
bool battery_port_poweroff(void) { return false; }
void battery_port_key_init(void) { }
int  battery_port_key_poll(void) { return 0; }
void battery_port_key_clear(void) { }
void battery_port_key_trace(int seconds) { (void)seconds; }
void battery_port_dump(void) {
    refresh();
    ESP_LOGI(TAG, "battery: no PMIC on this board; GPIO%d reads %d mV at the cell (uncalibrated), no charger to ask", PIN_BAT_ADC, s_valid ? s_mv : 0);
}
int  battery_port_charge_ma(void) { return 0; }
bool battery_port_set_charge_ma(int ma) { (void)ma; return false; }
void battery_port_charge_report(void) { ESP_LOGI(TAG, "charge: no charger on this board (no PMIC)"); }
bool battery_port_set_charger(bool on) { (void)on; return false; }
bool battery_port_set_cell(int mah) { (void)mah; return false; }
bool battery_port_set_rail(const char *name, bool on) { (void)name; (void)on; return false; }   /* no PMIC rails: the codec's rail call is harmless */
void battery_port_trim_rails(void) { }
void battery_port_pin_rail(const char *name) { (void)name; }
