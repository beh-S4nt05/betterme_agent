"""Cliente MCP (Model Context Protocol) para o Pluto Agente.

Conecta o agente a servidores MCP externos (Figma, GitHub, bancos de dados…).
As ferramentas de cada servidor aparecem para o modelo como tools normais,
prefixadas: mcp_<servidor>_<ferramenta> (ex.: mcp_figma_create_design).

Transportes suportados:
- stdio: servidor lançado como processo local (ex.: npx figma-developer-mcp)
- http:  servidor Streamable HTTP (ex.: Figma Dev Mode em 127.0.0.1:3845/mcp)

Configuração (config.yaml):
  mcp_servers:
    - name: figma
      command: npx
      args: ["-y", "figma-developer-mcp", "--figma-api-key=SUA-CHAVE", "--stdio"]
    - name: figma-devmode
      url: http://127.0.0.1:3845/mcp
"""

from __future__ import annotations

import atexit
import json
import os
import re
import subprocess
import threading
import time
import urllib.request
from collections import deque
from pathlib import Path

import requests

PROTOCOL_VERSION = "2024-11-05"
PROJECT_ROOT = Path(__file__).resolve().parent.parent


class MCPError(Exception):
    pass


def map_tool_name(server_name: str, tool_name: str) -> str:
    """figma-demo + figma_create_design -> mcp_figma_demo_figma_create_design"""
    raw = f"{server_name}_{tool_name}"
    return "mcp_" + re.sub(r"[^a-z0-9_]", "_", raw.lower())


def _content_to_text(result: dict) -> str:
    parts = []
    for c in result.get("content") or []:
        if isinstance(c, dict) and c.get("type") == "text":
            parts.append(str(c.get("text", "")))
    return "\n".join(p for p in parts if p)


class BaseMCPServer:
    """Handshake JSON-RPC 2.0: initialize -> tools/list -> tools/call."""

    def __init__(self, name: str, timeout: float = 60):
        self.name = name
        self.timeout = timeout
        self.started = False
        self._id = 0

    # ------------------------------------------------- interface transporte
    def _rpc(self, method: str, params: dict | None, timeout: float) -> dict:
        raise NotImplementedError

    def _notify(self, obj: dict) -> None:
        pass

    def start(self) -> dict:
        result = self._rpc(
            "initialize",
            {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "pluto-agent", "version": "1.0.0"},
            },
            self.timeout,
        )
        self._notify({"jsonrpc": "2.0", "method": "notifications/initialized"})
        self.started = True
        return result

    def stop(self) -> None:
        self.started = False

    def alive(self) -> bool:
        return self.started

    # ----------------------------------------------------------- operações
    def list_tools(self) -> list[dict]:
        result = self._rpc("tools/list", {}, self.timeout)
        return result.get("tools") or []

    # --------------------------- recursos e prompts (v8.6.0, Genkit parity)
    def list_resources(self) -> list[dict]:
        """resources/list — servidor sem suporte devolve [] (honesto)."""
        try:
            return self._rpc("resources/list", {}, self.timeout).get(
                "resources") or []
        except MCPError:
            return []

    def read_resource(self, uri: str) -> str:
        """resources/read → texto do recurso (blob vira aviso honesto)."""
        r = self._rpc("resources/read", {"uri": uri}, self.timeout)
        partes = []
        for c in r.get("contents") or []:
            if c.get("text") is not None:
                partes.append(str(c["text"]))
            elif c.get("blob"):
                partes.append("(conteúdo binário em base64)")
        return "\n".join(partes) or "(recurso vazio)"

    def list_prompts(self) -> list[dict]:
        """prompts/list — servidor sem suporte devolve [] (honesto)."""
        try:
            return self._rpc("prompts/list", {}, self.timeout).get(
                "prompts") or []
        except MCPError:
            return []

    def get_prompt(self, name: str, args: dict | None = None) -> str:
        """prompts/get → mensagens renderizadas como texto."""
        r = self._rpc("prompts/get",
                      {"name": name, "arguments": args or {}}, self.timeout)
        linhas = []
        for m in r.get("messages") or []:
            c = m.get("content") or {}
            if c.get("type") == "text":
                linhas.append(f"{m.get('role', 'user')}: {c.get('text', '')}")
            else:
                linhas.append(f"{m.get('role', 'user')}: (conteúdo não-texto)")
        return "\n".join(linhas) or "(prompt vazio)"

    def call_tool(self, tool: str, arguments: dict) -> str:
        result = self._rpc(
            "tools/call", {"name": tool, "arguments": arguments or {}}, self.timeout * 2
        )
        text = _content_to_text(result)
        if result.get("isError"):
            raise MCPError(f"{self.name}.{tool}: {text or 'erro na ferramenta'}")
        return text or "(sem saída)"


