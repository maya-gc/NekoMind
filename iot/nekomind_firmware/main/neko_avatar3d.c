#include "neko_avatar3d.h"

#include <math.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdlib.h>
#include <string.h>

typedef struct {
    float x, y, z, rx, ry, rz;
    uint8_t r, g, b;
} ellipsoid_t;

static uint16_t rgb565(int r, int g, int b)
{
    if (r > 255) r = 255;
    if (g > 255) g = 255;
    if (b > 255) b = 255;
    return (uint16_t)(((r & 0xf8) << 8) | ((g & 0xfc) << 3) | (b >> 3));
}

static float minf(float a, float b) { return a < b ? a : b; }

/* Superficie de uma orelha conica, com ponta e profundidade reais. */
static bool ear_surface(float u, float v, float cosine, float sine,
                        int side, bool inner, float bob,
                        float *depth, float *light)
{
    float tip = inner ? -0.84f : -0.94f;
    float base = inner ? -0.43f : -0.39f;
    float t = (v - bob - tip) / (base - tip);
    if (t <= 0.f || t >= 1.f) return false;
    float local_x = side * (0.56f + 0.07f * (1.f - t));
    float local_z = inner ? 0.09f : -0.05f;
    float center_x = cosine * local_x + sine * local_z;
    float radius = (inner ? 0.12f : 0.22f) * t;
    float across = (u - center_x) / radius;
    if (across < -1.f || across > 1.f) return false;
    *depth = -sine * local_x + cosine * local_z
             + (inner ? 0.06f : 0.15f) * t * sqrtf(1.f - across * across);
    *light = 0.77f + 0.18f * (1.f - fabsf(across));
    return true;
}

/* Raio ortografico contra um elipsoide girado em Y; devolve profundidade e normal. */
static bool intersect(float u, float v, float cosine, float sine,
                      const ellipsoid_t *shape, float *depth, float *light)
{
    float center_x = cosine * shape->x + sine * shape->z;
    float center_z = -sine * shape->x + cosine * shape->z;
    float dx = u - center_x, dy = v - shape->y;
    float irx = 1.f / (shape->rx * shape->rx);
    float iry = 1.f / (shape->ry * shape->ry);
    float irz = 1.f / (shape->rz * shape->rz);
    float a = sine * sine * irx + cosine * cosine * irz;
    float b = 2.f * dx * cosine * sine * (irz - irx);
    float c = dx * dx * (cosine * cosine * irx + sine * sine * irz)
              + dy * dy * iry - 1.f;
    float discriminant = b * b - 4.f * a * c;
    if (discriminant < 0.f) return false;
    float z = (-b + sqrtf(discriminant)) / (2.f * a);
    float local_x = cosine * dx - sine * z;
    float local_z = sine * dx + cosine * z;
    float nx = cosine * local_x * irx + sine * local_z * irz;
    float ny = dy * iry;
    float nz = -sine * local_x * irx + cosine * local_z * irz;
    float inv_len = 1.f / sqrtf(nx * nx + ny * ny + nz * nz);
    *depth = center_z + z;
    *light = minf(1.f, 0.60f + 0.42f * fmaxf(0.f,
        (-0.32f * nx - 0.43f * ny + 0.84f * nz) * inv_len));
    return true;
}

static void whisker(neko_avatar3d_pixel_fn pixel, int x0, int y0,
                    int x1, int y1, int clip_y0, int clip_y1, uint16_t color)
{
    int dx = abs(x1 - x0), dy = abs(y1 - y0);
    int sx = x0 < x1 ? 1 : -1, sy = y0 < y1 ? 1 : -1;
    int err = dx - dy;
    for (;;) {
        if (y0 >= clip_y0 && y0 < clip_y1) pixel(x0, y0, color);
        if (x0 == x1 && y0 == y1) break;
        int twice = 2 * err;
        if (twice > -dy) { err -= dy; x0 += sx; }
        if (twice < dx) { err += dx; y0 += sy; }
    }
}

