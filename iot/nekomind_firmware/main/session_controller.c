#include "session_controller.h"

#include <stdio.h>
#include <inttypes.h>

#include "esp_log.h"
#include "esp_system.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

#include "avatar_state.h"
#include "audio_capture.h"
#include "audio_transport.h"
#include "display_ui.h"

static const char *TAG = "session_ctrl";

/* TODO(config): duracao da sessao de demonstracao, em segundos. */
#define NEKO_DEMO_SESSION_SECONDS (5)

static void send_device_status(void)
{
    char buf[192];
    snprintf(buf, sizeof(buf),
             "{\"type\":\"device_status\",\"state\":\"%s\","
             "\"free_heap\":%" PRIu32 ",\"simulated\":%d}",
             avatar_state_name(avatar_state_get()),
             (uint32_t)esp_get_free_heap_size(), 1);
    audio_transport_send_json(buf);
}

esp_err_t session_controller_init(void)
{
    avatar_state_init();
    ESP_ERROR_CHECK(display_ui_init());
    ESP_ERROR_CHECK(audio_transport_init(NEKO_TRANSPORT_SERIAL));
    ESP_ERROR_CHECK(audio_capture_init());
    display_ui_render("pronto");
    return ESP_OK;
}

esp_err_t session_controller_run_demo(void)
{
    const char *session_id = "demo-0001";

    /* 1. session_start */
    avatar_state_set(NEKO_STATE_RECORDING);
    display_ui_render("gravando explicacao");
    audio_transport_send_json(
        "{\"type\":\"session_start\",\"session_id\":\"demo-0001\","
        "\"sample_rate\":16000,\"format\":\"pcm_s16le\"}");
    audio_capture_start(session_id);

    TickType_t deadline = xTaskGetTickCount()
        + pdMS_TO_TICKS(NEKO_DEMO_SESSION_SECONDS * 1000);

    /* 2. Loop de gravacao + envio (RECORDING <-> SENDING) */
    while (xTaskGetTickCount() < deadline) {
        const uint8_t *buf = NULL;
        size_t len = 0;
        uint32_t seq = 0;

        esp_err_t err = audio_capture_next_chunk(&buf, &len, &seq, 100);
        if (err == ESP_ERR_TIMEOUT) {
            continue;
        }
        if (err != ESP_OK) {
            ESP_LOGE(TAG, "falha na captura: %s", esp_err_to_name(err));
            avatar_state_set(NEKO_STATE_ERROR);
            display_ui_render("erro de captura");
            audio_transport_send_json(
                "{\"type\":\"error\",\"where\":\"capture\"}");
            audio_capture_stop();
            return err;
        }

        avatar_state_set(NEKO_STATE_SENDING);
        display_ui_render("enviando chunk");
        audio_transport_send_chunk(session_id, seq, buf, len);
        audio_capture_release_chunk();
        avatar_state_set(NEKO_STATE_RECORDING);
        send_device_status();
    }

    /* 3. session_end e espera da analise */
    audio_capture_stop();
    avatar_state_set(NEKO_STATE_PROCESSING);
    display_ui_render("aguardando analise");
    audio_transport_send_json(
        "{\"type\":\"session_end\",\"session_id\":\"demo-0001\"}");

    /* Espera curta por uma resposta (stub: nunca chega no MVP). */
    char rx[128];
    if (audio_transport_poll_rx(rx, sizeof(rx), 500) == ESP_OK) {
        ESP_LOGI(TAG, "analise recebida: %s", rx);
        avatar_state_set(NEKO_STATE_SUCCESS);
    } else {
        /* Sem resposta nao e erro fatal no MVP: o backend ainda nao
         * esta conectado ao device. Consideramos a sessao concluida. */
        avatar_state_set(NEKO_STATE_SUCCESS);
    }
    display_ui_render("sessao concluida");

    vTaskDelay(pdMS_TO_TICKS(2000));
    avatar_state_set(NEKO_STATE_IDLE);
    display_ui_render("pronto");
    return ESP_OK;
}

static void session_task(void *arg)
{
    (void)arg;
    while (true) {
        send_device_status();
        vTaskDelay(pdMS_TO_TICKS(5000));
    }
}

esp_err_t session_controller_start_task(void)
{
    BaseType_t ok = xTaskCreate(session_task, "neko_session",
                                4096, NULL, 5, NULL);
    return ok == pdPASS ? ESP_OK : ESP_ERR_NO_MEM;
}
