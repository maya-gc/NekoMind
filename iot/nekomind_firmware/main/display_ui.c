#include "display_ui.h"

#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include "board_spi.h"
#include "driver/gpio.h"
#include "esp_check.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

#define LCD_W 240
#define LCD_H 320
#define TILE_H 16
#define RGB565(r, g, b) ((((r) & 0xF8) << 8) | (((g) & 0xFC) << 3) | ((b) >> 3))

static const char *TAG = "display_ui";
static spi_device_handle_t s_lcd;
static uint8_t s_tile[LCD_W * TILE_H * 2];
static neko_scene_t s_last_scene;
static neko_scene_t s_pre_calibration_scene;
static bool s_have_scene;
static bool s_calibrating;
static int s_tile_y;

static const uint16_t C_BG = RGB565(10, 13, 19);
static const uint16_t C_PANEL = RGB565(31, 40, 53);
static const uint16_t C_WHITE = RGB565(246, 249, 255);
static const uint16_t C_MUTED = RGB565(156, 171, 189);
static const uint16_t C_CYAN = RGB565(70, 205, 239);
static const uint16_t C_AMBER = RGB565(255, 185, 80);

/* Fonte 5x7 local, suficiente para os textos curtos da interface. */
static const uint8_t FONT[][5] = {
    {0x7e,0x11,0x11,0x11,0x7e}, {0x7f,0x49,0x49,0x49,0x36},
    {0x3e,0x41,0x41,0x41,0x22}, {0x7f,0x41,0x41,0x22,0x1c},
    {0x7f,0x49,0x49,0x49,0x41}, {0x7f,0x09,0x09,0x09,0x01},
    {0x3e,0x41,0x49,0x49,0x7a}, {0x7f,0x08,0x08,0x08,0x7f},
    {0x00,0x41,0x7f,0x41,0x00}, {0x20,0x40,0x41,0x3f,0x01},
    {0x7f,0x08,0x14,0x22,0x41}, {0x7f,0x40,0x40,0x40,0x40},
    {0x7f,0x02,0x0c,0x02,0x7f}, {0x7f,0x04,0x08,0x10,0x7f},
    {0x3e,0x41,0x41,0x41,0x3e}, {0x7f,0x09,0x09,0x09,0x06},
    {0x3e,0x41,0x51,0x21,0x5e}, {0x7f,0x09,0x19,0x29,0x46},
    {0x46,0x49,0x49,0x49,0x31}, {0x01,0x01,0x7f,0x01,0x01},
    {0x3f,0x40,0x40,0x40,0x3f}, {0x1f,0x20,0x40,0x20,0x1f},
    {0x7f,0x20,0x18,0x20,0x7f}, {0x63,0x14,0x08,0x14,0x63},
    {0x03,0x04,0x78,0x04,0x03}, {0x61,0x51,0x49,0x45,0x43},
    {0x3e,0x51,0x49,0x45,0x3e}, {0x00,0x42,0x7f,0x40,0x00},
    {0x42,0x61,0x51,0x49,0x46}, {0x21,0x41,0x45,0x4b,0x31},
    {0x18,0x14,0x12,0x7f,0x10}, {0x27,0x45,0x45,0x45,0x39},
    {0x3c,0x4a,0x49,0x49,0x30}, {0x01,0x71,0x09,0x05,0x03},
    {0x36,0x49,0x49,0x49,0x36}, {0x06,0x49,0x49,0x29,0x1e},
};

static const uint8_t *glyph(char ch)
{
    if (ch >= 'A' && ch <= 'Z') return FONT[ch - 'A'];
    if (ch >= '0' && ch <= '9') return FONT[26 + ch - '0'];
    static const uint8_t dash[5] = {0x08,0x08,0x08,0x08,0x08};
    static const uint8_t dot[5] = {0,0x60,0x60,0,0};
    static const uint8_t slash[5] = {0x40,0x30,0x08,0x06,0x01};
    static const uint8_t colon[5] = {0,0x36,0x36,0,0};
    if (ch == '-') return dash;
    if (ch == '.') return dot;
    if (ch == '/') return slash;
    if (ch == ':') return colon;
    return NULL;
}

