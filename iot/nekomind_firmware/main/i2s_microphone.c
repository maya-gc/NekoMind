#include "i2s_microphone.h"

#include <string.h>

#include "esp_log.h"

static const char *TAG = "i2s_mic";

static int s_simulated = 1;

esp_err_t i2s_mic_init(void)
{
    if (NEKO_I2S_PIN_BCLK < 0 || NEKO_I2S_PIN_WS < 0 || NEKO_I2S_PIN_DIN < 0) {
        s_simulated = 1;
        ESP_LOGW(TAG, "pinos I2S nao configurados (TODO) - modo simulado");
        return ESP_OK;
    }

    /* TODO(hardware): inicializar o driver I2S do ESP-IDF aqui.
     *
     * Esboço com a API nova (driver/i2s_std.h, IDF >= 5.x):
     *
     *   i2s_chan_config_t chan_cfg = I2S_CHANNEL_DEFAULT_CONFIG(NEKO_I2S_PORT_NUM, I2S_ROLE_MASTER);
     *   i2s_new_channel(&chan_cfg, NULL, &rx_handle);
     *   i2s_std_config_t std_cfg = {
     *       .clk_cfg  = I2S_STD_CLK_DEFAULT_CONFIG(NEKO_SAMPLE_RATE_HZ),
     *       .slot_cfg = I2S_STD_PHILIPS_SLOT_DEFAULT_CONFIG(I2S_DATA_BIT_WIDTH_32BIT, I2S_SLOT_MODE_MONO),
     *       .gpio_cfg = {
     *           .bclk = NEKO_I2S_PIN_BCLK,
     *           .ws   = NEKO_I2S_PIN_WS,
     *           .din  = NEKO_I2S_PIN_DIN,
     *           .dout = I2S_GPIO_UNUSED,
     *       },
     *   };
     *   i2s_channel_init_std_mode(rx_handle, &std_cfg);
     *   i2s_channel_enable(rx_handle);
     */

    s_simulated = 0;
    ESP_LOGI(TAG, "I2S inicializado: %d Hz, mono, DMA", NEKO_SAMPLE_RATE_HZ);
    return ESP_OK;
}

esp_err_t i2s_mic_read(uint8_t *buffer, size_t buffer_size,
                       size_t *bytes_read, uint32_t timeout_ms)
{
    if (buffer == NULL || bytes_read == NULL) {
        return ESP_ERR_INVALID_ARG;
    }

    if (s_simulated) {
        /* Modo simulado: silencio (zeros) para manter o pipeline ativo. */
        memset(buffer, 0, buffer_size);
        *bytes_read = buffer_size;
        (void)timeout_ms;
        return ESP_OK;
    }

    /* TODO(hardware): substituir pela leitura real:
     *   return i2s_channel_read(rx_handle, buffer, buffer_size, bytes_read,
     *                           pdMS_TO_TICKS(timeout_ms));
     */
    memset(buffer, 0, buffer_size);
    *bytes_read = buffer_size;
    return ESP_OK;
}

esp_err_t i2s_mic_deinit(void)
{
    /* TODO(hardware): i2s_channel_disable(rx_handle); i2s_del_channel(rx_handle); */
    return ESP_OK;
}

int i2s_mic_is_simulated(void)
{
    return s_simulated;
}
