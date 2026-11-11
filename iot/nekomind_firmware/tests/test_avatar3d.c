#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

#include "../main/neko_avatar3d.h"

#define W 176
#define H 134

static uint16_t image[W * H];
static int writes;

static void put_pixel(int x, int y, uint16_t color)
{
    assert(x >= 0 && x < W);
    assert(y >= 0 && y < H);
    image[y * W + x] = color;
    writes++;
}

static uint64_t image_hash(void)
{
    uint64_t hash = 1469598103934665603ULL;
    for (size_t i = 0; i < W * H; ++i) {
        hash ^= image[i];
        hash *= 1099511628211ULL;
    }
    return hash;
}

int main(int argc, char **argv)
{
    const uint16_t bg = 0xffff;
    neko_avatar3d_render(0, 0, W, H, 0, H, "face-ready", 1000, bg, put_pixel);
    assert(writes >= W * H);
    uint64_t first = image_hash();
    int foreground = 0, red = 0, dark = 0;
    for (size_t i = 0; i < W * H; ++i) {
        if (image[i] != bg) foreground++;
        if ((image[i] & 0xf800) > 0x8000 && (image[i] & 0x07e0) < 0x0220) red++;
        if (image[i] < 0x4208) dark++;
    }
    assert(foreground > 6000 && red > 50 && dark > 30);
    neko_avatar3d_render(0, 0, W, H, 0, H, "face-ready", 1250, bg, put_pixel);
    assert(image_hash() != first);
    neko_avatar3d_render(0, 0, W, H, 0, H, "face-paused", 1250, bg, put_pixel);
    assert(image_hash() != first);
    neko_avatar3d_render(0, 0, W, H, 0, H, "face-static", 1000, bg, put_pixel);
    uint64_t still = image_hash();
    neko_avatar3d_render(0, 0, W, H, 0, H, "face-static", 1250, bg, put_pixel);
    assert(image_hash() == still);
    neko_avatar3d_render(0, 0, W, H, 0, H, "face-ready", 1000, bg, put_pixel);
    uint64_t complete = image_hash();
    for (size_t i = 0; i < W * H; ++i) image[i] = 0;
    neko_avatar3d_render(0, 0, W, H, 48, 64, "face-ready", 1000, bg, put_pixel);
    for (int yy = 0; yy < H; ++yy)
        if (yy < 48 || yy >= 64)
            for (int xx = 0; xx < W; ++xx) assert(image[yy * W + xx] == 0);
    assert(image_hash() != complete);
    neko_avatar3d_render(0, 0, W, H, 0, H, "face-ready", 1000, bg, put_pixel);
    if (argc >= 2) {
        uint32_t frame_ms = argc >= 3 ? (uint32_t)strtoul(argv[2], NULL, 10) : 1000U;
        neko_avatar3d_render(0, 0, W, H, 0, H, "face-ready", frame_ms, bg, put_pixel);
        FILE *file = fopen(argv[1], "wb");
        assert(file != NULL);
        fprintf(file, "P6\n%d %d\n255\n", W, H);
        for (size_t i = 0; i < W * H; ++i) {
            uint16_t c = image[i];
            fputc((c >> 8) & 0xf8, file);
            fputc((c >> 3) & 0xfc, file);
            fputc((c << 3) & 0xf8, file);
        }
        fclose(file);
    }
    puts("avatar 3D: geometria, cor, estados e quadros OK");
    return 0;
}
