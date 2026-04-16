""" Hugo Augusto Silva de Faria - 22.2.4064
    Rafael Stylita Duarte - 22.1.4021 
"""

import socket
import os
import select
import tkinter as tk
from tkinter import messagebox
import threading
import queue

# Configurações do servidor
SERVER_IP = "0.0.0.0"  # Escuta em todas as interfaces
SERVER_PORT = 7891     # Porta do servidor
BUFFER_SIZE = 1024     # Tamanho do buffer para dados
RAIZ = os.getcwd()     # Diretório raiz do servidor

# Usuários e senhas para autenticação
USUARIOS = {
    "rafael": "1234",
    "hugo": "5678",
    "aluno": "UFOP",
    "user": "teste"
}

# Dicionário para rastrear clientes conectados
clientes = {}  # {addr: {"usuario": str, "dir_atual": str, "transferindo": bool}}

class MyFTPServer:
    def __init__(self, root):
        self.root = root
        self.root.title("MyFTP Server")

        # Fila para logs entre threads
        self.log_queue = queue.Queue()

        # Status do servidor
        self.running = False
        self.server_socket = None
        self.server_thread = None

        # Área de saída (log)
        self.text_area = tk.Text(root, height=20, width=70, state='disabled')
        self.text_area.pack(pady=10)

        # Botões principais
        frame = tk.Frame(root)
        frame.pack()

        tk.Button(frame, text="Iniciar Servidor", command=self.start_server).grid(row=0, column=0, padx=5, pady=5)
        tk.Button(frame, text="Parar Servidor", command=self.stop_server).grid(row=0, column=1, padx=5, pady=5)
        tk.Button(frame, text="Limpar Log", command=self.clear_log).grid(row=0, column=2, padx=5, pady=5)

        # Label para status
        self.status_label = tk.Label(root, text="Servidor parado")
        self.status_label.pack(pady=5)

        # Atualiza logs periodicamente
        self.root.after(100, self.update_log)

    def log(self, msg):
        """Adiciona mensagem à fila de logs."""
        self.log_queue.put(msg)

    def update_log(self):
        """Atualiza a área de texto com logs da fila."""
        while not self.log_queue.empty():
            msg = self.log_queue.get()
            self.text_area.configure(state='normal')
            self.text_area.insert(tk.END, msg + "\n")
            self.text_area.see(tk.END)
            self.text_area.configure(state='disabled')
        self.root.after(100, self.update_log)

    def clear_log(self):
        """Limpa a área de log."""
        self.text_area.configure(state='normal')
        self.text_area.delete(1.0, tk.END)
        self.text_area.configure(state='disabled')

    def start_server(self):
        """Inicia o servidor em um thread separado."""
        if not self.running:
            self.running = True
            self.status_label.config(text="Servidor rodando")
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                self.server_socket.bind((SERVER_IP, SERVER_PORT))
                self.log(f"Servidor UDP escutando em {SERVER_IP}:{SERVER_PORT}")
                self.server_thread = threading.Thread(target=self.run_server)
                self.server_thread.daemon = True  # Fecha com a GUI
                self.server_thread.start()
            except Exception as e:
                self.log(f"[ERRO] Falha ao iniciar servidor: {e}")
                self.running = False
                self.status_label.config(text="Servidor parado")
                self.server_socket.close()

    def stop_server(self):
        """Para o servidor."""
        if self.running:
            self.running = False
            self.status_label.config(text="Servidor parado")
            if self.server_socket:
                self.server_socket.close()
            self.log("Servidor parado.")

    def receive_file(self, addr, filename, server_socket):
        """Recebe arquivo do cliente, salvando no diretório atual."""
        dir_atual = clientes[addr]["dir_atual"]
        caminho = os.path.join(dir_atual, filename)
        self.log(f"[INFO] Recebendo arquivo '{filename}' de {clientes[addr]['usuario']}...")

        try:
            with open(caminho, "wb") as f:
                while True:
                    ready = select.select([server_socket], [], [], 10)
                    if not ready[0]:
                        self.log(f"[ERRO] Timeout ao receber arquivo '{filename}' de {clientes[addr]['usuario']}.")
                        server_socket.sendto(f"Erro: Timeout na recepção do arquivo '{filename}'.".encode(), addr)
                        clientes[addr]["transferindo"] = False
                        return False

                    data, client_addr = server_socket.recvfrom(BUFFER_SIZE)
                    self.log(f"[DEBUG] Recebido pacote de {client_addr}: {data}")

                    if client_addr != addr:
                        self.log(f"[DEBUG] Ignorando pacote de {client_addr}, esperado {addr}")
                        continue

                    if data.strip() == b"END":
                        self.log(f"[INFO] Pacote END recebido para '{filename}'")
                        break

                    try:
                        id_pacote, conteudo = data.split(b"|", 1)
                        id_pacote = int(id_pacote.decode())
                        self.log(f"[DEBUG] Pacote {id_pacote} recebido com {len(conteudo)} bytes")
                    except Exception as e:
                        self.log(f"[ERRO] Pacote inválido de {clientes[addr]['usuario']}: {e}")
                        continue

                    f.write(conteudo)
                    server_socket.sendto(f"ACK {id_pacote}".encode(), addr)
                    self.log(f"[DEBUG] Enviado ACK {id_pacote} para {addr}")

            server_socket.sendto(f"Arquivo '{filename}' recebido com sucesso.".encode(), addr)
            self.log(f"[INFO] Arquivo '{filename}' recebido com sucesso de {clientes[addr]['usuario']}.")
            clientes[addr]["transferindo"] = False
            return True

        except Exception as e:
            self.log(f"[ERRO] Falha ao receber arquivo '{filename}' de {clientes[addr]['usuario']}: {e}")
            server_socket.sendto(f"Erro ao receber arquivo '{filename}': {e}".encode(), addr)
            clientes[addr]["transferindo"] = False
            return False

    def send_file(self, addr, filename, server_socket):
        """Envia arquivo para o cliente com confirmação via ACKs."""
        dir_atual = clientes[addr]["dir_atual"]
        caminho = os.path.join(dir_atual, filename)

        if not os.path.isfile(caminho):
            server_socket.sendto(f"Arquivo '{filename}' não existe.".encode(), addr)
            clientes[addr]["transferindo"] = False
            return

        server_socket.sendto(b"START_GET", addr)
        self.log(f"[INFO] Enviando arquivo '{filename}' para {clientes[addr]['usuario']}...")

        with open(caminho, "rb") as f:
            id_pacote = 0
            while True:
                dados = f.read(BUFFER_SIZE - 20)
                if not dados:
                    break

                pacote = f"{id_pacote}|".encode() + dados

                while True:
                    server_socket.sendto(pacote, addr)
                    ready = select.select([server_socket], [], [], 10)
                    if ready[0]:
                        ack, client_addr = server_socket.recvfrom(BUFFER_SIZE)
                        if client_addr != addr:
                            continue
                        self.log(f"[DEBUG] Recebido durante send: {ack}")
                        if ack.decode().strip() == f"ACK {id_pacote}":
                            break
                    self.log(f"[ERRO] Reenviando pacote {id_pacote}...")

                id_pacote += 1

        server_socket.sendto(b"END", addr)
        self.log(f"[INFO] Arquivo '{filename}' enviado com sucesso para {clientes[addr]['usuario']}.")
        clientes[addr]["transferindo"] = False

    def handle_client(self, addr, data, server_socket):
        """Processa comandos do cliente (login, ls, cd, mkdir, rmdir, put, get)."""
        if addr in clientes and clientes[addr].get("transferindo", False):
            return

        try:
            mensagem = data.decode("utf-8").strip()
        except UnicodeDecodeError:
            return

        usuario_cliente = clientes.get(addr)

        if usuario_cliente is None:
            if mensagem.startswith("login "):
                try:
                    _, usuario, senha = mensagem.split(maxsplit=2)
                    if usuario in USUARIOS and USUARIOS[usuario] == senha:
                        clientes[addr] = {"usuario": usuario, "dir_atual": RAIZ, "transferindo": False}
                        resposta = f"Login bem-sucedido! Bem-vindo, {usuario}."
                        self.log(f"[INFO] {usuario} logou com sucesso.")
                    else:
                        resposta = "Usuário ou senha incorretos."
                        self.log(f"[WARN] Tentativa de login falhou -> {usuario}")
                except ValueError:
                    resposta = "Formato incorreto. Use: login usuario senha"
            else:
                resposta = "Você precisa fazer login primeiro. Use: login usuario senha"

            server_socket.sendto(resposta.encode("utf-8"), addr)
            return

        dir_atual = clientes[addr]["dir_atual"]
        usuario = clientes[addr]["usuario"]

        try:
            if mensagem == "ls":
                arquivos = os.listdir(dir_atual)
                resposta = "\n".join(arquivos) if arquivos else "Diretório vazio."
                self.log(f"[INFO] {usuario} executou 'ls' em {dir_atual}")

            elif mensagem.startswith("cd"):
                pasta = mensagem[2:].strip()
                if pasta == "":
                    resposta = "Erro: comando 'cd' precisa de argumento."
                elif pasta == "..":
                    novo_dir = os.path.dirname(dir_atual)
                    if os.path.commonpath([RAIZ, novo_dir]) == RAIZ:
                        clientes[addr]["dir_atual"] = novo_dir
                        resposta = f"Voltou para: {novo_dir}"
                    else:
                        resposta = "Não pode sair do diretório raiz."
                else:
                    novo_dir = os.path.join(dir_atual, pasta)
                    if os.path.isdir(novo_dir):
                        clientes[addr]["dir_atual"] = novo_dir
                        resposta = f"Entrou na pasta: {pasta}"
                    else:
                        resposta = "Pasta inexistente."

            elif mensagem.startswith("mkdir"):
                pasta = mensagem[6:].strip()
                novo_dir = os.path.join(dir_atual, pasta)
                if os.path.exists(novo_dir):
                    resposta = f"A pasta '{pasta}' já existe."
                else:
                    try:
                        os.mkdir(novo_dir)
                        resposta = f"Pasta '{pasta}' criada com sucesso."
                    except Exception as e:
                        resposta = f"Erro ao criar pasta: {e}"

            elif mensagem.startswith("rmdir"):
                pasta = mensagem[6:].strip()
                alvo = os.path.join(dir_atual, pasta)
                if not os.path.exists(alvo):
                    resposta = f"A pasta '{pasta}' não existe."
                else:
                    try:
                        os.rmdir(alvo)
                        resposta = f"Pasta '{pasta}' removida com sucesso."
                    except Exception as e:
                        resposta = f"Erro ao remover pasta: {e}"

            elif mensagem.startswith("put"):
                filename = mensagem[4:].strip()
                clientes[addr]["transferindo"] = True
                server_socket.sendto(b"READY", addr)
                self.receive_file(addr, filename, server_socket)
                return

            elif mensagem.startswith("get"):
                filename = mensagem[4:].strip()
                clientes[addr]["transferindo"] = True
                self.send_file(addr, filename, server_socket)
                return

            else:
                resposta = f"Comando desconhecido: {mensagem}"
                self.log(f"[WARN] {usuario} enviou comando inválido -> {mensagem}")

        except Exception as e:
            resposta = f"Erro ao executar comando: {e}"
            self.log(f"[ERRO] {usuario} -> {e}")

        server_socket.sendto(resposta.encode("utf-8"), addr)

    def run_server(self):
        """Loop principal do servidor, executado em thread separado."""
        while self.running:
            try:
                data, addr = self.server_socket.recvfrom(BUFFER_SIZE)
                self.handle_client(addr, data, self.server_socket)
            except Exception as e:
                if self.running:
                    self.log(f"[ERRO] Erro no servidor: {e}")

    def quit(self):
        """Fecha o servidor e a interface."""
        self.stop_server()
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = MyFTPServer(root)
    root.mainloop()