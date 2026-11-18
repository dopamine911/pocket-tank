# The CYD: Freenove ESP32-S3 Display 2.8 (FNK0104B)

A 2.8-inch ILI9341V IPS panel, 320 x 240 landscape, on an ESP32-S3 with 16 MB flash and 8 MB octal PSRAM.
Its build is `CONFIG_POCKET_TANK_CYD` (TANK_CYD): the tank is a native 320 x 240 rectangle, square corners.
Its release id is `cyd28` (common/version.h PT_BOARD), and `tools/pt_boards.py` reads it from the image.

## Pins (vendor wiring, matching the ES3C28P spec sheet; touch, codec and panel confirmed on the bench 2026-11-18)

| part | pins |
|---|---|
| LCD ILI9341V, 4-wire SPI, 40 MHz | CS 10, DC 46, SCLK 12, MOSI 11, MISO 13. Reset is the chip's (no pin) |
| backlight, active high (LEDC PWM) | GPIO 45 |
| I2C (touch, codec, socket) | SDA 16, SCL 15 |
| FT6336G touch, 0x38 | RST 18 (low = reset) |
| ES8311 codec, 0x18 (or 0x19) | I2S: MCLK 4, BCLK 5, WS 7, DOUT 8 |
| power amplifier, enabled LOW | GPIO 1 |
| cell voltage, through the divider | GPIO 9 (ADC1 channel 8), read x2 |

No PMIC, no IMU (the QMI8658 is absent: the IMU port reports nothing and the tank stays upright), no RTC,
no charger status line, no PWR key (BOOT is the key).

## Code

- `firmware/main/display_port_ili9341.c`: the panel. MADCTL swap_xy (the vendor's rotation 1); the flip is
  both mirrors. Frame row-major, stripes of 8 rows in internal DMA RAM, the sh8601 port's flush task. Sleep is
  SLPIN with the backlight off. The panel stays dark until the first whole frame.
- `firmware/main/touch_port_ft3168.c`: the CYD branch (`cyd_touch_init`, bias 0, the 180-degree map in
  `map_touch`). The same FT5x06 driver as the 1.8's, reset on GPIO 18.
- `firmware/main/audio_port_es8311.c`: the CYD's I2S pins; the amplifier's level is `AMP_EN_ON` (0). It is set
  off before the pin becomes an output, and held off through deep sleep.
- `firmware/main/battery_port_adc.c`: the battery port without a PMIC. Uncalibrated (see below).
- `firmware/main/board_probe.h`: the CYD signature (no expander, no ES7210, no PMIC, FT6336 at 0x38, ES8311 at 0x18).

## The pages: drawn scaled (`PAGE_SCALED`, common/render.h)

The glass is smaller than the 448 x 368 page in both ways, so the pages keep their layout and are drawn at
`PAGE_K` = 240 / 368, centred (`PAGE_X` 14). Every page shape is mapped where it is drawn (render.c `ctx_page`:
a rect whole, a span, a pixel); the pixel font is drawn at a whole scale near the page's (`PAGE_TEXT`: 2 -> 1,
3 -> 2) and `text_w` answers in page px, so a label centred by its width stays centred. A ring drawn one page
px inside the ring before it (a button's, a panel's double edge) is kept one frame px inside it. Anything that
crosses between the frame and the page goes through `PAGE_FX` / `PAGE_FY` and `FX_PAGE` / `FY_PAGE` (a tap
in, a fish's ring out); MY TANKS' pictures are frame pictures, the scaled glass's size (`SH_THUMB_W/H`).
On the other boards `PAGE_K` is 1 and all of it is the old sums: their pages draw pixel for pixel as before.
The card bakes are off here (a bake is painted unscaled into a sprite).

## Build and flash

    cd firmware && idf.py -B build-cyd -DSDKCONFIG=build-cyd/sdkconfig \
        -DSDKCONFIG_DEFAULTS="sdkconfig.defaults;sdkconfig.cyd" build
    CYD_SERIAL=<usb serial> tools/flash_cyd.sh          # --build-only to stop after the build, --full for a blank board

The build is signed (firmware/keys/ota_signing_key.pem, tools/ota_key.sh).

## Measured (2026-11-18, the first board) and not measured

- Booted from the full flash (bootloader, table, app, the model, its trailer): `chips: ... FT6336 1, ES8311 1 -> cyd28`,
  `panel up`, `FT6336 ready`, the ES8311 at 0x18, the v3m model loaded. 19-25 fps (render 4-15 ms, the frame's
  send 34 ms at 40 MHz - one after the other: the asynchronous flush is not overlapping yet), 13.6 tok/s, 3.2 s a
  decision. Picture upright, colours right, taps land where the finger is (the 180-degree map holds).
- A boot loop on the first image: the stats card (258 px) was copied into a 240 px frame - fixed (226 px, and a
  static assert in render.h for every board).
- Not measured: the audio level on a speaker, the backlight PWM curve, every battery number, the sleep currents.
- The battery is uncalibrated: the x2 divider ratio is the vendor's sketch, and the percent is a straight line
  from 3.3 V to 4.2 V; with no cell fitted it reads ~4.1 V (the charger's output). The meter reports not charging,
  on battery, because the cable is not sensed.
- The RTC: there is none, so the clock is the ESP32's own. A deep sleep keeps it; a power cut or RESET loses
  it (rtc_port_pcf85063.c leaves it unset, and the network or the save sets it).
- The tank's own world numbers are the rectangle's formulas at 320 x 240 (beds, frond pitch, algae cells of 16 px,
  VEG_SEG_PX 2.0): not yet tuned. `make CYD=1 check` still fails world selftests (grass loop patching,
  algae cap, roost, hold distances...); the page selftests pass but settings-nav, whose castle-moved stage is a
  grass-loop case.
- Factory image: back it up first (below); the USB-Serial-JTAG drops a 16 MB `read_flash` at 921600 - read it in
  1 MB chunks at 460800 and `verify_flash` the result.

## Bench checklist

1. `flash_id` reads 16 MB. `read_flash 0 0x1000000` backs up the factory image before any flash.
2. I2C scan: 0x18 (ES8311) and 0x38 (FT6336) answer; 0x20, 0x34 and 0x40 do not.
3. First boot log, in order: `chips: expander 0, ES7210 0x00, PMIC 0, FT6336 1, ES8311 1 -> cyd28`, then
   `panel up: 320x240 landscape (MADCTL swap_xy) at 40 MHz`. The backlight comes on with the first frame.
4. Touch: a tap on a button lands on that button. If the reading is turned, change the CYD branch's map in
   `map_touch` (touch_port_ft3168.c), not the display.
5. Sound: the first cue plays through the codec. The amplifier's pin is low (ON) from reset until
   audio_port_init sets it high (off).
