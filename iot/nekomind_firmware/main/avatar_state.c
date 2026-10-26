#include "avatar_state.h"

#include "esp_log.h"

static const char *TAG = "neko_state";

static volatile neko_state_t s_state = NEKO_STATE_IDLE;

void avatar_state_init(void)
{
    s_state = NEKO_STATE_IDLE;
    ESP_LOGI(TAG, "avatar inicializado em IDLE");
}

void avatar_state_set(neko_state_t new_state)
{
    neko_state_t old = s_state;
    s_state = new_state;
    ESP_LOGI(TAG, "estado: %s -> %s", avatar_state_name(old), avatar_state_name(new_state));

    /* O display e avisado sobre a mudanca de estado.
     * Chamada indireta para evitar dependencia circular:
     * display_ui observa avatar_state_get() em sua task de refresh. */
}

neko_state_t avatar_state_get(void)
{
    return s_state;
}

const char *avatar_state_name(neko_state_t state)
{
    switch (state) {
    case NEKO_STATE_IDLE:       return "IDLE";
    case NEKO_STATE_PENDING:    return "PENDING";
    case NEKO_STATE_RECORDING:  return "RECORDING";
    case NEKO_STATE_PAUSED:     return "PAUSED";
    case NEKO_STATE_SENDING:    return "SENDING";
    case NEKO_STATE_PROCESSING: return "PROCESSING";
    case NEKO_STATE_SUCCESS:    return "SUCCESS";
    case NEKO_STATE_ERROR:      return "ERROR";
    default:                    return "UNKNOWN";
    }
}
