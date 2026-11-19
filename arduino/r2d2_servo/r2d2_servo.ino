/*
  R.2.D.2 - Servo do grito + LEDs de estado (Arduino Uno)

  Protocolo serial (9600 baud). O Python envia 1 caractere por comando
  (o 'p' leva mais 3 digitos):
    'a' -> comeca a balancar o servo (R2D2 gritando)
    'b' -> para o servo e volta ao centro
    'c' -> LED VERDE aceso   (R2D2 escutando)
    'd' -> LED VERDE apagado
    'e' -> LED VERMELHO piscando (R2D2 respondendo)
    'f' -> LED VERMELHO apagado
    'p' + 3 digitos -> leva a cabeca ao angulo (ex.: "p090"), em passos
           suaves; usado pelo rastreamento da webcam. Responde "OK p090".
           O angulo e limitado a POS_MIN..POS_MAX e interrompe o balanco.
    '?' -> responde "R2D2/2" (identificacao do firmware)
    's' -> responde "STATE <servo> <verde> <vermelho>" (0 ou 1)
  Cada comando de 'a' a 'f' responde "OK <comando>".
  Um 'p' seguido de algo que nao seja digito responde "ERR p".

  Ligacao:
    Servo sinal (laranja/amarelo) -> pino 9
    Servo VCC (vermelho)          -> 5V
    Servo GND (marrom/preto)      -> GND
    LED verde:    pino 7 -> resistor 220 ohm -> perna longa (anodo, +);
                  perna curta (catodo, -) -> GND
    LED vermelho: pino 8 -> resistor 220 ohm -> perna longa (anodo, +);
                  perna curta (catodo, -) -> GND

  Servo pequeno (SG90 / MG90S) pode ser alimentado pelo 5V do Uno via USB.
  Servo maior ou com carga: use fonte externa de 5-6V e ligue o GND dela
  junto com o GND do Arduino.
*/

#include <Servo.h>

// ---------------- Pinos ----------------
const int PINO_SERVO    = 9;
const int PINO_LED_VERDE    = 7;   // escutando
const int PINO_LED_VERMELHO = 8;   // respondendo

// ---------------- Servo ----------------
const int POS_CENTRO = 90;   // posicao de repouso
const int POS_MIN    = 45;   // limite esquerdo do balanco
const int POS_MAX    = 135;  // limite direito do balanco
const int PASSO      = 1;    // cerca de 33 graus/s, com giro mais amplo
const unsigned long INTERVALO_SERVO_MS = 30;
// Rastreamento: a cabeca anda 1 grau a cada 15 ms ate o angulo pedido
// (cerca de 66 graus/s), evitando trancos quando a webcam pede correcoes.
const unsigned long INTERVALO_RASTREIO_MS = 15;

// ---------------- LEDs ----------------
const unsigned long INTERVALO_PISCA_MS = 250;  // velocidade do LED vermelho

// ---------------- Seguranca (watchdogs) ----------------
// Se o Python travar e nunca mandar o comando de "desligar", cada saida
// desliga sozinha depois do tempo abaixo. Os tempos sao renovados a cada
// novo comando de "ligar" enviado pelo Python.
const unsigned long TEMPO_MAX_SERVO_MS   = 15000;  // grito
const unsigned long TEMPO_MAX_VERDE_MS   = 30000;  // escuta (max ~20 s)
const unsigned long TEMPO_MAX_VERMELHO_MS = 60000; // respostas longas

Servo servo;

// Estado do servo
bool servoMovendo = false;
int pos = POS_CENTRO;
int direcao = 1;
unsigned long ultimaAtualizacaoServo = 0;
unsigned long inicioServo = 0;

// Rastreamento (comando 'p'): angulo pedido e leitura dos 3 digitos
int posAlvo = POS_CENTRO;
unsigned long ultimoPassoRastreio = 0;
int digitosLidos = -1;      // -1 = nao esta lendo um comando 'p'
int anguloLido = 0;

// Estado dos LEDs
bool verdeLigado = false;
unsigned long inicioVerde = 0;

bool vermelhoPiscando = false;
bool vermelhoAceso = false;
unsigned long ultimaPiscada = 0;
unsigned long inicioVermelho = 0;

// ---------------- Funcoes auxiliares ----------------
void pararServo() {
  servoMovendo = false;
  pos = POS_CENTRO;
  posAlvo = POS_CENTRO;
  direcao = 1;
  servo.write(POS_CENTRO);
}