# ------------------------------------------------------------------- stdio

class StdioServer(BaseMCPServer):
    """Servidor MCP como processo local, JSON-RPC por linhas no stdin/stdout."""

    def __init__(self, name, command, args=None, env=None, cwd=None, timeout=60):
        super().__init__(name, timeout)
        self.command = command
        self.args = list(args or [])
        self.env = dict(env or {})
        self.cwd = cwd or str(PROJECT_ROOT)
        self.proc: subprocess.Popen | None = None
        self.stderr_tail: deque[str] = deque(maxlen=6)
        self._lock = threading.Lock()
        self._responses: dict[int, dict] = {}
        self._events: dict[int, threading.Event] = {}

    def start(self) -> dict:
        if self.proc and self.proc.poll() is None and self.started:
            return {}
        env = dict(os.environ)
        env.update({str(k): str(v) for k, v in self.env.items()})
        try:
            self.proc = subprocess.Popen(
                [self.command, *self.args],
                cwd=self.cwd,
                env=env,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
            )
        except FileNotFoundError as exc:
            raise MCPError(
                f"comando não encontrado para o servidor MCP '{self.name}': "
                f"{self.command} ({exc})"
            ) from exc
        threading.Thread(target=self._read_stdout, daemon=True).start()
        threading.Thread(target=self._read_stderr, daemon=True).start()
        try:
            return super().start()
        except MCPError:
            self.stop()
            raise

    def _read_stdout(self) -> None:
        proc = self.proc
        if not proc or not proc.stdout:
            return
        try:
            for line in proc.stdout:
                line = line.strip()
                if not line:
                    continue
                try:
                    msg = json.loads(line)
                except json.JSONDecodeError:
                    continue
                rid = msg.get("id")
                if rid is not None and ("result" in msg or "error" in msg):
                    with self._lock:
                        self._responses[rid] = msg
                        ev = self._events.get(rid)
                    if ev:
                        ev.set()
        except Exception:
            pass

    def _read_stderr(self) -> None:
        proc = self.proc
        if not proc or not proc.stderr:
            return
        try:
            for line in proc.stderr:
                self.stderr_tail.append(line.rstrip()[:300])
        except Exception:
            pass

    def _rpc(self, method, params, timeout):
        proc = self.proc
        if not proc or proc.poll() is not None or not proc.stdin:
            raise MCPError(f"servidor MCP '{self.name}' não está ativo")
        self._id += 1
        rid = self._id
        ev = threading.Event()
        with self._lock:
            self._events[rid] = ev
            self._responses.pop(rid, None)
        payload = {"jsonrpc": "2.0", "id": rid, "method": method}
        if params is not None:
            payload["params"] = params
        try:
            proc.stdin.write(json.dumps(payload) + "\n")
            proc.stdin.flush()
            if not ev.wait(timeout):
                tail = " | ".join(list(self.stderr_tail)[-3:])
                raise MCPError(
                    f"timeout ({timeout:g}s) aguardando o servidor MCP '{self.name}'"
                    + (f" — stderr: {tail}" if tail else "")
                )
            with self._lock:
                resp = self._responses.pop(rid, {})
        finally:
            with self._lock:
                self._events.pop(rid, None)
        if "error" in resp:
            err = resp["error"] or {}
            raise MCPError(f"{self.name}: {err.get('message') or err}")
        return resp.get("result") or {}

    def _notify(self, obj) -> None:
        proc = self.proc
        try:
            if proc and proc.stdin and proc.poll() is None:
                proc.stdin.write(json.dumps(obj) + "\n")
                proc.stdin.flush()
        except OSError:
            pass

    def alive(self) -> bool:
        return bool(self.started and self.proc and self.proc.poll() is None)

    def stop(self) -> None:
        self.started = False
        proc, self.proc = self.proc, None
        if proc and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(3)
            except subprocess.TimeoutExpired:
                proc.kill()


