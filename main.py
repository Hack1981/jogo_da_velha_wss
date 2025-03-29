from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import asyncio
import uuid
from fastapi.responses import HTMLResponse

app = FastAPI()

salas = {}

class Sala:
    def __init__(self, id):
        self.id = id
        self.jogadores = []
        self.nomes = {}
        self.simbolos = {}
        self.tabuleiro = [""] * 9
        self.turno = None
        self.partida_encerrada = False

    async def enviar_mensagem(self, mensagem):
        for jogador in self.jogadores:
            await jogador.send_json(mensagem)

    def verificar_vitoria(self):
        vitorias = [
            [0, 1, 2], [3, 4, 5], [6, 7, 8],
            [0, 3, 6], [1, 4, 7], [2, 5, 8],
            [0, 4, 8], [2, 4, 6]
        ]
        for a, b, c in vitorias:
            if self.tabuleiro[a] and self.tabuleiro[a] == self.tabuleiro[b] == self.tabuleiro[c]:
                return self.tabuleiro[a]
        if "" not in self.tabuleiro:
            return "empate"
        return None

@app.get("/", response_class=HTMLResponse)
def home():
    return """
    <html>
        <head>
            <title>Servidor Jogo da Velha</title>
        </head>
        <body>
            <h1>Servidor WebSocket para Jogo da Velha</h1>
            <p>Conecte-se via WebSocket para jogar.</p>
        </body>
    </html>
    """

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    jogador_nome = await websocket.receive_text()
    sala_encontrada = None

    for sala in salas.values():
        if len(sala.jogadores) < 2:
            sala_encontrada = sala
            break

    if not sala_encontrada:
        sala_id = str(uuid.uuid4())[:8]
        sala_encontrada = Sala(sala_id)
        salas[sala_id] = sala_encontrada

    sala_encontrada.jogadores.append(websocket)
    sala_encontrada.nomes[websocket] = jogador_nome

    if len(sala_encontrada.jogadores) == 1:
        sala_encontrada.simbolos[websocket] = "X"
        sala_encontrada.turno = websocket
    else:
        sala_encontrada.simbolos[websocket] = "O"

    simbolo = sala_encontrada.simbolos[websocket]
    await websocket.send_json({
        "mensagem": f"Você entrou na sala {sala_encontrada.id}. Você é '{simbolo}'",
        "simbolo": simbolo
    })

    if len(sala_encontrada.jogadores) == 2:
        turno_simbolo = sala_encontrada.simbolos[sala_encontrada.turno]
        jogador_turno = sala_encontrada.nomes[sala_encontrada.turno]
        await sala_encontrada.enviar_mensagem({
            "mensagem": f"O jogo começou! Vez de {jogador_turno} ({turno_simbolo})",
            "tabuleiro": sala_encontrada.tabuleiro,
            "turno": turno_simbolo
        })

    try:
        while True:
            jogada = await websocket.receive_json()
            index = int(jogada["posicao"])
            if websocket != sala_encontrada.turno or sala_encontrada.partida_encerrada:
                continue
            if sala_encontrada.tabuleiro[index] == "":
                sala_encontrada.tabuleiro[index] = simbolo
                sala_encontrada.turno = (
                    sala_encontrada.jogadores[0]
                    if websocket == sala_encontrada.jogadores[1]
                    else sala_encontrada.jogadores[1]
                )
                turno_simbolo = sala_encontrada.simbolos[sala_encontrada.turno]
                jogador_turno = sala_encontrada.nomes[sala_encontrada.turno]
                await sala_encontrada.enviar_mensagem({
                    "tabuleiro": sala_encontrada.tabuleiro,
                    "mensagem": f"Vez de {jogador_turno} ({turno_simbolo})",
                    "turno": turno_simbolo
                })
                resultado = sala_encontrada.verificar_vitoria()
                if resultado:
                    if resultado == "empate":
                        await sala_encontrada.enviar_mensagem({"mensagem": "Empate! O jogo será reiniciado..."})
                        await asyncio.sleep(2)
                        sala_encontrada.tabuleiro = [""] * 9
                        await sala_encontrada.enviar_mensagem({"tabuleiro": sala_encontrada.tabuleiro, "turno": turno_simbolo})
                    else:
                        vencedor = [j for j, s in sala_encontrada.simbolos.items() if s == resultado][0]
                        await sala_encontrada.enviar_mensagem({"mensagem": f"{sala_encontrada.nomes[vencedor]} ({resultado}) venceu!"})
                        sala_encontrada.partida_encerrada = True
                        await asyncio.sleep(5)
                        del salas[sala_encontrada.id]
                        break
    except WebSocketDisconnect:
        sala_encontrada.jogadores.remove(websocket)
        if sala_encontrada.jogadores:
            vencedor = sala_encontrada.jogadores[0]
            await vencedor.send_json({"mensagem": f"{sala_encontrada.nomes[websocket]} desconectou. Você venceu!"})
        del salas[sala_encontrada.id]