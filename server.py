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


def broadcast_offers(tcp_port):
    udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    udp_socket.bind(('', 0))
    server_ip = socket.gethostbyname(socket.gethostname())
    print(f"Server started, listening on IP address {server_ip}")

    while True:
        offer_message = struct.pack('!IbHH', MAGIC_COOKIE, MESSAGE_TYPE_OFFER, UDP_DATA_PORT, tcp_port)
        udp_socket.sendto(offer_message, ('<broadcast>', UDP_BROADCAST_PORT))
        time.sleep(1)


def handle_client(client_socket, client_address):
    try:
        request_data = client_socket.recv(1024)
        if len(request_data) < 15:
            print(f"Invalid request from {client_address}")
            return

        magic_cookie, message_type, file_size, tcp_connections, udp_connections = struct.unpack('!IbQbb', request_data[:15])
        if magic_cookie != MAGIC_COOKIE or message_type != MESSAGE_TYPE_REQUEST:
            print(f"Invalid request format from {client_address}")
            return

        print(f"Request from {client_address}: File size: {file_size} bytes, TCP: {tcp_connections}, UDP: {udp_connections}")

        threads = []

        # TCP Transfers
        for _ in range(tcp_connections):
            t = threading.Thread(target=send_tcp_data, args=(client_socket, file_size // tcp_connections))
            threads.append(t)
            t.start()

        # UDP Transfers
        for connection_number in range(udp_connections):
            t = threading.Thread(target=send_udp_data, args=(client_address[0], UDP_DATA_PORT + connection_number, file_size // udp_connections))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()
    except Exception as e:
        print(f"Error handling client {client_address}: {e}")
    finally:
        client_socket.close()


def send_tcp_data(client_socket, chunk_size):
    data = b'x' * PAYLOAD_SIZE
    bytes_sent = 0

    while bytes_sent < chunk_size:
        client_socket.send(data)
        bytes_sent += len(data)


def send_udp_data(client_ip, udp_port, total_size):
    udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # Simple payload
        data = b'x' * PAYLOAD_SIZE
        bytes_sent = 0

        while bytes_sent < total_size:
            # Calculate remaining bytes
            remaining = total_size - bytes_sent
            current_payload = min(PAYLOAD_SIZE, remaining)

            # Simple header with just magic cookie and message type
            header = struct.pack('!IbQQH', MAGIC_COOKIE, MESSAGE_TYPE_PAYLOAD, 0, 0, current_payload)
            packet = header + data[:current_payload]

            udp_socket.sendto(packet, (client_ip, udp_port))
            bytes_sent += current_payload

    finally:
        udp_socket.close()


if __name__ == "__main__":
    try:
        tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        tcp_socket.bind(('', 0))
        tcp_port = tcp_socket.getsockname()[1]
        tcp_socket.listen()

        threading.Thread(target=broadcast_offers, args=(tcp_port,), daemon=True).start()

        print("Server is running... Press Ctrl+C to stop.")
        while True:
            client_socket, client_address = tcp_socket.accept()
            threading.Thread(target=handle_client, args=(client_socket, client_address)).start()
    except KeyboardInterrupt:
        print("Server shutting down.")
    finally:
        tcp_socket.close()
