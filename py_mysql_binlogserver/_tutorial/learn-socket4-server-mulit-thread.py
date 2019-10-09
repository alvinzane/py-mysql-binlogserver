import socket
import threading
import socketserver


class ThreadedTCPRequestHandler(socketserver.BaseRequestHandler):

    def handle(self):
        data = str(self.request.recv(1024), 'ascii')
        response = bytes("{} = {}".format(data, eval(data)), 'ascii')
        self.request.sendall(response)


class ThreadedTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    pass


def client(ip, port, message):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.connect((ip, port))
        sock.sendall(bytes(message, 'ascii'))
        response = str(sock.recv(1024), 'ascii')
        print("Send: {}".format(message))
        print("Received: {}".format(response))
        print("")


if __name__ == "__main__":
    # Port 0 means to select an arbitrary unused port
    HOST, PORT = "localhost", 0

    server = ThreadedTCPServer((HOST, PORT), ThreadedTCPRequestHandler)
    with server:
        ip, port = server.server_address
        server_thread = threading.Thread(target=server.serve_forever)
        # Exit the server thread when the main thread terminates
        server_thread.daemon = True
        server_thread.start()
        print(f"Calculator Server start at {ip} : {port}")

        client(ip, port, "1+1")
        client(ip, port, "3+2-5")
        client(ip, port, "12345679*81")

        server.shutdown()