// Recebe um digito do comando 'p'. Devolve false se o caractere nao for
// digito, para que ele seja tratado como um comando normal.
bool lerDigitoAngulo(char c) {
  if (c < '0' || c > '9') {
    digitosLidos = -1;
    Serial.println(F("ERR p"));
    return false;
  }
  anguloLido = anguloLido * 10 + (c - '0');
  digitosLidos++;
  if (digitosLidos < 3) {
    return true;
  }
  digitosLidos = -1;
  servoMovendo = false;               // rastreamento interrompe o balanco
  posAlvo = constrain(anguloLido, POS_MIN, POS_MAX);
  Serial.print(F("OK p"));
  if (anguloLido < 100) Serial.print('0');
  if (anguloLido < 10) Serial.print('0');
  Serial.println(anguloLido);         // ecoa o que foi recebido
  return true;
}

void desligarVerde() {
  verdeLigado = false;
  digitalWrite(PINO_LED_VERDE, LOW);
}

void pararVermelho() {
  vermelhoPiscando = false;
  vermelhoAceso = false;
  digitalWrite(PINO_LED_VERMELHO, LOW);
}

void processarComando(char c) {
  if (digitosLidos >= 0 && lerDigitoAngulo(c)) {
    return;
  }
  switch (c) {
    case '?':
      Serial.println(F("R2D2/2"));
      return;
    case 'p':
      digitosLidos = 0;
      anguloLido = 0;
      return;
    case 's':
      Serial.print(F("STATE "));
      Serial.print(servoMovendo ? 1 : 0);
      Serial.print(' ');
      Serial.print(verdeLigado ? 1 : 0);
      Serial.print(' ');
      Serial.println(vermelhoPiscando ? 1 : 0);
      return;
    case 'a':
      servoMovendo = true;
      inicioServo = millis();
      break;
    case 'b':
      pararServo();
      break;
    case 'c':
      verdeLigado = true;
      inicioVerde = millis();
      digitalWrite(PINO_LED_VERDE, HIGH);
      break;
    case 'd':
      desligarVerde();
      break;
    case 'e':
      if (!vermelhoPiscando) {          // nao reinicia se ja estiver piscando
        vermelhoPiscando = true;
        vermelhoAceso = true;
        ultimaPiscada = millis();
        digitalWrite(PINO_LED_VERMELHO, HIGH);
      }
      inicioVermelho = millis();
      break;
    case 'f':
      pararVermelho();
      break;
    default:
      return;
  }
  Serial.print(F("OK "));
  Serial.println(c);
}

// ---------------- Setup ----------------
void setup() {
  Serial.begin(9600);

  pinMode(PINO_LED_VERDE, OUTPUT);
  pinMode(PINO_LED_VERMELHO, OUTPUT);

  servo.attach(PINO_SERVO);
  servo.write(POS_CENTRO);

  // Teste de ligacao: os dois LEDs acendem por 0,4 s ao ligar/reiniciar
  digitalWrite(PINO_LED_VERDE, HIGH);
  digitalWrite(PINO_LED_VERMELHO, HIGH);
  delay(400);
  digitalWrite(PINO_LED_VERDE, LOW);
  digitalWrite(PINO_LED_VERMELHO, LOW);
}

// ---------------- Loop (sem delay, tudo por millis) ----------------
void loop() {
  // Le comandos vindos do Python
  while (Serial.available() > 0) {
    processarComando(Serial.read());
  }

  // O instante precisa ser posterior aos inicios registrados nos comandos.
  // Caso contrario, a subtracao unsigned pode estourar e disparar o watchdog.
  unsigned long agora = millis();

  // Watchdogs
  if (servoMovendo && agora - inicioServo > TEMPO_MAX_SERVO_MS) {
    pararServo();
  }
  if (verdeLigado && agora - inicioVerde > TEMPO_MAX_VERDE_MS) {
    desligarVerde();
  }
  if (vermelhoPiscando && agora - inicioVermelho > TEMPO_MAX_VERMELHO_MS) {
    pararVermelho();
  }

  // Balanco do servo
  if (servoMovendo && agora - ultimaAtualizacaoServo >= INTERVALO_SERVO_MS) {
    ultimaAtualizacaoServo = agora;
    pos += direcao * PASSO;

    if (pos >= POS_MAX) { pos = POS_MAX; direcao = -1; }
    else if (pos <= POS_MIN) { pos = POS_MIN; direcao = 1; }

    servo.write(pos);
  }

  // Rastreamento: aproxima a cabeca do angulo pedido, 1 grau por vez
  if (!servoMovendo && pos != posAlvo && agora - ultimoPassoRastreio >= INTERVALO_RASTREIO_MS) {
    ultimoPassoRastreio = agora;
    pos += (posAlvo > pos) ? 1 : -1;
    servo.write(pos);
  }

  // Pisca do LED vermelho
  if (vermelhoPiscando && agora - ultimaPiscada >= INTERVALO_PISCA_MS) {
    ultimaPiscada = agora;
    vermelhoAceso = !vermelhoAceso;
    digitalWrite(PINO_LED_VERMELHO, vermelhoAceso ? HIGH : LOW);
  }
}
