# Fontes técnicas consultadas em 2026-09-10

- [faster-whisper](https://github.com/SYSTRAN/faster-whisper): gerador lazy de segmentos,
  configuração de dispositivo/compute_type, idioma e carregamento local; MIT. Já fazia
  parte do desenho original. Extra real fixa versão1.2.1; modelo real ainda não executado.
- [sounddevice0.5.3](https://python-sounddevice.readthedocs.io/en/0.5.3/api/raw-streams.html):
  RawInputStream PCM e ciclo start/stop/close; MIT. A instalação pip no macOS inclui
  PortAudio ([instalação oficial](https://python-sounddevice.readthedocs.io/en/0.5.3/installation.html)).
- [pyserial3.5](https://pyserial.readthedocs.io/en/latest/pyserial_api.html): leitura/escrita
  com timeout e exclusividade; BSD-3-Clause. `flush()` pode aguardar drenagem; o bridge
  usa escrita limitada, sem flush bloqueante, ver regressão PTY.
- [webrtcvad-wheels2.0.14](https://github.com/daanzu/py-webrtcvad-wheels): detector WebRTC
  local, PCM16 mono, frames10/20/30ms. MIT no wrapper, preservar avisos WebRTC distribuídos.
- [SQLAlchemy2 DDL](https://docs.sqlalchemy.org/en/20/core/ddl.html): create_all verifica
  tabelas, não substitui migração de colunas. Migração aditiva e backup explícitos.

Extrator lexical é implementação própria sem nova biblioteca, modelo ou API. Nenhuma
contratação ou inferência remota foi executada. Benchmarks e calibração não são inferidos
destas fontes. Dependências transitivas seguem seus próprios avisos de licença.
