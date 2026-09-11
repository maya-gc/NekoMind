# Hardware anunciado — Teknimas ILI9341 2,4"

O módulo comprado foi anunciado como LCD TFT touch Teknimas de 2,4", resolução
240x320, interface SPI e controlador gráfico ILI9341. A documentação do projeto pode
usar esses dados como alvo de layout e planejamento de driver gráfico.

Essas informações não autorizam presumir controlador de toque, pinagem, tensão lógica,
orientação final, revisão da placa, compatibilidade com um ESP32 específico, target de
flash, PSRAM ou mapeamento de interrupção. A integração física só deve avançar depois
de inspecionar a unidade real e a documentação do fornecedor.

O firmware e a UI tratam duas orientações lógicas:

| Orientação | Uso esperado | Regra de layout |
|---|---|---|
| 240x320 | portrait provável | rosto felino central dominante, mensagem curta e ação principal no rodapé |
| 320x240 | landscape possível | rosto à esquerda, texto e ação à direita, sem tabelas |

O rosto do gatinho precisa permanecer visível em pronto, diagnóstico, gravando,
pausado, processando, resultado e erro. O layout de host em `neko_layout.*` calcula
alvos de toque mínimos, cartões e posição do rosto, mas não comprova display físico,
touch real ou legibilidade no painel comprado.

Gate humano pendente: escolher placa ESP32, confirmar tensão/pinos, controlador de
touch e orientação física antes de ligar hardware. Não há validação física nesta entrega.
