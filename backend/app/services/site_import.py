"""Fetch a small public page for local, operator-reviewed reference context."""

from __future__ import annotations

import http.client
import ipaddress
import re
import socket
import ssl
from html.parser import HTMLParser
from urllib.parse import quote, urljoin, urlsplit

from app.services.content_matching import suggest_review_points
from app.services.pdf_import import MAX_REFERENCE_CHARS

MAX_SITE_BYTES = 1024 * 1024
MAX_REDIRECTS = 3
TIMEOUT_SECONDS = 5


class SiteImportError(ValueError):
    pass


class _PinnedHTTP(http.client.HTTPConnection):
    def __init__(self, host: str, port: int, ip: str):
        super().__init__(host, port, timeout=TIMEOUT_SECONDS)
        self._ip = ip

    def connect(self):
        self.sock = socket.create_connection((self._ip, self.port), self.timeout)


class _PinnedHTTPS(http.client.HTTPSConnection):
    def __init__(self, host: str, port: int, ip: str):
        super().__init__(host, port, timeout=TIMEOUT_SECONDS, context=ssl.create_default_context())
        self._ip = ip

    def connect(self):
        raw = socket.create_connection((self._ip, self.port), self.timeout)
        try:
            self.sock = self._context.wrap_socket(raw, server_hostname=self.host)
        except Exception:
            raw.close()
            raise


def _target(url: str) -> tuple[str, str, int, str, str]:
    try:
        parsed = urlsplit(url.strip())
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise SiteImportError("Use um link http:// ou https:// de um site público.")
        if parsed.username or parsed.password:
            raise SiteImportError("Links com usuário ou senha não são aceitos.")
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        if port != (443 if parsed.scheme == "https" else 80):
            raise SiteImportError("Use a porta padrão do site (80 ou 443).")
        host = parsed.hostname.encode("idna").decode("ascii")
        addresses = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
        ips = {ipaddress.ip_address(info[4][0]) for info in addresses}
        if not ips or any(not ip.is_global for ip in ips):
            raise SiteImportError("O link deve apontar para um site público.")
        # HTTP request targets must be ASCII. Preserve existing percent escapes
        # while encoding Unicode paths such as /wiki/Mecânica_hamiltoniana.
        path = quote(parsed.path or "/", safe="/%:@!$&'()*+,;=-._~")
        if parsed.query:
            path += "?" + quote(parsed.query, safe="/%:@!$&'()*+,;=?-._~")
        return parsed.scheme, host, port, str(min(ips, key=lambda ip: (ip.version, str(ip)))), path
    except (ValueError, UnicodeError) as exc:
        if isinstance(exc, SiteImportError):
            raise
        raise SiteImportError("Link inválido. Confira o endereço do site.") from exc
    except OSError as exc:
        raise SiteImportError("Não foi possível localizar esse site.") from exc


def _load(target: tuple[str, str, int, str, str]) -> tuple[int, dict[str, str], bytes]:
    scheme, host, port, ip, path = target
    connection = (_PinnedHTTPS if scheme == "https" else _PinnedHTTP)(host, port, ip)
    try:
        connection.request(
            "GET", path, headers={"Accept": "text/html,text/plain", "User-Agent": "NekoMind/1.0"}
        )
        response = connection.getresponse()
        headers = {name.lower(): value for name, value in response.getheaders()}
        declared = headers.get("content-length")
        if declared and declared.isdigit() and int(declared) > MAX_SITE_BYTES:
            raise SiteImportError("A página excede 1 MB. Use um trecho menor.")
        body = response.read(MAX_SITE_BYTES + 1)
        if len(body) > MAX_SITE_BYTES:
            raise SiteImportError("A página excede 1 MB. Use um trecho menor.")
        return response.status, headers, body
    except (TimeoutError, OSError, ssl.SSLError, http.client.HTTPException) as exc:
        raise SiteImportError(
            "Não foi possível abrir o site. Confira o link e tente novamente."
        ) from exc
    finally:
        connection.close()


class _VisibleText(HTMLParser):
    HIDDEN = frozenset({"script", "style", "noscript", "svg", "nav", "footer"})
    BLOCK = frozenset({"p", "li", "h1", "h2", "h3", "h4", "article", "section", "br", "div"})

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.hidden_depth = 0
        self.parts: list[str] = []
        self.in_title = False
        self.title_parts: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag in self.HIDDEN:
            self.hidden_depth += 1
        if tag == "title":
            self.in_title = True
        if tag in self.BLOCK:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in self.HIDDEN and self.hidden_depth:
            self.hidden_depth -= 1
        if tag == "title":
            self.in_title = False
        if tag in self.BLOCK:
            self.parts.append("\n")

    def handle_data(self, data):
        if self.in_title:
            self.title_parts.append(data)
        elif not self.hidden_depth:
            self.parts.append(data)


def import_site(url: str) -> dict:
    current = url.strip()
    for _ in range(MAX_REDIRECTS + 1):
        target = _target(current)  # Validate and pin every redirect hop.
        status, headers, body = _load(target)
        if status in {301, 302, 303, 307, 308}:
            location = headers.get("location")
            if not location:
                raise SiteImportError("O site redirecionou sem informar o destino.")
            current = urljoin(current, location)
            continue
        if status != 200:
            raise SiteImportError(f"O site respondeu com HTTP {status}.")
        kind = headers.get("content-type", "").split(";", 1)[0].strip().lower()
        if kind not in {"text/html", "text/plain"}:
            raise SiteImportError("Esse link não contém uma página de texto ou HTML.")
        if headers.get("content-encoding", "identity").lower() != "identity":
            raise SiteImportError(
                "O site enviou texto comprimido não compatível. Cole o trecho manualmente."
            )
        encoding_match = re.search(
            r"charset=([\w-]+)", headers.get("content-type", ""), re.IGNORECASE
        )
        encoding = encoding_match.group(1) if encoding_match else "utf-8"
        try:
            decoded = body.decode(encoding, errors="replace")
        except LookupError as exc:
            raise SiteImportError("A codificação da página não é reconhecida.") from exc
        if kind == "text/html":
            parser = _VisibleText()
            parser.feed(decoded)
            raw = "".join(parser.parts)
            title = " ".join(parser.title_parts).strip() or target[1]
        else:
            raw, title = decoded, target[1]
        text = "\n".join(
            line for line in (re.sub(r"\s+", " ", p).strip() for p in raw.splitlines()) if line
        )
        if not text:
            raise SiteImportError("A página não trouxe texto legível. Cole o trecho manualmente.")
        if len(text) > MAX_REFERENCE_CHARS:
            raise SiteImportError("O texto do site excede 50 mil caracteres. Cole um trecho menor.")
        return {
            "title": title[:200],
            "text": text,
            "points": suggest_review_points(text),
            "source": "url",
        }
    raise SiteImportError("O link redirecionou muitas vezes.")
