/**
 * i2s_microphone.h - Driver do microfone digital INMP441 via I2S + DMA.
 *
 * TODO(hardware): definir os pinos reais do seu ESP32-S3 abaixo antes de
 * gravar no hardware. Os valores atuais sao placeholders seguros (-1)
 * para manter o firmware compilavel no MVP.
 */
#pragma once

#include <stddef.h>
#include <stdint.h>

#include "esp_err.h"

#ifdef __cplusplus
extern "C" {
#endif

/* ------------------------------------------------------------------
 * TODO(hardware): ajuste estes pinos para a sua placa ESP32-S3.
 * Exemplos comuns em devkits (NAO garantidos para o seu modelo):
 *   BCLK (SCK) -> GPIO4, WS (LRCL) -> GPIO5, SD (DOUT) -> GPIO6
 * Ligue o pino L/R do INMP441 em GND para canal esquerdo.
 * ------------------------------------------------------------------ */
#define NEKO_I2S_PIN_BCLK   (-1) /* TODO: GPIO do clock (SCK/BCLK)  */
#define NEKO_I2S_PIN_WS     (-1) /* TODO: GPIO do word select (WS)  */
#define NEKO_I2S_PIN_DIN    (-1) /* TODO: GPIO dos dados (SD/DOUT)  */

#define NEKO_I2S_PORT_NUM   (0)  /* Porta I2S utilizada              */

/** Frequencia de amostragem alvo (Hz). MVP: 16 kHz (compativel com ASR). */
#define NEKO_SAMPLE_RATE_HZ 16000

/**
 * Inicializa o barramento I2S em modo RX com DMA.
 * No MVP, se os pinos estiverem como TODO (-1), apenas registra um aviso
 * e retorna ESP_OK operando em modo simulado.
 */
esp_err_t i2s_mic_init(void);

/**
 * Le amostras PCM do microfone.
 *
 * @param buffer      destino das amostras (16 bits, mono, little-endian)
 * @param buffer_size capacidade do buffer em bytes
 * @param bytes_read  [out] quantidade efetivamente lida
 * @param timeout_ms  tempo maximo de espera
 *
 * Em modo simulado preenche o buffer com zeros e retorna ESP_OK.
 */
esp_err_t i2s_mic_read(uint8_t *buffer, size_t buffer_size,
                       size_t *bytes_read, uint32_t timeout_ms);

/** Libera o driver I2S. */
esp_err_t i2s_mic_deinit(void);

/** Retorna 1 se o hardware real esta configurado; 0 em modo simulado. */
int i2s_mic_is_simulated(void);

#ifdef __cplusplus
}
#endif
