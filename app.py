import argparse
import json
import os
import sqlite3
import sys
import urllib.error
import urllib.request
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse


def load_env(path=".env"):
    env_path = Path(path)
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_env()

VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "dev-token")
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN", "")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID", "")
PORT = int(os.getenv("PORT", "3000"))
DB_PATH = os.getenv("DB_PATH", "notes.db")


class NotesStore:
    def __init__(self, db_path):
        self.db_path = db_path
        self.init_db()

    def connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self):
        with self.connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS notes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    phone TEXT NOT NULL,
                    body TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_notes_phone_created ON notes(phone, created_at)"
            )

    def add(self, phone, body):
        created_at = datetime.now().isoformat(timespec="seconds")
        with self.connect() as conn:
            cursor = conn.execute(
                "INSERT INTO notes (phone, body, created_at) VALUES (?, ?, ?)",
                (phone, body, created_at),
            )
            note_id = cursor.lastrowid
        return {"id": note_id, "body": body, "created_at": created_at}

    def list_recent(self, phone, limit=10):
        with self.connect() as conn:
            return conn.execute(
                """
                SELECT id, body, created_at
                FROM notes
                WHERE phone = ?
                ORDER BY datetime(created_at) DESC, id DESC
                LIMIT ?
                """,
                (phone, limit),
            ).fetchall()

    def search(self, phone, term, limit=10):
        with self.connect() as conn:
            return conn.execute(
                """
                SELECT id, body, created_at
                FROM notes
                WHERE phone = ? AND body LIKE ?
                ORDER BY datetime(created_at) DESC, id DESC
                LIMIT ?
                """,
                (phone, f"%{term}%", limit),
            ).fetchall()

    def today(self, phone):
        today = datetime.now().date().isoformat()
        with self.connect() as conn:
            return conn.execute(
                """
                SELECT id, body, created_at
                FROM notes
                WHERE phone = ? AND date(created_at) = ?
                ORDER BY datetime(created_at) DESC, id DESC
                """,
                (phone, today),
            ).fetchall()

    def delete(self, phone, note_id):
        with self.connect() as conn:
            cursor = conn.execute(
                "DELETE FROM notes WHERE phone = ? AND id = ?",
                (phone, note_id),
            )
            return cursor.rowcount > 0


store = NotesStore(DB_PATH)


def format_notes(rows):
    if not rows:
        return "Nenhuma anotacao encontrada."

    lines = []
    for row in rows:
        created = row["created_at"].replace("T", " ")[:16]
        lines.append(f"#{row['id']} - {row['body']} ({created})")
    return "\n".join(lines)


def help_text():
    return (
        "Pode mandar qualquer texto que eu salvo como anotacao.\n\n"
        "Comandos:\n"
        "/listar - mostra as ultimas notas\n"
        "/buscar texto - procura uma nota\n"
        "/apagar 3 - apaga a nota #3\n"
        "/hoje - mostra notas de hoje\n"
        "/ajuda - mostra esta ajuda"
    )


def handle_message(phone, text):
    clean = text.strip()
    if not clean:
        return "Manda uma anotacao em texto que eu salvo."

    if clean.startswith("/"):
        parts = clean.split(maxsplit=1)
        command = parts[0].lower()
        arg = parts[1].strip() if len(parts) > 1 else ""

        if command in {"/ajuda", "/help"}:
            return help_text()

        if command == "/listar":
            return format_notes(store.list_recent(phone))

        if command == "/buscar":
            if not arg:
                return "Use assim: /buscar texto"
            return format_notes(store.search(phone, arg))

        if command == "/apagar":
            if not arg.isdigit():
                return "Use assim: /apagar 3"
            deleted = store.delete(phone, int(arg))
            return "Anotacao apagada." if deleted else "Nao encontrei essa anotacao."

        if command == "/hoje":
            return format_notes(store.today(phone))

        return "Nao conheco esse comando.\n\n" + help_text()

    note = store.add(phone, clean)
    return f"Anotado.\n#{note['id']} - {note['body']}"


def send_whatsapp_text(to, body):
    if not WHATSAPP_TOKEN or not PHONE_NUMBER_ID:
        print(f"[modo local] Resposta para {to}: {body}")
        return

    url = f"https://graph.facebook.com/v20.0/{PHONE_NUMBER_ID}/messages"
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": body},
    }
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {WHATSAPP_TOKEN}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            response.read()
    except urllib.error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        print(f"Erro ao enviar WhatsApp: HTTP {exc.code} {details}", file=sys.stderr)
    except urllib.error.URLError as exc:
        print(f"Erro de rede ao enviar WhatsApp: {exc}", file=sys.stderr)


def extract_messages(payload):
    messages = []
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            for message in value.get("messages", []):
                if message.get("type") != "text":
                    continue
                phone = message.get("from")
                text = message.get("text", {}).get("body", "")
                if phone and text:
                    messages.append((phone, text))
    return messages


class WebhookHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print("%s - %s" % (self.address_string(), fmt % args))

    def send_text(self, status, body):
        encoded = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path != "/webhook":
            self.send_text(404, "Not found")
            return

        params = parse_qs(parsed.query)
        mode = params.get("hub.mode", [""])[0]
        token = params.get("hub.verify_token", [""])[0]
        challenge = params.get("hub.challenge", [""])[0]

        if mode == "subscribe" and token == VERIFY_TOKEN:
            self.send_text(200, challenge)
            return

        self.send_text(403, "Forbidden")

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path != "/webhook":
            self.send_text(404, "Not found")
            return

        length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(length)

        try:
            payload = json.loads(raw_body.decode("utf-8"))
        except json.JSONDecodeError:
            self.send_text(400, "Invalid JSON")
            return

        for phone, text in extract_messages(payload):
            reply = handle_message(phone, text)
            send_whatsapp_text(phone, reply)

        self.send_text(200, "OK")


def run_server():
    server = ThreadingHTTPServer(("0.0.0.0", PORT), WebhookHandler)
    print(f"Servidor rodando em http://localhost:{PORT}")
    print(f"Webhook: http://localhost:{PORT}/webhook")
    server.serve_forever()


def run_chat():
    phone = "local"
    print("Modo chat local. Digite /sair para encerrar.")
    while True:
        try:
            text = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if text.lower() in {"/sair", "/exit", "exit"}:
            return
        print(handle_message(phone, text))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="WhatsApp Notas Bot")
    parser.add_argument("--chat", action="store_true", help="testa o bot no terminal")
    args = parser.parse_args()

    if args.chat:
        run_chat()
    else:
        run_server()
