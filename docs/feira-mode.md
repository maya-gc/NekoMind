# Modo feira

O modo feira é uma experiência local de mesa. Um visitante toca no display, explica
um assunto para o microfone do Mac, vê uma resposta curta e sai sem deixar dados
visíveis para a próxima pessoa.

O fluxo aceito é:

1. atração com rosto felino dominante e chamada curta;
2. autoteste com backend, captura, serial/dispositivo e providers;
3. captura iniciada pelo touch e confirmada pelo Mac antes de mostrar `recording`;
4. pausa, retomada, finalização e cancelamento por comandos idempotentes;
5. jornada real de captura, transcrição, tópicos e resultado;
6. dois cartões no gatinho: confirmação de processamento e até cinco termos agrupados;
7. painel público do Mac com jornada, fala detectada, duração, contagem de palavras,
   etapas concluídas e origem local; sem transcrição completa nem nota pedagógica;
8. reset confirmado para limpar touch, público e presenter.

Essa apresentação foi desenhada para falas livres de visitantes: ela comprova que a
bancada captou e processou aquela sessão e aponta termos literais da transcrição local.
Os termos são atribuídos ao reconhecimento do NekoMind porque o ASR pode errar. Ela não
tenta construir um resumo coerente de frases aleatórias e não avalia conhecimento.

O modo demo é permitido e precisa aparecer como demo no touch, público, presenter e
cartões. O modo real falha fechado: modelo ausente, provider inválido, áudio inutilizável
ou extração indisponível geram erro explícito, sem fallback silencioso para mock.

Não há temporizador que finja progresso ou sucesso. Inatividade pode agendar reset da
experiência pelo heartbeat autenticado do bridge; a consulta pública permanece leitura.
