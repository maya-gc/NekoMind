#include "audio_capture.h"

#include <string.h>

#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

#include "i2s_microphone.h"

static const char *TAG = "audio_capture";

/* Buffer circular simples de chunks (pool fixo, sem alocacao dinamica). */
static uint8_t  s_pool[NEKO_AUDIO_CHUNK_COUNT][NEKO_AUDIO_CHUNK_SIZE];
static size_t   s_pool_len[NEKO_AUDIO_CHUNK_COUNT];
static uint32_t s_pool_seq[NEKO_AUDIO_CHUNK_COUNT];
static volatile int s_head = 0; /* proximo a preencher */
static volatile int s_tail = 0; /* proximo a consumir  */

static volatile bool s_recording = false;
static uint32_t s_seq_counter = 0;
static char s_session_id[32] = {0};

esp_err_t audio_capture_init(void)
{
    ESP_ERROR_CHECK(i2s_mic_init());
    s_head = s_tail = 0;
    s_seq_counter = 0;
    s_recording = false;
    ESP_LOGI(TAG, "pipeline de captura inicializado (%d chunks x %d bytes)",
             NEKO_AUDIO_CHUNK_COUNT, NEKO_AUDIO_CHUNK_SIZE);
    return ESP_OK;
}

esp_err_t audio_capture_start(const char *session_id)
{
    if (s_recording) {
        return ESP_ERR_INVALID_STATE;
    }
    if (session_id != NULL) {
        strncpy(s_session_id, session_id, sizeof(s_session_id) - 1);
        s_session_id[sizeof(s_session_id) - 1] = '\0';
    } else {
        s_session_id[0] = '\0';
    }
    s_seq_counter = 0;
    s_recording = true;
    ESP_LOGI(TAG, "captura iniciada (sessao=%s)",
             s_session_id[0] ? s_session_id : "(sem id)");
    return ESP_OK;
}

esp_err_t audio_capture_stop(void)
{
    s_recording = false;
    s_head = s_tail = 0;
    ESP_LOGI(TAG, "captura parada");
    return ESP_OK;
}

esp_err_t audio_capture_next_chunk(const uint8_t **out_buf, size_t *out_len,
                                   uint32_t *out_seq, uint32_t timeout_ms)
{
    if (out_buf == NULL || out_len == NULL || out_seq == NULL) {
        return ESP_ERR_INVALID_ARG;
    }
    if (!s_recording) {
        return ESP_ERR_INVALID_STATE;
    }

    /* No modo simulado, preenche o proximo slot do pool com dados do I2S
     * (que, simulado, retorna silencio) e o entrega ao consumidor. */
    if (s_head == ((s_tail + NEKO_AUDIO_CHUNK_COUNT - 1) % NEKO_AUDIO_CHUNK_COUNT)) {
        /* Pool cheio: aguarda consumo. */
        vTaskDelay(pdMS_TO_TICKS(timeout_ms > 0 ? timeout_ms : 1));
        return ESP_ERR_TIMEOUT;
    }

    uint8_t *slot = s_pool[s_head];
    size_t read_len = 0;
    esp_err_t err = i2s_mic_read(slot, NEKO_AUDIO_CHUNK_SIZE, &read_len, timeout_ms);
    if (err != ESP_OK) {
        return err;
    }

    s_pool_len[s_head] = read_len;
    s_pool_seq[s_head] = s_seq_counter++;

    *out_buf = slot;
    *out_len = read_len;
    *out_seq = s_pool_seq[s_head];

    s_head = (s_head + 1) % NEKO_AUDIO_CHUNK_COUNT;
    return ESP_OK;
}

void audio_capture_release_chunk(void)
{
    /* MVP: libera sempre o slot mais antigo consumido. */
    s_tail = (s_tail + 1) % NEKO_AUDIO_CHUNK_COUNT;
}
