#include "audio_transport.h"
#include "neko_protocol.h"

#include <stdio.h>
#include <string.h>
#include <errno.h>
#include <fcntl.h>
#include <unistd.h>

#include "esp_log.h"

static const char *TAG = "audio_transport";

static neko_transport_mode_t s_mode = NEKO_TRANSPORT_SERIAL;
static int s_serial_fd = -1;
static char s_input_line[NEKO_PROTOCOL_MAX_LINE_BYTES];
static char s_output_line[NEKO_PROTOCOL_MAX_LINE_BYTES];
static size_t s_input_used;
static bool s_input_discard;

esp_err_t audio_transport_init(neko_transport_mode_t mode)
{
    s_mode = mode;
    switch (mode) {
    case NEKO_TRANSPORT_SERIAL:
        /* O console de logs usa USB Serial/JTAG, mas fd 0 nao e necessariamente
         * associado ao VFS. Abrir o dispositivo registrado pelo IDF garante
         * que read() receba os bytes do Mac. */
        s_serial_fd = open("/dev/usbserjtag", O_RDWR | O_NONBLOCK);
        if (s_serial_fd < 0) {
            ESP_LOGE(TAG, "falha ao abrir USB Serial/JTAG VFS: errno=%d", errno);
            return ESP_FAIL;
        }
        ESP_LOGI(TAG, "transporte USB Serial/JTAG pronto (JSON Lines)");
        return ESP_OK;
    case NEKO_TRANSPORT_WIFI:
        /* TODO(wifi): transporte futuro fora do MVP USB/serial. */
        ESP_LOGW(TAG, "transporte Wi-Fi ainda nao implementado (stub)");
        return ESP_ERR_NOT_SUPPORTED;
    default:
        return ESP_ERR_INVALID_ARG;
    }
}

esp_err_t audio_transport_send_json(const char *json_line)
{
    if (json_line == NULL) {
        return ESP_ERR_INVALID_ARG;
    }
    size_t length = strlen(json_line);
    if (s_serial_fd < 0 || length + 1 > sizeof(s_output_line)) {
        return ESP_ERR_INVALID_STATE;
    }
    memcpy(s_output_line, json_line, length);
    s_output_line[length] = '\n';
    return write(s_serial_fd, s_output_line, length + 1) == (ssize_t)(length + 1)
        ? ESP_OK : ESP_FAIL;
}

esp_err_t audio_transport_send_chunk(const char *session_id, uint32_t seq,
                                     const uint8_t *data, size_t len)
{
    (void)data; /* TODO: codificar payload em base64 no JSON final. */

    if (s_mode == NEKO_TRANSPORT_SERIAL) {
        /* Futuro: caminho de microfone embarcado fora do MVP touch + Mac. */
        ESP_LOGI(TAG, "audio_chunk sessao=%s seq=%lu bytes=%u (stub)",
                 session_id != NULL ? session_id : "?",
                 (unsigned long)seq, (unsigned int)len);
        printf("{\"type\":\"audio_chunk\",\"session_id\":\"%s\",\"seq\":%lu,"
               "\"bytes\":%u,\"encoding\":\"none-stub\"}\n",
               session_id != NULL ? session_id : "?",
               (unsigned long)seq, (unsigned int)len);
        return ESP_OK;
    }
    return ESP_ERR_NOT_SUPPORTED;
}

esp_err_t audio_transport_poll_rx(char *out_line, size_t max_len,
                                  uint32_t timeout_ms)
{
    int read_count;
    char ch;
    (void)timeout_ms;
    if (out_line == NULL || max_len == 0) {
        return ESP_ERR_INVALID_ARG;
    }
    for (read_count = 0; read_count < 256; read_count++) {
        ssize_t n = read(s_serial_fd, &ch, 1);
        if (n < 0) {
            return errno == EAGAIN || errno == EWOULDBLOCK
                ? ESP_ERR_TIMEOUT : ESP_FAIL;
        }
        if (n == 0) {
            return ESP_ERR_TIMEOUT;
        }
        if (ch == '\r') {
            continue;
        }
        if (ch == '\n') {
            if (s_input_discard) {
                s_input_discard = false;
                s_input_used = 0;
                continue;
            }
            if (s_input_used == 0) {
                continue;
            }
            if (s_input_used >= max_len) {
                s_input_used = 0;
                return ESP_ERR_INVALID_SIZE;
            }
            memcpy(out_line, s_input_line, s_input_used);
            out_line[s_input_used] = '\0';
            s_input_used = 0;
            return ESP_OK;
        }
        if (s_input_discard) {
            continue;
        }
        if (s_input_used + 1 >= sizeof(s_input_line)) {
            s_input_discard = true;
            s_input_used = 0;
            continue;
        }
        s_input_line[s_input_used++] = ch;
    }
    return ESP_ERR_TIMEOUT;
}
