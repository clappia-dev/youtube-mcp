import http.server
import socketserver
import threading
import urllib.parse

class OAuthCallbackHandler(http.server.SimpleHTTPRequestHandler):
    authorization_code = None
    state = None
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
    
    def do_GET(self):
        parsed_path = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed_path.query)
        
        if parsed_path.path == '/oauth2callback':
            if 'state' in params and 'code' in params:
                OAuthCallbackHandler.state = params['state'][0]
                OAuthCallbackHandler.authorization_code = params['code'][0]
            
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(bytes("""
            <html>
            <head><title>Authentication Successful</title></head>
            <body>
                <h1>Authentication Successful!</h1>
                <p>You can close this window and return to Claude Desktop.</p>
            </body>
            </html>
            """, "utf-8"))
            
            threading.Thread(target=self.server.shutdown).start()
        else:
            self.send_response(404)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(b'Not found')

    def log_message(self, format, *args):
        return

def start_oauth_server(port):
    handler = OAuthCallbackHandler
    server = socketserver.TCPServer(("", port), handler)
    print(f"Starting OAuth callback server on port {port}")
    server.timeout = 300
    server.serve_forever()
    return server, handler 