/**
 * nekomind_main.c - Ponto de entrada do firmware NekoMind (ESP32-S3).
 *
 * MVP: inicializa o controlador de sessao, dispara uma sessao de
 * demonstracao (captura simulada + protocolo JSON Lines) e mantem uma
 * task de telemetria de 5 em 5 segundos.
 */
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

#include "session_controller.h"

static const char *TAG = "nekomind";

void app_main(void)
{
    ESP_LOGI(TAG, "NekoMind firmware - MVP (ESP32-S3)");
    ESP_LOGI(TAG, "protocolo: JSON Lines via serial (docs/iot_protocol.md)");

    if (session_controller_init() != ESP_OK) {
        ESP_LOGE(TAG, "falha na inicializacao");
        return;
    }

    /* Sessao de demonstracao para validar o fluxo sem hardware. */
    session_controller_run_demo();

    /* Telemetria periodica em segundo plano. */
    session_controller_start_task();

    ESP_LOGI(TAG, "loop principal livre; avatar em IDLE");
}
