/**
 * session_controller.h - Orquestra uma sessao de estudo Feynman:
 *
 *   IDLE -> RECORDING -> SENDING/RECORDING (intercalado) -> PROCESSING
 *        -> SUCCESS | ERROR
 *
 * Coordena audio_capture, audio_transport, avatar_state e display_ui,
 * e emite as mensagens do protocolo JSON Lines (docs/iot_protocol.md).
 */
#pragma once

#include "esp_err.h"

#ifdef __cplusplus
extern "C" {
#endif

/** Inicializa todos os modulos e entra em IDLE. */
esp_err_t session_controller_init(void);

/**
 * Executa uma sessao completa de demonstracao.
 * Duracao definida por NEKO_DEMO_SESSION_SECONDS (MVP, por logs).
 */
esp_err_t session_controller_run_demo(void);

/** Inicia a task FreeRTOS do controlador (loop de eventos). */
esp_err_t session_controller_start_task(void);

#ifdef __cplusplus
}
#endif
