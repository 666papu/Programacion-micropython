from machine import Pin
import time
import sys
import select

# Pines de botones: arriba, abajo, izquierda, derecha, bomba
# Jugador 1 -> lado IZQUIERDO de la placa
pines_j1 = [18, 19, 21, 22, 23]
# Jugador 2 -> lado DERECHO de la placa
pines_j2 = [13, 14, 27, 26, 25]

# Pines de LEDs (uno por punto)
pines_led_j1 = [15, 2, 4]     # lado izquierdo
pines_led_j2 = [33, 32, 12]   # lado derecho

botones = [Pin(p, Pin.IN, Pin.PULL_UP) for p in pines_j1 + pines_j2]
leds_j1 = [Pin(p, Pin.OUT, value=0) for p in pines_led_j1]
leds_j2 = [Pin(p, Pin.OUT, value=0) for p in pines_led_j2]


def mostrar_puntos(p1, p2):
    for i, led in enumerate(leds_j1):
        led.value(1 if i < p1 else 0)
    for i, led in enumerate(leds_j2):
        led.value(1 if i < p2 else 0)


# Para leer lo que manda la computadora sin bloquear el programa
entrada = select.poll()
entrada.register(sys.stdin, select.POLLIN)
buffer = ""

while True:
    # 1) Leer puntos desde la computadora (formato "p1,p2\n")
    while entrada.poll(0):
        c = sys.stdin.read(1)
        if c == "\n":
            try:
                a, b = buffer.strip().split(",")
                mostrar_puntos(int(a), int(b))
            except Exception:
                pass
            buffer = ""
        else:
            buffer += c
            if len(buffer) > 20:  # protección por si llega basura
                buffer = ""

    # 2) Enviar el estado de los botones
    texto = ""
    for b in botones:
        texto += "1" if b.value() == 0 else "0"

    print(texto)
    time.sleep_ms(20)
