#include "audio_transport.h"

#include <stdio.h>
#include <string.h>

#include "esp_log.h"

static const char *TAG = "audio_transport";

static neko_transport_mode_t s_mode = NEKO_TRANSPORT_SERIAL;

esp_err_t audio_transport_init(neko_transport_mode_t mode)
{
    s_mode = mode;
    switch (mode) {
    case NEKO_TRANSPORT_SERIAL:
        /* USB Serial/JTAG ou UART0 ja sao inicializados pelo console
         * do ESP-IDF (ver CONFIG_ESP_CONSOLE_USB_SERIAL_JTAG em
         * sdkconfig.defaults). Nada mais a fazer no MVP. */
        ESP_LOGI(TAG, "transporte serial pronto (JSON Lines no stdout)");
        return ESP_OK;
    case NEKO_TRANSPORT_WIFI:
        /* TODO(wifi): inicializar NVS + esp_wifi + conectar ao AP e
         * abrir socket TCP/WebSocket com o backend.
         * Valores em NEKO_WIFI_* estao vazios por seguranca. */
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
    /* JSON Lines: uma mensagem por linha. */
    printf("%s\n", json_line);
    return ESP_OK;
}

esp_err_t audio_transport_send_chunk(const char *session_id, uint32_t seq,
                                     const uint8_t *data, size_t len)
{
    (void)data; /* TODO: codificar payload em base64 no JSON final. */

    if (s_mode == NEKO_TRANSPORT_SERIAL) {
        /* Stub: anuncia o chunk sem transmitir o payload bruto, para nao
         * poluir o monitor serial durante o desenvolvimento do MVP.
         * Implementacao final: {"type":"audio_chunk","session_id":...,
         * "seq":...,"encoding":"base64","data":"..."} */
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
    /* TODO: leitura nao bloqueante da serial (fgets com timeout via
     * driver UART/USB). No MVP, nunca ha mensagem de entrada. */
    (void)out_line;
    (void)max_len;
    (void)timeout_ms;
    return ESP_ERR_TIMEOUT;
}
