"""Servidor HTTP falso que imita o SGS do Banco Central (só biblioteca padrão).

Reproduz o que a API real faz (verificado em 2026-09-25): `Content-Type: text/html` com
corpo JSON, janela máxima de 10 anos em séries diárias (HTTP 406), intervalo sem dados
(HTTP 404 "Value(s) not found") e, opcionalmente, linhas com datas futuras. Falha sob
comando (`modo`) e conta as chamadas. Usado pelos testes do `pytest` e pelos scripts de
validação da Etapa 8.
"""
import json
import threading
import time
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse
from zoneinfo import ZoneInfo

CDI, IPCA = 4389, 13522


def hoje_brasilia():
    return datetime.now(ZoneInfo("America/Sao_Paulo")).date()


def _primeiro_dia_mes_anterior(hoje):
    primeiro = hoje.replace(day=1)
    return (primeiro - timedelta(days=1)).replace(day=1)


def serie(codigo, hoje):
    """Linhas `(data, valor em texto)` da série falsa, como a real: CDI em dias úteis até
    ontem; IPCA mensal (dia 1) até o mês anterior."""
    linhas = []
    if codigo == CDI:
        dia = hoje - timedelta(days=3650)
        while dia < hoje:
            if dia.weekday() < 5:
                linhas.append((dia, f"{10 + (dia.toordinal() % 40) / 10:.2f}"))
            dia += timedelta(days=1)
    elif codigo == IPCA:
        mes = _primeiro_dia_mes_anterior(hoje)
        while mes > hoje - timedelta(days=3650):
            linhas.append((mes, f"{3 + (mes.year * 12 + mes.month) % 30 / 10:.2f}"))
            mes = (mes - timedelta(days=1)).replace(day=1)
        linhas.reverse()
    return linhas


class ServidorFalsoSgs:
    def __init__(self, hoje=None):
        self.hoje = hoje or hoje_brasilia()
        self.modo = None  # None = normal; ou o nome de uma falha (ver `_responder_falha`)
        self.atraso = 0.0  # segundos antes de responder (para testar timeout)
        self.chamadas = []  # (codigo, dataInicial, dataFinal)
        self._trava = threading.Lock()
        servidor = self

        class Tratador(BaseHTTPRequestHandler):
            def do_GET(self):  # noqa: N802
                servidor._tratar(self)

            def log_message(self, *args):
                pass

        class Servidor(ThreadingHTTPServer):
            def handle_error(self, request, client_address):
                pass  # cliente que desiste por timeout: BrokenPipe esperado, sem ruído no teste

        self._httpd = Servidor(("127.0.0.1", 0), Tratador)
        self._httpd.daemon_threads = True
        self._thread = threading.Thread(target=lambda: self._httpd.serve_forever(poll_interval=0.02), daemon=True)

    @property
    def url_base(self):
        return f"http://127.0.0.1:{self._httpd.server_address[1]}/bcdata.sgs"

    def __enter__(self):
        self._thread.start()
        return self

    def __exit__(self, *args):
        self._httpd.shutdown()
        self._httpd.server_close()

    def numero_de_chamadas(self):
        with self._trava:
            return len(self.chamadas)

    # -------------------------------------------------------------- respostas

    def _enviar(self, tratador, status, corpo, tipo="text/html; charset=utf-8"):
        dados = corpo.encode("utf-8")
        tratador.send_response(status)
        tratador.send_header("Content-Type", tipo)  # o SGS real usa text/html mesmo com JSON
        tratador.send_header("Content-Length", str(len(dados)))
        tratador.end_headers()
        tratador.wfile.write(dados)

    def _tratar(self, tratador):
        url = urlparse(tratador.path)
        consulta = {k: v[0] for k, v in parse_qs(url.query).items()}
        codigo = int(url.path.split(".")[-1].split("/")[0]) if url.path.startswith("/bcdata.sgs.") else None
        with self._trava:
            self.chamadas.append((codigo, consulta.get("dataInicial"), consulta.get("dataFinal")))
        if self.atraso:
            time.sleep(self.atraso)
        if self.modo:
            return self._responder_falha(tratador)
        try:
            inicio = datetime.strptime(consulta["dataInicial"], "%d/%m/%Y").date()
            fim = datetime.strptime(consulta["dataFinal"], "%d/%m/%Y").date()
        except (KeyError, ValueError):
            return self._enviar(tratador, 400, '{"erro":{"statusCode":400,"detail":"SGSNegocioException: Invalid initial date"}}')
        if codigo == CDI and (fim - inicio).days > 3650:
            return self._enviar(tratador, 406, '{"error":"O sistema aceita uma janela de consulta de, no máximo, 10 anos em séries de periodicidade diária"}')
        linhas = [(d, v) for d, v in serie(codigo, self.hoje) if inicio <= d <= fim]
        if not linhas:
            return self._enviar(tratador, 404, '{"erro":{"statusCode":404,"detail":"br.gov.bcb.pec.sgs.comum.excecoes.SGSNegocioException: Value(s) not found"}}')
        return self._enviar(tratador, 200, self._json(linhas))

    @staticmethod
    def _json(linhas):
        return json.dumps([{"data": d.strftime("%d/%m/%Y"), "valor": v} for d, v in linhas])

    def _responder_falha(self, tratador):
        modo = self.modo
        if modo == "500":
            return self._enviar(tratador, 500, "Internal Server Error")
        if modo == "503":
            return self._enviar(tratador, 503, "<html>Serviço indisponível</html>")
        if modo == "406":
            return self._enviar(tratador, 406, '{"error":"janela acima de 10 anos"}')
        if modo == "404_sem_dados":
            return self._enviar(tratador, 404, '{"erro":{"statusCode":404,"detail":"SGSNegocioException: Value(s) not found"}}')
        if modo == "404_outro":
            return self._enviar(tratador, 404, '{"erro":{"statusCode":404,"detail":"recurso inexistente"}}')
        if modo == "html":
            return self._enviar(tratador, 200, "<html><body>Manutenção</body></html>")
        if modo == "quebrado":
            return self._enviar(tratador, 200, '[{"data":"24/09/2026","valor":"13.6')
        if modo == "linha_invalida":
            return self._enviar(tratador, 200, '[{"data":"24/09/2026","valor":"13.65"},{"data":"25/09/2026","valor":"abc"}]')
        if modo == "vazio":
            return self._enviar(tratador, 200, "[]")
        if modo == "objeto":
            return self._enviar(tratador, 200, '{"data":"24/09/2026","valor":"13.65"}')
        if modo == "futuro":  # série normal + linhas com datas futuras (como a meta Selic real)
            url = urlparse(tratador.path)
            codigo = int(url.path.split(".")[-1].split("/")[0])
            linhas = serie(codigo, self.hoje)[-3:] + [(self.hoje + timedelta(days=n), "99.99") for n in (1, 2, 40)]
            return self._enviar(tratador, 200, self._json(linhas))
        return self._enviar(tratador, 500, f"modo desconhecido: {modo}")
