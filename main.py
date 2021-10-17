import socket
from threading import Thread

# Contains a HTTP request in a convenient form
class HttpRequest:
    def __init__(self, original_request: bytes):
        self.original = original_request

        self.meta = ''
        self.headers = {}

        self.host = None
        self.port = None

    @classmethod
    # Parses the request into parts
    def parse(cls, request: bytes):
        request_instance = cls(request)

        http_parts = request.split(b"\r\n\r\n")
        http_head = http_parts[0].split(b"\r\n")
        request_instance.meta = http_head[0].decode("utf-8")
        http_head = http_head[1:]

        if len(http_parts) >= 2:
            request_instance.bytes = http_parts[1]

        for header in http_head:
            key, value = header.split(b": ")
            request_instance.headers[key.decode("utf-8")] = value.decode("utf-8")

        # If request contains port, get it, else port = 80
        if ':' in request_instance.headers['Host']:
            host, port = request_instance.headers['Host'].split(':')
        else:
            host, port = request_instance.headers['Host'], 80

        request_instance.host = host
        request_instance.port = int(port)

        return request_instance

# Main Proxy server class
class ProxyServer:
    def __init__(self, host="0.0.0.0", port=3000):
        self.host = host
        self.port = port
        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.buffer_size = 8192

    def run(self):
        self.client_socket.bind((self.host, self.port))
        self.client_socket.listen(50)
        print(f"Proxy server is running on {self.host}:{self.port}")

        # Accept connections from clients and handle requests
        while True:
            client, (client_host, client_port) = self.client_socket.accept()
            print(f"Accept connection from {client_host}:{client_port}")
            Thread(target=self.handle_request, args=(client,)).start()

    def handle_request(self, client):
        data = client.recv(self.buffer_size)
        request = HttpRequest.parse(data)
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        if 'CONNECT' in request.meta:
            self.start_https_tunnel(request, client, server)
        else:
            server.connect((request.host, request.port))
            server.sendall(request.original)

            response = server.recv(self.buffer_size)
            try:
                # Get response while size less then Content Length
                parsed_response = HttpRequest.parse(response)
                while len(response) < parsed_response.headers['Content-Length']:
                    response += server.recv(self.buffer_size)
            except:
                # Get response to the end
                while not response.endswith(b'0\r\n\r\n'):
                    part = server.recv(self.buffer_size)
                    response += part

            client.sendall(response)

            server.close()
            client.close()

    def start_https_tunnel(self, request, client, server):
        try:
            # Connect to server and send OK to client
            server.connect((request.host, request.port))
            reply = "HTTP/1.1 200 Connection established\r\n"
            reply += "ProxyServer-agent: PyProxyServer\r\n\r\n"
            client.sendall(reply.encode())
        except socket.error as err:
            print(err)

        # Sockets will return immediately if there is no data available
        client.setblocking(False)
        server.setblocking(False)

        # Data exchange
        while True:
            try:
                data = client.recv(self.buffer_size)
                if not data:
                    client.close()
                    break
                server.sendall(data)
            except socket.error:
                pass
            try:
                reply = server.recv(self.buffer_size)
                if not reply:
                    server.close()
                    break
                client.sendall(reply)
            except socket.error:
                pass


proxy = ProxyServer()
proxy.run()