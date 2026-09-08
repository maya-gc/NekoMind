#include "display_ui.h"

#include "esp_log.h"

static const char *TAG = "display_ui";

/* Avatar em ASCII por estado (fallback ate o LCD existir). */
static const char *avatar_face(neko_state_t state)
{
    switch (state) {
    case NEKO_STATE_IDLE:       return "(=^.^=) zZ";
    case NEKO_STATE_RECORDING:  return "(=O.o=) ouvindo...";
    case NEKO_STATE_SENDING:    return "(=>^.^)=> enviando";
    case NEKO_STATE_PROCESSING: return "(=@.@=) pensando";
    case NEKO_STATE_SUCCESS:    return "(=^*^=) sucesso!";
    case NEKO_STATE_ERROR:      return "(=x.x=) erro";
    default:                    return "(=?.?=)";
    }
}

esp_err_t display_ui_init(void)
{
    if (NEKO_LCD_PIN_CLK < 0) {
        ESP_LOGW(TAG, "LCD nao configurado (TODO pinos) - avatar via log");
        return ESP_OK;
    }
    /* TODO(hardware): inicializar SPI/I2C e driver do LCD aqui. */
    return ESP_OK;
}

esp_err_t display_ui_render(const char *status_line)
{
    neko_state_t st = avatar_state_get();
    ESP_LOGI(TAG, "NEKO %s | %s", avatar_face(st),
             status_line != NULL ? status_line : avatar_state_name(st));
    return ESP_OK;
}

esp_err_t display_ui_show_telemetry(const char *telemetry_line)
{
    ESP_LOGI(TAG, "telemetria: %s", telemetry_line != NULL ? telemetry_line : "-");
    return ESP_OK;
}
