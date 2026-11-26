"""HTTP interface for the in-memory URL shortener."""

import argparse
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.linear_probing import LinearProbingHashTable
from src.shortener import URLShortener


_TEMPLATE_PATH = Path(__file__).parent / "templates" / "index.html"
_MAX_REQUEST_BYTES = 1_048_576


def create_server(
    port: int = 8000,
    shortener: URLShortener | None = None,
    host: str = "127.0.0.1",
) -> ThreadingHTTPServer:
    """Create an HTTP server, optionally using an existing shortener instance."""
    service = shortener if shortener is not None else URLShortener()
    linear_table = LinearProbingHashTable()

    class ShortenerRequestHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            path = urlsplit(self.path).path
            if path == "/":
                self._send_bytes(
                    200,
                    _TEMPLATE_PATH.read_bytes(),
                    "text/html; charset=utf-8",
                )
                return

            if not path.startswith("/") or "/" in path[1:] or not path[1:]:
                self._send_error(404, "Not found")
                return

            code = unquote(path[1:])
            try:
                original_url = service.expand(code)
            except KeyError:
                self._send_error(404, "Short URL not found")
                return

            self.send_response(302)
            self.send_header("Location", original_url)
            self.send_header("Content-Length", "0")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()

        def do_POST(self) -> None:
            path = urlsplit(self.path).path
            if path not in ("/shorten", "/visualize"):
                self._send_error(404, "Not found")
                return

            payload = self._read_json()
            if payload is None:
                return

            if path == "/shorten":
                self._shorten(payload)
            else:
                self._visualize(payload)

        def _shorten(self, payload: dict[str, object]) -> None:
            url = payload.get("url")
            if not isinstance(url, str):
                self._send_error(400, "The 'url' field must be a string")
                return

            try:
                origin = self._public_origin()
                code, created = service.shorten_with_status(url)
            except ValueError as error:
                self._send_error(400, str(error))
                return
            linear_table.put(url, code)

            response_body = json.dumps(
                {
                    "code": code,
                    "short_url": f"{origin}/{code}",
                },
                ensure_ascii=False,
            ).encode("utf-8")
            self._send_bytes(
                201 if created else 200,
                response_body,
                "application/json; charset=utf-8",
            )

        def _visualize(self, payload: dict[str, object]) -> None:
            key = payload.get("key")
            if not isinstance(key, str):
                self._send_error(400, "The 'key' field must be a string")
                return

            collision_resolution = payload.get(
                "collision_resolution",
                "separate_chaining",
            )
            if collision_resolution not in (
                "separate_chaining",
                "linear_probing",
            ):
                self._send_error(400, "Unknown collision resolution method")
                return

            try:
                if collision_resolution == "separate_chaining":
                    trace = service.inspect_url_lookup(key)
                else:
                    service.inspect_url_lookup(key)
                    probe_trace = linear_table.inspect_lookup(key)
            except ValueError as error:
                self._send_error(400, str(error))
                return

            if collision_resolution == "separate_chaining":
                chain = []
                for index, (stored_key, value) in enumerate(trace.bucket_entries):
                    compared = index < trace.comparisons
                    matches = compared and stored_key == key
                    chain.append(
                        {
                            "key": stored_key,
                            "value": value,
                            "compared": compared,
                            "comparison_number": index + 1 if compared else None,
                            "matches": matches,
                        }
                    )

                response_body = {
                    "key": key,
                    "collision_resolution": collision_resolution,
                    "steps": [
                        {
                            "character": step.character,
                            "codepoint": step.codepoint,
                            "previous_hash": step.previous_hash,
                            "current_hash": step.current_hash,
                        }
                        for step in trace.steps
                    ],
                    "bucket_index": trace.bucket_index,
                    "chain": chain,
                    "chain_length": len(trace.bucket_entries),
                    "collision": len(trace.bucket_entries) > 1,
                    "found": trace.found,
                    "value": trace.value,
                    "comparisons": trace.comparisons,
                }
            else:
                probe_entries = [
                    {
                        "slot_index": entry.slot_index,
                        "key": entry.key,
                        "value": entry.value,
                        "occupied": entry.occupied,
                        "matches": entry.matches,
                        "next_slot": (
                            (entry.slot_index + 1) % linear_table.capacity
                            if entry.occupied and not entry.matches
                            else None
                        ),
                    }
                    for entry in probe_trace.probes
                ]
                response_body = {
                    "key": key,
                    "collision_resolution": collision_resolution,
                    "steps": [
                        {
                            "character": step.character,
                            "codepoint": step.codepoint,
                            "previous_hash": step.previous_hash,
                            "current_hash": step.current_hash,
                        }
                        for step in probe_trace.steps
                    ],
                    "initial_bucket": probe_trace.initial_bucket,
                    "probes": probe_entries,
                    "final_slot": probe_trace.final_slot,
                    "found": probe_trace.found,
                    "value": probe_trace.value,
                    "slot_probes": probe_trace.slot_probes,
                }
            self._send_bytes(
                200,
                json.dumps(response_body, ensure_ascii=False).encode("utf-8"),
                "application/json; charset=utf-8",
            )

        def _read_json(self) -> dict[str, object] | None:
            content_length = self.headers.get("Content-Length")
            try:
                request_size = int(content_length) if content_length is not None else 0
            except ValueError:
                self._send_error(400, "Invalid Content-Length")
                return None

            if request_size <= 0 or request_size > _MAX_REQUEST_BYTES:
                self._send_error(400, "Request body must be between 1 byte and 1 MiB")
                return None

            try:
                payload = json.loads(self.rfile.read(request_size).decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                self._send_error(400, "Request body must be valid JSON")
                return None

            if not isinstance(payload, dict):
                self._send_error(400, "Request body must be a JSON object")
                return None
            return payload

        def _public_origin(self) -> str:
            forwarded_host = self.headers.get("X-Forwarded-Host")
            host_header = forwarded_host or self.headers.get("Host")
            if host_header is None:
                host_header = f"localhost:{self.server.server_port}"
            host = host_header.split(",", maxsplit=1)[0].strip()

            forwarded_proto = self.headers.get("X-Forwarded-Proto", "http")
            scheme = forwarded_proto.split(",", maxsplit=1)[0].strip().lower()
            if scheme not in ("http", "https"):
                raise ValueError("Forwarded protocol must be http or https")

            try:
                parsed_host = urlsplit(f"//{host}")
                parsed_host.port
            except ValueError as error:
                raise ValueError("Invalid request host") from error
            if (
                not host
                or not parsed_host.hostname
                or parsed_host.username is not None
                or parsed_host.password is not None
                or parsed_host.path
                or parsed_host.query
                or parsed_host.fragment
                or any(character.isspace() for character in host)
            ):
                raise ValueError("Invalid request host")
            return f"{scheme}://{host}"

        def _send_error(self, status: int, message: str) -> None:
            body = json.dumps({"error": message}, ensure_ascii=False).encode("utf-8")
            self._send_bytes(
                status,
                body,
                "application/json; charset=utf-8",
            )

        def _send_bytes(self, status: int, body: bytes, content_type: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

    server = ThreadingHTTPServer((host, port), ShortenerRequestHandler)
    server.daemon_threads = True
    return server


def run_server(port: int) -> None:
    """Run the HTTP service on all interfaces for local and forwarded access."""
    with create_server(port=port, host="0.0.0.0") as server:
        print(f"URL shortener listening on port {server.server_port}")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nStopping URL shortener")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the URL shortener service")
    parser.add_argument("--port", type=int, default=8000)
    arguments = parser.parse_args()
    run_server(arguments.port)


if __name__ == "__main__":
    main()
