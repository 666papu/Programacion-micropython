progra pytho 
import pygame
import serial
import sys
import random
import time

# ---------------- CONFIGURACIÓN ----------------
PUERTO = "COM4"      
BAUDIOS = 115200
COLS, ROWS = 13, 11  
TAM = 48             
RANGO = 2            
TIEMPO_BOMBA = 2.0   
TIEMPO_FUEGO = 0.5   
VELOCIDAD = 0.15   
BARRA = 40           
PUNTOS_PARA_GANAR = 3
PAUSA_RONDA = 2.0    

# ---------------- CONEXIÓN CON LA ESP32 ----------------
try:
    ser = serial.Serial(PUERTO, BAUDIOS, timeout=0)
    print("ESP32 conectada en", PUERTO)
except Exception:
    ser = None
    print("No se encontró la ESP32. Usando teclado:")
    print("J1: W A S D + ESPACIO   |   J2: flechas + ENTER")

estado = "0" * 10  # último estado de los 10 botones


def leer_esp32():
    """Lee lo que manda la ESP32 y guarda el último estado válido."""
    global estado
    if ser is None:
        return
    try:
        while ser.in_waiting:
            linea = ser.readline().decode(errors="ignore").strip()
            if len(linea) == 10 and set(linea) <= {"0", "1"}:
                estado = linea
    except Exception:
        pass


def enviar_puntos():
    """Manda los puntos a la ESP32 para encender los LEDs."""
    if ser is None:
        return
    try:
        ser.write(("%d,%d\n" % (puntos[0], puntos[1])).encode())
    except Exception:
        pass


def leer_teclado():
    """Modo de prueba si no hay ESP32 conectada."""
    k = pygame.key.get_pressed()
    teclas = [
        k[pygame.K_w], k[pygame.K_s], k[pygame.K_a], k[pygame.K_d], k[pygame.K_SPACE],
        k[pygame.K_UP], k[pygame.K_DOWN], k[pygame.K_LEFT], k[pygame.K_RIGHT], k[pygame.K_RETURN],
    ]
    return "".join("1" if t else "0" for t in teclas)


# ---------------- JUEGO ----------------
mapa = []
jugadores = []
bombas = []
fuego = {}          # {(x, y): hora_en_que_se_apaga}
puntos = [0, 0]     # puntos de cada jugador
fin_ronda = None    # hora en que terminó la ronda actual (None = en juego)
ganador = None      # índice del ganador de la partida (None = nadie aún)
resultado_ronda = ""  # texto que se muestra al terminar una ronda


def nuevo_juego():
    """Crea el mapa y los jugadores desde cero (no toca los puntos)."""
    global mapa, jugadores, bombas, fuego
    # 0 = vacío, 1 = pared fija, 2 = caja que se rompe
    mapa = [[0] * COLS for _ in range(ROWS)]
    for y in range(ROWS):
        for x in range(COLS):
            if x == 0 or y == 0 or x == COLS - 1 or y == ROWS - 1:
                mapa[y][x] = 1                      # borde
            elif x % 2 == 0 and y % 2 == 0:
                mapa[y][x] = 1                      # pilares
            elif random.random() < 0.6:
                mapa[y][x] = 2                      # cajas al azar

    # Dejamos libres las esquinas para que los jugadores no queden atrapados
    libres = [(1, 1), (2, 1), (1, 2),
              (COLS - 2, ROWS - 2), (COLS - 3, ROWS - 2), (COLS - 2, ROWS - 3)]
    for (x, y) in libres:
        mapa[y][x] = 0

    jugadores = [
        {"x": 1, "y": 1, "vivo": True, "color": (60, 120, 255),
         "ultimo_paso": 0, "bomba_antes": False},
        {"x": COLS - 2, "y": ROWS - 2, "vivo": True, "color": (255, 70, 70),
         "ultimo_paso": 0, "bomba_antes": False},
    ]
    bombas = []
    fuego = {}


def reiniciar_todo():
    """Reinicia la partida completa: puntos y nivel."""
    global puntos, fin_ronda, ganador, resultado_ronda
    puntos = [0, 0]
    fin_ronda = None
    ganador = None
    resultado_ronda = ""
    nuevo_juego()
    enviar_puntos()


def mover(j, dx, dy, ahora):
    if ahora - j["ultimo_paso"] < VELOCIDAD:
        return
    nx, ny = j["x"] + dx, j["y"] + dy
    if mapa[ny][nx] == 0:  # solo se mueve si la casilla está vacía
        j["x"], j["y"] = nx, ny
        j["ultimo_paso"] = ahora


def poner_bomba(j, indice, ahora):
    # Solo 1 bomba por jugador a la vez
    for b in bombas:
        if b["dueno"] == indice:
            return
    bombas.append({"x": j["x"], "y": j["y"], "t": ahora + TIEMPO_BOMBA, "dueno": indice})


def explotar(b, ahora):
    celdas = [(b["x"], b["y"])]
    for dx, dy in [(1, 0), (-1, 0), (0, 1), (0, -1)]:
        for i in range(1, RANGO + 1):
            x, y = b["x"] + dx * i, b["y"] + dy * i
            if mapa[y][x] == 1:      # pared fija: el fuego se detiene
                break
            celdas.append((x, y))
            if mapa[y][x] == 2:      # caja: se rompe y el fuego se detiene
                mapa[y][x] = 0
                break
    for c in celdas:
        fuego[c] = ahora + TIEMPO_FUEGO