static void ascii_upper(char *out, size_t size, const char *in)
{
    size_t used = 0;
    if (size == 0) return;
    while (in != NULL && *in != '\0' && used + 1 < size) {
        unsigned char ch = (unsigned char)*in++;
        if (ch == 0xC3 && *in != '\0') {
            unsigned char tail = (unsigned char)*in++;
            if (tail >= 0x80 && tail <= 0x85) ch = 'A';
            else if (tail == 0x87 || tail == 0xA7) ch = 'C';
            else if ((tail >= 0x88 && tail <= 0x8B) || (tail >= 0xA8 && tail <= 0xAB)) ch = 'E';
            else if ((tail >= 0x8C && tail <= 0x8F) || (tail >= 0xAC && tail <= 0xAF)) ch = 'I';
            else if ((tail >= 0x92 && tail <= 0x96) || (tail >= 0xB2 && tail <= 0xB6)) ch = 'O';
            else if ((tail >= 0x99 && tail <= 0x9C) || (tail >= 0xB9 && tail <= 0xBC)) ch = 'U';
            else if (tail >= 0xA0 && tail <= 0xA5) ch = 'A';
            else ch = '?';
        } else if (ch >= 0x80) {
            while ((*in & 0xC0) == 0x80) in++;
            ch = '?';
        }
        if (ch >= 'a' && ch <= 'z') ch -= 32;
        out[used++] = (char)ch;
    }
    out[used] = '\0';
}

static esp_err_t lcd_tx(bool data_mode, const void *bytes, size_t length)
{
    gpio_set_level(NEKO_PIN_LCD_DC, data_mode ? 1 : 0);
    spi_transaction_t tx = {.length = length * 8, .tx_buffer = bytes};
    return spi_device_polling_transmit(s_lcd, &tx);
}

static esp_err_t lcd_cmd(uint8_t command, const uint8_t *params, size_t count)
{
    esp_err_t err = lcd_tx(false, &command, 1);
    if (err == ESP_OK && count > 0) err = lcd_tx(true, params, count);
    return err;
}

static esp_err_t lcd_window(int y0, int y1)
{
    uint8_t x[] = {0, 0, 0, LCD_W - 1};
    uint8_t y[] = {(uint8_t)(y0 >> 8), (uint8_t)y0,
                   (uint8_t)(y1 >> 8), (uint8_t)y1};
    esp_err_t err = lcd_cmd(0x2A, x, sizeof(x));
    if (err == ESP_OK) err = lcd_cmd(0x2B, y, sizeof(y));
    if (err == ESP_OK) err = lcd_cmd(0x2C, NULL, 0);
    return err;
}

static void pixel(int x, int y, uint16_t color)
{
    if (x < 0 || x >= LCD_W || y < s_tile_y || y >= s_tile_y + TILE_H || y >= LCD_H)
        return;
    size_t offset = (size_t)((y - s_tile_y) * LCD_W + x) * 2U;
    s_tile[offset] = (uint8_t)(color >> 8);
    s_tile[offset + 1] = (uint8_t)color;
}

static void rect(int x, int y, int w, int h, uint16_t color)
{
    int x0 = x < 0 ? 0 : x, x1 = x + w > LCD_W ? LCD_W : x + w;
    int y0 = y < s_tile_y ? s_tile_y : y;
    int y1 = y + h > s_tile_y + TILE_H ? s_tile_y + TILE_H : y + h;
    for (int yy = y0; yy < y1; yy++)
        for (int xx = x0; xx < x1; xx++) pixel(xx, yy, color);
}

static void oval(int x, int y, int w, int h, uint16_t color)
{
    if (w < 2 || h < 2) return;
    int y0 = y < s_tile_y ? s_tile_y : y, y1 = y + h > s_tile_y + TILE_H ? s_tile_y + TILE_H : y + h;
    int x0 = x < 0 ? 0 : x, x1 = x + w > LCD_W ? LCD_W : x + w;
    int64_t ww = (int64_t)w * w, hh = (int64_t)h * h;
    for (int yy = y0; yy < y1; yy++) {
        int64_t dy = 2LL * (yy - y) - h + 1;
        for (int xx = x0; xx < x1; xx++) {
            int64_t dx = 2LL * (xx - x) - w + 1;
            if (dx * dx * hh + dy * dy * ww <= ww * hh) pixel(xx, yy, color);
        }
    }
}

static void character(int x, int y, char ch, int scale, uint16_t color)
{
    const uint8_t *bits = glyph(ch);
    if (bits == NULL) return;
    for (int col = 0; col < 5; col++)
        for (int row = 0; row < 7; row++)
            if (bits[col] & (1U << row))
                rect(x + col * scale, y + row * scale, scale, scale, color);
}

