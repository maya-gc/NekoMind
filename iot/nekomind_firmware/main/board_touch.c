#include "board_touch.h"

#include "esp_log.h"

static const char *TAG = "board_touch";

esp_err_t board_touch_init(void)
{
    ESP_LOGW(TAG, "touch fisico nao configurado; selecione placa/controlador");
    return ESP_ERR_NOT_SUPPORTED;
}

esp_err_t board_touch_poll(neko_touch_event_t *out_event)
{
    (void)out_event;
    return ESP_ERR_NOT_SUPPORTED;
}

esp_err_t board_touch_poll_point(int *out_x, int *out_y, bool *out_pressed)
{
    (void)out_x;
    (void)out_y;
    (void)out_pressed;
    return ESP_ERR_NOT_SUPPORTED;
}
