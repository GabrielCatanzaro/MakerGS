# Manual do R.2.D.2

[Voltar ao projeto e à lista de integrantes](../README.md)

> Assistente virtual por voz em português, com agenda, calculadora, IA generativa,
> comandos extras e um **Arduino Uno** que move um servo e acende LEDs de estado.
> Uma webcam sobre a cabeça guia o servo para manter quem está na frente centralizado.
> Projeto CP4 — 2º Semestre | Programação Orientada a Objetos em Python

## Sumário

- [Sobre o projeto](#sobre-o-projeto)
- [O que vem na pasta](#o-que-vem-na-pasta)
- [Requisitos](#requisitos)
- [Instalação passo a passo](#instalação-passo-a-passo)
- [Montagem do Arduino (servo e LEDs)](#montagem-do-arduino-servo-e-leds)
- [Webcam da cabeça (rastreamento)](#webcam-da-cabeça-rastreamento)
- [Como executar](#como-executar)
- [Comandos de voz](#comandos-de-voz)
- [Configurações opcionais](#configurações-opcionais)
- [Problemas comuns](#problemas-comuns)
- [Arquitetura OOP](#arquitetura-oop)
- [Status do projeto](#status-do-projeto)

---

## Sobre o projeto

O R.2.D.2 escuta o microfone, entende comandos em português e responde por voz.
Ele **só age quando ouve a palavra de ativação "dedão"** no começo do comando.
Sem ela, apenas imprime no console o que entendeu.
"Então" e "dedo" não são palavras de ativação. Acentos, maiúsculas e pontuação
após o nome são aceitos, como em `"Dedão, que horas são?"`.

O Arduino é **opcional**: sem ele, o assistente funciona normalmente, só não move o
servo nem acende os LEDs. Com ele e a webcam presa na cabeça, o R2 gira a cabeça
para seguir quem está na frente enquanto conversa.

## O que vem na pasta

Veja a [estrutura completa no README](../README.md#estrutura-do-projeto).
O código principal permanece em `checkpoint_alexa.py`; os diagnósticos ficam em
`scripts/`, o som em `assets/audio/` e o firmware em `arduino/r2d2_servo/`.

Para iniciar no Windows, use o `Iniciar R2D2.bat`, na raiz do projeto.

A agenda é criada automaticamente em `data/agenda.txt`. Capturas de tela e
gravações de diagnóstico ficam em `outputs/`, e o sinal de parada do
`Iniciar R2D2.bat` fica em `controle/`. Essas pastas são locais e não entram no
repositório.

## Requisitos

| Item | Obrigatório? | Observação |
|---|---|---|
| Python 3.10 ou superior | Sim | Marque "Add Python to PATH" ao instalar no Windows |
| Microfone e caixa de som | Sim | |
| Internet | Sim | Voz (Google STT e gTTS), clima, dólar e bitcoin |
| [Ollama](https://ollama.com) com `llama3.2:3b` | Para a IA | Roda local, ~2 GB. Se faltar, o Groq (opcional) assume |
| Webcam presa sobre a cabeça (testado com Logi C270) | Para seguir rostos e o comando de face | O rastreamento exige o Arduino |
| Arduino Uno + servo + 2 LEDs + 2 resistores 220 Ω | Opcional | Ver [montagem](#montagem-do-arduino-servo-e-leds) |
| [Arduino IDE](https://www.arduino.cc/en/software) | Só se usar o Arduino | Para enviar o sketch ao Uno |

## Instalação passo a passo

### 1. Baixe e extraia o projeto

Extraia o ZIP e abra um terminal **dentro da pasta `R2D2`**.

### 2. Crie e ative o ambiente virtual

**Windows (PowerShell):**

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

> Se aparecer erro de "execução de scripts desabilitada", rode uma vez:
> `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` e tente de novo.

**Mac / Linux:**

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Instale as dependências

```bash
pip install -r requirements.txt
```

> **PyAudio com erro?**
> - **Windows:** tente `pip install pipwin` e depois `pipwin install pyaudio`.
> - **Linux:** `sudo apt install portaudio19-dev python3-dev` e rode o `pip install` de novo.
> - **Mac:** `brew install portaudio` e rode o `pip install` de novo.

### 4. Instale o Ollama e baixe o modelo

1. Baixe e instale em <https://ollama.com>
2. Em um terminal:

```bash
ollama pull llama3.2:3b
```

O Ollama normalmente já fica rodando em segundo plano após instalar. Se não estiver,
rode `ollama serve` em outro terminal.

### 5. (Opcional) Configure o Arduino

Siga a seção abaixo. Pode ser feito depois: o assistente funciona sem ele.

## Montagem do Arduino (servo e LEDs)

### Ligações

```
Arduino Uno
 ├─ pino 9 ────────────── sinal do servo   (fio laranja/amarelo)
 ├─ 5V ────────────────── VCC do servo     (fio vermelho)
 ├─ GND ───────────────── GND do servo     (fio marrom/preto)
 ├─ pino 7 ──[220 Ω]──►|── GND             LED VERDE (escutando)
 └─ pino 8 ──[220 Ω]──►|── GND             LED VERMELHO (respondendo)
```

Em cada LED, a **perna longa (ânodo, +)** recebe o resistor vindo do pino e a
**perna curta (cátodo, −)** vai ao GND.

> Servo pequeno (SG90, MG90S) funciona com o 5 V do USB. Servo maior ou com carga:
> use fonte externa de 5–6 V e **ligue o GND dela ao GND do Arduino**.

### O que cada saída faz

| Saída | Comportamento |
|---|---|
| LED de escuta, verde no esquema (pino 7) | Aceso enquanto o R2 está **escutando**. Pode ser de outra cor, como azul |
| LED vermelho (pino 8) | **Pisca** enquanto o R2 está **respondendo** (fala ou grito) |
| Servo (pino 9) | **Balança** durante o comando "grita" e **gira para seguir um rosto** no rastreamento |

No `grita`, a cabeça percorre de 45° a 135° em passos de 1° a cada 30 ms
(cerca de 33° por segundo) e volta ao centro ao terminar.
Com o Arduino conectado, a animação e o LED vermelho duram pelo
menos quatro segundos, mesmo que o áudio termine antes.
Se a conexão com o Arduino estiver indisponível ou falhar durante o grito,
o assistente avisa por voz depois do som que não conseguiu confirmar o comando
da cabeça. As confirmações da serial comprovam o recebimento pelo firmware;
o movimento físico ainda precisa ser observado.

### Enviando o sketch ao Uno

1. Abra `arduino/r2d2_servo/r2d2_servo.ino` na Arduino IDE.
2. Em **Ferramentas → Placa**, escolha **Arduino Uno**.
3. Em **Ferramentas → Porta**, escolha a porta do Arduino (ex.: `COM7`). Em clones,
   ela pode aparecer como "Serial Port (USB)". As portas Bluetooth não servem.
4. Clique em **Carregar** (seta →).
5. Ao terminar, os dois LEDs acendem por meio segundo. Isso confirma a fiação.
6. **Feche o Monitor Serial da IDE** antes de rodar o Python: só um programa usa a porta por vez.

### Protocolo serial (para quem quiser testar à mão)

9600 baud, um caractere por comando (o `p` leva mais três dígitos):

| Comando | Ação |
|---|---|
| `a` / `b` | servo balança / para |
| `c` / `d` | LED verde acende / apaga |
| `e` / `f` | LED vermelho pisca / apaga |
| `p` + 3 dígitos | Leva a cabeça ao ângulo, em passos suaves (ex.: `p090`); responde `OK p090` |
| `?` | Identifica o firmware: responde `R2D2/2` |
| `s` | Consulta os estados: `STATE <servo> <verde> <vermelho>`, cada um `0` ou `1` |

Cada comando de `a` a `f` devolve `OK <comando>`. O Python verifica a
identificação e essas confirmações. O `p` limita o ângulo a 45°–135°, interrompe o
balanço e responde `ERR p` se receber algo que não seja dígito. O Python também
aceita o firmware antigo (`R2D2/1`), mas sem rastreamento. É necessário carregar a versão atual do
sketch no Uno; abrir a porta serial, sozinho, não confirma a comunicação.

Para testar só a placa, sem depender do microfone, feche o assistente e o Monitor
Serial e rode `python -m scripts.diagnostico_arduino` (para fixar a porta, use
`--porta COM7`).
O teste aciona separadamente o LED verde, o LED vermelho e a cabeça, consulta
os estados antes e depois e desliga tudo ao terminar. Com o firmware `R2D2/2`,
também leva a cabeça a 60°, 120° e ao centro, indicando para que lado ela deve olhar. As respostas confirmam o
estado do programa no Uno; confirme as luzes e o movimento olhando o robô.

## Webcam da cabeça (rastreamento)

Com o Arduino (firmware `R2D2/2`) e a webcam conectados, **a cabeça começa a seguir
quem estiver na frente assim que o assistente inicia**. O rastreamento roda em
segundo plano, sem janela: o R2 continua ouvindo, respondendo e piscando os LEDs
normalmente. Diga `dedão parar de seguir` para desligar e `dedão seguir rosto` para
ligar de novo. Durante o `grita` e o `reconhecer face`, o rastreamento faz uma pausa
(libera a câmera e a cabeça) e retoma sozinho depois, voltando ao ângulo em que estava.

A webcam fica **presa em cima da cabeça e gira junto com ela**, apontada para a
frente. O assistente procura o maior rosto da imagem (normalmente a pessoa mais
próxima) e gira a cabeça na direção dele até que fique na faixa central. Isso
funciona como uma malha fechada: a cada correção, a própria imagem mostra se
ainda falta girar.

| Parâmetro (`HeadTracker`) | Valor | Efeito |
|---|---|---|
| `ZONA_MORTA` | 0,10 | Faixa central (10% da meia-largura) em que a cabeça não se move |
| `GANHO_GRAUS` | 12 | Graus de correção quando o rosto está na borda da imagem |
| `PASSO_MAX` | 6 | Maior correção por ciclo, em graus |
| `INTERVALO_S` | 0,15 | Espera mínima entre correções, para a imagem acompanhar o servo |

Se a cabeça tremer em volta da pessoa, aumente `ZONA_MORTA` ou reduza
`GANHO_GRAUS`. Se estiver lenta, faça o contrário. O firmware anda até cada ângulo
pedido a cerca de 66° por segundo e respeita os limites de 45° a 135°. Se a cabeça
física aguentar mais, altere `POS_MIN`/`POS_MAX` no sketch **e** na classe
`ArduinoController`.

**Primeiro teste, sem voz:**

1. Rode `python -m scripts.diagnostico_arduino` e veja para que lado a
   cabeça olha em 60°. Deve ser para a **direita do robô**; se for para a esquerda,
   use `R2D2_CABECA_INVERTER=1` (ou `--inverter` no passo seguinte).
2. Rode `python -m scripts.rastrear_cabeca`. A câmera padrão é a segunda do
   computador (índice 1), a webcam do robô. Fique na frente do robô e ande para os lados.
3. A janela mostra o rosto, a faixa central e o ângulo atual. **Q** encerra, e a
   cabeça volta ao centro.

A detecção de rostos (rastreamento e `dedão reconhecer face`) usa a **segunda câmera**
do computador, índice 1, porque a primeira costuma ser a do notebook. Se a imagem
aberta não for a do robô, teste `--camera 0`, `--camera 2`… e fixe o número certo com
`R2D2_CAMERA_CABECA`. No Windows, as câmeras são abertas pelo DirectShow.

## Como executar

**Windows:** clique duas vezes em **`Iniciar R2D2.bat`**, na pasta do projeto. Ele usa
o Python do `.venv`, corrige os acentos do console e abre o assistente.

**Qualquer sistema:** com o ambiente virtual ativo (e o Ollama rodando, para a IA):

```bash
python checkpoint_alexa.py
```

1. **Arduino:** a porta é detectada sozinha. O programa ignora portas Bluetooth, testa
   as portas USB e aceita a que responder `R2D2/…`. Aparece
   `Arduino confirmado em COM7 (R2D2/2)`.
2. **Saudação e câmera:** ele fala *"Sistemas online..."* e a cabeça começa a seguir
   quem estiver na frente (`Seguindo rostos com a camera do robo`).
3. **Calibração:** fique em silêncio durante *"Calibrando microfone"*.
4. **Comandos:** com `Ouvindo...` e o LED de escuta aceso, diga **"dedão" + o comando**.
5. **Encerrar:** diga `"dedão sair"`. A cabeça volta ao centro e os LEDs apagam.

`Ctrl+C` na janela do assistente também encerra, então evite usá-lo para copiar
texto enquanto ela estiver em foco. Pelo `Iniciar R2D2.bat`, criar o arquivo
`controle/parar` na pasta do projeto encerra o assistente do mesmo jeito que o
`dedão sair`. Isso é útil para parar sem mexer na janela.

### Exemplo

```
Você:      "dedão que horas são"
R.2.D.2:   "São 18 horas e 30 minutos."

Você:      "dedão calcular cinquenta mais vinte e cinco"
R.2.D.2:   "O resultado é 75"

Você:      "bom dia"                      ← sem a palavra de ativação
Console:   [Reconhecido, sem acao]: bom dia
```

## Comandos de voz

Sempre começam com **"dedão"**. Diga `dedão listar comandos` para ouvir a lista.
O pedido vem logo após o nome. Palavras dentro do assunto de uma pesquisa ou
pergunta não acionam outros comandos: `dedão pesquisar como sair do Windows`
faz uma pesquisa e mantém o assistente ligado. Para encerrar, diga `dedão sair`,
`dedão encerrar` ou `dedão tchau`.

### Agenda

| Comando | O que faz |
|---|---|
| `dedão cadastrar evento` | Pergunta o evento e salva em `data/agenda.txt` |
| `dedão ler agenda` | Lê os eventos cadastrados |
| `dedão limpar agenda` | Pede confirmação ("sim") e apaga tudo |

### Data e hora

| Comando | O que faz |
|---|---|
| `dedão que horas são` | Fala a hora atual |
| `dedão que dia é hoje` | Fala a data com o dia da semana |

### Calculadora

Aceita números por extenso (inclusive compostos) ou em algarismos.

| Fale | Resultado |
|---|---|
| `dedão calcular dois mais três` | 5 |
| `dedão calcular cinquenta mais vinte e cinco` | 75 |
| `dedão calcular cento e vinte e cinco mais um` | 126 |
| `dedão quanto é dois vezes oito` | 16 |
| `dedão calcular cem dividido por quatro` | 25 |
| `dedão calcular dez multiplicado por três` | 30 |
| `dedão calcular dois elevado a dez` | 1024 |

Operadores: mais, menos, vezes, multiplicado por, dividido por, elevado a.

### Inteligência artificial

| Comando | O que faz |
|---|---|
| `dedão perguntar <assunto>` | Consulta o Ollama local (ou o Groq, se o Ollama estiver offline) |
| `dedão me fale sobre <tema>` | Mesma função |

### Extras

| Comando | O que faz |
|---|---|
| `dedão previsão do tempo em <cidade>` | Temperatura e condições da cidade |
| `dedão valor do dólar` | Cotação USD/BRL |
| `dedão bitcoin` | Valor do Bitcoin em BRL e USD |
| `dedão tirar screenshot` | Salva uma captura da tela em PNG na pasta `outputs/` |
| `dedão pesquisar <termo>` | Pesquisa no Google |
| `dedão abrir youtube` / `dedão youtube sobre <tema>` | Abre o YouTube ou busca um vídeo |
| `dedão abrir portal` | Abre o portal da FIAP |
| `dedão grita` | Toca o som do R2D2, **balança o servo e pisca o LED vermelho** |
| `dedão reconhecer face` | Abre a webcam do robô e detecta rostos (**Q** fecha a janela) |
| `dedão seguir rosto` / `dedão me acompanhe` / `dedão centralizar` | Liga o rastreamento: a cabeça segue quem está na frente, em segundo plano |
| `dedão parar de seguir` / `dedão não me siga` | Desliga o rastreamento e devolve a cabeça ao centro |
| `dedão sair` | Encerra |

## Configurações opcionais

Todas por variáveis de ambiente. **Nunca escreva chaves dentro do código.**

| Variável | Para que serve | Padrão |
|---|---|---|
| `GROQ_API_KEY` | Chave do Groq, usada se o Ollama estiver offline | vazio (sem backup) |
| `GROQ_MODEL` | Modelo do Groq | `openai/gpt-oss-20b` |
| `ARDUINO_PORT` | Fixa a porta serial do Arduino | detecção automática (portas USB que respondem `R2D2/…`) |
| `R2D2_MIC_INDEX` | Índice do microfone usado pelo Python | entrada padrão do Windows |
| `R2D2_CAMERA_CABECA` | Índice da webcam do robô, usada para detectar rostos e guiar a cabeça | `1` (segunda câmera) |
| `R2D2_CABECA_INVERTER` | `1` inverte o sentido do giro no rastreamento | desligado |
| `R2D2_RASTREIO_AUTOMATICO` | `0` impede que a cabeça comece a seguir rostos ao iniciar | ligado |

**Windows (PowerShell), valendo para a sessão atual:**

```powershell
$env:GROQ_API_KEY = "gsk_sua_chave_aqui"
$env:ARDUINO_PORT = "COM7"
python checkpoint_alexa.py
```

**Mac / Linux:**

```bash
export GROQ_API_KEY="gsk_sua_chave_aqui"
export ARDUINO_PORT="/dev/ttyACM0"
python checkpoint_alexa.py
```

Para criar uma chave do Groq: <https://console.groq.com> (conta gratuita).
Modelos do Groq são descontinuados com frequência. Se o backup parar de funcionar,
confira a lista atual em <https://console.groq.com/docs/deprecations> e ajuste `GROQ_MODEL`.

## Problemas comuns

| Sintoma | Causa provável e solução |
|---|---|
| `Arduino desativado. Confira o cabo USB...` | Nenhuma porta respondeu. Confira o cabo, feche o Monitor Serial da IDE e o outro assistente aberto, e veja a porta na Arduino IDE. Se precisar, fixe com `ARDUINO_PORT` |
| Upload falha com `cannot set com-state` em placa CH340 | Instale e selecione o driver **3.7.2022.1**, seguindo a [orientação oficial do Arduino](https://support.arduino.cc/hc/en-us/articles/13148652511260-avrdude-ser-open-can-t-set-com-state-for-COMn). Confira a versão ativa no Gerenciador de Dispositivos: instalar o pacote pode manter a versão mais recente selecionada |
| `Firmware nao confirmado em COMx` | Confira o cabo e a conexão USB. Verifique se o Uno está executando o `arduino/r2d2_servo/r2d2_servo.ino` atualizado e reinicie o assistente |
| `pyserial nao instalado` | `pip install pyserial` com o ambiente virtual ativo |
| LEDs não acendem ao enviar o sketch | Revise a fiação: perna longa do LED no resistor, perna curta no GND |
| Servo treme ou reinicia o Arduino | Falta corrente: use fonte externa de 5–6 V com GND comum |
| "A inteligência artificial local não está disponível" | Ollama não está rodando: abra o app do Ollama ou rode `ollama serve` |
| Não entende o que eu falo | Fale logo após o LED de escuta acender, perto do microfone e sem ruído. Precisa de internet |
| Não ativa ao chamar | Confira no console se o reconhecimento retornou "dedão" no início. "Então", "dedo" e o nome no meio da frase não ativam o assistente |
| `ModuleNotFoundError` | Ambiente virtual não está ativo, ou faltou o `pip install -r requirements.txt` |
| "O firmware do Arduino está desatualizado" | Envie o `r2d2_servo.ino` atual; o console deve mostrar `R2D2/2` |
| Cabeça foge da pessoa em vez de segui-la | Defina `R2D2_CABECA_INVERTER=1` |
| Cabeça fica balançando em volta da pessoa | Aumente `ZONA_MORTA` ou reduza `GANHO_GRAUS` em `HeadTracker` |
| "Não consegui abrir a câmera" no rastreamento | Ajuste `R2D2_CAMERA_CABECA` e feche outros programas que usam a webcam (app Câmera, Teams, Discord) |
| A cabeça não segue ao iniciar | Veja no console se apareceu `Seguindo rostos com a camera do robo`. Sem o Arduino `R2D2/2`, o rastreamento não liga |
| Sem som no grito | Confirme que `assets/audio/r2d2_grito.mp3` existe na pasta do projeto |

Os comandos deste manual devem ser executados na raiz do projeto. O assistente
localiza o áudio e grava a agenda e as capturas com base na localização de
`checkpoint_alexa.py`, mesmo quando iniciado a partir de outra pasta.

### Diagnóstico da voz

Na primeira escuta, mantenha silêncio durante o segundo de calibração e fale
depois de `Ouvindo...`. A calibração acontece uma vez por execução; o assistente
tolera pausas de até aproximadamente 1,2 segundo durante o comando.

Para separar problemas da gravação de erros de transcrição, execute
`python -m scripts.diagnostico_voz`. Pressione Enter quando estiver pronto e diga
"dedão listar comandos". O teste grava seis segundos sem cortar nas pausas,
salva `outputs/diagnostico_voz.wav` e mostra o texto reconhecido pelo Google.
Ouça o arquivo: se o áudio estiver baixo, cortado ou distorcido, investigue a
captação; se estiver claro e a transcrição errada, investigue o reconhecimento.

Liste dispositivos com `python -m scripts.diagnostico_voz --listar` e teste outro com
`python -m scripts.diagnostico_voz --microfone 1`. Para usar esse mesmo índice no
assistente, defina `$env:R2D2_MIC_INDEX = "1"` no PowerShell antes de iniciar.
Feche a outra instância do assistente antes do teste.

## Arquitetura OOP

```
checkpoint_alexa.py
│
├── SpeechManager        # Escuta (Google STT) e fala (gTTS + pygame); controla os LEDs de estado
├── AgendaManager        # Cadastro, leitura e limpeza em data/agenda.txt
├── Calculator           # Interpreta contas ditas por voz; avaliação segura (sem eval)
├── FaceRecognizer       # Detecção facial (OpenCV + Haar Cascade)
├── AIIntegration        # IA via Ollama, com fallback para o Groq
├── ArduinoController    # Serial com o Arduino: servo + LEDs; detecta a porta e trava o acesso
├── HeadTracker          # Webcam do robô guia o servo; roda em segundo plano (thread)
├── ExtraCommands        # Clima, dólar, bitcoin, screenshot, buscas e o "grita"
└── R2D2                 # Orquestradora: loop de escuta e despacho de comandos
```

```
R2D2
 ├── arduino  → ArduinoController
 ├── speech   → SpeechManager (usa arduino para os LEDs)
 ├── agenda   → AgendaManager
 ├── calc     → Calculator
 ├── face     → FaceRecognizer
 ├── cabeca   → HeadTracker (usa arduino e o detector do face)
 ├── ai       → AIIntegration
 └── extras   → ExtraCommands (usa arduino para o servo e o LED no grito)
```

## Status do projeto

- [x] Palavra de ativação antes de qualquer comando
- [x] Agenda: cadastrar, ler e limpar (`data/agenda.txt`)
- [x] Hora e data
- [x] Calculadora por voz, com números compostos
- [x] IA generativa (Ollama local + Groq como backup)
- [x] Extras: clima, dólar, bitcoin, screenshot, Google, YouTube, portal FIAP, grito
- [x] Integração com Arduino: servo no grito e LEDs de estado
- [x] Webcam do robô centralizando a pessoa na horizontal, em segundo plano e junto com a voz
- [x] Programação orientada a objetos, com comentários e docstrings
- [ ] **Reconhecimento facial**: hoje só **detecta** rostos. Identificar *quem* é a pessoa
  (modelo LBPH treinado + "desconhecido") ainda será implementado
