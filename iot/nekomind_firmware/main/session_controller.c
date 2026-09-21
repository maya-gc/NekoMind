#include "session_controller.h"

#include <stdio.h>
#include <string.h>

#include "esp_log.h"
#include "esp_random.h"
#include "esp_system.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "nvs.h"

#include "avatar_state.h"
#include "audio_transport.h"
#include "board_touch.h"
#include "display_ui.h"
#include "neko_controller.h"
#include "neko_layout.h"

static const char *TAG = "session_ctrl";
#define NEKO_DISPLAY_WIDTH 240
#define NEKO_DISPLAY_HEIGHT 320

static neko_controller_t s_controller;
static char s_rx_line[NEKO_PROTOCOL_MAX_LINE_BYTES];
static bool s_touch_driver_ready = false;
static neko_layout_model_t s_layout;
static neko_touch_edge_t s_touch_edge;
static neko_scene_t s_scene;
static bool s_have_ui_scene;
static bool s_dark_theme;
static uint32_t s_theme_last_toggle_ms;

static void load_theme(void)
{
    nvs_handle_t nvs;
    uint8_t value = 0;
    if (nvs_open("neko_ui", NVS_READONLY, &nvs) == ESP_OK) {
        if (nvs_get_u8(nvs, "dark", &value) == ESP_OK) s_dark_theme = value == 1;
        nvs_close(nvs);
    }
}

static void toggle_theme(uint32_t t_ms)
{
    if (s_theme_last_toggle_ms != 0
        && (uint32_t)(t_ms - s_theme_last_toggle_ms) < NEKO_TOUCH_DEBOUNCE_MS)
        return;
    s_theme_last_toggle_ms = t_ms;
    s_dark_theme = !s_dark_theme;
    neko_layout_set_theme(&s_layout, s_dark_theme);
    if (s_have_ui_scene) {
        s_scene.dark_theme = s_dark_theme;
        for (size_t i = 0; i < s_scene.op_count; i++) {
            neko_scene_op_t *op = &s_scene.ops[i];
            if (op->kind == NEKO_SCENE_OP_BUTTON
                && op->rect.x == s_layout.hits[0].rect.x
                && op->rect.y == s_layout.hits[0].rect.y) {
                snprintf(op->text, sizeof(op->text), "%s",
                         s_dark_theme ? "CLARO" : "ESCURO");
                break;
            }
        }
        display_ui_draw_scene(&s_scene);
    }
    nvs_handle_t nvs;
    if (nvs_open("neko_ui", NVS_READWRITE, &nvs) == ESP_OK) {
        esp_err_t err = nvs_set_u8(nvs, "dark", s_dark_theme ? 1 : 0);
        if (err == ESP_OK) err = nvs_commit(nvs);
        if (err != ESP_OK) ESP_LOGW(TAG, "tema nao persistido: %s", esp_err_to_name(err));
        nvs_close(nvs);
    } else {
        ESP_LOGW(TAG, "tema nao persistido: NVS indisponivel");
    }
}

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
    case NEKO_CONTROLLER_CHECKING:
        return NEKO_STATE_PENDING;
    case NEKO_CONTROLLER_READY:
        return NEKO_STATE_IDLE;
    case NEKO_CONTROLLER_RECOVERY:
        return NEKO_STATE_ERROR;
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
    neko_layout_model_t layout;
    neko_scene_t scene;
    avatar_state_set(avatar_from_controller(state));
    if (neko_layout_build(state, view, NEKO_DISPLAY_WIDTH, NEKO_DISPLAY_HEIGHT,
                          false, view != NULL ? view->card_index : 0, &layout)) {
        neko_layout_set_theme(&layout, s_dark_theme);
        if (neko_scene_build(state, view, &layout, &scene)) {
            s_layout = layout;
            s_scene = scene;
            s_have_ui_scene = true;
            display_ui_draw_scene(&scene);
            return;
        }
    }
    display_ui_render(view != NULL ? view->message : neko_controller_state_name(state));
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
    esp_err_t init_err = display_ui_init();
    if (init_err != ESP_OK) {
        ESP_LOGE(TAG, "display indisponivel: %s", esp_err_to_name(init_err));
        return init_err;
    }
    init_err = audio_transport_init(NEKO_TRANSPORT_SERIAL);
    if (init_err != ESP_OK) {
        display_ui_render("USB indisponivel");
        ESP_LOGE(TAG, "serial indisponivel: %s", esp_err_to_name(init_err));
        return init_err;
    }
    s_touch_driver_ready = false;
    neko_touch_edge_init(&s_touch_edge);
    {
        esp_err_t touch_err = board_touch_init();
        if (touch_err != ESP_OK) {
            avatar_state_set(NEKO_STATE_ERROR);
            display_ui_render("hardware touch indisponivel");
            ESP_LOGE(TAG, "touch indisponivel: %s", esp_err_to_name(touch_err));
            return touch_err;
        }
    }
    load_theme();
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
    int x = 0;
    int y = 0;
    bool pressed = false;
    if (!s_touch_driver_ready) {
        return;
    }
    if (board_touch_poll_point(&x, &y, &pressed) == ESP_OK) {
        bool enabled = false;
        if (neko_touch_edge_update(&s_touch_edge, pressed, t_ms)
            && neko_layout_hit_test(&s_layout, x, y, &event, &enabled) && enabled) {
            if (event == NEKO_TOUCH_THEME) toggle_theme(t_ms);
            else neko_controller_touch(&s_controller, event, t_ms);
        }
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
        if (strcmp(s_rx_line, "!touch-calibrate") == 0) {
            esp_err_t cal = board_touch_calibrate();
            ESP_LOGI(TAG, "calibracao touch: %s", esp_err_to_name(cal));
            return;
        }
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
                                12288, NULL, 5, NULL);
    return ok == pdPASS ? ESP_OK : ESP_ERR_NO_MEM;
}
