/**
 * audio_capture.h - Pipeline de captura e bufferizacao de audio PCM mono.
 *
 * Consome o driver i2s_microphone, acumula amostras em buffers
 * ("chunks") de tamanho fixo e os entrega ao modulo de transporte.
 */
#pragma once

#include <stddef.h>
#include <stdint.h>

#include "esp_err.h"

#ifdef __cplusplus
extern "C" {
#endif

/* ------------------------------------------------------------------
 * TODO: ajuste conforme a memoria da sua placa e a latencia desejada.
 * Tamanho de um chunk de audio enviado ao computador (bytes).
 * Com 16 kHz / 16 bits / mono, 4096 bytes ~= 128 ms de audio.
 * ------------------------------------------------------------------ */
#define NEKO_AUDIO_CHUNK_SIZE (4096)

/** Numero de chunks no buffer circular. */
#define NEKO_AUDIO_CHUNK_COUNT (4)

/** Inicializa o pipeline de captura (inclui o driver I2S). */
esp_err_t audio_capture_init(void);

/**
 * Inicia a captura continua para uma sessao.
 * @param session_id identificador curto da sessao (vai nas mensagens JSON)
 */
esp_err_t audio_capture_start(const char *session_id);

/** Para a captura e esvazia os buffers pendentes. */
esp_err_t audio_capture_stop(void);

/**
 * Obtem o proximo chunk de audio preenchido (bloqueante).
 *
 * @param out_buf     [out] ponteiro para o buffer interno do chunk
 * @param out_len     [out] tamanho valido em bytes
 * @param out_seq     [out] numero de sequencia do chunk na sessao
 * @param timeout_ms  tempo maximo de espera
 */
esp_err_t audio_capture_next_chunk(const uint8_t **out_buf, size_t *out_len,
                                   uint32_t *out_seq, uint32_t timeout_ms);

/** Devolve o chunk obtido por audio_capture_next_chunk ao pool. */
void audio_capture_release_chunk(void);

#ifdef __cplusplus
}
#endif
