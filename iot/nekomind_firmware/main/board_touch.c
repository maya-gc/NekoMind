#include "board_touch.h"

#include <stdlib.h>

#include "board_spi.h"
#include "display_ui.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "nvs.h"
#include "nvs_flash.h"

static const char *TAG = "board_touch";
static spi_device_handle_t s_touch;
static int32_t s_x0 = 300, s_x1 = 3800, s_y0 = 300, s_y1 = 3800;
static bool s_swap_axes = true; /* baseline usa XPT2046 com rotacao 1 */
static bool s_was_pressed;

static esp_err_t sample(uint8_t command, int *value)
{
    uint8_t tx[3] = {command, 0, 0};
    uint8_t rx[3] = {0};
    spi_transaction_t transaction = {
        .length = 24,
        .tx_buffer = tx,
        .rx_buffer = rx,
    };
    esp_err_t err = spi_device_polling_transmit(s_touch, &transaction);
    if (err == ESP_OK) *value = ((rx[1] << 8) | rx[2]) >> 3;
    return err;
}

static esp_err_t read_raw(int *raw_x, int *raw_y, bool *pressed)
{
    int z1, z2, x, y;
    esp_err_t err = sample(0xB0, &z1);
    if (err != ESP_OK) return err;
    err = sample(0xC0, &z2);
    if (err != ESP_OK) return err;
    if (z1 < 80 || z1 + 4095 - z2 < 350) {
        *pressed = false;
        return ESP_OK;
    }
    err = sample(0xD0, &x);
    if (err != ESP_OK) return err;
    err = sample(0x90, &y);
    if (err != ESP_OK) return err;
    if (x < 50 || x > 4050 || y < 50 || y > 4050) {
        *pressed = false;
        return ESP_OK;
    }
    *raw_x = x;
    *raw_y = y;
    *pressed = true;
    return ESP_OK;
}

static int map_axis(int raw, int first, int last, int screen_max)
{
    if (first == last) return 0;
    int value = (raw - first) * screen_max / (last - first);
    if (value < 0) return 0;
    if (value > screen_max) return screen_max;
    return value;
}

esp_err_t board_touch_init(void)
{
    esp_err_t err = board_spi_add_touch(&s_touch);
    if (err != ESP_OK) return err;
    err = nvs_flash_init();
    if (err == ESP_OK) {
        nvs_handle_t nvs;
        if (nvs_open("neko_touch", NVS_READONLY, &nvs) == ESP_OK) {
            int8_t swap = 1;
            nvs_get_i32(nvs, "x0", &s_x0);
            nvs_get_i32(nvs, "x1", &s_x1);
            nvs_get_i32(nvs, "y0", &s_y0);
            nvs_get_i32(nvs, "y1", &s_y1);
            nvs_get_i8(nvs, "swap", &swap);
            s_swap_axes = swap != 0;
            nvs_close(nvs);
            ESP_LOGI(TAG, "calibracao touch carregada do NVS");
        } else {
            ESP_LOGW(TAG, "sem calibracao touch; usar mapa inicial ate calibrar");
        }
    } else {
        ESP_LOGW(TAG, "NVS indisponivel; calibracao nao sera persistida");
    }
    ESP_LOGI(TAG, "XPT2046 pronto no SPI compartilhado; IRQ ignorada");
    return ESP_OK;
}

esp_err_t board_touch_poll_point(int *out_x, int *out_y, bool *out_pressed)
{
    if (out_x == NULL || out_y == NULL || out_pressed == NULL)
        return ESP_ERR_INVALID_ARG;
    int raw_x = 0, raw_y = 0;
    esp_err_t err = read_raw(&raw_x, &raw_y, out_pressed);
    if (err != ESP_OK) return err;
    if (*out_pressed) {
        int screen_x_raw = s_swap_axes ? raw_y : raw_x;
        int screen_y_raw = s_swap_axes ? raw_x : raw_y;
        *out_x = map_axis(screen_x_raw, s_x0, s_x1, 239);
        *out_y = map_axis(screen_y_raw, s_y0, s_y1, 319);
        if (!s_was_pressed) {
            ESP_LOGI(TAG, "toque raw=%d,%d tela=%d,%d", raw_x, raw_y,
                     *out_x, *out_y);
        }
    }
    s_was_pressed = *out_pressed;
    return ESP_OK;
}

esp_err_t board_touch_poll(neko_touch_event_t *out_event)
{
    (void)out_event;
    return ESP_ERR_NOT_SUPPORTED;
}

/* Calibracao local explicita: topo-esquerda, topo-direita e base-esquerda.
 * Chamada apenas pelo comando serial de manutencao, nunca pelo bridge Mac. */
esp_err_t board_touch_calibrate(void)
{
    int x[3], y[3];
    for (int point = 0; point < 3; point++) {
        display_ui_calibration_step(point);
        ESP_LOGI(TAG, "calibracao %d/3: toque %s", point + 1,
                 point == 0 ? "SUPERIOR ESQUERDO" :
                 point == 1 ? "SUPERIOR DIREITO" : "INFERIOR ESQUERDO");
        bool pressed = false, armed = false, captured = false;
        int64_t deadline = esp_timer_get_time() + 30000000LL;
        while (esp_timer_get_time() < deadline) {
            int raw_x = 0, raw_y = 0;
            esp_err_t err = read_raw(&raw_x, &raw_y, &pressed);
            if (err != ESP_OK) {
                display_ui_calibration_step(3);
                return err;
            }
            if (!pressed) armed = true;
            if (armed && pressed) {
                x[point] = raw_x;
                y[point] = raw_y;
                ESP_LOGI(TAG, "ponto %d raw=%d,%d", point + 1, raw_x, raw_y);
                while (pressed && esp_timer_get_time() < deadline) {
                    vTaskDelay(pdMS_TO_TICKS(30));
                    err = read_raw(&raw_x, &raw_y, &pressed);
                    if (err != ESP_OK) {
                        display_ui_calibration_step(3);
                        return err;
                    }
                }
                captured = true;
                break;
            }
            vTaskDelay(pdMS_TO_TICKS(30));
        }
        if (!captured) {
            display_ui_calibration_step(3);
            return ESP_ERR_TIMEOUT;
        }
    }
    bool swap = abs(y[1] - y[0]) > abs(x[1] - x[0]);
    int first_x = swap ? y[0] : x[0];
    int last_x = swap ? y[1] : x[1];
    int first_y = swap ? x[0] : y[0];
    int last_y = swap ? x[2] : y[2];
    if (abs(last_x - first_x) < 500 || abs(last_y - first_y) < 500) {
        display_ui_calibration_step(3);
        return ESP_ERR_INVALID_RESPONSE;
    }
    s_x0 = first_x; s_x1 = last_x;
    s_y0 = first_y; s_y1 = last_y;
    s_swap_axes = swap;
    nvs_handle_t nvs;
    if (nvs_open("neko_touch", NVS_READWRITE, &nvs) == ESP_OK) {
        nvs_set_i32(nvs, "x0", s_x0);
        nvs_set_i32(nvs, "x1", s_x1);
        nvs_set_i32(nvs, "y0", s_y0);
        nvs_set_i32(nvs, "y1", s_y1);
        nvs_set_i8(nvs, "swap", swap ? 1 : 0);
        nvs_commit(nvs);
        nvs_close(nvs);
    }
    ESP_LOGI(TAG, "calibracao concluida: x=%ld..%ld y=%ld..%ld swap=%d",
             (long)s_x0, (long)s_x1, (long)s_y0, (long)s_y1, (int)swap);
    display_ui_calibration_step(3);
    return ESP_OK;
}
