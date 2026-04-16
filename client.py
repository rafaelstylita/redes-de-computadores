import socket
import os
import select

SERVER_IP = "192.168.0.155"
SERVER_PORT = 7891
BUFFER_SIZE = 1024


def send_file(client_socket, filename):
    if not os.path.isfile(filename):
        print(f"Arquivo '{filename}' não existe.")
        return

    client_socket.sendto(f"put {filename}".encode(), (SERVER_IP, SERVER_PORT))
    data, _ = client_socket.recvfrom(BUFFER_SIZE)

    if data == b"READY":
        print(f"Enviando arquivo '{filename}'...")

        with open(filename, "rb") as f:
            id_pacote = 0
            while True:
                dados = f.read(BUFFER_SIZE - 20)  # espaço p/ cabeçalho
                if not dados:
                    break

                pacote = f"{id_pacote}|".encode() + dados

                while True:
                    client_socket.sendto(pacote, (SERVER_IP, SERVER_PORT))

                    ready = select.select([client_socket], [], [], 2)
                    if ready[0]:
                        ack, _ = client_socket.recvfrom(BUFFER_SIZE)
                        if ack.decode().strip() == f"ACK {id_pacote}":
                            break
                    print(f"[ERRO] Reenviando pacote {id_pacote}...")
                id_pacote += 1

        # Fim do arquivo
        client_socket.sendto(b"END", (SERVER_IP, SERVER_PORT))
        data, _ = client_socket.recvfrom(BUFFER_SIZE)
        print(data.decode("utf-8"))
    else:
        print(data.decode("utf-8"))


def get_file(client_socket, filename):
    client_socket.sendto(f"get {filename}".encode(), (SERVER_IP, SERVER_PORT))
    data, _ = client_socket.recvfrom(BUFFER_SIZE)

    if data == b"START_GET":
        print(f"Recebendo arquivo '{filename}'...")
        with open(filename, "wb") as f:
            while True:
                pacote, _ = client_socket.recvfrom(BUFFER_SIZE)
                if pacote == b"END":
                    break

                try:
                    id_pacote, conteudo = pacote.split(b"|", 1)
                    id_pacote = int(id_pacote.decode())
                except Exception:
                    continue

                f.write(conteudo)
                client_socket.sendto(f"ACK {id_pacote}".encode(), (SERVER_IP, SERVER_PORT))

        print(f"Arquivo '{filename}' recebido com sucesso.")
    else:
        print(data.decode("utf-8"))


def main():
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    print("Bem-vindo ao MyFTP!")
    print("Para logar, digite: login usuario senha")
    print("Comandos disponíveis após login: ls, cd <pasta>, cd.., mkdir <pasta>, rmdir <pasta>, put <arquivo>, get <arquivo>, quit")

    while True:
        comando = input("> ").strip()

        if comando.lower() == "quit":
            print("Encerrando cliente...")
            client_socket.close()
            break
        elif comando.startswith("put "):
            filename = comando[4:].strip()
            send_file(client_socket, filename)
        elif comando.startswith("get "):
            filename = comando[4:].strip()
            get_file(client_socket, filename)
        else:
            client_socket.sendto(comando.encode(), (SERVER_IP, SERVER_PORT))
            data, _ = client_socket.recvfrom(BUFFER_SIZE)
            print(data.decode("utf-8"))


if __name__ == "__main__":
    main()
