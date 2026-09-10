#include "session_controller.h"

#include <stdio.h>

#include "esp_log.h"
#include "esp_system.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

#include "avatar_state.h"
#include "audio_transport.h"
#include "board_touch.h"
#include "display_ui.h"
#include "neko_controller.h"

static const char *TAG = "session_ctrl";

static neko_controller_t s_controller;
static char s_rx_line[NEKO_PROTOCOL_MAX_LINE_BYTES];
static bool s_touch_driver_ready = false;

static uint32_t now_ms(void)
{
    return (uint32_t)(esp_timer_get_time() / 1000ULL);
}

static neko_state_t avatar_from_controller(neko_controller_state_t state)
{
    switch (state) {
    case NEKO_CONTROLLER_IDLE:
        return NEKO_STATE_IDLE;
    case NEKO_CONTROLLER_PENDING:
        return NEKO_STATE_PENDING;
    case NEKO_CONTROLLER_RECORDING:
        return NEKO_STATE_RECORDING;
    case NEKO_CONTROLLER_PAUSED:
        return NEKO_STATE_PAUSED;
    case NEKO_CONTROLLER_PROCESSING:
        return NEKO_STATE_PROCESSING;
    case NEKO_CONTROLLER_SUCCESS:
        return NEKO_STATE_SUCCESS;
    case NEKO_CONTROLLER_ERROR:
    default:
        return NEKO_STATE_ERROR;
    }
}

static void controller_send_line(const char *line, void *user_data)
{
    (void)user_data;
    if (audio_transport_send_json(line) != ESP_OK) {
        ESP_LOGE(TAG, "falha ao enviar linha serial");
    }
}

static void controller_render_view(neko_controller_state_t state,
                                   const neko_controller_view_t *view,
                                   void *user_data)
{
    (void)user_data;
    avatar_state_set(avatar_from_controller(state));
    display_ui_render_view(view != NULL ? view->message : neko_controller_state_name(state),
                           view != NULL ? view->summary : "",
                           view != NULL ? view->topics : NULL,
                           view != NULL ? view->topic_count : 0,
                           view != NULL && view->is_demo);
}

esp_err_t session_controller_init(void)
{
    char boot_nonce[36];
    neko_controller_callbacks_t callbacks = {
        .send_line = controller_send_line,
        .render_view = controller_render_view,
        .user_data = NULL,
    };

    avatar_state_init();
    ESP_ERROR_CHECK(display_ui_init());
    ESP_ERROR_CHECK(audio_transport_init(NEKO_TRANSPORT_SERIAL));
    s_touch_driver_ready = false;
    {
        esp_err_t touch_err = board_touch_init();
        if (touch_err != ESP_OK) {
            avatar_state_set(NEKO_STATE_ERROR);
            display_ui_render_view("hardware touch indisponivel",
                                   "selecione placa/controlador touch",
                                   NULL, 0, false);
            ESP_LOGE(TAG, "touch indisponivel: %s", esp_err_to_name(touch_err));
            return touch_err;
        }
    }
    snprintf(boot_nonce, sizeof(boot_nonce), "esp%08lx%08lx%08lx%08lx",
             (unsigned long)esp_random(),
             (unsigned long)esp_random(),
             (unsigned long)esp_random(),
             (unsigned long)esp_random());
    s_touch_driver_ready = true;
    if (neko_controller_init_with_boot_nonce(&s_controller, &callbacks, boot_nonce)
        != NEKO_CONTROLLER_OK) {
        return ESP_ERR_INVALID_STATE;
    }
    return ESP_OK;
}

static void poll_touch(uint32_t t_ms)
{
    neko_touch_event_t event;
    if (!s_touch_driver_ready) {
        return;
    }
    esp_err_t err = board_touch_poll(&event);
    if (err == ESP_OK) {
        neko_controller_touch(&s_controller, event, t_ms);
    } else if (err != ESP_ERR_NOT_SUPPORTED && err != ESP_ERR_TIMEOUT) {
        ESP_LOGW(TAG, "falha no touch: %s", esp_err_to_name(err));
    }
}

static void poll_serial(uint32_t t_ms)
{
    esp_err_t err = audio_transport_poll_rx(s_rx_line, sizeof(s_rx_line), 0);
    if (err == ESP_OK) {
        neko_controller_status_t status =
            neko_controller_receive(&s_controller, s_rx_line, t_ms);
        if (status != NEKO_CONTROLLER_OK && status != NEKO_CONTROLLER_STALE) {
            ESP_LOGW(TAG, "mensagem Mac rejeitada: %d", status);
        }
    } else if (err != ESP_ERR_TIMEOUT && err != ESP_ERR_NOT_SUPPORTED) {
        ESP_LOGW(TAG, "falha no RX serial: %s", esp_err_to_name(err));
    }
}

static void session_task(void *arg)
{
    (void)arg;
    while (true) {
        uint32_t t_ms = now_ms();
        poll_touch(t_ms);
        poll_serial(t_ms);
        neko_controller_tick(&s_controller, t_ms);
        vTaskDelay(pdMS_TO_TICKS(50));
    }
}

esp_err_t session_controller_start_task(void)
{
    BaseType_t ok = xTaskCreate(session_task, "neko_session",
                                8192, NULL, 5, NULL);
    return ok == pdPASS ? ESP_OK : ESP_ERR_NO_MEM;
}
