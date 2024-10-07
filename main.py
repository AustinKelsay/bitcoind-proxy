import socket
import ssl
import asyncio
import zmq
import zmq.asyncio
import signal
import struct
import threading
import select
import time
import os

class TCPProxy:

    def __init__(self, host, port, zmq_subscriptions):
        self.host = host
        self.port = port
        self.proxy_host = "0.0.0.0"
        self.zmq_subscriptions = zmq_subscriptions
        self.running = True
        self.server_sockets = []

    def setup_proxy(self):
        for subscription, proxy_port in self.zmq_subscriptions.items():
            retries = 5
            while retries > 0:
                try:
                    server_socket = socket.socket(socket.AF_INET,
                                                  socket.SOCK_STREAM)
                    server_socket.setsockopt(socket.SOL_SOCKET,
                                             socket.SO_REUSEADDR, 1)
                    server_socket.bind((self.proxy_host, proxy_port))
                    server_socket.listen(5)
                    self.server_sockets.append(server_socket)
                    print(
                        f"Listening on {self.proxy_host}:{proxy_port} for {subscription}"
                    )
                    break
                except OSError as e:
                    print(f"Error binding to port {proxy_port}: {e}")
                    retries -= 1
                    if retries == 0:
                        print(
                            f"Failed to bind to port {proxy_port} after multiple attempts. Exiting."
                        )
                        self.stop()
                        return
                    print(
                        f"Retrying in 5 seconds... ({retries} attempts left)")
                    time.sleep(5)

        while self.running:
            try:
                readable, _, _ = select.select(self.server_sockets, [], [],
                                               1.0)
                for server_socket in readable:
                    try:
                        client_socket, _ = server_socket.accept()
                        print(
                            f"Accepted connection from client on port {server_socket.getsockname()[1]}"
                        )
                        client_handler = threading.Thread(
                            target=self.handle_client,
                            args=(client_socket, self.host, self.port))
                        client_handler.start()
                    except Exception as e:
                        print(f"Error accepting connection: {e}")
            except Exception as e:
                print(f"Error in select: {e}")
                if not self.running:
                    break

    def handle_client(self, client_socket, target_host, target_port):
        try:
            target_socket = create_tls_tcp_socket(target_host, target_port)
            if target_socket is None:
                print("Failed to create TLS connection to target. Closing client connection.")
                client_socket.close()
                return

            def forward(source, destination, direction):
                try:
                    while self.running:
                        data = source.recv(4096)
                        if not data:
                            break
                        destination.sendall(data)
                except Exception as e:
                    print(f"Error in {direction} forward: {e}")

            client_thread = threading.Thread(target=forward, args=(client_socket, target_socket, "Client -> Target"))
            target_thread = threading.Thread(target=forward, args=(target_socket, client_socket, "Target -> Client"))
            client_thread.start()
            target_thread.start()
            client_thread.join()
            target_thread.join()
        except Exception as e:
            print(f"Error handling client: {e}")
        finally:
            client_socket.close()

    def stop(self):
        self.running = False
        for sock in self.server_sockets:
            try:
                sock.close()
            except Exception as e:
                print(f"Error closing server socket: {e}")


def create_tls_tcp_socket(hostname, port):
    try:
        ssl_context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
        ssl_context.maximum_version = ssl.TLSVersion.TLSv1_2
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        tcp_sock = socket.create_connection((hostname, port))
        tls_sock = ssl_context.wrap_socket(tcp_sock,
                                           do_handshake_on_connect=True,
                                           server_hostname=hostname)
        print(f"Connected with TLS: {tls_sock.version()}")
        return tls_sock
    except Exception as e:
        print(f"Error creating TLS socket: {e}")
        return None


class ZMQHandler:

    def __init__(self, host, port, topic):
        self.loop = asyncio.new_event_loop()
        self.zmqContext = zmq.asyncio.Context()
        self.running = True
        self.host = host
        self.port = port
        self.topic = topic
        self.zmqSubSocket = None

    async def connect(self):
        retries = 5
        while retries > 0:
            try:
                self.zmqSubSocket = self.zmqContext.socket(zmq.SUB)
                self.zmqSubSocket.setsockopt(zmq.RCVHWM, 0)
                self.zmqSubSocket.setsockopt_string(zmq.SUBSCRIBE, self.topic)
                zmq_address = f"tcp://{self.host}:{self.port}"
                print(f"Connecting to: {zmq_address}")
                self.zmqSubSocket.connect(zmq_address)
                return True
            except zmq.error.ZMQError as e:
                print(f"Error connecting to ZMQ: {e}")
                retries -= 1
                if retries == 0:
                    print(f"Failed to connect to ZMQ after multiple attempts. Exiting.")
                    return False
                print(f"Retrying in 5 seconds... ({retries} attempts left)")
                await asyncio.sleep(5)

    async def handle(self):
        if not await self.connect():
            return

        while self.running:
            try:
                topic, body, seq = await self.zmqSubSocket.recv_multipart()
                sequence = "Unknown"
                if len(seq) == 4:
                    sequence = str(struct.unpack('<I', seq)[-1])
                print(f'- {topic.decode()} ({sequence}) -')
                print(body.hex())
            except Exception as e:
                print(f"Error receiving message: {e}")
                if not self.running:
                    break
                await asyncio.sleep(1)

    def start(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self.handle())

    def stop(self):
        self.running = False
        if self.zmqSubSocket:
            self.zmqSubSocket.close()
        self.zmqContext.term()
        self.loop.stop()


if __name__ == "__main__":
    hostname = os.environ.get("BITCOIND_HOST")
    port = int(os.environ.get("BITCOIND_PORT", 28332))
    zmq_host = os.environ.get("ZMQ_HOST", "127.0.0.1")  # Default to localhost if not specified

    zmq_subscriptions = {
        "rawblock": int(os.environ.get("ZMQ_RAWBLOCK_PORT", 28331)),
        "rawtx": int(os.environ.get("ZMQ_RAWTX_PORT", 28330)),
        "hashblock": int(os.environ.get("ZMQ_HASHBLOCK_PORT", 28329)),
        "hashtx": int(os.environ.get("ZMQ_HASHTX_PORT", 28328)),
        "sequence": int(os.environ.get("ZMQ_SEQUENCE_PORT", 28327))
    }

    tcp_proxy = TCPProxy(hostname, port, zmq_subscriptions)
    proxy_thread = threading.Thread(target=tcp_proxy.setup_proxy)
    proxy_thread.start()

    zmq_handlers = [ZMQHandler(zmq_host, port, topic) for topic, port in zmq_subscriptions.items()]

    zmq_threads = []
    for zmq_handler in zmq_handlers:
        thread = threading.Thread(target=zmq_handler.start)
        thread.start()
        zmq_threads.append(thread)

    try:
        signal.pause()
    except KeyboardInterrupt:
        print("Shutting down...")
        tcp_proxy.stop()
        for zmq_handler in zmq_handlers:
            zmq_handler.stop()
        proxy_thread.join()
        for thread in zmq_threads:
            thread.join()
        print("Shutdown complete.")