def actualizar(ahora):
    global fuego
    # Apagar fuego viejo
    fuego = {c: t for c, t in fuego.items() if t > ahora}

    # Explotar bombas (con reacción en cadena)
    hubo = True
    while hubo:
        hubo = False
        for b in bombas[:]:
            if ahora >= b["t"]:
                bombas.remove(b)
                explotar(b, ahora)
                hubo = True
        for b in bombas:
            if (b["x"], b["y"]) in fuego:
                b["t"] = 0

    # Jugadores que tocan el fuego mueren
    for j in jugadores:
        if j["vivo"] and (j["x"], j["y"]) in fuego:
            j["vivo"] = False


def dibujar(pantalla, fuente, grande):
    pantalla.fill((30, 30, 30))

    # Mapa
    for y in range(ROWS):
        for x in range(COLS):
            rect = (x * TAM, y * TAM + BARRA, TAM, TAM)
            if mapa[y][x] == 1:
                pygame.draw.rect(pantalla, (90, 90, 90), rect)
            elif mapa[y][x] == 2:
                pygame.draw.rect(pantalla, (160, 110, 60), rect)
            else:
                pygame.draw.rect(pantalla, (50, 140, 50), rect)
            pygame.draw.rect(pantalla, (20, 20, 20), rect, 1)

    # Fuego
    for (x, y) in fuego:
        pygame.draw.rect(pantalla, (255, 160, 0), (x * TAM, y * TAM + BARRA, TAM, TAM))

    # Bombas
    for b in bombas:
        centro = (b["x"] * TAM + TAM // 2, b["y"] * TAM + BARRA + TAM // 2)
        pygame.draw.circle(pantalla, (0, 0, 0), centro, TAM // 3)

    # Jugadores
    for j in jugadores:
        if j["vivo"]:
            centro = (j["x"] * TAM + TAM // 2, j["y"] * TAM + BARRA + TAM // 2)
            pygame.draw.circle(pantalla, j["color"], centro, TAM // 2 - 6)

    # Marcador de arriba
    t1 = fuente.render("Jugador 1 (azul): %d" % puntos[0], True, (60, 120, 255))
    t2 = fuente.render("Jugador 2 (rojo): %d" % puntos[1], True, (255, 70, 70))
    pantalla.blit(t1, (10, 10))
    pantalla.blit(t2, t2.get_rect(topright=(COLS * TAM - 10, 10)))

    # Mensajes
    mensaje = None
    if ganador is not None:
        mensaje = "¡GANA EL JUGADOR %d! - Presiona R" % (ganador + 1)
    elif fin_ronda is not None:
        mensaje = resultado_ronda
    if mensaje:
        texto = grande.render(mensaje, True, (255, 255, 255))
        fondo = texto.get_rect(center=(COLS * TAM // 2, ROWS * TAM // 2 + BARRA))
        pygame.draw.rect(pantalla, (0, 0, 0), fondo.inflate(30, 20))
        pantalla.blit(texto, fondo)

    pygame.display.flip()


# ---------------- PROGRAMA PRINCIPAL ----------------
pygame.init()
pantalla = pygame.display.set_mode((COLS * TAM, ROWS * TAM + BARRA))
pygame.display.set_caption("Bomberman ESP32")
fuente = pygame.font.SysFont("arial", 20)
grande = pygame.font.SysFont("arial", 32, bold=True)
reloj = pygame.time.Clock()

reiniciar_todo()
ultimo_envio = 0

while True:
    for evento in pygame.event.get():
        if evento.type == pygame.QUIT:
            pygame.quit()
            sys.exit()
        if evento.type == pygame.KEYDOWN and evento.key == pygame.K_r:
            reiniciar_todo()

    leer_esp32()
    botones = estado if ser is not None else leer_teclado()
    ahora = time.time()

    # Reenviamos los puntos cada segundo por si la ESP32 se reinició
    if ahora - ultimo_envio > 1:
        enviar_puntos()
        ultimo_envio = ahora

    if ganador is None:
        vivos = [i for i, j in enumerate(jugadores) if j["vivo"]]

        if len(vivos) >= 2:  # la ronda sigue solo si ambos están vivos
            for i, j in enumerate(jugadores):
                b = botones[i * 5: i * 5 + 5]   # los 5 botones de este jugador
                if b[0] == "1": mover(j, 0, -1, ahora)   # arriba
                if b[1] == "1": mover(j, 0, 1, ahora)    # abajo
                if b[2] == "1": mover(j, -1, 0, ahora)   # izquierda
                if b[3] == "1": mover(j, 1, 0, ahora)    # derecha

                # La bomba se pone solo al momento de presionar (no mientras se mantiene)
                presionado = (b[4] == "1")
                if presionado and not j["bomba_antes"]:
                    poner_bomba(j, i, ahora)
                j["bomba_antes"] = presionado

        else:
            if fin_ronda is None:
                # La ronda acaba de terminar: damos el punto
                fin_ronda = ahora
                if len(vivos) == 1:
                    puntos[vivos[0]] += 1
                    resultado_ronda = "Punto para el jugador %d" % (vivos[0] + 1)
                    enviar_puntos()
                    if puntos[vivos[0]] >= PUNTOS_PARA_GANAR:
                        ganador = vivos[0]
                else:
                    resultado_ronda = "EMPATE - nadie suma"
            elif ahora - fin_ronda >= PAUSA_RONDA:
                # Pasó la pausa: nuevo nivel
                nuevo_juego()
                fin_ronda = None

    actualizar(ahora)
    dibujar(pantalla, fuente, grande)
    reloj.tick(60)