# -------------------------------------------------------------------- http

class HTTPServer(BaseMCPServer):
    """Servidor MCP via Streamable HTTP (POST JSON-RPC; resposta JSON ou SSE)."""

    def __init__(self, name, url, headers=None, timeout=60):
        super().__init__(name, timeout)
        self.url = url
        self.headers = dict(headers or {})
        self.session_id: str | None = None

    def start(self) -> dict:
        result = super().start()
        self.started = True
        return result

    def _post(self, obj: dict, timeout: float) -> dict:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            **self.headers,
        }
        if self.session_id:
            headers["mcp-session-id"] = self.session_id
        r = requests.post(self.url, json=obj, headers=headers, timeout=timeout)
        sid = r.headers.get("mcp-session-id")
        if sid:
            self.session_id = sid
        if r.status_code >= 400:
            raise MCPError(f"{self.name}: HTTP {r.status_code}: {r.text[:200]}")
        return self._parse(r)

    @staticmethod
    def _parse(r) -> dict:
        ctype = r.headers.get("Content-Type", "")
        if "text/event-stream" in ctype:
            data = None
            for line in r.text.splitlines():
                if line.startswith("data:"):
                    data = line[5:].strip()
            if data:
                try:
                    return json.loads(data)
                except json.JSONDecodeError:
                    return {}
            return {}
        try:
            return r.json()
        except ValueError:
            return {}

    def _rpc(self, method, params, timeout):
        self._id += 1
        payload = {"jsonrpc": "2.0", "id": self._id, "method": method}
        if params is not None:
            payload["params"] = params
        resp = self._post(payload, timeout)
        if "error" in resp:
            err = resp["error"] or {}
            raise MCPError(f"{self.name}: {err.get('message') or err}")
        return resp.get("result") or {}

    def _notify(self, obj) -> None:
        try:
            self._post(obj, self.timeout)
        except MCPError:
            pass

    def alive(self) -> bool:
        return self.started and self.session_id is not None

    def stop(self) -> None:
        self.started = False


