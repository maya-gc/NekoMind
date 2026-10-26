#pragma once

#include "driver/spi_master.h"
#include "esp_err.h"

/* Pinagem do baseline ESP32-S3 + ILI9341/XPT2046 documentado em pipeline. */
#define NEKO_PIN_MOSI 11
#define NEKO_PIN_SCLK 12
#define NEKO_PIN_MISO 13
#define NEKO_PIN_LCD_CS 10
#define NEKO_PIN_LCD_DC 9
#define NEKO_PIN_LCD_RST 8
#define NEKO_PIN_TOUCH_CS 7
#define NEKO_PIN_TOUCH_IRQ 6

esp_err_t board_spi_init(void);
esp_err_t board_spi_add_lcd(spi_device_handle_t *out_device);
esp_err_t board_spi_add_touch(spi_device_handle_t *out_device);
