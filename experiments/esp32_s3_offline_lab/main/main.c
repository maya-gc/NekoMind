/* A resource and control-flow probe, not an AI implementation. */
#include <stdbool.h>
#include <stdint.h>
#include <string.h>

#include "esp_heap_caps.h"
#include "esp_log.h"
#include "esp_psram.h"

#define MIB (1024U * 1024U)
#define PSRAM_CAPS (MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT)

static const char *TAG = "neko_lab";

static void memory_snapshot(const char *stage)
{
    ESP_LOGI(TAG, "MEM stage=%s internal_free=%u psram_free=%u psram_largest=%u",
             stage,
             (unsigned)heap_caps_get_free_size(MALLOC_CAP_INTERNAL | MALLOC_CAP_8BIT),
             (unsigned)heap_caps_get_free_size(PSRAM_CAPS),
             (unsigned)heap_caps_get_largest_free_block(PSRAM_CAPS));
}

static bool probe_stage(const char *name, size_t bytes)
{
    void *arena = heap_caps_malloc(bytes, PSRAM_CAPS);
    ESP_LOGI(TAG, "ARENA name=%s requested=%u allocated=%s", name,
             (unsigned)bytes, arena ? "yes" : "no");
    if (arena) {
        ((uint8_t *)arena)[0] = 0xA5;
        ((uint8_t *)arena)[bytes - 1] = 0x5A;
        heap_caps_free(arena);
    }
    memory_snapshot(name);
    return arena != NULL;
}

static void probe_parallel(void)
{
    const size_t asr_bytes = (54U * MIB) / 10U;
    const size_t llm_bytes = (65U * MIB) / 10U;
    void *asr = heap_caps_malloc(asr_bytes, PSRAM_CAPS);
    void *llm = heap_caps_malloc(llm_bytes, PSRAM_CAPS);
    ESP_LOGI(TAG, "PARALLEL asr=%s llm=%s combined_requested=%u",
             asr ? "yes" : "no", llm ? "yes" : "no",
             (unsigned)(asr_bytes + llm_bytes));
    if (llm) {
        heap_caps_free(llm);
    }
    if (asr) {
        heap_caps_free(asr);
    }
    memory_snapshot("parallel_released");
}

static void synthetic_flow(void)
{
    static const char *query = "Como a fotossintese utiliza luz?";
    static const char *passages[] = {
        "A fotossintese converte energia luminosa em energia quimica. A clorofila absorve luz.",
        "A respiracao celular transforma energia quimica em ATP.",
        "A agua circula pelas plantas e participa de diversas reacoes.",
    };
    int selected = -1;
    for (int i = 0; i < 3; ++i) {
        if (strstr(query, "fotossintese") && strstr(passages[i], "fotossintese")) {
            selected = i;
            break;
        }
    }
    ESP_LOGI(TAG, "FLOW audio=synthetic asr=injected_text retrieval=%d tts=not_run", selected);
    if (selected >= 0) {
        ESP_LOGI(TAG, "FLOW evidence=%s", passages[selected]);
    }
}

void app_main(void)
{
    ESP_LOGI(TAG, "LAB_BEGIN target=esp32s3 models=none peripheral_audio=none");
    ESP_LOGI(TAG, "PSRAM size=%u", (unsigned)esp_psram_get_size());
    memory_snapshot("boot");

    /* Persistent allocations approximate a short audio ring, a tiny text index,
       and a 20-row RGB565 display strip. The real peripherals are not emulated. */
    void *audio_ring = heap_caps_malloc(4U * 16000U * 2U, PSRAM_CAPS);
    void *text_index = heap_caps_malloc(256U * 1024U, PSRAM_CAPS);
    void *display_strip = heap_caps_malloc(240U * 20U * 2U,
                                            MALLOC_CAP_INTERNAL | MALLOC_CAP_DMA);
    ESP_LOGI(TAG, "BASE audio_ring=%s text_index=%s display_strip=%s",
             audio_ring ? "yes" : "no", text_index ? "yes" : "no",
             display_strip ? "yes" : "no");
    memory_snapshot("base");

    /* Memory demands are from the cited projects. These are allocation probes,
       not their actual models, weights, latency, or quality measurements. */
    probe_stage("oido_asr_2p4mib", (24U * MIB) / 10U);
    probe_stage("ivy_asr_5p4mib", (54U * MIB) / 10U);
    probe_stage("ivy_llm_6p5mib", (65U * MIB) / 10U);
    probe_parallel();
    synthetic_flow();

    heap_caps_free(display_strip);
    heap_caps_free(text_index);
    heap_caps_free(audio_ring);
    memory_snapshot("end");
    ESP_LOGI(TAG, "LAB_END result=resource_probe_only");
}
