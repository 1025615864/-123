import json
from http.server import BaseHTTPRequestHandler, HTTPServer


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        return

    def _send(self, status: int, obj: object) -> None:
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(int(status))
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:  # noqa: N802
        content_length = int(self.headers.get("Content-Length", "0") or 0)
        raw = self.rfile.read(content_length) if content_length > 0 else b""

        try:
            payload = json.loads(raw.decode("utf-8") or "{}")
        except Exception:
            payload = {}

        if isinstance(payload, dict) and "response_format" in payload:
            self._send(422, {"error": {"message": "response_format not supported"}})
            return

        content = json.dumps(
            {
                "summary": "stub summary",
                "highlights": ["h1", "h2", "h3"],
                "keywords": ["k1", "k2", "k3", "k4", "k5"],
            },
            ensure_ascii=False,
        )

        self._send(200, {"choices": [{"message": {"content": content}}]})


def main() -> None:
    host = "127.0.0.1"
    port = 9011
    print(f"mock openai server on http://{host}:{port}")
    HTTPServer((host, port), Handler).serve_forever()


if __name__ == "__main__":
    main()
