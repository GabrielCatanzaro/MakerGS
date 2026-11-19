"""
============================================================
  CP4 - Assistente Virtual R.2.D.2
  Robotic Responsive Digital Dual Assistant
  Checkpoint 4 - 2 Semestre
  Programacao Orientada a Objetos em Python
============================================================

Comandos disponiveis (fale "dedao" para ativar):
  - "dedao cadastrar evento na agenda"
  - "dedao ler agenda"
  - "dedao limpar agenda"
  - "dedao que horas sao"
  - "dedao que dia e hoje"
  - "dedao calcular <expressao>"
  - "dedao reconhecer face" / "dedao quem sou eu"
  - "dedao seguir rosto" / "dedao me acompanhe" -> camera do robo guia a cabeca
  - "dedao parar de seguir"
  - "dedao perguntar <pergunta>"   -> IA via Ollama (llama3.2:3b)
  - "dedao previsao do tempo"
  - "dedao valor do dolar"
  - "dedao bitcoin"
  - "dedao tirar screenshot"
  - "dedao pesquisar <termo>"
  - "dedao abrir youtube"
  - "dedao grita"                  -> som do R2D2 com a cabeca balancando
  - "dedao listar comandos"
  - "dedao sair"

Ao iniciar, a cabeca passa a seguir quem estiver na frente (webcam do robo +
Arduino com firmware R2D2/2). Detalhes em README.md e docs/manual.md.
============================================================
"""

import os
import io
import contextlib
import threading
import _thread
import re
import ast
import time
import operator
import unicodedata
import logging
import datetime
import webbrowser
from pathlib import Path
import requests
import speech_recognition as sr
import cv2
from gtts import gTTS
from pygame import mixer


# Caminhos relativos ao projeto, independentemente do diretorio do terminal.
PASTA_PROJETO = Path(__file__).resolve().parent
PASTA_DADOS = PASTA_PROJETO / "data"
PASTA_SAIDAS = PASTA_PROJETO / "outputs"
AUDIO_GRITO = PASTA_PROJETO / "assets" / "audio" / "r2d2_grito.mp3"

# Suprime logs de retry/debug do gTTS no console
logging.getLogger("gtts").setLevel(logging.ERROR)


# Webcam usada para detectar rostos: a segunda camera do computador (indice 1),
# que e a Logi C270 presa no robo. Pode ser trocada por R2D2_CAMERA_CABECA.
CAMERA_ROBO_PADRAO = 1


def indice_camera_robo() -> int:
    """Indice da webcam do robo: R2D2_CAMERA_CABECA ou CAMERA_ROBO_PADRAO."""
    valor = os.getenv("R2D2_CAMERA_CABECA", "").strip()
    return int(valor) if valor else CAMERA_ROBO_PADRAO


def abrir_camera(indice: int):
    """
    Abre uma webcam pelo indice. No Windows usa o DirectShow, que segue a
    mesma ordem de cameras do Windows e abre a C270 mais rapido.
    """
    if os.name == "nt":
        return cv2.VideoCapture(indice, cv2.CAP_DSHOW)
    return cv2.VideoCapture(indice)


def remover_acentos(texto: str) -> str:
    """Remove acentos de um texto (ex.: 'três' -> 'tres')."""
    texto = unicodedata.normalize("NFD", texto)
    return "".join(c for c in texto if unicodedata.category(c) != "Mn")


# ============================================================
#  CLASSE 1 - SpeechManager
#  Gerencia reconhecimento e sintese de voz
# ============================================================
class SpeechManager:
    """
    Responsavel por ouvir o usuario (microfone -> texto)
    e falar para o usuario (texto -> voz).

    Sintese de voz: gTTS (Google Text-to-Speech) + pygame mixer.
    Reconhecimento: SpeechRecognition + Google STT.
    """

    VELOCIDADE_WPM = 175

    def __init__(self, idioma: str = "pt-BR", arduino: "ArduinoController" = None):
        """
        Args:
            idioma:  idioma do reconhecimento de voz
            arduino: ArduinoController (opcional) para acender os LEDs de
                     estado: verde = escutando, vermelho = respondendo
        """
        self.idioma     = idioma
        self.arduino    = arduino
        self.recognizer = sr.Recognizer()
        self.recognizer.pause_threshold = 1.2
        self.recognizer.non_speaking_duration = 0.6
        self.recognizer.operation_timeout = 10
        # A calibracao inicial define o limiar. Nao o aumente durante a fala,
        # pois trechos mais baixos podem acabar tratados como silencio.
        self.recognizer.dynamic_energy_threshold = False
        self._microfone_calibrado = False
        indice = os.getenv("R2D2_MIC_INDEX", "").strip()
        self.microfone_index = int(indice) if indice else None

        # Mixer para reproducao de audio (fala + som R2D2)
        if not mixer.get_init():
            mixer.pre_init(frequency=24000, size=-16, channels=1, buffer=512)
            mixer.init()

        print("[R.2.D.2]: Sistema de audio iniciado (gTTS + pygame).")
        print(f"[R.2.D.2]: Microfone: {self.microfone_index if self.microfone_index is not None else 'padrao do Windows'}.")

    def _led_escuta(self, ligado: bool):
        """Acende/apaga o LED verde (escutando), se houver Arduino."""
        if self.arduino:
            self.arduino.escutando(ligado)

    def _led_resposta(self, ligado: bool):
        """Liga/desliga o pisca do LED vermelho (respondendo), se houver Arduino."""
        if self.arduino:
            self.arduino.respondendo(ligado)

    def falar(self, texto: str):
        """
        Fala o texto e mantem o LED vermelho piscando enquanto responde
        (da geracao da voz ate o fim da reproducao). O LED e sempre
        apagado no final, mesmo se ocorrer algum erro.
        """
        self._led_resposta(True)
        try:
            self._falar_audio(texto)
        finally:
            self._led_resposta(False)

    def _falar_audio(self, texto: str):
        """
        Converte texto em voz com gTTS e toca via pygame.
        Gera o MP3 em memoria (sem arquivo em disco), toca e aguarda
        o fim antes de retornar — garante que o microfone so abre depois.
        """
        print(f"\n[R.2.D.2]: {texto}")
        try:
            tts = gTTS(text=texto, lang="pt", slow=False, timeout=(3, 10))
            buf = io.BytesIO()
            tts.write_to_fp(buf)
            buf.seek(0)

            mixer.music.stop()
            mixer.music.load(buf)
            mixer.music.set_volume(1.0)
            mixer.music.play()

            while mixer.music.get_busy():
                time.sleep(0.05)

            mixer.music.unload()
            time.sleep(0.3)
        except Exception as erro:
            print(f"[R.2.D.2]: Erro de audio: {erro}")

    # Variacoes do nome "r2" que o STT costuma devolver (ja sem acentos).
    # Sao aplicadas com limite de palavra (\b) e NUNCA incluem sequencias
    # puramente numericas (ex.: "32", "112"), para nao corromper calculos.
    VARIACOES_R2 = [
        "erre dois d dois", "erre 2 d 2", "r dois d dois", "r dois d 2",
        "r 2 d dois", "r 2 d 2", "are too d 2", "are 2 d 2", "our 2 d 2",
        "s 2 d 2", "r2d 2", "r 2d2", "r 2d 2", "r2 d2", "r2 z2", "r2 e2",
        "r2 b2", "r2z2", "r2b2", "r2e2", "s2 d2", "2 d 2", "2 d2", "r2d2",
        "erre2", "erre dois", "s2",
    ]

    def _normalizar_texto(self, texto: str) -> str:
        """
        Normaliza o texto reconhecido pelo Google STT:
        - Converte para minusculas
        - Remove acentos (para comparacao robusta de comandos)
        - Padroniza variacoes do nome 'r2'
        - Preserva palavras como 'entao' e 'dedo', que nao sao ativadores

        Returns:
            Texto normalizado em minusculas sem acentos
        """
        texto = remover_acentos(texto.lower().strip())

        # Variacoes do mais longo para o mais curto (evita substituicao parcial)
        for variacao in sorted(self.VARIACOES_R2, key=len, reverse=True):
            texto = re.sub(rf"\b{re.escape(variacao)}\b", "r2", texto)

        return texto

    def ouvir(self, timeout: int = 8, duracao: int = 10) -> str:
        """
        Captura audio do microfone e retorna o texto reconhecido.

        Args:
            timeout:  segundos esperando o usuario comecar a falar (padrao 8)
            duracao:  duracao maxima da fala em segundos (padrao 10)

        Returns:
            Texto reconhecido ou string vazia
        """
        audio = None

        # Passo 1: captura o audio e fecha o microfone imediatamente
        try:
            with sr.Microphone(device_index=self.microfone_index) as mic:
                if not self._microfone_calibrado:
                    print("[R.2.D.2]: Calibrando microfone: mantenha silencio por 1 segundo.")
                    self.recognizer.adjust_for_ambient_noise(mic, duration=1)
                    self._microfone_calibrado = True
                    print(f"[R.2.D.2]: Limiar de voz: {self.recognizer.energy_threshold:.0f}.")
                print("[R.2.D.2]: Ouvindo...")
                self._led_escuta(True)   # LED verde: escutando
                try:
                    audio = self.recognizer.listen(mic, timeout=timeout, phrase_time_limit=duracao)
                finally:
                    self._led_escuta(False)
            # Microfone fechado aqui — driver de audio liberado para pygame

        except sr.WaitTimeoutError:
            print("[R.2.D.2]: Tempo esgotado.")
            return ""
        except Exception as erro:
            print(f"[R.2.D.2]: Erro ao capturar audio: {erro}")
            return ""

        # Passo 2: envia para o Google STT (microfone ja fechado)
        try:
            texto = self.recognizer.recognize_google(audio, language=self.idioma)
            texto = self._normalizar_texto(texto)
            print(f"[Voce disse]: {texto}")
            return texto

        except sr.UnknownValueError:
            print("[R.2.D.2]: Nao entendi o que voce disse.")
            return ""
        except (sr.RequestError, TimeoutError) as erro:
            print(f"[R.2.D.2]: Erro na API de reconhecimento: {erro}")
            return ""

    def ouvir_resposta(self, pergunta: str) -> str:
        """
        Fala uma pergunta e aguarda a resposta do usuario.

        Args:
            pergunta: texto que o R.2.D.2 vai falar antes de ouvir

        Returns:
            Resposta do usuario em texto
        """
        self.falar(pergunta)
        return self.ouvir(timeout=7)


