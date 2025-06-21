import os
import json
import time
from collections import defaultdict, deque
from urllib.parse import quote
from http.server import BaseHTTPRequestHandler, HTTPServer
from dotenv import load_dotenv
import requests

# Load environment variables from .env file
load_dotenv()

# --- Configuration ---
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")
OLLAMA_ENDPOINT = "http://localhost:11434/api/generate"

# API Key for your custom server (important for security)
SERVER_API_KEY = os.getenv("SERVER_API_KEY")
if not SERVER_API_KEY:
    print("Warning: SERVER_API_KEY not found in .env file.")
    print("Please add SERVER_API_KEY=your_secret_key_here to your .env file for API security.")
    # Exit if no API key is set, as it's critical for security
    exit("Server cannot run without SERVER_API_KEY. Please set it in your .env file.")

HOST = 'localhost'
PORT = 8080

# --- Rate Limiting Configuration ---
# Store request timestamps per API key (or IP if no key)
# { 'api_key_or_ip': deque([timestamp1, timestamp2, ...]) }
REQUEST_LOGS = defaultdict(deque)

# Rate limit: Max N requests per M seconds
MAX_REQUESTS_PER_WINDOW = 5 # Example: 5 requests
RATE_LIMIT_WINDOW_SECONDS = 60 # Example: per 60 seconds (1 minute)

