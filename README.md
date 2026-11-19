# R.2.D.2 — Robotic Responsive Digital Dual Assistant

Assistente virtual por voz em português, ativado pela palavra **"dedão"**, com
agenda, calculadora, consultas a IA e um corpo físico em Arduino Uno: a cabeça
gira para **seguir quem está na frente** usando uma webcam presa nela.

Projeto **CP4 — 2º semestre**, da disciplina de Programação Orientada a Objetos
em Python.

## Funcionalidades

- **Voz em português:** reconhecimento (Google STT) e fala (gTTS). Só age quando a
  frase começa com "dedão".
- **Agenda, data, hora e calculadora** com números por extenso
  ("cento e vinte e cinco mais um").
- **IA generativa** via Ollama local, com Groq como alternativa opcional.
- **Extras:** clima, dólar, bitcoin, pesquisa no Google, YouTube, captura de tela e
  portal da FIAP.
- **Cabeça que segue rostos:** a webcam do robô detecta o rosto mais próximo e o
  servo gira até deixá-lo no centro da imagem. Roda em segundo plano, enquanto o
  assistente continua ouvindo e respondendo.
- **Arduino Uno:** servo da cabeça, LED de escuta (aceso enquanto ouve) e LED de
  resposta (pisca enquanto fala). No comando "grita", a cabeça balança.
- **Detecção de rostos** em janela, pelo comando "reconhecer face".

Sem o Arduino, o assistente funciona normalmente, só não move a cabeça nem acende
os LEDs. A câmera detecta rostos; identificar *quem* é a pessoa ainda não está
implementado.

## Hardware

| Item | Uso |
|---|---|
| Computador com microfone, alto-falante e internet | Obrigatório |
| Webcam presa em cima da cabeça do robô (testado com Logi C270) | Seguir rostos e "reconhecer face" |
| Arduino Uno + servo SG90/MG90S + 2 LEDs + 2 resistores de 220 Ω | Cabeça e LEDs (opcional) |