static void text_in_rect(const neko_layout_rect_t *r, const char *source,
                         int preferred_scale, uint16_t color)
{
    char text[NEKO_SCENE_TEXT_MAX * 2];
    ascii_upper(text, sizeof(text), source);
    int scale = preferred_scale, len = (int)strlen(text);
    if (len * 6 * scale > r->width - 8) scale = 1;
    int per_line = (r->width - 8) / (6 * scale);
    int line_height = 8 * scale, max_lines = r->height / line_height;
    if (per_line < 1 || max_lines < 1) return;
    if (max_lines > 3) max_lines = 3;
    int pos = 0;
    for (int line = 0; line < max_lines && text[pos] != '\0'; line++) {
        int count = len - pos;
        if (count > per_line) {
            count = per_line;
            int cut = count;
            while (cut > per_line / 2 && text[pos + cut] != ' ') cut--;
            if (cut > per_line / 2) count = cut;
        }
        while (count > 0 && text[pos + count - 1] == ' ') count--;
        int x = r->x + (r->width - count * 6 * scale) / 2;
        int y = r->y + (r->height - max_lines * line_height) / 2 + line * line_height;
        for (int c = 0; c < count; c++)
            character(x + c * 6 * scale, y, text[pos + c], scale, color);
        pos += count;
        while (text[pos] == ' ') pos++;
    }
}

static void draw_op(const neko_scene_op_t *op)
{
    const neko_layout_rect_t *r = &op->rect;
    switch (op->kind) {
    case NEKO_SCENE_OP_FACE:
        oval(r->x + 3, r->y + 3, r->width - 6, r->height - 6, C_PANEL);
        break;
    case NEKO_SCENE_OP_POLYGON:
        for (int yy = 0; yy < r->height; yy++) {
            int span = (yy * r->width) / (2 * r->height);
            int cx = strstr(op->text, "direita") != NULL
                ? r->x + r->width - 2 - span : r->x + 1 + span;
            rect(cx - span, r->y + yy, 2 * span + 1, 1, C_AMBER);
        }
        break;
    case NEKO_SCENE_OP_ELLIPSE:
        if (strstr(op->text, "cabeca") != NULL) {
            oval(r->x, r->y, r->width, r->height, C_WHITE);
            oval(r->x + 5, r->y + 5, r->width - 10, r->height - 10, C_BG);
        } else {
            oval(r->x, r->y, r->width, r->height, C_WHITE);
            oval(r->x + r->width / 3, r->y + r->height / 3,
                 r->width / 3, r->height / 3, C_CYAN);
        }
        break;
    case NEKO_SCENE_OP_LINE:
        rect(r->x, r->y, r->width, 2, C_CYAN);
        oval(r->x + r->width / 2 - 4, r->y - 4, 8, 7, C_CYAN);
        break;
    case NEKO_SCENE_OP_BUTTON:
        rect(r->x, r->y, r->width, r->height, op->enabled ? C_CYAN : C_MUTED);
        rect(r->x + 2, r->y + 2, r->width - 4, r->height - 4, C_PANEL);
        text_in_rect(r, op->text, 1, op->enabled ? C_WHITE : C_MUTED);
        break;
    case NEKO_SCENE_OP_TEXT:
        if (r->height >= 30) {
            rect(r->x, r->y, r->width, r->height, C_PANEL);
            text_in_rect(r, op->text, 2, C_WHITE);
        } else {
            text_in_rect(r, op->text, 2, C_CYAN);
        }
        break;
    default:
        break;
    }
}

esp_err_t display_ui_init(void)
{
    gpio_config_t pins = {
        .pin_bit_mask = (1ULL << NEKO_PIN_LCD_DC) | (1ULL << NEKO_PIN_LCD_RST),
        .mode = GPIO_MODE_OUTPUT,
    };
    ESP_RETURN_ON_ERROR(gpio_config(&pins), TAG, "GPIO LCD");
    gpio_set_level(NEKO_PIN_LCD_RST, 0);
    vTaskDelay(pdMS_TO_TICKS(25));
    gpio_set_level(NEKO_PIN_LCD_RST, 1);
    vTaskDelay(pdMS_TO_TICKS(120));
    ESP_RETURN_ON_ERROR(board_spi_add_lcd(&s_lcd), TAG, "SPI LCD");
    ESP_RETURN_ON_ERROR(lcd_cmd(0x01, NULL, 0), TAG, "reset LCD");
    vTaskDelay(pdMS_TO_TICKS(150));
    const uint8_t power1[] = {0x23}, power2[] = {0x10};
    const uint8_t vcom1[] = {0x3E, 0x28}, vcom2[] = {0x86};
    const uint8_t frame[] = {0x00, 0x18};
    const uint8_t display_fn[] = {0x08, 0x82, 0x27};
    const uint8_t madctl[] = {0x48}; /* portrait, BGR */
    const uint8_t rgb565[] = {0x55};
    ESP_RETURN_ON_ERROR(lcd_cmd(0xC0, power1, sizeof(power1)), TAG, "power1");
    ESP_RETURN_ON_ERROR(lcd_cmd(0xC1, power2, sizeof(power2)), TAG, "power2");
    ESP_RETURN_ON_ERROR(lcd_cmd(0xC5, vcom1, sizeof(vcom1)), TAG, "vcom1");
    ESP_RETURN_ON_ERROR(lcd_cmd(0xC7, vcom2, sizeof(vcom2)), TAG, "vcom2");
    ESP_RETURN_ON_ERROR(lcd_cmd(0xB1, frame, sizeof(frame)), TAG, "frame");
    ESP_RETURN_ON_ERROR(lcd_cmd(0xB6, display_fn, sizeof(display_fn)), TAG, "display fn");
    ESP_RETURN_ON_ERROR(lcd_cmd(0x36, madctl, sizeof(madctl)), TAG, "orientation");
    ESP_RETURN_ON_ERROR(lcd_cmd(0x3A, rgb565, sizeof(rgb565)), TAG, "color");
    ESP_RETURN_ON_ERROR(lcd_cmd(0x11, NULL, 0), TAG, "sleep out");
    vTaskDelay(pdMS_TO_TICKS(120));
    ESP_RETURN_ON_ERROR(lcd_cmd(0x29, NULL, 0), TAG, "display on");
    ESP_LOGI(TAG, "ILI9341 iniciado: 240x320, 20 MHz");
    return ESP_OK;
}