# --- Handler with Security and Rate Limiting ---
class SimpleHandler(BaseHTTPRequestHandler):
    # Add CORS headers for local development if needed by a frontend app
    def _set_headers(self, status_code=200, content_type='application/json'):
        self.send_response(status_code)
        self.send_header('Content-type', content_type)
        # Allow requests from any origin for local testing. In production, restrict this.
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, X-API-Key')
        self.end_headers()

    def do_OPTIONS(self):
        # Handle CORS preflight requests
        self._set_headers(200)

    def do_POST(self):
        # --- Path Check ---
        if self.path != "/places":
            self._set_headers(404, 'text/plain')
            self.wfile.write(b"Not Found")
            return

        # --- API Key Authentication ---
        client_api_key = self.headers.get('X-API-Key')
        if not client_api_key or client_api_key != SERVER_API_KEY:
            self._set_headers(401, 'text/plain')
            self.wfile.write(b"Unauthorized: Invalid or missing X-API-Key header.")
            return

        # --- Rate Limiting ---
        # Identify the client by their API key for rate limiting
        # For a truly robust system, consider IP + API key or a user ID.
        client_identifier = client_api_key

        current_time = time.time()
        
        # Clean up old requests outside the window
        while REQUEST_LOGS[client_identifier] and \
              REQUEST_LOGS[client_identifier][0] < current_time - RATE_LIMIT_WINDOW_SECONDS:
            REQUEST_LOGS[client_identifier].popleft()

        # Check if the limit is exceeded
        if len(REQUEST_LOGS[client_identifier]) >= MAX_REQUESTS_PER_WINDOW:
            self._set_headers(429, 'text/plain')
            # Suggest when to retry
            retry_after = int(RATE_LIMIT_WINDOW_SECONDS - (current_time - REQUEST_LOGS[client_identifier][0])) + 1
            self.send_header('Retry-After', str(retry_after))
            self.wfile.write(f"Too Many Requests. Please try again after {retry_after} seconds.".encode())
            return
        
        # Log the current request
        REQUEST_LOGS[client_identifier].append(current_time)


        # --- Process Request Body ---
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        try:
            body = json.loads(post_data.decode())
            prompt = body.get("prompt", "")
        except json.JSONDecodeError:
            self._set_headers(400, 'text/plain')
            self.wfile.write(b"Invalid JSON body")
            return

        # --- Query LLM via Ollama ---
        llm_payload = {
            "model": "gemma3:1b",
            # Improve prompt to ensure it only returns the query for map.
            # Adding "North Jakarta, Jakarta, Indonesia" as current context for LLM.
            "prompt": f"Given the current location is North Jakarta, Jakarta, Indonesia. Extract a concise Google Maps search query from the following request: '{prompt}'. Only return the query, do not add any other text.",
            "stream": False,
            "options": {
                "temperature": 0.0 # Make the LLM less creative, more direct for query extraction
            }
        }

        try:
            llm_response = requests.post(OLLAMA_ENDPOINT, json=llm_payload)
            llm_response.raise_for_status() # Raises HTTPError for bad responses (4xx or 5xx)
            llm_json = llm_response.json()
            raw_query = llm_json.get("response", "").strip()
            
            # Basic cleaning for LLM output to ensure it's just the query
            # Gemma 1B might still produce conversational filler.
            # This is a heuristic and might need fine-tuning based on actual LLM output.
            if raw_query.lower().startswith("the query is:"):
                raw_query = raw_query[len("the query is:"):].strip()
            elif raw_query.lower().startswith("google maps search query:"):
                raw_query = raw_query[len("google maps search query:"):].strip()
            # Remove quotes if LLM added them
            if raw_query.startswith('"') and raw_query.endswith('"'):
                raw_query = raw_query[1:-1]

        except requests.exceptions.ConnectionError:
            self._set_headers(503, 'text/plain')
            self.wfile.write(b"Service Unavailable: Could not connect to Ollama.")
            return
        except Exception as e:
            self._set_headers(500, 'text/plain')
            self.wfile.write(f"LLM processing error: {str(e)}".encode())
            return

        if not raw_query:
            self._set_headers(400, 'text/plain')
            self.wfile.write(b"Empty or invalid query extracted by LLM.")
            return

        query_encoded = quote(raw_query) # Ensure the query is URL-encoded
        # --- Generate Map Links ---
        # Corrected base URL for Google Maps interactive link
        # The previous 'https://www.google.com/maps/search/?api=1&query=' was likely an artifact or placeholder.
        # Standard interactive Google Maps URL for a search query
        maps_link = f"https://www.google.com/maps/search/?api=1&query={query_encoded}"

        # For embedding a static map image (requires center/markers, not just a query directly)
        # To get latitude/longitude from a query for a static map, you'd need the Geocoding API first.
        # Since the LLM is giving a search query, a direct interactive link is more practical here.
        # If you want a static map, you'd need to add the `get_coordinates` function from the previous example.
        # For now, I'll use the search query with a generic embed URL placeholder that you'd replace with an iframe.
        # Note: Google Maps Embed API is for iframes, not direct image links with a 'q' parameter.
        # A static map would use latitude/longitude.
        map_embed_url = f"https://www.google.com/maps/embed/v1/place?key={GOOGLE_MAPS_API_KEY}&q={query_encoded}"
        
        # If you specifically want a static map image based on the query:
        # You would need to make another Geocoding API call here to get lat/lng from `raw_query`
        # and then use the Maps Static API (as in the previous example's `generate_static_map_link`).
        # For simplicity and direct relevance to a search query, the interactive link is more suitable.
        

        # --- Prepare and Send Response ---
        response_data = {
            "original_prompt": prompt,
            "llm_query_extracted": raw_query,
            "Maps_interactive_link": maps_link,
            "Maps_embed_iframe_url": map_embed_url # Use this in an iframe in a web page
        }

        self._set_headers(200, 'application/json')
        self.wfile.write(json.dumps(response_data).encode('utf-8'))

# --- Server Initialization ---
if __name__ == '__main__':
    # Verify Google Maps API Key existence
    if not GOOGLE_MAPS_API_KEY:
        print("Error: Maps_API_KEY not found in .env file.")
        print("Please ensure it's set for map functionality.")
        exit("Missing Google Maps API Key.")

    server = HTTPServer((HOST, PORT), SimpleHandler)
    print(f"Server running on http://{HOST}:{PORT}")
    print(f"Using Ollama endpoint: {OLLAMA_ENDPOINT}")
    print(f"Rate Limit: {MAX_REQUESTS_PER_WINDOW} requests per {RATE_LIMIT_WINDOW_SECONDS} seconds per client API key.")
    print(f"API Key authentication required via 'X-API-Key' header.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer is shutting down.")
        server.server_close()