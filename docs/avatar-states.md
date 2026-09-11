# Estados do gatinho

O rosto felino é o elemento de assinatura do NekoMind. Ele deve aparecer nas telas
centrais e carregar estado operacional sem depender só de cor.

| Estado | Expressão/uso | Evidência exigida |
|---|---|---|
| pronto | olhos atentos, ação Começar | backend/bridge prontos ou demo identificado |
| verificando | checks reais por componente | autoteste executado, sem liberar captura falsa |
| ouvindo | bigodes/indicador reagem ao nível compacto | captura confirmada no Mac |
| voz baixa | alerta curto e recuperável | métrica `voice.quality=low` durante gravação |
| clipping | alerta alto/âmbar ou vermelho | `voice.clipping=true` |
| pausado | expressão calma, ação Retomar | captura pausada confirmada |
| processando | etapas reais da jornada | eventos persistidos em `journey_json` |
| sucesso | expressão satisfeita | resultado válido da sessão atual |
| erro | código curto e ação segura | erro persistido ou snapshot reconciliado |
| recuperação | bifurcação Retomar/Descartar | sessão interrompida, sem reabrir microfone |

Animações antigas devem ser canceladas quando o estado muda. `prefers-reduced-motion`
usa fallback estático. O layout 240x320 e 320x240 não deve reduzir botões abaixo de
44px nem ocultar o rosto.
