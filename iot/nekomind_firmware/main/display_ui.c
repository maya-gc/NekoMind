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

typedef struct {
    uint16_t bg, panel, text, muted, accent, border, soft;
} theme_palette_t;

static const theme_palette_t LIGHT = {
    RGB565(255, 246, 248), RGB565(255, 255, 255), RGB565(55, 43, 53),
    RGB565(105, 82, 95), RGB565(199, 51, 92), RGB565(218, 161, 181),
    RGB565(255, 225, 234)
};
static const theme_palette_t DARK = {
    RGB565(32, 27, 39), RGB565(55, 46, 63), RGB565(255, 242, 247),
    RGB565(202, 180, 194), RGB565(255, 150, 179), RGB565(161, 106, 131),
    RGB565(79, 55, 74)
};
static const theme_palette_t *s_palette = &LIGHT;
static const uint16_t FACE_INK = RGB565(48, 40, 45);
static const uint16_t FACE_WHITE = RGB565(255, 254, 251);
static const uint16_t BOW_RED = RGB565(235, 55, 83);
static const uint16_t NOSE_YELLOW = RGB565(248, 202, 77);
static const uint16_t CHEEK_PINK = RGB565(255, 223, 229);

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

static void triangle(int ax, int ay, int bx, int by, int cx, int cy,
                     uint16_t color)
{
    int left = ax < bx ? ax : bx, right = ax > bx ? ax : bx;
    int top = ay < by ? ay : by, bottom = ay > by ? ay : by;
    if (cx < left) left = cx;
    if (cx > right) right = cx;
    if (cy < top) top = cy;
    if (cy > bottom) bottom = cy;
    if (top < s_tile_y) top = s_tile_y;
    if (bottom >= s_tile_y + TILE_H) bottom = s_tile_y + TILE_H - 1;
    for (int y = top; y <= bottom; y++) {
        for (int x = left; x <= right; x++) {
            int64_t a = (int64_t)(bx - ax) * (y - ay) - (int64_t)(by - ay) * (x - ax);
            int64_t b = (int64_t)(cx - bx) * (y - by) - (int64_t)(cy - by) * (x - bx);
            int64_t c = (int64_t)(ax - cx) * (y - cy) - (int64_t)(ay - cy) * (x - cx);
            if ((a >= 0 && b >= 0 && c >= 0) || (a <= 0 && b <= 0 && c <= 0))
                pixel(x, y, color);
        }
    }
}

static void stroke(int x0, int y0, int x1, int y1, uint16_t color)
{
    int dx = x1 > x0 ? x1 - x0 : x0 - x1;
    int dy = y1 > y0 ? y1 - y0 : y0 - y1;
    int sx = x0 < x1 ? 1 : -1, sy = y0 < y1 ? 1 : -1;
    int err = dx - dy;
    while (true) {
        pixel(x0, y0, color);
        pixel(x0, y0 + 1, color);
        if (x0 == x1 && y0 == y1) break;
        int e2 = 2 * err;
        if (e2 > -dy) { err -= dy; x0 += sx; }
        if (e2 < dx) { err += dx; y0 += sy; }
    }
}

static int fx(const neko_layout_rect_t *r, int percent)
{
    return r->x + r->width * percent / 100;
}

static int fy(const neko_layout_rect_t *r, int percent)
{
    return r->y + r->height * percent / 100;
}