A montagem do circuito e o envio do firmware estão no
[manual](docs/manual.md#montagem-do-arduino-servo-e-leds).

## Estrutura do projeto

```text
R2D2/
├── checkpoint_alexa.py          # Aplicação principal e todas as classes
├── Iniciar R2D2.bat             # Inicia o assistente com dois cliques (Windows)
├── requirements.txt             # Dependências Python
├── README.md
├── .gitignore                   # Exclusão de dados locais e credenciais
├── .gitattributes               # Fim de linha de texto e arquivos binários
├── arduino/
│   └── r2d2_servo/
│       └── r2d2_servo.ino       # Firmware R2D2/2: servo, LEDs e ângulo da cabeça
├── assets/
│   └── audio/
│       └── r2d2_grito.mp3       # Som do comando "grita"
├── docs/
│   ├── manual.md                # Instalação, montagem, comandos e diagnóstico
│   └── publicacao.md            # Como enviar o projeto ao GitHub
├── scripts/
│   ├── __init__.py
│   ├── diagnostico_arduino.py   # Testa LEDs, balanço e posições da cabeça
│   ├── diagnostico_voz.py       # Grava o microfone e compara com a transcrição
│   └── rastrear_cabeca.py       # Cabeça segue um rosto em uma janela, sem voz
└── tests/
    └── test_comandos_voz.py     # 57 testes, sem hardware nem rede
```

As pastas `data/` (agenda), `outputs/` (capturas e gravações) e `controle/` (sinal
de parada) são criadas durante o uso e ficam fora do Git, assim como `.venv/` e
`dist/`.

## Instalação

Requisitos: **Python 3.10 ou superior**. Abra um terminal na pasta do projeto.

**Windows — PowerShell:**

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

**Linux / macOS:**

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

Para a IA local, instale o [Ollama](https://ollama.com) e execute
`ollama pull llama3.2:3b`. Se o PyAudio não instalar, veja as dicas no
[manual](docs/manual.md#3-instale-as-dependências).

Com o Arduino, envie `arduino/r2d2_servo/r2d2_servo.ino` ao Uno pela Arduino IDE
uma vez. Sem o firmware atual (`R2D2/2`), a cabeça não segue rostos.

## Como executar

**Windows:** clique duas vezes em **`Iniciar R2D2.bat`**.

**Qualquer sistema:** com o ambiente virtual, execute na raiz do projeto:

```bash
python checkpoint_alexa.py
```

O que acontece ao iniciar:

1. Conecta ao Arduino, detectando a porta sozinho
   (`Arduino confirmado em COM7 (R2D2/2)`).
2. Fala a saudação e abre a webcam do robô: a cabeça começa a seguir quem estiver
   na frente (`Seguindo rostos com a camera do robo`).
3. Calibra o microfone: **fique em silêncio por 1 segundo**.
4. Mostra `Ouvindo...` e acende o LED de escuta. Diga **"dedão"** + o comando.

Comece por **"dedão listar comandos"**. Para encerrar, diga **"dedão sair"**. Evite
`Ctrl+C` na janela do assistente, a menos que queira encerrá-lo.

## Comandos de voz

| Diga | O que faz |
|---|---|
| `dedão que horas são` / `dedão que dia é hoje` | Hora e data |
| `dedão calcular cinquenta mais vinte e cinco` | Calculadora por voz |
| `dedão cadastrar evento` / `ler agenda` / `limpar agenda` | Agenda local |
| `dedão perguntar <assunto>` | Pergunta à IA |
| `dedão previsão do tempo em <cidade>` | Clima |
| `dedão valor do dólar` / `dedão bitcoin` | Cotações |
| `dedão pesquisar <termo>` / `dedão youtube sobre <tema>` | Abre buscas no navegador |
| `dedão tirar screenshot` | Captura da tela em `outputs/` |
| `dedão grita` | Som do R2D2 com a cabeça balançando |
| `dedão seguir rosto` / `dedão parar de seguir` | Liga ou desliga a cabeça seguindo rostos |
| `dedão reconhecer face` | Janela da webcam com os rostos detectados |
| `dedão sair` | Encerra, centraliza a cabeça e apaga os LEDs |

A lista completa, com variações, está no [manual](docs/manual.md#comandos-de-voz).

## Configurações

Todas são opcionais e feitas por variáveis de ambiente. Nunca escreva chaves no
código.

| Variável | Para que serve | Padrão |
|---|---|---|
| `ARDUINO_PORT` | Fixa a porta do Arduino (ex.: `COM7`) | detecção automática |
| `R2D2_CAMERA_CABECA` | Índice da webcam do robô | `1` (segunda câmera) |
| `R2D2_CABECA_INVERTER` | `1` inverte o sentido do giro da cabeça | desligado |
| `R2D2_RASTREIO_AUTOMATICO` | `0` não segue rostos ao iniciar | ligado |
| `R2D2_MIC_INDEX` | Índice do microfone | entrada padrão |
| `GROQ_API_KEY` / `GROQ_MODEL` | IA na nuvem quando o Ollama está offline | sem Groq |

## Diagnósticos e testes

Com o ambiente virtual ativo, na raiz do projeto:

```bash
python -m scripts.diagnostico_arduino          # LEDs, balanço e posições da cabeça
python -m scripts.rastrear_cabeca              # cabeça seguindo rostos, com janela
python -m scripts.diagnostico_voz --listar     # microfones disponíveis
python -m unittest discover -s tests -v        # testes automatizados
```

Feche o assistente e o Monitor Serial da Arduino IDE antes dos diagnósticos do
Arduino.

Os 57 testes simulam áudio, rede, câmera, Arduino e relógio. Eles rodam com a
biblioteca padrão do Python 3.10+, sem instalar `requirements.txt` e sem hardware.
O funcionamento físico deve ser conferido com os diagnósticos acima.

## Arquitetura

Tudo fica em `checkpoint_alexa.py`, com uma classe por responsabilidade:

| Classe | Responsabilidade |
|---|---|
| `R2D2` | Orquestra: loop de escuta, palavra de ativação e despacho de comandos |
| `SpeechManager` | Ouve (Google STT) e fala (gTTS + pygame); controla os LEDs |
| `AgendaManager` | Agenda em `data/agenda.txt` |
| `Calculator` | Contas faladas, avaliadas com `ast` (sem `eval`) |
| `AIIntegration` | Ollama local, com Groq como reserva |
| `ExtraCommands` | Clima, cotações, buscas, captura de tela e grito |
| `FaceRecognizer` | Detecção de rostos (OpenCV Haar Cascade) |
| `HeadTracker` | Webcam guia o servo para centralizar o rosto; roda em uma thread |
| `ArduinoController` | Serial com o Uno, com confirmação de cada comando |

A webcam fica presa na cabeça e gira com ela. A cada quadro, o `HeadTracker` mede
a distância do rosto ao centro da imagem e corrige o ângulo em até 6°, até o rosto
entrar na faixa central. O grito e o "reconhecer face" pausam o rastreamento e o
retomam no final. Uma trava na porta serial garante que a thread da câmera e o
assistente não misturem comandos ao Arduino.

## Documentação

- [Manual completo: instalação, montagem, comandos e solução de problemas](docs/manual.md)
- [Publicação no GitHub: Git ou upload pelo navegador](docs/publicacao.md)

## Integrantes

| Integrante | RM |
|---|---|
| Gabriel Gomes Catanzaro | RM93445 |
| Lucas Gomes Alcântara | RM98766 |
| Filipe Prado Menezes | RM98765 |
| Henrique Canali Cuzato | RM551326 |
| Cassio Eid Kobayashi Yonetsuka | RM99678 |
| Pedro Henrique Salvitti Habiro | RM88166 |