class SSEServer(BaseMCPServer):
    """Servidor MCP via HTTP+SSE CLÁSSICO (v8.6.0, paridade Genkit MCP —
    protocolo aberto, implementação própria em stdlib): GET <url> abre o
    stream; o servidor envia `event: endpoint` com a URL de POST; as
    respostas JSON-RPC voltam pelo stream. É o transporte usado pela
    maioria dos servidores MCP remotos pré-Streamable-HTTP."""

    def __init__(self, name, url, headers=None, timeout=60):
        super().__init__(name, timeout=timeout)
        self.url = url.rstrip("/")
        self.headers = dict(headers or {})
        self._endpoint: str | None = None
        self._resp = None
        self._thread = None
        self._stop_evt = threading.Event()
        self._pend: dict[int, dict] = {}
        self._lk = threading.Lock()

    def start(self) -> dict:
        req = urllib.request.Request(
            self.url, headers={"Accept": "text/event-stream",
                               **self.headers})
        try:
            self._resp = urllib.request.urlopen(req, timeout=self.timeout)
        except Exception as exc:  # noqa: BLE001 — conexão recusada etc.
            raise MCPError(f"{self.name}: SSE {self.url}: {exc}") from exc
        self._thread = threading.Thread(target=self._ler, daemon=True)
        self._thread.start()
        t0 = time.time()
        while self._endpoint is None:
            if time.time() - t0 > self.timeout:
                raise MCPError(f"{self.name}: SSE não enviou 'endpoint'")
            time.sleep(0.05)
        result = super().start()               # initialize + initialized
        self.started = True
        return result

    # ----------------------------------------------------------- stream SSE
    def _ler(self) -> None:
        evento, dados = "", []
        try:
            for bruto in self._resp:
                if self._stop_evt.is_set():
                    return
                linha = bruto.decode("utf-8", "replace").rstrip("\r\n")
                if linha.startswith("event:"):
                    evento = linha[6:].strip()
                elif linha.startswith("data:"):
                    dados.append(linha[5:].strip())
                elif not linha:
                    if evento or dados:
                        self._despacha(evento, "\n".join(dados))
                    evento, dados = "", []
        except Exception:  # noqa: BLE001 — stream caiu
            with self._lk:
                for item in self._pend.values():
                    item["resp"] = {"error": {"message": "SSE caiu"}}
                    item["ev"].set()

    def _despacha(self, evento: str, dados: str) -> None:
        if evento == "endpoint" and dados:
            self._endpoint = dados.strip()
            return
        if evento not in ("message", ""):
            return
        try:
            msg = json.loads(dados)
        except (json.JSONDecodeError, ValueError):
            return
        rid = msg.get("id")
        if rid is None:
            return
        with self._lk:
            item = self._pend.pop(int(rid), None)
        if item:
            item["resp"] = msg
            item["ev"].set()

    # ------------------------------------------------------------- JSON-RPC
    def _url_post(self) -> str:
        ep = self._endpoint or ""
        if ep.startswith(("http://", "https://")):
            return ep
        base = self.url
        for sufixo in ("/sse", "/messages", "/message"):
            if base.endswith(sufixo):
                base = base[: -len(sufixo)]
                break
        return base.rstrip("/") + (ep if ep.startswith("/") else "/" + ep)

    def _post(self, payload: dict, timeout: float) -> None:
        req = urllib.request.Request(
            self._url_post(), data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", **self.headers},
            method="POST")
        urllib.request.urlopen(req, timeout=timeout).read()

    def _rpc(self, method, params, timeout):
        with self._lk:
            self._id += 1
            rid = self._id
            item = {"ev": threading.Event(), "resp": None}
            self._pend[rid] = item
        payload = {"jsonrpc": "2.0", "id": rid, "method": method}
        if params is not None:
            payload["params"] = params
        try:
            self._post(payload, timeout)
        except Exception as exc:  # noqa: BLE001
            with self._lk:
                self._pend.pop(rid, None)
            raise MCPError(f"{self.name}: POST {method}: {exc}") from exc
        if not item["ev"].wait(timeout):
            with self._lk:
                self._pend.pop(rid, None)
            raise MCPError(f"{self.name}: timeout ({timeout}s) em {method}")
        resp = item["resp"] or {}
        if "error" in resp:
            err = resp["error"] or {}
            raise MCPError(f"{self.name}: {err.get('message') or err}")
        return resp.get("result") or {}

    def _notify(self, obj) -> None:
        try:
            self._post(obj, self.timeout)
        except Exception:  # noqa: BLE001 — notificação é melhor-esforço
            pass

    def alive(self) -> bool:
        return bool(self._thread and self._thread.is_alive()
                    and not self._stop_evt.is_set())

    def stop(self) -> None:
        self._stop_evt.set()
        try:
            if self._resp:
                self._resp.close()
        except Exception:  # noqa: BLE001
            pass
        self.session_id = None


# ----------------------------------------------------------------- gerente

_MANAGERS: dict[str, "MCPManager"] = {}


def get_manager(cfg) -> "MCPManager":
    key = str(cfg.data_dir)
    if key not in _MANAGERS:
        _MANAGERS[key] = MCPManager(cfg)
    return _MANAGERS[key]