# ============================================================
#  CLASSE 2 - AgendaManager
#  Gerencia eventos: cadastrar, ler e limpar agenda
# ============================================================
class AgendaManager:
    """
    Responsavel por salvar, ler e limpar eventos na agenda.
    Os eventos sao gravados em um arquivo texto (data/agenda.txt).
    """

    def __init__(self, caminho_arquivo: str | Path = PASTA_DADOS / "agenda.txt"):
        """
        Inicializa o gerenciador de agenda.

        Args:
            caminho_arquivo: caminho do arquivo onde os eventos sao salvos
        """
        self.caminho = Path(caminho_arquivo)
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        # Cria o arquivo se nao existir
        if not os.path.exists(self.caminho):
            open(self.caminho, "w", encoding="utf-8").close()

    def cadastrar_evento(self, evento: str) -> str:
        """
        Grava um evento na agenda com data e hora atuais.

        Args:
            evento: descricao do evento a ser cadastrado

        Returns:
            Mensagem de confirmacao
        """
        agora = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
        linha = f"[{agora}] {evento}\n"

        with open(self.caminho, "a", encoding="utf-8") as arquivo:
            arquivo.write(linha)

        return f"Evento cadastrado com sucesso: {evento}"

    def ler_agenda(self) -> str:
        """
        Le todos os eventos salvos na agenda.

        Returns:
            String com todos os eventos ou mensagem de agenda vazia
        """
        with open(self.caminho, "r", encoding="utf-8") as arquivo:
            conteudo = arquivo.read().strip()

        if not conteudo:
            return "Sua agenda está vazia."

        linhas = conteudo.split("\n")
        resultado = f"Você tem {len(linhas)} evento(s) na agenda: "
        for i, linha in enumerate(linhas, 1):
            resultado += f" Evento {i}: {linha}."
        return resultado

    def limpar_agenda(self) -> str:
        """
        Apaga todos os eventos sem excluir o arquivo.

        Returns:
            Mensagem de confirmacao
        """
        with open(self.caminho, "w", encoding="utf-8") as arquivo:
            arquivo.write("")  # Sobrescreve com conteudo vazio

        return "Agenda limpa com sucesso."


# ============================================================
#  CLASSE 3 - Calculator
#  Calcula operacoes matematicas faladas pelo usuario
# ============================================================
class Calculator:
    """
    Interpreta expressoes matematicas ditas por voz
    e retorna o resultado das operacoes basicas.

    Suporta numeros compostos por extenso ("vinte e cinco",
    "cento e dois", "mil e quinhentos"), simbolos (+, -, *, /, x)
    e palavras em portugues (mais, menos, vezes, dividido por...).
    A conta e avaliada por um avaliador seguro (sem eval).
    """

    # Frases de operador (tratadas ANTES das palavras soltas)
    FRASES_OPERADORES = [
        (r"\bmultiplicado\s+por\b", "*"),
        (r"\bdividido\s+por\b", "/"),
        (r"\bdividido\s+entre\b", "/"),
        (r"\belevado\s+(?:a|ao)\b", "**"),
        (r"\bsubtraido\s+de\b", "-"),
        (r"\badicionado\s+(?:a|com)\b", "+"),
        (r"\bsomado\s+(?:a|com)\b", "+"),
    ]

    # Palavras soltas -> operadores
    PALAVRAS_OPERADORES = {
        "mais": "+", "soma": "+", "somar": "+",
        "menos": "-", "subtraido": "-",
        "vezes": "*", "multiplicar": "*",
        "dividir": "/", "sobre": "/", "por": "/",
        "elevado": "**",
    }

    # Numeros por extenso (sem acento) -> valor
    UNIDADES = {
        "zero": 0, "um": 1, "uma": 1, "dois": 2, "duas": 2, "tres": 3,
        "quatro": 4, "cinco": 5, "seis": 6, "sete": 7, "oito": 8, "nove": 9,
        "dez": 10, "onze": 11, "doze": 12, "treze": 13, "quatorze": 14,
        "catorze": 14, "quinze": 15, "dezesseis": 16, "dezessete": 17,
        "dezoito": 18, "dezenove": 19,
    }
    DEZENAS = {
        "vinte": 20, "trinta": 30, "quarenta": 40, "cinquenta": 50,
        "sessenta": 60, "setenta": 70, "oitenta": 80, "noventa": 90,
    }
    CENTENAS = {
        "cem": 100, "cento": 100, "duzentos": 200, "trezentos": 300,
        "quatrocentos": 400, "quinhentos": 500, "seiscentos": 600,
        "setecentos": 700, "oitocentos": 800, "novecentos": 900,
    }
    MULTIPLICADORES = {"mil": 1_000, "milhao": 1_000_000, "milhoes": 1_000_000}

    # Limites de seguranca
    MAX_EXPOENTE = 100
    MAX_TAMANHO_EXPRESSAO = 120

    # Operadores permitidos no avaliador seguro
    _OPS_BINARIOS = {
        ast.Add: operator.add, ast.Sub: operator.sub,
        ast.Mult: operator.mul, ast.Div: operator.truediv,
        ast.Pow: operator.pow,
    }

    # ----------------------------------------------------------
    #  Numeros por extenso -> algarismos
    # ----------------------------------------------------------
    def _valor_palavra(self, palavra: str):
        """Retorna o valor (<1000) de uma palavra numerica, ou None."""
        for tabela in (self.UNIDADES, self.DEZENAS, self.CENTENAS):
            if palavra in tabela:
                return tabela[palavra]
        return None

    @staticmethod
    def _pode_somar(grupo: int, valor: int) -> bool:
        """
        Diz se 'valor' continua o mesmo numero que 'grupo'.
        Ex.: 20 + 5 sim ("vinte e cinco"), 100 + 20 sim, 5 + 3 nao.
        """
        if grupo == 0:
            return True
        if grupo % 100 == 0 and valor < 100:      # centena + resto
            return True
        if grupo % 100 in range(20, 100, 10) and valor < 10:  # dezena + unidade
            return True
        return False

    def _converter_extenso(self, texto: str) -> str:
        """Troca numeros por extenso (inclusive compostos) por algarismos."""
        tokens = texto.split()
        saida = []
        total, grupo, ativo = 0, 0, False

        def fechar():
            nonlocal total, grupo, ativo
            if ativo:
                saida.append(str(total + grupo))
            total, grupo, ativo = 0, 0, False

        i = 0
        while i < len(tokens):
            tok = tokens[i]
            valor = self._valor_palavra(tok)

            if valor is not None:
                if ativo and not self._pode_somar(grupo, valor):
                    fechar()
                grupo += valor
                ativo = True
            elif tok in self.MULTIPLICADORES:
                total += (grupo or 1) * self.MULTIPLICADORES[tok]
                grupo, ativo = 0, True
            elif tok == "e" and ativo and i + 1 < len(tokens) and (
                self._valor_palavra(tokens[i + 1]) is not None
                or tokens[i + 1] in self.MULTIPLICADORES
            ):
                pass  # "e" ligando partes do mesmo numero
            else:
                fechar()
                saida.append(tok)
            i += 1

        fechar()
        return " ".join(saida)

    # ----------------------------------------------------------
    #  Avaliador seguro (substitui eval)
    # ----------------------------------------------------------
    def _avaliar_no(self, no):
        """Avalia recursivamente a AST permitindo apenas + - * / ** e numeros."""
        if isinstance(no, ast.Expression):
            return self._avaliar_no(no.body)
        if isinstance(no, ast.Constant) and isinstance(no.value, (int, float)):
            return no.value
        if isinstance(no, ast.UnaryOp) and isinstance(no.op, (ast.UAdd, ast.USub)):
            valor = self._avaliar_no(no.operand)
            return -valor if isinstance(no.op, ast.USub) else valor
        if isinstance(no, ast.BinOp) and type(no.op) in self._OPS_BINARIOS:
            esquerda = self._avaliar_no(no.left)
            direita = self._avaliar_no(no.right)
            if isinstance(no.op, ast.Pow) and abs(direita) > self.MAX_EXPOENTE:
                raise OverflowError("expoente muito grande")
            return self._OPS_BINARIOS[type(no.op)](esquerda, direita)
        raise ValueError("expressao nao permitida")

    # ----------------------------------------------------------
    #  Interface publica
    # ----------------------------------------------------------
    def calcular(self, expressao: str) -> str:
        """
        Interpreta e calcula uma expressao matematica.

        Args:
            expressao: texto com a expressao (ex: "vinte e cinco mais tres")

        Returns:
            String com o resultado ou mensagem de erro
        """
        expressao = remover_acentos(expressao.lower())

        # Remove palavras de ativacao/comando
        for palavra in ["dedao", "calcular", "quanto e", "quanto vale", "r2"]:
            expressao = re.sub(rf"\b{re.escape(palavra)}\b", " ", expressao)

        # "x" como multiplicacao apenas quando e uma palavra isolada (10 x 2)
        expressao = re.sub(r"\bx\b", " * ", expressao)

        # Numeros no formato brasileiro: 1.000 -> 1000 ; 2,5 -> 2.5
        expressao = re.sub(r"(?<=\d)\.(?=\d{3}(?!\d))", "", expressao)
        expressao = re.sub(r"(?<=\d),(?=\d)", ".", expressao)

        # Frases de operador primeiro ("multiplicado por", "dividido por"...)
        for padrao, simbolo in self.FRASES_OPERADORES:
            expressao = re.sub(padrao, f" {simbolo} ", expressao)

        # Numeros por extenso -> algarismos (antes das palavras soltas)
        expressao = self._converter_extenso(expressao)

        # Palavras soltas de operador -> simbolos
        for palavra, simbolo in self.PALAVRAS_OPERADORES.items():
            expressao = re.sub(rf"\b{palavra}\b", f" {simbolo} ", expressao)

        # Mantem apenas numeros e operadores
        expressao_limpa = re.sub(r"[^\d\+\-\*\/\.\(\)\s]", " ", expressao)
        expressao_limpa = re.sub(r"\s+", " ", expressao_limpa).strip()

        if not expressao_limpa or len(expressao_limpa) > self.MAX_TAMANHO_EXPRESSAO:
            return "Não consegui entender a expressão matemática."

        try:
            arvore = ast.parse(expressao_limpa, mode="eval")
            resultado = self._avaliar_no(arvore)

            if isinstance(resultado, float):
                resultado = round(resultado, 4)
                if resultado.is_integer():
                    resultado = int(resultado)

            # Virgula decimal para a fala em portugues
            return f"O resultado é {str(resultado).replace('.', ',')}"
        except ZeroDivisionError:
            return "Erro: divisão por zero não é permitida."
        except OverflowError:
            return "Esse número é grande demais para eu calcular."
        except Exception:
            return "Não consegui calcular essa expressão."


