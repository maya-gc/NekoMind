/**
 * audio_transport.h - Transporte de mensagens/chunks para o computador.
 *
 * Protocolo: JSON Lines (uma mensagem JSON por linha) - ver
 * docs/iot_protocol.md. MVP usa a serial USB; uma interface Wi-Fi
 * esta prevista como alternativa futura.
 */
#pragma once

#include <stddef.h>
#include <stdint.h>

#include "esp_err.h"

#ifdef __cplusplus
extern "C" {
#endif

/* ------------------------------------------------------------------
 * TODO(config): modo de transporte e configuracao de rede.
 * ------------------------------------------------------------------ */
typedef enum {
    NEKO_TRANSPORT_SERIAL = 0, /* Padrao no MVP: USB serial (JSON Lines) */
    NEKO_TRANSPORT_WIFI        /* Futuro: TCP/WebSocket via Wi-Fi        */
} neko_transport_mode_t;

#define NEKO_TRANSPORT_MODE_NELO_DEFAULT NEKO_TRANSPORT_SERIAL

/* TODO(config): credenciais Wi-Fi - NUNCA versionar valores reais. */
#define NEKO_WIFI_SSID      ""   /* TODO: sua rede                    */
#define NEKO_WIFI_PASSWORD  ""   /* TODO: sua senha                   */
#define NEKO_WIFI_HOST      ""   /* TODO: IP/hostname do computador   */
#define NEKO_WIFI_PORT      (0)  /* TODO: porta do backend            */

/** Inicializa o transporte no modo escolhido. */
esp_err_t audio_transport_init(neko_transport_mode_t mode);

/** Envia uma mensagem JSON (uma linha, sem '\n' final - sera adicionado). */
esp_err_t audio_transport_send_json(const char *json_line);

/** Envia um chunk de audio + metadados (formato base64 provisorio). */
esp_err_t audio_transport_send_chunk(const char *session_id, uint32_t seq,
                                     const uint8_t *data, size_t len);

/**
 * Tenta receber uma linha JSON do computador (ex.: analysis_result).
 * @return ESP_OK se uma linha foi recebida; ESP_ERR_TIMEOUT caso contrario.
 */
esp_err_t audio_transport_poll_rx(char *out_line, size_t max_len,
                                  uint32_t timeout_ms);

#ifdef __cplusplus
}
#endif
