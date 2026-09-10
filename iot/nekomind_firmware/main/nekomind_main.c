/**
 * nekomind_main.c - Ponto de entrada do firmware NekoMind (familia ESP32; placa pendente).
 *
 * MVP: inicializa o controlador touch + serial. A captura acontece no Mac;
 * o ESP nao envia audio no caminho principal.
 */
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

#include "session_controller.h"

static const char *TAG = "nekomind";

void app_main(void)
{
    ESP_LOGI(TAG, "NekoMind firmware - MVP touch + Mac");
    ESP_LOGI(TAG, "protocolo: JSON Lines via serial; audio capturado no Mac");

    if (session_controller_init() != ESP_OK) {
        ESP_LOGE(TAG, "falha na inicializacao");
        return;
    }

    if (session_controller_start_task() != ESP_OK) {
        ESP_LOGE(TAG, "falha ao iniciar controlador");
        return;
    }

    ESP_LOGI(TAG, "controlador pronto; touch fisico depende da placa escolhida");
}