esp_err_t display_ui_draw_scene(const neko_scene_t *scene)
{
    if (scene == NULL || scene->width != LCD_W || scene->height != LCD_H)
        return ESP_ERR_INVALID_ARG;
    if (s_have_scene && memcmp(scene, &s_last_scene, sizeof(*scene)) == 0)
        return ESP_OK;
    for (s_tile_y = 0; s_tile_y < LCD_H; s_tile_y += TILE_H) {
        for (size_t i = 0; i < sizeof(s_tile); i += 2) {
            s_tile[i] = (uint8_t)(C_BG >> 8);
            s_tile[i + 1] = (uint8_t)C_BG;
        }
        for (size_t i = 0; i < scene->op_count; i++) draw_op(&scene->ops[i]);
        ESP_RETURN_ON_ERROR(lcd_window(s_tile_y, s_tile_y + TILE_H - 1), TAG, "janela");
        ESP_RETURN_ON_ERROR(lcd_tx(true, s_tile, sizeof(s_tile)), TAG, "quadro");
    }
    s_last_scene = *scene;
    s_have_scene = true;
    return ESP_OK;
}

esp_err_t display_ui_render(const char *status_line)
{
    neko_scene_t scene = {.width = LCD_W, .height = LCD_H};
    scene.op_count = 1;
    scene.ops[0].kind = NEKO_SCENE_OP_TEXT;
    scene.ops[0].rect = (neko_layout_rect_t){.x = 12, .y = 135, .width = 216, .height = 48};
    snprintf(scene.ops[0].text, sizeof(scene.ops[0].text), "%s",
             status_line != NULL ? status_line : "NekoMind");
    return display_ui_draw_scene(&scene);
}

esp_err_t display_ui_render_view(const char *status_line,
                                 const char *summary,
                                 const char (*topics)[NEKO_TOPIC_MAX + 1],
                                 size_t topic_count, bool is_demo,
                                 int duration_seconds, const char *trend_text,
                                 int voice_level, bool voice_clipping)
{
    (void)summary; (void)topics; (void)topic_count; (void)is_demo;
    (void)duration_seconds; (void)trend_text; (void)voice_level;
    (void)voice_clipping;
    return display_ui_render(status_line);
}

esp_err_t display_ui_show_telemetry(const char *telemetry_line)
{
    (void)telemetry_line;
    return ESP_OK;
}

esp_err_t display_ui_calibration_step(int step)
{
    if (step >= 3) {
        if (!s_calibrating) return ESP_OK;
        s_calibrating = false;
        s_have_scene = false;
        return display_ui_draw_scene(&s_pre_calibration_scene);
    }
    if (step == 0 && !s_calibrating) {
        s_pre_calibration_scene = s_last_scene;
        s_calibrating = true;
    }
    neko_scene_t scene = {.width = LCD_W, .height = LCD_H, .op_count = 2};
    scene.ops[0].kind = NEKO_SCENE_OP_TEXT;
    scene.ops[0].rect = (neko_layout_rect_t){.x = 12, .y = 120, .width = 216, .height = 48};
    snprintf(scene.ops[0].text, sizeof(scene.ops[0].text), "CALIBRAR: TOQUE O ALVO");
    scene.ops[1].kind = NEKO_SCENE_OP_ELLIPSE;
    scene.ops[1].rect = (neko_layout_rect_t){
        .x = step == 1 ? 202 : 14,
        .y = step == 2 ? 280 : 14,
        .width = 24, .height = 24
    };
    snprintf(scene.ops[1].text, sizeof(scene.ops[1].text), "alvo");
    return display_ui_draw_scene(&scene);
}
