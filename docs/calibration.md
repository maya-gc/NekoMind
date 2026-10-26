# Calibração do microfone

A calibração é curta, local e explicitamente iniciada. Ela não mantém escuta contínua
e não autoriza abrir o microfone após interrupção sem novo comando.

O autoteste deve indicar backend, microfone/permissão quando disponível, captura,
serial/dispositivo e provider exigido pelo modo. Em demo, componentes reais
desnecessários podem ser `skipped`, desde que isso apareça na interface.

Critérios de orientação:

- ausência de fala: pedir conferir microfone e falar de novo;
- nível baixo persistente: aproximar ou falar mais alto;
- clipping: afastar ou reduzir ganho;
- ruído excessivo: mudar ambiente ou dispositivo.

O resultado de calibração fica associado ao dispositivo informado pelo Mac quando
disponível. Troca de microfone invalida a confiança operacional e exige repetir o teste.
Áudio sintético cobre testes automatizados; validação física exige consentimento antes
de gravar pessoa real e não deve versionar áudio/transcrição.
