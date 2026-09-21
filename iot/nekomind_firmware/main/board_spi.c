#include "board_spi.h"
#include <stdbool.h>

static bool s_bus_ready;

esp_err_t board_spi_init(void)
{
    if (s_bus_ready) {
        return ESP_OK;
    }
    spi_bus_config_t config = {
        .mosi_io_num = NEKO_PIN_MOSI,
        .miso_io_num = NEKO_PIN_MISO,
        .sclk_io_num = NEKO_PIN_SCLK,
        .quadwp_io_num = -1,
        .quadhd_io_num = -1,
        .max_transfer_sz = 240 * 16 * 2 + 16,
    };
    esp_err_t err = spi_bus_initialize(SPI2_HOST, &config, SPI_DMA_CH_AUTO);
    if (err == ESP_OK || err == ESP_ERR_INVALID_STATE) {
        s_bus_ready = true;
        return ESP_OK;
    }
    return err;
}

esp_err_t board_spi_add_lcd(spi_device_handle_t *out_device)
{
    if (out_device == NULL) {
        return ESP_ERR_INVALID_ARG;
    }
    esp_err_t err = board_spi_init();
    if (err != ESP_OK) {
        return err;
    }
    spi_device_interface_config_t config = {
        .clock_speed_hz = 20 * 1000 * 1000,
        .mode = 0,
        .spics_io_num = NEKO_PIN_LCD_CS,
        .queue_size = 1,
    };
    return spi_bus_add_device(SPI2_HOST, &config, out_device);
}

esp_err_t board_spi_add_touch(spi_device_handle_t *out_device)
{
    if (out_device == NULL) {
        return ESP_ERR_INVALID_ARG;
    }
    esp_err_t err = board_spi_init();
    if (err != ESP_OK) {
        return err;
    }
    spi_device_interface_config_t config = {
        .clock_speed_hz = 2 * 1000 * 1000,
        .mode = 0,
        .spics_io_num = NEKO_PIN_TOUCH_CS,
        .queue_size = 1,
    };
    return spi_bus_add_device(SPI2_HOST, &config, out_device);
}