# ============================================================
#  CLASSE 4 - FaceRecognizer
#  Reconhecimento facial com OpenCV (Haar Cascade)
# ============================================================
class FaceRecognizer:
    """
    Detecta e exibe faces usando a webcam com OpenCV.
    Usa o classificador Haar Cascade pre-treinado do proprio OpenCV.

    STAND BY: por enquanto apenas DETECTA rostos. O reconhecimento de
    quem e a pessoa (modelo LBPH .yml + "desconhecido") sera implementado depois.
    """

    def __init__(self, camera: int | None = None):
        """
        Inicializa o detector de faces com o modelo Haar Cascade.

        Args:
            camera: indice da webcam (padrao: a camera do robo, indice 1)
        """
        self.camera = indice_camera_robo() if camera is None else camera
        caminho_modelo = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        self.detector = cv2.CascadeClassifier(caminho_modelo)

    def reconhecer(self) -> str:
        """
        Abre a webcam e detecta faces em tempo real.
        Pressione 'Q' para fechar a janela.

        Returns:
            Mensagem sobre o resultado do reconhecimento
        """
        cap = abrir_camera(self.camera)  # Webcam do robo

        if not cap.isOpened():
            return "Não consegui acessar a webcam. Verifique se ela está conectada."

        print("[R.2.D.2]: Pressione Q para fechar a c\u00e2mera.")
        faces_detectadas = 0

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            # Converte para escala de cinza (exigido pelo detector Haar)
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

            # Detecta faces no frame
            faces = self.detector.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5)
            faces_detectadas = len(faces)

            # Desenha retangulo e label em cada face detectada
            for (x, y, w, h) in faces:
                cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
                cv2.putText(
                    frame, "Pessoa detectada",
                    (x, y - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2
                )

            # Contador de faces no canto superior esquerdo
            cv2.putText(
                frame, f"Faces: {faces_detectadas}",
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2
            )

            cv2.imshow("R.2.D.2 - Reconhecimento Facial (Q para sair)", frame)

            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

        cap.release()
        cv2.destroyAllWindows()

        if faces_detectadas == 0:
            return "Nenhuma face foi detectada."
        elif faces_detectadas == 1:
            return "Detectei uma pessoa na câmera."
        else:
            return f"Detectei {faces_detectadas} pessoas na câmera."


# ============================================================
#  CLASSE 5 - AIIntegration
#  Integracao com IA generativa via Ollama (local)
# ============================================================
class AIIntegration:
    """
    Integra o R.2.D.2 com modelos de linguagem generativos.
    Usa Ollama local (llama3.2:3b) como principal.
    Usa Groq (nuvem) como fallback se Ollama estiver offline.
    A chave do Groq vem da variavel de ambiente GROQ_API_KEY.
    """

    # Endereco local do Ollama
    OLLAMA_URL = "http://localhost:11434/api/generate"

    # Valor sentinela devolvido quando o Ollama nao esta acessivel.
    # Usado em perguntar() para decidir o fallback (evita comparar textos soltos).
    OLLAMA_OFFLINE = "ollama offline"

    # Modelo do Groq. O antigo "llama3-8b-8192" foi desligado em 08/2025 e o
    # "llama-3.1-8b-instant" tem desligamento em 16/08/2026 (ver
    # console.groq.com/docs/deprecations). Pode ser trocado pela variavel
    # de ambiente GROQ_MODEL sem mexer no codigo.
    GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")

    # Instrucao de sistema para o modelo
    SYSTEM_PROMPT = (
        "Voce e R.2.D.2, uma assistente virtual inteligente e amigavel. "
        "Responda sempre em portugues do Brasil, de forma clara e objetiva. "
        "Seja conciso nas respostas para que possam ser lidas em voz alta."
    )

    def __init__(self, modelo: str = "llama3.2:3b", groq_api_key: str = ""):
        """
        Inicializa a integracao com IA.

        Args:
            modelo: nome do modelo Ollama
            groq_api_key: chave da API Groq (opcional, alternativa na nuvem)
        """
        self.modelo = modelo
        self.groq_api_key = groq_api_key

    def perguntar_ollama(self, pergunta: str) -> str:
        """
        Envia uma pergunta ao modelo local via Ollama.

        Args:
            pergunta: texto da pergunta do usuario

        Returns:
            Resposta do modelo ou mensagem de erro
        """
        prompt_completo = f"{self.SYSTEM_PROMPT}\n\nUsuario: {pergunta}\nR.2.D.2:"

        try:
            resposta = requests.post(
                self.OLLAMA_URL,
                json={
                    "model": self.modelo,
                    "prompt": prompt_completo,
                    "stream": False  # Recebe a resposta completa de uma vez
                },
                timeout=30
            )
            dados = resposta.json()
            return dados.get("response", "Não recebi resposta do modelo.").strip()

        except requests.exceptions.ConnectionError:
            return self.OLLAMA_OFFLINE
        except requests.exceptions.Timeout:
            return "O modelo demorou muito para responder. Tente novamente."
        except Exception as erro:
            return f"Erro ao consultar a IA: {erro}"

    def perguntar_groq(self, pergunta: str) -> str:
        """
        Envia uma pergunta para a API Groq na nuvem (fallback).

        Args:
            pergunta: texto da pergunta do usuario

        Returns:
            Resposta do modelo ou mensagem de erro
        """
        if not self.groq_api_key:
            return "Chave da API Groq nao configurada."

        try:
            from groq import Groq
            cliente = Groq(api_key=self.groq_api_key)
            resposta = cliente.chat.completions.create(
                model=self.GROQ_MODEL,
                messages=[
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {"role": "user",   "content": pergunta}
                ]
            )
            return resposta.choices[0].message.content.strip()
        except Exception as erro:
            return f"Erro ao consultar o Groq: {erro}"

    def perguntar(self, pergunta: str) -> str:
        """
        Tenta Ollama primeiro; se offline, usa Groq como backup.

        Args:
            pergunta: texto da pergunta do usuario

        Returns:
            Resposta da IA
        """
        resposta = self.perguntar_ollama(pergunta)

        # Fallback para Groq se Ollama nao estiver rodando
        if resposta == self.OLLAMA_OFFLINE:
            if self.groq_api_key:
                print("[R.2.D.2]: Ollama offline, usando Groq como backup...")
                resposta = self.perguntar_groq(pergunta)
            else:
                resposta = (
                    "A inteligência artificial local não está disponível. "
                    "Inicie o Ollama com: ollama serve"
                )

        return resposta


# ============================================================
#  CLASSE 5.5 - ArduinoController
#  Controla servo e LEDs de estado (via Arduino Uno) pela porta serial
# ============================================================
class ArduinoController:
    """
    Comunica com o Arduino Uno (sketch r2d2_servo.ino) pela serial.

    Protocolo (1 caractere por comando, 9600 baud):
        b"a" -> comeca a balancar o servo      b"b" -> para o servo
        b"c" -> LED verde aceso (escutando)    b"d" -> LED verde apagado
        b"e" -> LED vermelho piscando          b"f" -> LED vermelho apagado
                (respondendo)
        b"p090" -> cabeca vai a 90 graus (firmware R2D2/2; rastreamento)

    Se o Arduino nao estiver conectado (ou o pyserial nao estiver instalado),
    a classe apenas avisa no console e o R.2.D.2 continua funcionando
    normalmente, so que sem servo e sem LEDs.

    A porta pode ser definida pela variavel de ambiente ARDUINO_PORT
    (ex.: COM7 no Windows, /dev/ttyACM0 no Linux). Se nao for definida,
    testa as portas USB (ignorando Bluetooth) ate uma responder R2D2/...;
    sem nenhuma candidata, tenta COM3.
    """

    BAUDRATE       = 9600
    PORTA_PADRAO   = "COM3"
    # Versoes do firmware aceitas. A 2 acrescenta o comando de posicao ('p'),
    # usado para a webcam guiar a cabeca; a 1 continua funcionando sem ele.
    PROTOCOLOS     = {b"R2D2/1": 1, b"R2D2/2": 2}
    CMD_PING       = b"?"
    CMD_ESTADO     = b"s"
    CMD_SERVO_ON   = b"a"
    CMD_SERVO_OFF  = b"b"
    CMD_VERDE_ON   = b"c"
    CMD_VERDE_OFF  = b"d"
    CMD_VERM_ON    = b"e"
    CMD_VERM_OFF   = b"f"
    ESPERA_RESET_S = 2  # o Uno reinicia ao abrir a serial

    # Limites da cabeca; precisam ser iguais a POS_MIN/POS_MAX do sketch
    POS_CENTRO = 90
    POS_MIN    = 45
    POS_MAX    = 135

    def __init__(self, porta: str = ""):
        """
        Args:
            porta: porta serial (opcional; vazio = ARDUINO_PORT ou autodeteccao)
        """
        self.porta = porta or os.getenv("ARDUINO_PORT", "")
        self.conexao = None
        self.versao = 0
        # A camera (thread de rastreamento) e o assistente usam a mesma serial:
        # a trava garante que cada comando receba a propria confirmacao.
        self._trava = threading.RLock()
        self._conectar()

    @property
    def disponivel(self) -> bool:
        """True se ha uma conexao serial aberta com o Arduino."""
        return self.conexao is not None and self.conexao.is_open

    @property
    def aceita_posicao(self) -> bool:
        """True se o firmware conectado entende o comando de angulo ('p')."""
        return self.disponivel and self.versao >= 2

    # Fabricantes de chips USB-serial usados no Uno e em clones (VID USB)
    VIDS_ARDUINO = {0x2341, 0x2A03, 0x1A86, 0x0403, 0x10C4}

    def _portas_candidatas(self) -> list[str]:
        """
        Lista as portas que podem ser o Uno, das mais provaveis as menos.
        Portas Bluetooth sao ignoradas; se nada for encontrado, usa a padrao.
        """
        try:
            from serial.tools import list_ports
            portas = list(list_ports.comports())
        except Exception:
            return [self.PORTA_PADRAO]

        provaveis, outras = [], []
        for info in portas:
            texto = f"{info.description} {info.manufacturer} {info.hwid}".lower()
            if "bluetooth" in texto or "bthenum" in texto:
                continue
            if info.vid in self.VIDS_ARDUINO or any(
                chave in texto for chave in ("arduino", "ch340", "usb serial", "usb-serial")
            ):
                provaveis.append(info.device)
            elif "usb" in texto:
                outras.append(info.device)
        return provaveis + outras or [self.PORTA_PADRAO]

    def _conectar(self):
        """Abre a serial (uma vez, na inicializacao) e aguarda o reset do Uno."""
        try:
            import serial
        except ImportError:
            print("[R.2.D.2]: pyserial nao instalado (pip install pyserial). Arduino desativado.")
            return

        # Porta fixada (ARDUINO_PORT) ou deteccao: testa cada candidata ate
        # uma responder a identificacao do firmware.
        for porta in ([self.porta] if self.porta else self._portas_candidatas()):
            if self._tentar_porta(serial, porta):
                return
        print("[R.2.D.2]: Arduino desativado. Confira o cabo USB ou defina ARDUINO_PORT (ex.: COM7).")

    def _tentar_porta(self, serial, porta: str) -> bool:
        """Abre a porta e aceita o Uno so se ele se identificar como R2D2."""
        try:
            self.conexao = serial.Serial(porta, self.BAUDRATE, timeout=0.5, write_timeout=1)
            time.sleep(self.ESPERA_RESET_S)
            self.conexao.reset_input_buffer()
            resposta = self._enviar(self.CMD_PING)
        except Exception as erro:
            self._desconectar()
            print(f"[R.2.D.2]: Arduino nao encontrado em {porta} ({erro}).")
            return False
        if resposta not in self.PROTOCOLOS:
            self._desconectar()
            print(f"[R.2.D.2]: Firmware nao confirmado em {porta}. "
                  "Confira se o Uno esta executando r2d2_servo.ino.")
            return False
        self.porta = porta
        self.versao = self.PROTOCOLOS[resposta]
        print(f"[R.2.D.2]: Arduino confirmado em {porta} ({resposta.decode()}).")
        if self.versao < 2:
            print("[R.2.D.2]: Firmware antigo: envie o r2d2_servo.ino atual para a webcam guiar a cabeca.")
        return True

    def _desconectar(self):
        """Libera a serial mesmo quando uma operacao falha."""
        with self._trava:
            self._fechar_porta()

    def _fechar_porta(self):
        if self.conexao is not None:
            try:
                self.conexao.close()
            except Exception:
                pass
            self.conexao = None

    def _enviar(self, comando: bytes) -> bytes:
        """Envia um comando e exige resposta do firmware; falhas fecham a serial."""
        with self._trava:
            return self._enviar_sem_trava(comando)

    def _enviar_sem_trava(self, comando: bytes) -> bytes:
        if not self.disponivel:
            return b""
        try:
            if self.conexao.write(comando) != len(comando):
                raise OSError("comando enviado parcialmente")
            self.conexao.flush()
            resposta = self.conexao.readline().strip()
            if comando == self.CMD_PING:
                valida = resposta in self.PROTOCOLOS
            elif comando == self.CMD_ESTADO:
                valida = re.fullmatch(rb"STATE [01] [01] [01]", resposta) is not None
            else:
                valida = resposta == b"OK " + comando
            if not valida:
                raise OSError(f"sem confirmacao para {comando!r}: {resposta!r}")
            return resposta
        except Exception as erro:
            print(f"[R.2.D.2]: Falha na comunicacao com o Arduino: {erro}")
            self._desconectar()
            return b""

    def consultar_estado(self):
        """Le os estados logicos do Uno; nao comprova movimento ou fiacao."""
        resposta = self._enviar(self.CMD_ESTADO)
        if not resposta:
            return None
        valores = resposta.split()[1:]
        return dict(zip(("servo", "verde", "vermelho"), (valor == b"1" for valor in valores)))

    # ---------------- Servo ----------------
    def iniciar_movimento(self):
        """Manda o servo comecar a balancar."""
        self._enviar(self.CMD_SERVO_ON)

    def parar_movimento(self):
        """Manda o servo parar e voltar ao centro."""
        self._enviar(self.CMD_SERVO_OFF)

    def posicionar_cabeca(self, angulo: int) -> int | None:
        """
        Leva a cabeca a um angulo (o firmware anda ate ele em passos suaves).

        Args:
            angulo: graus; e limitado a POS_MIN..POS_MAX antes do envio

        Returns:
            Angulo confirmado pelo Uno, ou None se nao houve confirmacao
        """
        if not self.aceita_posicao:
            return None
        angulo = max(self.POS_MIN, min(self.POS_MAX, int(round(angulo))))
        if self._enviar(b"p%03d" % angulo):
            return angulo
        return None

    # ---------------- LEDs ----------------
    def escutando(self, ligado: bool):
        """LED verde: aceso enquanto o R.2.D.2 esta escutando."""
        self._enviar(self.CMD_VERDE_ON if ligado else self.CMD_VERDE_OFF)

    def respondendo(self, ligado: bool):
        """LED vermelho: pisca enquanto o R.2.D.2 esta respondendo."""
        self._enviar(self.CMD_VERM_ON if ligado else self.CMD_VERM_OFF)

    def fechar(self):
        """Desliga servo e LEDs e fecha a porta serial."""
        self.parar_movimento()
        self.escutando(False)
        self.respondendo(False)
        self._desconectar()


# ============================================================
#  CLASSE 5.6 - HeadTracker
#  Webcam sobre a cabeca guia o servo para centralizar um rosto
# ============================================================
class HeadTracker:
    """
    Usa a webcam presa em cima da cabeca do R2 para manter o rosto de quem
    esta na frente centralizado na horizontal.

    Funciona em malha fechada: como a camera gira junto com a cabeca, a
    distancia entre o rosto e o centro da imagem ja e o erro a corrigir.
    A cada ciclo a cabeca anda alguns graus na direcao do rosto, ate ele
    entrar na zona morta central. Se o rosto sumir, a cabeca fica parada
    onde esta, esperando ele voltar.

    Dois modos:
    - iniciar_continuo(): segue rostos em segundo plano, sem janela, enquanto
      o assistente de voz continua funcionando (modo usado pelo R2D2);
    - rastrear(): abre uma janela com a imagem, para testes e ajustes.

    Se a cabeca girar para o lado errado (afastando-se da pessoa), defina
    R2D2_CABECA_INVERTER=1: isso depende de como o servo foi montado.
    """

    ZONA_MORTA        = 0.10   # |erro| abaixo disso = centralizado (10% da meia-largura)
    GANHO_GRAUS       = 12.0   # graus de correcao para erro 1 (rosto na borda)
    PASSO_MAX         = 6      # maior correcao por ciclo, em graus
    INTERVALO_S       = 0.15   # espera minima entre correcoes (servo + atraso da camera)
    SUAVIZACAO        = 0.5    # media movel do centro do rosto (0 = sem filtro)
    LARGURA_FRAME     = 640
    ALTURA_FRAME      = 480
    TAMANHO_MIN_ROSTO = 60     # px; ignora deteccoes pequenas demais (ruido)
    ESPERA_CAMERA_S   = 8.0    # tempo maximo para a webcam abrir ou ser liberada
    JANELA = "R.2.D.2 - Rastreamento da cabeca (Q para sair)"

    def __init__(self, arduino: "ArduinoController", camera: int | None = None,
                 inverter: bool | None = None, detector=None):
        """
        Args:
            arduino:  ArduinoController com firmware R2D2/2
            camera:   indice da webcam da cabeca (padrao: R2D2_CAMERA_CABECA ou 1)
            inverter: inverte o sentido do giro (padrao: R2D2_CABECA_INVERTER)
            detector: classificador de rostos (padrao: Haar Cascade do OpenCV)
        """
        self.arduino = arduino
        if camera is None:
            camera = indice_camera_robo()
        self.camera = camera
        if inverter is None:
            inverter = os.getenv("R2D2_CABECA_INVERTER", "").strip().lower() in ("1", "sim", "true")
        self.inverter = inverter
        self.detector = detector or cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        )
        # Estado do controle (angulo atual e filtro do centro do rosto)
        self.angulo = None
        self._centro_suave = None
        self._ultimo_envio = 0.0
        # Modo continuo: thread, pedidos de parada e pausas
        self._thread = None
        self._erro = ""
        self._parar = threading.Event()
        self._pronto = threading.Event()
        self._camera_livre = threading.Event()
        self._camera_livre.set()
        self._trava_pausa = threading.Lock()
        self._pausas = 0

    def calcular_passo(self, centro_x: float, largura: int) -> int:
        """
        Converte a posicao do rosto na imagem em uma correcao de angulo.

        Args:
            centro_x: coordenada horizontal do centro do rosto, em pixels
            largura:  largura da imagem, em pixels

        Returns:
            Graus a somar ao angulo atual (0 = ja esta centralizado)
        """
        meia = largura / 2
        erro = (centro_x - meia) / meia          # -1 (borda esquerda) a 1 (direita)
        if abs(erro) < self.ZONA_MORTA:
            return 0
        passo = max(-self.PASSO_MAX, min(self.PASSO_MAX, self.GANHO_GRAUS * erro))
        passo = int(round(passo)) or (1 if erro > 0 else -1)
        # Na maioria dos servos, aumentar o angulo gira a cabeca para a
        # esquerda do robo. Rosto a direita na imagem -> diminuir o angulo.
        return passo if self.inverter else -passo

    @staticmethod
    def escolher_rosto(faces):
        """Escolhe o maior rosto (normalmente a pessoa mais proxima)."""
        return max(faces, key=lambda face: face[2] * face[3])

    # ----------------------------------------------------------
    #  Um quadro da camera -> uma correcao (usado nos dois modos)
    # ----------------------------------------------------------
    def _verificar_arduino(self) -> str:
        """Mensagem de erro se a cabeca nao pode ser movida, ou "" se pode."""
        if self.arduino is None or not self.arduino.disponivel:
            return "Preciso do Arduino conectado para mover a cabeça."
        if not self.arduino.aceita_posicao:
            return ("O firmware do Arduino está desatualizado. "
                    "Envie o r2d2 servo atualizado para a placa.")
        return ""

    def _abrir(self):
        """Abre a webcam do robo na resolucao usada pelo rastreamento."""
        cap = abrir_camera(self.camera)
        if cap.isOpened():
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.LARGURA_FRAME)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.ALTURA_FRAME)
        return cap

    def _processar_quadro(self, frame, agora: float):
        """
        Detecta o rosto em um quadro e, se preciso, corrige o angulo.

        Returns:
            (status, rosto ou None, perdeu_arduino)
        """
        largura = frame.shape[1]
        cinza = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = self.detector.detectMultiScale(
            cinza, scaleFactor=1.1, minNeighbors=5,
            minSize=(self.TAMANHO_MIN_ROSTO, self.TAMANHO_MIN_ROSTO),
        )
        if not len(faces):
            self._centro_suave = None
            return "Procurando rosto...", None, False

        rosto = self.escolher_rosto(faces)
        x, _, w, _ = rosto
        centro = x + w / 2
        self._centro_suave = centro if self._centro_suave is None else (
            self.SUAVIZACAO * self._centro_suave + (1 - self.SUAVIZACAO) * centro
        )
        passo = self.calcular_passo(self._centro_suave, largura)
        status = "Centralizado" if passo == 0 else "Ajustando"
        if passo and agora - self._ultimo_envio >= self.INTERVALO_S:
            novo = self.arduino.posicionar_cabeca(self.angulo + passo)
            if novo is None:
                return status, rosto, True
            if novo == self.angulo:
                status = "Limite de giro"
            self.angulo = novo
            self._ultimo_envio = agora
        return status, rosto, False

    # ----------------------------------------------------------
    #  Modo com janela (teste: scripts/rastrear_cabeca.py)
    # ----------------------------------------------------------
    def rastrear(self, duracao_max: float | None = None) -> str:
        """
        Abre a webcam do robo em uma janela e corrige o angulo ate o rosto
        ficar no centro. Pressione Q (ou Esc) na janela para encerrar.

        Args:
            duracao_max: encerra sozinho depois desses segundos (None = so pelo Q)

        Returns:
            Mensagem para ser falada ao final
        """
        erro = self._verificar_arduino()
        if erro:
            return erro
        cap = self._abrir()
        if not cap.isOpened():
            return f"Não consegui abrir a câmera {self.camera} da cabeça."

        self.angulo = self.arduino.posicionar_cabeca(self.arduino.POS_CENTRO)
        perdeu_arduino = self.angulo is None
        self._centro_suave = None
        self._ultimo_envio = 0.0
        viu_rosto = False
        inicio = time.monotonic()
        print("[R.2.D.2]: Rastreando rosto. Pressione Q na janela da camera para parar.")

        try:
            while not perdeu_arduino:
                ok, frame = cap.read()
                if not ok:
                    break
                agora = time.monotonic()
                status, rosto, perdeu_arduino = self._processar_quadro(frame, agora)
                if perdeu_arduino:
                    break
                if rosto is not None:
                    viu_rosto = True
                    x, y, w, h = rosto
                    cv2.rectangle(frame, (int(x), int(y)), (int(x + w), int(y + h)), (0, 255, 0), 2)

                # Linha central e faixa da zona morta
                altura, largura = frame.shape[:2]
                meio = largura // 2
                folga = int(self.ZONA_MORTA * meio)
                cv2.line(frame, (meio, 0), (meio, altura), (255, 255, 0), 1)
                cv2.rectangle(frame, (meio - folga, 0), (meio + folga, altura), (255, 255, 0), 1)
                cv2.putText(frame, f"Cabeca: {self.angulo} graus - {status}", (10, 30),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                cv2.imshow(self.JANELA, frame)

                if (cv2.waitKey(1) & 0xFF) in (ord("q"), 27):
                    break
                if duracao_max is not None and agora - inicio >= duracao_max:
                    break
        finally:
            cap.release()
            cv2.destroyAllWindows()
            if self.arduino.disponivel:
                self.arduino.posicionar_cabeca(self.arduino.POS_CENTRO)

        if perdeu_arduino:
            return "Perdi a comunicação com o Arduino. Confira a conexão USB."
        if not viu_rosto:
            return "Não encontrei nenhum rosto na câmera da cabeça."
        return "Rastreamento encerrado. Cabeça de volta ao centro."

    # ----------------------------------------------------------
    #  Modo continuo (segundo plano, junto com o assistente de voz)
    # ----------------------------------------------------------
    @property
    def ativo(self) -> bool:
        """True enquanto o rastreamento em segundo plano esta rodando."""
        return self._thread is not None and self._thread.is_alive()

    def iniciar_continuo(self) -> str:
        """
        Comeca a seguir rostos em segundo plano, sem janela. O assistente
        continua ouvindo e respondendo enquanto a cabeca acompanha a pessoa.

        Returns:
            Mensagem para ser falada
        """
        erro = self._verificar_arduino()
        if erro:
            return erro
        if self.ativo:
            return "Já estou seguindo quem está na minha frente."
        self._parar.clear()
        self._pronto.clear()
        self._erro = ""
        self._thread = threading.Thread(target=self._laco_continuo, name="rastreio-cabeca", daemon=True)
        self._thread.start()
        # Espera a camera abrir para poder avisar se algo deu errado
        self._pronto.wait(timeout=self.ESPERA_CAMERA_S)
        if self._erro:
            self._thread.join(timeout=1)
            return self._erro
        return "Vou virar a cabeça para seguir quem estiver na minha frente."

    def parar_continuo(self) -> str:
        """Para o rastreamento em segundo plano e devolve a cabeca ao centro."""
        if not self.ativo:
            return "Não estou seguindo ninguém agora."
        self._parar.set()
        self._thread.join(timeout=3)
        return "Parei de seguir. Cabeça de volta ao centro."

    @contextlib.contextmanager
    def pausado(self):
        """
        Suspende o rastreamento enquanto outro comando usa a cabeca ou a
        camera (grito, reconhecer face). A camera e liberada durante a pausa
        e, ao final, a cabeca volta ao angulo em que estava.
        """
        with self._trava_pausa:
            self._pausas += 1
        try:
            if not self._camera_livre.wait(timeout=self.ESPERA_CAMERA_S):
                print("[R.2.D.2]: O rastreamento demorou para liberar a camera.")
            yield
        finally:
            with self._trava_pausa:
                self._pausas -= 1

    def _laco_continuo(self):
        """Laco da thread: abre a camera, segue o rosto e respeita as pausas."""
        cap = None
        try:
            while not self._parar.is_set():
                with self._trava_pausa:
                    pausado = self._pausas > 0
                    if not pausado and cap is None:
                        self._camera_livre.clear()   # avisa que a camera sera usada
                if pausado:
                    if cap is not None:
                        cap.release()
                        cap = None
                    self._camera_livre.set()
                    time.sleep(0.05)
                    continue

                if cap is None:
                    cap = self._abrir()
                    if not cap.isOpened():
                        self._erro = f"Não consegui abrir a câmera {self.camera} do robô."
                        break
                    # Ao comecar ou depois de uma pausa, volta ao ultimo angulo
                    alvo = self.angulo if self.angulo is not None else self.arduino.POS_CENTRO
                    self.angulo = self.arduino.posicionar_cabeca(alvo)
                    if self.angulo is None:
                        self._erro = "Perdi a comunicação com o Arduino. Confira a conexão USB."
                        break
                    self._centro_suave = None
                    self._ultimo_envio = 0.0
                    self._pronto.set()
                    print("[R.2.D.2]: Seguindo rostos com a camera do robo.")

                ok, frame = cap.read()
                if not ok:
                    self._erro = "A câmera do robô parou de enviar imagens."
                    print(f"[R.2.D.2]: {self._erro}")
                    break
                _, _, perdeu_arduino = self._processar_quadro(frame, time.monotonic())
                if perdeu_arduino:
                    self._erro = "Perdi a comunicação com o Arduino. Confira a conexão USB."
                    print(f"[R.2.D.2]: {self._erro}")
                    break
        except Exception as erro:
            self._erro = f"O rastreamento parou por um erro: {erro}"
            print(f"[R.2.D.2]: {self._erro}")
        finally:
            if cap is not None:
                cap.release()
            self._camera_livre.set()
            self._pronto.set()
            if self.arduino.disponivel:
                self.arduino.posicionar_cabeca(self.arduino.POS_CENTRO)
            self.angulo = None


# ============================================================
#  CLASSE 6 - ExtraCommands
#  Comandos extras: clima, dolar, bitcoin, screenshot, busca
# ============================================================
class ExtraCommands:
    """
    Comandos extras que enriquecem a experiencia do R.2.D.2:
    - Previsao do tempo (wttr.in, sem chave)
    - Cotacao do dolar (AwesomeAPI, sem chave)
    - Valor do Bitcoin (CoinGecko, sem chave)
    - Screenshot da tela (Pillow)
    - Pesquisa no Google
    - Abrir YouTube
    - Abrir portal da FIAP
    """

    # URLs de APIs publicas e gratuitas
    URL_DOLAR   = "https://economia.awesomeapi.com.br/json/last/USD-BRL"
    URL_BITCOIN = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=brl,usd"
    URL_CLIMA   = "https://wttr.in/{cidade}?format=j1"
    TEMPO_MIN_MOVIMENTO_S = 4.0

    def __init__(self, arduino: "ArduinoController" = None):
        """
        Args:
            arduino: ArduinoController usado para mexer o servo e piscar o
                     LED vermelho durante o grito (opcional; sem ele o
                     grito toca apenas o som)
        """
        self.arduino = arduino

    def obter_dolar(self) -> str:
        """
        Consulta a cotacao atual do dolar em reais.

        Returns:
            String com a cotacao ou mensagem de erro
        """
        try:
            resposta = requests.get(self.URL_DOLAR, timeout=5)
            dados = resposta.json()
            cotacao = float(dados["USDBRL"]["bid"])
            return f"O dólar está cotado a {cotacao:.2f} reais."
        except Exception:
            return "Não consegui obter a cotação do dólar agora."

    def obter_bitcoin(self) -> str:
        """
        Consulta o valor atual do Bitcoin em reais e dolares.

        Returns:
            String com o valor ou mensagem de erro
        """
        try:
            resposta = requests.get(self.URL_BITCOIN, timeout=5)
            dados = resposta.json()
            valor_brl = dados["bitcoin"]["brl"]
            valor_usd = dados["bitcoin"]["usd"]
            return (
                f"O Bitcoin está valendo {valor_brl:,.0f} reais "
                f"ou {valor_usd:,.0f} dólares."
            )
        except Exception:
            return "Não consegui obter o valor do Bitcoin agora."

    def obter_clima(self, cidade: str = "S\u00e3o Paulo") -> str:
        """
        Consulta a previsao do tempo para uma cidade.

        Args:
            cidade: nome da cidade (padrao S\u00e3o Paulo)

        Returns:
            String com a previsao ou mensagem de erro
        """
        try:
            url = self.URL_CLIMA.format(cidade=cidade.replace(" ", "+"))
            resposta = requests.get(url, timeout=5)
            dados = resposta.json()

            atual     = dados["current_condition"][0]
            temp_c    = atual["temp_C"]
            descricao = atual["weatherDesc"][0]["value"]
            umidade   = atual["humidity"]

            return (
                f"Em {cidade}, a temperatura é de {temp_c} graus Celsius, "
                f"{descricao}, com {umidade} porcento de umidade."
            )
        except Exception:
            return f"Não consegui obter a previsão do tempo para {cidade}."

    def tirar_screenshot(self) -> str:
        """
        Captura a tela e salva como arquivo PNG com timestamp.

        Returns:
            Mensagem com o nome do arquivo salvo ou erro
        """
        try:
            from PIL import ImageGrab
            agora = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            nome_arquivo = f"screenshot_{agora}.png"
            PASTA_SAIDAS.mkdir(parents=True, exist_ok=True)
            imagem = ImageGrab.grab()
            imagem.save(PASTA_SAIDAS / nome_arquivo)
            return f"Screenshot salvo em outputs/{nome_arquivo}."
        except ImportError:
            return "Instale o Pillow para tirar screenshots: pip install Pillow"
        except Exception as erro:
            return f"Erro ao tirar screenshot: {erro}"

    def pesquisar_google(self, termo: str) -> str:
        """
        Abre o Google com uma pesquisa no navegador padrao.

        Args:
            termo: o que pesquisar

        Returns:
            Confirmacao da acao
        """
        url = f"https://www.google.com/search?q={termo.replace(' ', '+')}"
        webbrowser.open(url)
        return f"Pesquisando por {termo} no Google."

    def abrir_youtube(self, busca: str = "") -> str:
        """
        Abre o YouTube, com busca opcional.

        Args:
            busca: termo de busca (opcional)

        Returns:
            Confirmacao da acao
        """
        if busca:
            url = f"https://www.youtube.com/results?search_query={busca.replace(' ', '+')}"
            webbrowser.open(url)
            return f"Abrindo YouTube com a busca: {busca}."
        else:
            webbrowser.open("https://www.youtube.com")
            return "Abrindo YouTube."

    def abrir_portal_fiap(self) -> str:
        """
        Abre o portal da FIAP no navegador.

        Returns:
            Confirmacao da acao
        """
        webbrowser.open("https://on.fiap.com.br")
        return "Abrindo o portal da FIAP."

    def grita(self) -> str:
        """
        Toca o som caracteristico do R2D2 e, ao mesmo tempo, balanca o
        servo motor e pisca o LED vermelho (Arduino). Com a placa conectada,
        mantem a animacao por pelo menos 4 segundos, mesmo se o audio acabar
        antes, para dar tempo de a cabeca completar o movimento.

        Servo e LED sao sempre desligados no final (bloco finally), mesmo
        se ocorrer algum erro na reproducao.

        Returns:
            String vazia (a resposta e o proprio som) ou mensagem de erro
        """
        try:
            mixer.music.stop()
            mixer.music.unload()
            mixer.music.load(str(AUDIO_GRITO))
            mixer.music.set_volume(1.0)
            mover_cabeca = self.arduino is not None and self.arduino.disponivel
            try:
                # Inicia o movimento antes do som para nao perder parte do
                # audio curto esperando pelas confirmacoes da serial.
                if mover_cabeca:
                    self.arduino.iniciar_movimento()
                    self.arduino.respondendo(True)
                inicio = time.monotonic()
                mixer.music.play()

                while mixer.music.get_busy() or (
                    mover_cabeca and time.monotonic() - inicio < self.TEMPO_MIN_MOVIMENTO_S
                ):
                    time.sleep(0.05)
            finally:
                # Falhas na reproducao interrompem a animacao imediatamente.
                if mover_cabeca:
                    self.arduino.parar_movimento()
                    self.arduino.respondendo(False)
                mixer.music.stop()
                mixer.music.unload()
            if self.arduino is not None and not self.arduino.disponivel:
                return (
                    "O som tocou, mas perdi a comunicação com o Arduino. "
                    "Não consegui confirmar o comando da cabeça. Confira a conexão USB."
                )
            return ""
        except Exception as erro:
            return f"N\u00e3o consegui tocar o som: {erro}"


# ============================================================
#  CLASSE 7 - R2D2 (Orquestradora Principal)
#  Integra todos os modulos e processa os comandos de voz
# ============================================================
class R2D2:
    """
    Classe principal que orquestra todas as funcionalidades do R.2.D.2.
    Processa comandos de voz e delega para os modulos corretos.

    O assistente so executa acoes quando ouve "dedao" no inicio da fala.
    Caso contrario, apenas imprime o texto reconhecido sem agir.
    """

    # Palavra de ativacao - usuario precisa dizer isso primeiro
    # "dedao" é a versao normalizada (sem acento) de "dedão"
    NOME = "dedao"

    def __init__(self, groq_api_key: str = ""):
        """
        Inicializa o R.2.D.2 e todos os seus modulos.

        Args:
            groq_api_key: chave opcional para usar o Groq como IA de backup
        """
        print("=" * 52)
        print("  R.2.D.2 - Robotic Responsive Digital Dual Assistant")
        print("  Inicializando sistemas...")
        print("=" * 52)

        # Composicao de objetos: cada modulo tem responsabilidade unica
        # Arduino primeiro: o SpeechManager usa os LEDs de estado
        self.arduino = ArduinoController()
        self.speech = SpeechManager(arduino=self.arduino)
        self.agenda = AgendaManager()
        self.calc   = Calculator()
        self.face   = FaceRecognizer()
        self.cabeca = HeadTracker(self.arduino, detector=self.face.detector)
        self.ai     = AIIntegration(modelo="llama3.2:3b", groq_api_key=groq_api_key)
        self.extras = ExtraCommands(arduino=self.arduino)

    def _dizer_hora(self) -> str:
        """Retorna a hora atual formatada para fala."""
        agora = datetime.datetime.now()
        return f"São {agora.hour} horas e {agora.minute} minutos."

    def _dizer_data(self) -> str:
        """Retorna a data atual formatada para fala."""
        agora      = datetime.datetime.now()
        dias       = ["segunda-feira", "terça-feira", "quarta-feira",
                      "quinta-feira", "sexta-feira", "sábado", "domingo"]
        meses      = ["janeiro", "fevereiro", "março", "abril", "maio", "junho",
                      "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"]
        dia_semana = dias[agora.weekday()]
        return (
            f"Hoje é {dia_semana}, {agora.day} de "
            f"{meses[agora.month - 1]} de {agora.year}."
        )

    def processar_comando(self, comando: str) -> bool:
        """
        Valida a ativacao no inicio da fala e aciona o modulo correto.

        Args:
            comando: fala completa, incluindo a palavra de ativacao

        Returns:
            False para encerrar o programa, True para continuar
        """

        comando = remover_acentos(comando.lower().strip())
        comando = re.sub(r"\s+", " ", comando)
        ativacao = re.match(rf"{re.escape(self.NOME)}\b[\s,.:;!?-]*", comando)
        if not ativacao:
            print(f"[Reconhecido, sem acao]: {comando}")
            return True

        # Retira apenas a ativacao inicial; o assunto pode mencionar "dedao".
        comando = comando[ativacao.end():].strip()

        # Cada intencao deve estar no inicio, nunca dentro de um assunto.
        # -- Sair: somente um pedido completo de encerramento -------
        if re.fullmatch(r"(?:sair|encerrar|tchau)[.!?]*", comando):
            self.speech.falar("Até logo! Sistemas desligando. Bip bup.")
            return False

        # -- Agenda: cadastrar -------------------------------------
        elif re.match(r"(?:cadastrar evento|adicionar evento)\b", comando):
            evento = self.speech.ouvir_resposta("Ok, qual evento devo cadastrar?")
            if evento:
                resultado = self.agenda.cadastrar_evento(evento)
                self.speech.falar(resultado)
            else:
                self.speech.falar("Não consegui ouvir o evento.")

        # -- Agenda: ler -------------------------------------------
        elif re.match(r"(?:ler agenda|minha agenda)\b", comando):
            resultado = self.agenda.ler_agenda()
            self.speech.falar(resultado)

        # -- Agenda: limpar ----------------------------------------
        elif re.match(r"(?:limpar agenda|apagar agenda)\b", comando):
            confirmacao = self.speech.ouvir_resposta(
                "Tem certeza que deseja limpar toda a agenda? Diga sim ou não."
            )
            if "sim" in confirmacao:
                resultado = self.agenda.limpar_agenda()
                self.speech.falar(resultado)
            else:
                self.speech.falar("Ok, agenda mantida.")

        # -- Horas -------------------------------------------------
        elif re.match(r"(?:que horas|horas sao)\b", comando):
            self.speech.falar(self._dizer_hora())

        # -- Data --------------------------------------------------
        elif re.match(r"(?:que dia|dia e hoje|data de hoje)\b", comando):
            self.speech.falar(self._dizer_data())

        # -- Calculo -----------------------------------------------
        elif re.match(r"(?:calcular|quanto e|quanto vale)\b", comando):
            resultado = self.calc.calcular(comando)
            self.speech.falar(resultado)

        # -- Reconhecimento facial ---------------------------------
        elif re.match(r"(?:reconhecer face|quem sou eu|reconhecer rosto)\b", comando):
            self.speech.falar("Abrindo a câmera para reconhecimento facial.")
            with self.cabeca.pausado():   # libera a camera do rastreamento
                resultado = self.face.reconhecer()
            self.speech.falar(resultado)

        # -- Camera do robo: parar de seguir -----------------------
        elif re.match(
            r"(?:(?:parar|pare) de (?:seguir|me seguir|acompanhar|me acompanhar)"
            r"|parar (?:o )?rastreamento|nao me (?:siga|acompanhe))\b",
            comando,
        ):
            self.speech.falar(self.cabeca.parar_continuo())

        # -- Camera do robo: seguir quem esta na frente ------------
        elif re.match(
            r"(?:seguir (?:rosto|pessoa)|me (?:siga|acompanhe)|rastrear rosto|centralizar)\b",
            comando,
        ):
            self.speech.falar(self.cabeca.iniciar_continuo())

        # -- IA generativa -----------------------------------------
        elif pedido_ia := re.match(r"(perguntar|me fale sobre|o que e)\b[\s,:-]*", comando):
            pergunta = comando[pedido_ia.end():].strip()
            if pedido_ia.group(1) == "o que e" and pergunta:
                pergunta = f"o que e {pergunta}"
            if not pergunta:
                pergunta = self.speech.ouvir_resposta("O que você quer saber?")

            if pergunta:
                self.speech.falar("Consultando a inteligência artificial, aguarde.")
                resposta = self.ai.perguntar(pergunta)
                self.speech.falar(resposta)

        # -- Previsao do tempo -------------------------------------
        elif re.match(r"(?:previsao do tempo|tempo em|como esta o tempo)\b", comando):
            cidade = "S\u00e3o Paulo"
            if "em " in comando:
                partes = comando.split("em ")
                if len(partes) > 1:
                    cidade = partes[-1].strip()
            resultado = self.extras.obter_clima(cidade)
            self.speech.falar(resultado)

        # -- Dolar -------------------------------------------------
        elif re.match(r"(?:(?:valor|cotacao) do )?(?:dolar|cambio)\b", comando):
            resultado = self.extras.obter_dolar()
            self.speech.falar(resultado)

        # -- Bitcoin -----------------------------------------------
        elif re.match(r"(?:(?:valor|cotacao) do )?(?:bitcoin|cripto)\b", comando):
            resultado = self.extras.obter_bitcoin()
            self.speech.falar(resultado)

        # -- Screenshot --------------------------------------------
        elif re.match(r"(?:tirar screenshot|screenshot|print da tela|capturar tela)\b", comando):
            resultado = self.extras.tirar_screenshot()
            self.speech.falar(resultado)

        # -- YouTube -----------------------------------------------
        elif pedido_youtube := re.match(
            r"(?:abrir (?:o )?)?youtube\b(?:\s+(?:sobre|video de)\b[\s,:-]*(.*))?",
            comando,
        ):
            busca = (pedido_youtube.group(1) or "").strip()
            resultado = self.extras.abrir_youtube(busca)
            self.speech.falar(resultado)

        # -- Pesquisa no Google ------------------------------------
        elif pedido_google := re.match(
            r"(?:pesquisar|buscar|pesquisa)\b(?:\s+no google\b)?[\s,:-]*", comando
        ):
            termo = comando[pedido_google.end():].strip()
            if not termo:
                termo = self.speech.ouvir_resposta("O que você quer pesquisar?")
            if termo:
                resultado = self.extras.pesquisar_google(termo)
                self.speech.falar(resultado)

        # -- Portal da FIAP ----------------------------------------
        elif re.match(r"(?:abrir (?:o |a )?)?(?:portal|fiap|faculdade)\b", comando):
            resultado = self.extras.abrir_portal_fiap()
            self.speech.falar(resultado)

        # -- Grita / som do R2D2 -----------------------------------
        elif re.match(r"(?:grita|grite|som)\b", comando):
            print("[R.2.D.2]: *beep boop*")
            with self.cabeca.pausado():   # o balanco usa a cabeca
                resultado = self.extras.grita()
            if resultado:  # So fala se houver mensagem de erro
                self.speech.falar(resultado)

        # -- Listar comandos ---------------------------------------
        elif re.match(r"(?:listar comandos|listar|comandos?)\b", comando):
            self.speech.falar(
                "Aqui estão os comandos disponíveis. "
                "Cadastrar evento. "
                "Ler agenda. "
                "Limpar agenda. "
                "Que horas são. "
                "Que dia é hoje. "
                "Calcular. "
                "Reconhecer face. "
                "Seguir rosto. "
                "Parar de seguir. "
                "Perguntar. "
                "Previsão do tempo. "
                "Valor do dólar. "
                "Bitcoin. "
                "Tirar screenshot. "
                "Pesquisar. "
                "Abrir YouTube. "
                "Abrir portal. "
                "Grita. "
                "Sair. "
                "Para usar qualquer comando, diga dedão seguido do comando."
            )

        # -- Comando nao reconhecido -------------------------------
        else:
            self.speech.falar(
                "Comando não reconhecido. "
                "Para ver todos os comandos, diga: dedão listar comandos."
            )

        return True  # Continua rodando

    def _vigiar_parada(self, arquivo: Path, fim: threading.Event):
        """
        Encerra o assistente quando o arquivo de parada aparece (usado pelo
        "Iniciar R2D2.bat"). Gera o mesmo efeito do Ctrl+C: despedida,
        cabeca no centro, LEDs apagados e porta serial liberada.
        """
        while not fim.wait(0.3):
            if arquivo.exists():
                try:
                    arquivo.unlink()
                except OSError:
                    pass
                print("\n[R.2.D.2]: Pedido de parada recebido.")
                _thread.interrupt_main()
                return

    def iniciar(self):
        """
        Loop principal do R.2.D.2.
        Ouve continuamente e so age quando a fala comeca com 'dedao'.
        Qualquer outra fala e impressa sem executar nenhuma acao.
        Encerra com "dedao sair", Ctrl+C ou o arquivo R2D2_ARQUIVO_PARADA.
        """
        fim_vigia = threading.Event()
        arquivo_parada = os.getenv("R2D2_ARQUIVO_PARADA", "").strip()
        if arquivo_parada:
            threading.Thread(
                target=self._vigiar_parada, args=(Path(arquivo_parada), fim_vigia),
                name="vigia-parada", daemon=True,
            ).start()

        try:
            self.speech.falar(
                "Sistemas online. Eu sou R 2 Dedão, sua assistente virtual. "
                "Diga dedão seguido do comando para interagir comigo. "
                "Para sair, diga dedão sair."
            )

            # A cabeca passa a seguir quem estiver na frente desde o inicio
            # (desligue com R2D2_RASTREIO_AUTOMATICO=0)
            if os.getenv("R2D2_RASTREIO_AUTOMATICO", "1").strip() != "0" and self.arduino.aceita_posicao:
                print(f"[R.2.D.2]: {self.cabeca.iniciar_continuo()}")

            print("\n[R.2.D.2]: Aguardando comandos... (diga 'dedão <comando>')")
            print("[R.2.D.2]: Para sair, diga 'dedão sair' ou pressione Ctrl+C\n")

            while True:
                comando = self.speech.ouvir(timeout=10, duracao=10)
                if not comando:
                    continue
                if not self.processar_comando(comando):
                    break

        except KeyboardInterrupt:
            print("\n[R.2.D.2]: Encerrando por interrupcao do usuario.")
            try:
                self.speech.falar("Até logo! Bip bup.")
            except KeyboardInterrupt:
                pass
        finally:
            fim_vigia.set()
            # Para a camera, desliga servo e LEDs e libera a porta serial
            self.cabeca.parar_continuo()
            self.arduino.fechar()


# ============================================================
#  PONTO DE ENTRADA
# ============================================================
if __name__ == "__main__":
    # Chave do Groq (opcional) - backup se Ollama estiver offline.
    # Defina na variavel de ambiente GROQ_API_KEY (NUNCA escreva a chave aqui,
    # para nao vazar no GitHub). Windows (PowerShell): $env:GROQ_API_KEY="gsk_..."
    GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

    assistente = R2D2(groq_api_key=GROQ_API_KEY)
    assistente.iniciar()