void neko_avatar3d_render(int x, int y, int width, int height,
                          int clip_y0, int clip_y1,
                          const char *expression, uint32_t time_ms,
                          uint16_t background, neko_avatar3d_pixel_fn pixel)
{
    if (pixel == NULL || width <= 0 || height <= 0) return;
    const char *state = expression != NULL ? expression : "";
    bool paused = strstr(state, "paused") != NULL;
    bool success = strstr(state, "success") != NULL || strstr(state, "happy") != NULL;
    bool thinking = strstr(state, "processing") != NULL || strstr(state, "thinking") != NULL;
    bool listening = strstr(state, "recording") != NULL;
    bool worried = strstr(state, "error") != NULL || strstr(state, "sad") != NULL
                   || strstr(state, "concerned") != NULL;
    bool still = strstr(state, "static") != NULL;
    float seconds = (float)(time_ms % 120000U) * 0.001f;
    float yaw = paused || still ? 0.f : (thinking ? 0.30f : 0.18f) * sinf(seconds * 1.9f);
    float cosine = cosf(yaw), sine = sinf(yaw);
    float bob = paused || still ? 0.f
        : (listening ? 0.025f * sinf(seconds * 4.0f)
                     : 0.018f * sinf(seconds * 2.8f));
    float blink_phase = fmodf(seconds, 3.4f);
    bool blink = paused || (!still && blink_phase > 3.16f && blink_phase < 3.32f);
    float eye_h = blink || success ? 0.025f : worried ? 0.075f : 0.105f;
    float eye_y = thinking ? -0.10f : -0.035f;
    float red = worried ? 250.f : 239.f;
    ellipsoid_t parts[] = {
        { 0.f, bob, 0.f, 0.79f, 0.61f, 0.48f, 255, 251, 249},
        {-0.30f, eye_y + bob, 0.49f, 0.066f, eye_h, 0.054f, 46, 35, 40},
        { 0.30f, eye_y + bob, 0.49f, 0.066f, eye_h, 0.054f, 46, 35, 40},
        { 0.f, 0.17f + bob, 0.51f, 0.075f, 0.052f, 0.060f, 249, 200, 66},
        { 0.43f, -0.51f + bob, 0.46f, 0.19f, 0.16f, 0.12f, (uint8_t)red, 45, 70},
        { 0.75f, -0.48f + bob, 0.42f, 0.18f, 0.15f, 0.12f, (uint8_t)red, 45, 70},
        { 0.60f, -0.49f + bob, 0.60f, 0.085f, 0.075f, 0.075f, 225, 32, 55},
    };
    /* A camera usa pixels retangulares para preservar o rosto largo no LCD. */
    float scale_x = (float)width / 1.85f;
    float scale_y = (float)height / 1.79f;
    float mid_x = (float)x + (float)width * 0.5f;
    float mid_y = (float)y + (float)height * 0.53f;
    int first_y = clip_y0 > y ? clip_y0 : y;
    int last_y = clip_y1 < y + height ? clip_y1 : y + height;
    for (int yy = first_y; yy < last_y; ++yy) {
        float v = ((float)yy + 0.5f - mid_y) / scale_y;
        for (int xx = x; xx < x + width; ++xx) {
            float u = ((float)xx + 0.5f - mid_x) / scale_x;
            float nearest = -10.f;
            uint16_t color = background;
            for (int side = -1; side <= 1; side += 2) {
                for (int inner = 0; inner <= 1; ++inner) {
                    float depth, light;
                    if (!ear_surface(u, v, cosine, sine, side, inner != 0,
                                     bob, &depth, &light) || depth <= nearest) continue;
                    nearest = depth;
                    color = inner ? rgb565((int)(250 * light), (int)(200 * light),
                                           (int)(214 * light))
                                  : rgb565((int)(255 * light), (int)(251 * light),
                                           (int)(249 * light));
                }
            }
            for (size_t i = 0; i < sizeof(parts) / sizeof(parts[0]); ++i) {
                float depth, light;
                if (!intersect(u, v, cosine, sine, &parts[i], &depth, &light)
                    || depth <= nearest) continue;
                nearest = depth;
                color = rgb565((int)(parts[i].r * light),
                               (int)(parts[i].g * light),
                               (int)(parts[i].b * light));
            }
            pixel(xx, yy, color);
        }
    }
    /* Bigodes sao segmentos 3D presos a face; acompanham a rotacao da cabeca. */
    uint16_t ink = rgb565(60, 46, 51);
    for (int side = -1; side <= 1; side += 2) {
        for (int i = -1; i <= 1; ++i) {
            float ax = cosine * (side * 0.56f) + sine * 0.33f;
            float bx = cosine * (side * 0.83f) + sine * 0.30f;
            float ay = 0.17f + bob + i * 0.085f;
            float by = ay + i * 0.04f;
            int x0 = (int)(mid_x + scale_x * ax), x1 = (int)(mid_x + scale_x * bx);
            int y0 = (int)(mid_y + scale_y * ay), y1 = (int)(mid_y + scale_y * by);
            if (x0 >= x && x0 < x + width && x1 >= x && x1 < x + width
                && y0 >= y && y0 < y + height && y1 >= y && y1 < y + height)
                whisker(pixel, x0, y0, x1, y1, first_y, last_y, ink);
        }
    }
}
