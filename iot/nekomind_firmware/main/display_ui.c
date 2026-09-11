#include "display_ui.h"

#include "esp_log.h"

static const char *TAG = "display_ui";

/* Avatar em ASCII por estado (fallback ate o LCD existir). */
static const char *avatar_face(neko_state_t state)
{
    switch (state) {
    case NEKO_STATE_IDLE:       return "(=^.^=) zZ";
    case NEKO_STATE_PENDING:    return "(=o.o=) aguardando";
    case NEKO_STATE_RECORDING:  return "(=O.o=) ouvindo...";
    case NEKO_STATE_PAUSED:     return "(=-.-=) pausado";
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
    (void)status_line;
    ESP_LOGI(TAG, "NEKO %s | estado=%s", avatar_face(st), avatar_state_name(st));
    return ESP_OK;
}

esp_err_t display_ui_render_view(const char *status_line,
                                 const char *summary,
                                 const char (*topics)[NEKO_TOPIC_MAX + 1],
                                 size_t topic_count,
                                 bool is_demo,
                                 int duration_seconds,
                                 const char *trend_text,
                                 int voice_level,
                                 bool voice_clipping)
{
    size_t i;
    display_ui_render(status_line);
    if (summary != NULL && summary[0] != '\0') {
        ESP_LOGI(TAG, "resultado %s: resumo_disponivel", is_demo ? "demo" : "real");
    }
    for (i = 0; topics != NULL && i < topic_count; i++) {
        ESP_LOGI(TAG, "topico[%u]: disponivel", (unsigned int)i);
    }
    if (duration_seconds > 0) {
        ESP_LOGI(TAG, "duracao: %ds", duration_seconds);
    }
    if (trend_text != NULL && trend_text[0] != '\0') {
        ESP_LOGI(TAG, "evolucao: disponivel");
    }
    if (voice_level > 0 || voice_clipping) {
        ESP_LOGI(TAG, "voz: nivel=%d clipping=%s",
                 voice_level, voice_clipping ? "sim" : "nao");
    }
    return ESP_OK;
}

esp_err_t display_ui_draw_scene(const neko_scene_t *scene)
{
    size_t i;
    size_t buttons = 0;
    if (scene == NULL) {
        return ESP_ERR_INVALID_ARG;
    }
    for (i = 0; i < scene->op_count; i++) {
        if (scene->ops[i].kind == NEKO_SCENE_OP_BUTTON) {
            buttons++;
        }
    }
    ESP_LOGI(TAG, "scene %dx%d ops=%u buttons=%u reduced_motion=%s",
             scene->width, scene->height, (unsigned int)scene->op_count,
             (unsigned int)buttons, scene->reduced_motion ? "sim" : "nao");
    return ESP_OK;
}

esp_err_t display_ui_show_telemetry(const char *telemetry_line)
{
    (void)telemetry_line;
    ESP_LOGI(TAG, "telemetria: disponivel");
    return ESP_OK;
}
