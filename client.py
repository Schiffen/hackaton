import socket
import struct
import threading
import time

# Constants
MAGIC_COOKIE = 0xabcddcba
MESSAGE_TYPE_OFFER = 0x2
MESSAGE_TYPE_REQUEST = 0x3
MESSAGE_TYPE_PAYLOAD = 0x4
UDP_BROADCAST_PORT = 13117
UDP_DATA_PORT = 13118
PAYLOAD_SIZE = 1024


class Client:
    def __init__(self):
        self.file_size = 0
        self.udp_connections = 0
        self.tcp_connections = 0

    def prompt_user_input(self):
        print("Client started, listening for offer requests...")
        self.listen_for_offers()

    def listen_for_offers(self):
        udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        udp_socket.bind(('', UDP_BROADCAST_PORT))

        while True:
            try:
                data, addr = udp_socket.recvfrom(1024)
                if len(data) >= 9:
                    magic_cookie, message_type, udp_port, tcp_port = struct.unpack('!IbHH', data[:9])
                    if magic_cookie == MAGIC_COOKIE and message_type == MESSAGE_TYPE_OFFER:
                        print(f"Received offer from {addr[0]}, UDP port: {udp_port}, TCP port: {tcp_port}")
                        self.connect_to_server(addr[0], tcp_port, udp_port)
                        return
            except Exception as e:
                print(f"Error while listening for offers: {e}")

    def connect_to_server(self, server_ip, tcp_port, udp_port):
        self.file_size = int(input("Enter file size (in bytes): "))
        self.tcp_connections = int(input("Enter number of TCP connections: "))
        self.udp_connections = int(input("Enter number of UDP connections: "))

        request_packet = struct.pack('!IbQbb', MAGIC_COOKIE, MESSAGE_TYPE_REQUEST, self.file_size,
                                     self.tcp_connections, self.udp_connections)
        print(f"Connecting to server {server_ip}...")

        try:
            # Open TCP socket
            tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            tcp_socket.connect((server_ip, tcp_port))
            tcp_socket.send(request_packet)

            threads = []

            # Handle TCP connections - keep the chunking for TCP
            if self.tcp_connections > 0:
                chunk_size = self.file_size // self.tcp_connections
                for connection_number in range(self.tcp_connections):
                    start_position = connection_number * chunk_size
                    end_position = min(start_position + chunk_size, self.file_size)
                    t = threading.Thread(target=self.receive_tcp_data,
                                         args=(tcp_socket, start_position, end_position - start_position,
                                               connection_number + 1))
                    threads.append(t)
                    t.start()

            # Handle UDP connections - each gets full file size
            if self.udp_connections > 0:
                for connection_number in range(self.udp_connections):
                    t = threading.Thread(target=self.receive_udp_data,
                                         args=(server_ip, udp_port + connection_number, 0,
                                               self.file_size, connection_number + 1))
                    threads.append(t)
                    t.start()

            for t in threads:
                t.join()

            print("All transfers complete, listening to offer requests...")
        except Exception as e:
            print(f"Failed to connect: {e}")
        finally:
            tcp_socket.close()

    def receive_tcp_data(self, tcp_socket, start_position, chunk_size, connection_number):
        print(f"Receiving TCP data for chunk starting at {start_position} with size {chunk_size}...")
        start_time = time.perf_counter()
        bytes_received = 0

        while bytes_received < chunk_size:
            data = tcp_socket.recv(min(PAYLOAD_SIZE, chunk_size - bytes_received))
            if not data:
                break
            bytes_received += len(data)

        duration = time.perf_counter() - start_time + 0.0001
        throughput = (bytes_received * 8) / duration
        print(
            f"TCP transfer #{connection_number} finished, total time: {duration:.6f} seconds, total speed: {throughput:.2f} bits/second")

    def receive_udp_data(self, server_ip, udp_port, start_position, total_size, connection_number):
        udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            udp_socket.bind(('', udp_port))
            print(f"UDP connection #{connection_number} starting on port {udp_port}")

            udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 65536)
            start_time = time.perf_counter()
            bytes_received = 0

            udp_socket.settimeout(5.0)

            while bytes_received < total_size:
                try:
                    data, addr = udp_socket.recvfrom(65536)

                    if len(data) < 23:  # Header size
                        print(f"Connection #{connection_number}: Invalid packet received")
                        continue

                    magic_cookie, message_type, _, _, payload_size = struct.unpack('!IbQQH', data[:23])

                    if magic_cookie != MAGIC_COOKIE or message_type != MESSAGE_TYPE_PAYLOAD:
                        print(f"Connection #{connection_number}: Invalid packet format")
                        continue

                    payload = data[23:]
                    bytes_received += len(payload)
                    print(f"UDP #{connection_number}: Received {bytes_received}/{total_size} bytes")

                except socket.timeout:
                    print(f"UDP connection #{connection_number} timed out")
                    break

            duration = time.perf_counter() - start_time + 0.0001
            throughput = (bytes_received * 8) / duration
            print(f"UDP #{connection_number} complete: {duration:.6f} sec, {throughput:.2f} bits/sec")

        finally:
            udp_socket.close()


    def main(self):
        self.prompt_user_input()


if __name__ == "__main__":
    client = Client()
    client.main()