static void draw_face(const neko_layout_rect_t *r, const char *expression)
{
    int inset = r->height < 110 ? 3 : 4;
    /* Orelhas, silhueta arredondada e laço são desenhados em RGB565 no LCD. */
    triangle(fx(r, 9), fy(r, 35), fx(r, 11), fy(r, 4),
             fx(r, 39), fy(r, 23), FACE_INK);
    triangle(fx(r, 61), fy(r, 23), fx(r, 86), fy(r, 3),
             fx(r, 93), fy(r, 37), FACE_INK);
    triangle(fx(r, 12), fy(r, 33), fx(r, 14), fy(r, 10),
             fx(r, 37), fy(r, 25), FACE_WHITE);
    triangle(fx(r, 63), fy(r, 25), fx(r, 84), fy(r, 9),
             fx(r, 90), fy(r, 34), FACE_WHITE);
    int hx = fx(r, 6), hy = fy(r, 22);
    int hw = r->width * 88 / 100, hh = r->height * 73 / 100;
    oval(hx, hy, hw, hh, FACE_INK);
    oval(hx + inset, hy + inset, hw - 2 * inset, hh - 2 * inset, FACE_WHITE);

    /* Olhos e nariz preservam a leitura mesmo no rosto compacto de resultado. */
    int ey = fy(r, 56);
    bool closed = strstr(expression, "paused") != NULL;
    bool worried = strstr(expression, "error") != NULL
                   || strstr(expression, "clipping") != NULL;
    if (closed) {
        stroke(fx(r, 31), ey + 3, fx(r, 39), ey + 3, FACE_INK);
        stroke(fx(r, 64), ey + 3, fx(r, 72), ey + 3, FACE_INK);
    } else {
        int eye_h = worried ? r->height * 10 / 100 : r->height * 12 / 100;
        oval(fx(r, 33), ey, r->width * 6 / 100, eye_h, FACE_INK);
        oval(fx(r, 66), ey, r->width * 6 / 100, eye_h, FACE_INK);
    }
    oval(fx(r, 21), fy(r, 73), r->width * 11 / 100, r->height * 6 / 100,
         CHEEK_PINK);
    oval(fx(r, 70), fy(r, 73), r->width * 11 / 100, r->height * 6 / 100,
         CHEEK_PINK);
    oval(fx(r, 46), fy(r, 69), r->width * 9 / 100, r->height * 9 / 100,
         FACE_INK);
    oval(fx(r, 47), fy(r, 70), r->width * 7 / 100, r->height * 7 / 100,
         NOSE_YELLOW);

    for (int i = 0; i < 3; i++) {
        int shift = i == 0 ? -10 : i == 2 ? 10 : 0;
        stroke(fx(r, 27), fy(r, 70 + i * 6), fx(r, 0), fy(r, 67 + i * 6 + shift / 2), FACE_INK);
        stroke(fx(r, 73), fy(r, 70 + i * 6), fx(r, 99), fy(r, 67 + i * 6 + shift / 2), FACE_INK);
    }

    /* Laço vermelho sobre a orelha direita (direita da personagem). */
    oval(fx(r, 54), fy(r, 3), r->width * 23 / 100, r->height * 35 / 100, FACE_INK);
    oval(fx(r, 56), fy(r, 6), r->width * 20 / 100, r->height * 30 / 100, BOW_RED);
    oval(fx(r, 75), fy(r, 16), r->width * 22 / 100, r->height * 30 / 100, FACE_INK);
    oval(fx(r, 77), fy(r, 19), r->width * 18 / 100, r->height * 24 / 100, BOW_RED);
    oval(fx(r, 68), fy(r, 21), r->width * 17 / 100, r->height * 19 / 100, FACE_INK);
    oval(fx(r, 70), fy(r, 23), r->width * 13 / 100, r->height * 15 / 100, BOW_RED);
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
        draw_face(r, op->text);
        break;
    case NEKO_SCENE_OP_POLYGON:
        for (int yy = 0; yy < r->height; yy++) {
            int span = (yy * r->width) / (2 * r->height);
            int cx = strstr(op->text, "direita") != NULL
                ? r->x + r->width - 2 - span : r->x + 1 + span;
            rect(cx - span, r->y + yy, 2 * span + 1, 1, s_palette->accent);
        }
        break;
    case NEKO_SCENE_OP_ELLIPSE:
        if (strstr(op->text, "cabeca") != NULL) {
            oval(r->x, r->y, r->width, r->height, s_palette->text);
            oval(r->x + 5, r->y + 5, r->width - 10, r->height - 10, s_palette->bg);
        } else {
            oval(r->x, r->y, r->width, r->height, s_palette->text);
            oval(r->x + r->width / 3, r->y + r->height / 3,
                 r->width / 3, r->height / 3, s_palette->accent);
        }
        break;
    case NEKO_SCENE_OP_LINE:
        rect(r->x, r->y, r->width, 2, s_palette->accent);
        oval(r->x + r->width / 2 - 4, r->y - 4, 8, 7, s_palette->accent);
        break;
    case NEKO_SCENE_OP_BUTTON:
        rect(r->x, r->y, r->width, r->height,
             op->enabled ? s_palette->accent : s_palette->border);
        rect(r->x + 2, r->y + 2, r->width - 4, r->height - 4,
             s_palette->panel);
        text_in_rect(r, op->text, 1,
                     op->enabled ? s_palette->text : s_palette->muted);
        break;
    case NEKO_SCENE_OP_TEXT:
        if (r->height >= 30) {
            rect(r->x, r->y, r->width, r->height, s_palette->panel);
            text_in_rect(r, op->text, 2, s_palette->text);
        } else {
            text_in_rect(r, op->text, 2, s_palette->accent);
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
    s_palette = scene->dark_theme ? &DARK : &LIGHT;
    for (s_tile_y = 0; s_tile_y < LCD_H; s_tile_y += TILE_H) {
        for (size_t i = 0; i < sizeof(s_tile); i += 2) {
            s_tile[i] = (uint8_t)(s_palette->bg >> 8);
            s_tile[i + 1] = (uint8_t)s_palette->bg;
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
