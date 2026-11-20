#include "neko_avatar3d.h"

#include <math.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdlib.h>
#include <string.h>

typedef struct {
    float x, y, z, rx, ry, rz;
    uint8_t r, g, b;
    float skew;
} ellipsoid_t;

static uint16_t rgb565(int r, int g, int b)
{
    if (r > 255) r = 255;
    if (g > 255) g = 255;
    if (b > 255) b = 255;
    return (uint16_t)(((r & 0xf8) << 8) | ((g & 0xfc) << 3) | (b >> 3));
}

static float minf(float a, float b) { return a < b ? a : b; }

/* Raio ortografico contra um volume girado em Y. O afunilamento deixa a
 * orelha arredondada no topo e larga na base, sem uma aresta triangular. */
static bool intersect(float u, float v, float cosine, float sine,
                      const ellipsoid_t *shape, bool tapered,
                      float *depth, float *light)
{
    float center_x = cosine * shape->x + sine * shape->z;
    float center_z = -sine * shape->x + cosine * shape->z;
    float dy = v - shape->y;
    if (fabsf(dy) >= shape->ry) return false;
    float dx = u - center_x - shape->skew * dy;
    float rx = shape->rx * (tapered ? 1.f + 0.4f * dy / shape->ry : 1.f);
    float irx = 1.f / (rx * rx);
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
    float ny = dy * iry - shape->skew * nx;
    float nz = -sine * local_x * irx + cosine * local_z * irz;
    float inv_len = 1.f / sqrtf(nx * nx + ny * ny + nz * nz);
    *depth = center_z + z;
    *light = minf(1.f, 0.76f + 0.25f * fmaxf(0.f,
        (-0.32f * nx - 0.43f * ny + 0.84f * nz) * inv_len));
    return true;
}

/* Cabeca como superelipsoide: topo e bochechas mais cheios que uma esfera. */
static bool head_surface(float u, float v, float cosine, float sine,
                         const ellipsoid_t *head, float *depth, float *light)
{
    float yy = (v - head->y) / head->ry;
    float ay = fabsf(yy);
    float y_profile = ay * ay * (0.5f + 0.5f * ay);
    float z_screen = head->rz;
    float local_x = 0.f, local_z = 0.f;
    for (int i = 0; i < 3; ++i) {
        local_x = cosine * u - sine * z_screen;
        float ax = fabsf(local_x / head->rx);
        float q = ax * ax * (0.5f + 0.5f * ax) + y_profile;
        if (q >= 1.f) return false;
        local_z = head->rz * sqrtf(1.f - q);
        z_screen = -sine * local_x + cosine * local_z;
    }
    float ax = fabsf(local_x / head->rx);
    float nx = (local_x >= 0.f ? 1.f : -1.f)
               * (ax + 1.5f * ax * ax) / head->rx;
    float ny = (yy >= 0.f ? 1.f : -1.f)
               * (ay + 1.5f * ay * ay) / head->ry;
    float nz = 2.f * local_z / (head->rz * head->rz);
    float camera_x = cosine * nx + sine * nz;
    float camera_z = -sine * nx + cosine * nz;
    float inv_len = 1.f / sqrtf(camera_x * camera_x + ny * ny + camera_z * camera_z);
    *depth = z_screen;
    float top = minf(1.f, fmaxf(0.f, (-v - 0.30f) / 0.35f));
    float diffuse = fmaxf(0.f,
        (-0.32f * camera_x - 0.43f * ny + 0.84f * camera_z) * inv_len);
    *light = minf(1.f, 0.76f + 0.12f * top
                       + (0.25f - 0.13f * top) * diffuse);
    return true;
}

static void stroke_line(neko_avatar3d_pixel_fn pixel, int x0, int y0,
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
    float teal = worried ? 244.f : 50.f;
    ellipsoid_t parts[] = {
        {-0.48f, -0.57f + bob, -0.28f, 0.25f, 0.34f, 0.16f, 91, 218, 205, -0.12f},
        { 0.48f, -0.57f + bob, -0.28f, 0.25f, 0.34f, 0.16f, 91, 218, 205,  0.12f},
        { 0.f, bob, 0.f, 0.76f, 0.69f, 0.48f, 184, 172, 236, 0.f},
        {-0.30f, eye_y + bob, 0.49f, 0.085f, eye_h, 0.060f, 245, 185, 66, 0.f},
        { 0.30f, eye_y + bob, 0.49f, 0.085f, eye_h, 0.060f, 245, 185, 66, 0.f},
        {-0.30f, eye_y + bob, 0.56f, 0.032f, eye_h * 0.55f, 0.025f, 51, 43, 85, 0.f},
        { 0.30f, eye_y + bob, 0.56f, 0.032f, eye_h * 0.55f, 0.025f, 51, 43, 85, 0.f},
        { 0.f, 0.19f + bob, 0.48f, 0.22f, 0.14f, 0.065f, 217, 255, 248, 0.f},
        { 0.f, 0.13f + bob, 0.56f, 0.055f, 0.036f, 0.030f, 51, 43, 85, 0.f},
        { 0.f, -0.40f + bob, 0.51f, 0.12f, 0.12f, 0.050f, (uint8_t)teal, 214, 196, 0.f},
    };
    /* Projecao ajustada ao retangulo reservado para o rosto no LCD. */
    float scale_y = (float)height / 1.79f;
    float scale_x = minf((float)width / 1.85f, scale_y * 1.30f);
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
            for (size_t i = 0; i < sizeof(parts) / sizeof(parts[0]); ++i) {
                float depth, light;
                bool hit = i == 2
                    ? head_surface(u, v, cosine, sine, &parts[i], &depth, &light)
                    : intersect(u, v, cosine, sine, &parts[i], i < 2,
                                &depth, &light);
                if (!hit
                    || depth <= nearest) continue;
                nearest = depth;
                color = rgb565((int)(parts[i].r * light),
                               (int)(parts[i].g * light),
                               (int)(parts[i].b * light));
            }
            pixel(xx, yy, color);
        }
    }
    /* O sorriso visivel diferencia Lumi e tambem comunica estado sem depender de cor. */
    uint16_t ink = rgb565(51, 43, 85);
    int mouth_x = (int)(mid_x + scale_x * sine * 0.42f);
    int mouth_y = (int)(mid_y + scale_y * (0.25f + bob));
    int mouth_drop = success ? 2 : worried ? -4 : 5;
    stroke_line(pixel, mouth_x, mouth_y, mouth_x - (int)(scale_x * 0.13f),
                mouth_y + mouth_drop, first_y, last_y, ink);
    stroke_line(pixel, mouth_x, mouth_y, mouth_x + (int)(scale_x * 0.13f),
                mouth_y + mouth_drop, first_y, last_y, ink);
}
