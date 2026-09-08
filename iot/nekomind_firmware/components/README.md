# components/

Diretório para componentes ESP-IDF extras do projeto NekoMind —
por exemplo, o driver do LCD quando o modelo for escolhido
(ex.: `esp_lcd`, LovyanGFX, lvgl port) ou libs de base64 para o
payload de áudio.

Cada componente deve ter seu próprio `CMakeLists.txt`:

```cmake
idf_component_register(SRCS "meu_driver.c"
                       INCLUDE_DIRS "include")
```

O ESP-IDF detecta automaticamente subdiretórios com `CMakeLists.txt`
durante o build.
