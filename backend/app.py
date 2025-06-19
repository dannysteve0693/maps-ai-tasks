import os
import json
from urllib.parse import parse_qs, quote
from http.server import BaseHTTPRequestHandler, HTTPServer
from dotenv import load_dotenv
import requests

load_dotenv()
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")
OLLAMA_ENDPOINT = "http://localhost:11434/api/generate"

HOST = 'localhost'
PORT = 8080

class SimpleHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path != "/places":
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Not Found")
            return

        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        try:
            body = json.loads(post_data.decode())
            prompt = body.get("prompt", "")
        except:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"Invalid JSON body")
            return

        # Query LLM via Ollama
        llm_payload = {
            "model": "gemma3:1b",
            "prompt": f"Extract a concise Google Maps search query from: '{prompt}'. Only return the query.",
            "stream": False
        }

        try:
            llm_response = requests.post(OLLAMA_ENDPOINT, json=llm_payload)
            llm_response.raise_for_status()
            llm_json = llm_response.json()
            raw_query = llm_json.get("response", "").strip()
        except Exception as e:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(f"LLM error: {str(e)}".encode())
            return

        if not raw_query:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"Empty query from LLM")
            return

        query_encoded = quote(raw_query)
        map_embed_url = f"https://www.google.com/maps/embed/v1/search?key={GOOGLE_MAPS_API_KEY}&q={query_encoded}"
        maps_link = f"https://www.google.com/maps/search/?api=1&query={query_encoded}"

        response = {
            "original_prompt": prompt,
            "llm_query": raw_query,
            "llm_raw_response": llm_json.get("response", ""),
            "map_embed_url": map_embed_url,
            "maps_link": maps_link
        }

        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(response).encode())

if __name__ == '__main__':
    server = HTTPServer((HOST, PORT), SimpleHandler)
    print(f"Server running on http://{HOST}:{PORT}")
    server.serve_forever()