class MCPManager:
    """Gerencia todos os servidores MCP configurados (uma instância por data dir)."""

    def __init__(self, cfg):
        self.cfg = cfg
        self._servers: dict[str, BaseMCPServer] = {}
        self._map: dict[str, tuple[str, str]] = {}      # mcp_x -> (servidor, original)
        self._meta: dict[str, dict] = {}                # mcp_x -> schema bruto
        self._server_tools: dict[str, list[str]] = {}   # servidor -> [mcp_x]
        self._state: dict[str, dict] = {}
        self._tried = False

    # ----------------------------------------------------------- configuração
    def _entries(self) -> list[dict]:
        out = []
        for e in self.cfg.mcp_servers or []:
            if isinstance(e, dict) and e.get("name"):
                out.append(e)
        return out

    def _make(self, e: dict) -> BaseMCPServer:
        timeout = float(e.get("timeout") or getattr(self.cfg, "mcp_timeout", 120))
        if e.get("transport") == "sse":          # v8.6.0: HTTP+SSE clássico
            return SSEServer(e["name"], e["url"], e.get("headers"), timeout)
        if e.get("url"):
            return HTTPServer(e["name"], e["url"], e.get("headers"), timeout)
        command = e.get("command")
        if not command:
            raise MCPError(f"servidor MCP '{e.get('name')}' sem 'command' nem 'url'")
        return StdioServer(
            e["name"], command, e.get("args") or [], e.get("env"),
            e.get("cwd") or str(PROJECT_ROOT), timeout,
        )

    # --------------------------------------------------------------- ciclo
    def start_all(self) -> None:
        self._tried = True
        for e in self._entries():
            name = str(e["name"])
            srv = self._servers.get(name)
            if srv and srv.alive():
                continue
            # placeholders de token no config = servidor nunca vai subir;
            # pula com mensagem clara em vez de travar o chat com timeout
            target = " ".join(
                [str(e.get("command", ""))] + [str(a) for a in e.get("args") or []]
                + [str(e.get("url", ""))]
            )
            if any(ph in target for ph in ("SEU-TOKEN", "YOUR-KEY", "SUA-CHAVE", "SUA-SENHA")):
                self._state[name] = {
                    "state": "erro",
                    "error": "placeholder de token no config — substitua pelo token real",
                }
                continue
            try:
                srv = self._make(e)
                srv.start()
                raw_tools = srv.list_tools()
                self._servers[name] = srv
                mapped_names = []
                for t in raw_tools:
                    orig = str(t.get("name") or "")
                    if not orig:
                        continue
                    mapped = map_tool_name(name, orig)
                    self._map[mapped] = (name, orig)
                    self._meta[mapped] = t
                    mapped_names.append(mapped)
                self._server_tools[name] = mapped_names
                self._state[name] = {"state": "ativo", "error": None}
                try:
                    from . import activity
                    activity.log(self.cfg, "mcp",
                                 f"🔌 '{name}' ativo ({len(mapped_names)} ferramentas)")
                except Exception:  # noqa: BLE001
                    pass
            except Exception as exc:
                self._servers.pop(name, None)
                self._server_tools.pop(name, None)
                self._state[name] = {"state": "erro", "error": str(exc)[:400]}
                try:
                    from . import activity
                    activity.log(self.cfg, "mcp",
                                 f"✖ '{name}' falhou ao subir: {str(exc)[:90]}")
                except Exception:  # noqa: BLE001
                    pass

    def _ensure(self) -> None:
        # Inicia UMA vez automaticamente. Servidores em erro NÃO são retentados
        # a cada mensagem (evita travar o chat esperando timeout) — use a GUI
        # (▶ ativar / ⟳ reiniciar) ou a API para tentar de novo.
        if not self._tried:
            self.start_all()

    def stop_all(self) -> None:
        for srv in self._servers.values():
            try:
                srv.stop()
            except Exception:
                pass
        self._servers.clear()
        self._map.clear()
        self._meta.clear()
        self._server_tools.clear()
        self._tried = False

    def restart(self) -> None:
        self.stop_all()
        self.start_all()

    def restart_server(self, name: str) -> None:
        """Reinicia UM servidor (usado pelo supervisor de saúde)."""
        entry = next((e for e in self._entries() if str(e.get("name")) == name), None)
        if entry is None:
            raise MCPError(f"servidor MCP '{name}' não está no config")
        srv = self._servers.pop(name, None)
        if srv:
            try:
                srv.stop()
            except Exception:
                pass
        # remove as ferramentas dele dos mapas
        for mapped in list(self._map):
            if self._map[mapped][0] == name:
                self._map.pop(mapped, None)
                self._meta.pop(mapped, None)
        self._server_tools.pop(name, None)
        # sobe de novo (mesmo caminho do start_all, sem placeholders)
        target = " ".join(
            [str(entry.get("command", ""))] + [str(a) for a in entry.get("args") or []]
            + [str(entry.get("url", ""))]
        )
        if any(ph in target for ph in ("SEU-TOKEN", "YOUR-KEY", "SUA-CHAVE", "SUA-SENHA")):
            raise MCPError("placeholder de token no config")
        srv = self._make(entry)
        srv.start()
        raw_tools = srv.list_tools()
        self._servers[name] = srv
        mapped_names = []
        for tool in raw_tools:
            orig = str(tool.get("name") or "")
            if not orig:
                continue
            mapped = map_tool_name(name, orig)
            self._map[mapped] = (name, orig)
            self._meta[mapped] = tool
            mapped_names.append(mapped)
        self._server_tools[name] = mapped_names
        self._state[name] = {"state": "ativo", "error": None}

    # ------------------------------------------------------------- ferramentas
    def openai_tools(self) -> list[dict]:
        if not self._entries():
            return []
        self._ensure()
        tools = []
        for mapped, meta in self._meta.items():
            schema = meta.get("inputSchema") or {"type": "object", "properties": {}}
            desc = str(meta.get("description") or mapped).strip()[:600] or mapped
            tools.append(
                {
                    "type": "function",
                    "function": {
                        "name": mapped,
                        "description": f"[MCP] {desc}",
                        "parameters": schema,
                    },
                }
            )
        return tools

    def handles(self, name: str) -> bool:
        return name in self._map

    def call(self, mapped: str, arguments: dict) -> dict:
        if mapped not in self._map:
            return {"ok": False, "output": f"ERRO: ferramenta MCP desconhecida: {mapped}"}
        sname, orig = self._map[mapped]
        srv = self._servers.get(sname)
        if not srv or not srv.alive():
            return {
                "ok": False,
                "output": f"ERRO: servidor MCP '{sname}' não está ativo "
                          "(ative no Painel → Servidores MCP e tente de novo)",
            }
        try:
            out = srv.call_tool(orig, arguments or {})
            return {"ok": True, "output": out[:6000]}
        except Exception as exc:
            # uma tentativa de recuperação: reinicia o servidor e repete
            try:
                srv.stop()
                srv.start()
                out = srv.call_tool(orig, arguments or {})
                return {"ok": True, "output": out[:6000]}
            except Exception:
                return {"ok": False, "output": f"ERRO MCP ({sname}.{orig}): {exc}"}

    # ---------------------------------------------------------------- status
    # ------------------------- recursos e prompts (v8.6.0, Genkit parity)
    def _vivos(self) -> list[BaseMCPServer]:
        try:
            self.start_all()
        except Exception:  # noqa: BLE001 — start_all já marca o estado
            pass
        return [srv for srv in self._servers.values() if srv.alive()]

    def listar_recursos(self) -> list[dict]:
        out = []
        for srv in self._vivos():
            for r in srv.list_resources():
                out.append({"servidor": srv.name,
                            "uri": r.get("uri", ""),
                            "nome": r.get("name", ""),
                            "descricao": (r.get("description") or "")[:120]})
        return out

    def ler_recurso(self, uri: str, servidor: str = "") -> str:
        for srv in self._vivos():
            if servidor and srv.name != servidor:
                continue
            if any(r.get("uri") == uri for r in srv.list_resources()):
                return srv.read_resource(uri)
        return ("✖ recurso não encontrado: " + uri
                + (f" (servidor {servidor})" if servidor else ""))

    def listar_prompts(self) -> list[dict]:
        out = []
        for srv in self._vivos():
            for pr in srv.list_prompts():
                out.append({"servidor": srv.name, "nome": pr.get("name", ""),
                            "descricao": (pr.get("description") or "")[:120]})
        return out

    def obter_prompt(self, nome: str, args: dict | None = None,
                     servidor: str = "") -> str:
        for srv in self._vivos():
            if servidor and srv.name != servidor:
                continue
            if any(pr.get("name") == nome for pr in srv.list_prompts()):
                return srv.get_prompt(nome, args)
        return ("✖ prompt não encontrado: " + nome
                + (f" (servidor {servidor})" if servidor else ""))

    def status(self) -> list[dict]:
        out = []
        for e in self._entries():
            name = str(e["name"])
            srv = self._servers.get(name)
            if srv and srv.alive():
                state = "ativo"
                error = None
            elif name in self._state:
                state = self._state[name]["state"]
                error = self._state[name].get("error")
            else:
                state, error = "inativo", None
            transport = "http" if e.get("url") else "stdio"
            target = e.get("url") or " ".join([str(e.get("command", ""))] + [str(a) for a in e.get("args") or []])
            out.append(
                {
                    "name": name,
                    "transport": transport,
                    "target": target[:120],
                    "state": state,
                    "error": error,
                    "tools": self._server_tools.get(name, []),
                }
            )
        return out


def _shutdown_all() -> None:
    for mgr in _MANAGERS.values():
        try:
            mgr.stop_all()
        except Exception:
            pass


atexit.register(_shutdown_all)
