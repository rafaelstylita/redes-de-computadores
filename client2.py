import socket
import os
import select
import tkinter as tk
from tkinter import filedialog, simpledialog, messagebox

SERVER_IP = "192.168.0.155"   # IP do servidor
SERVER_PORT = 7891
BUFFER_SIZE = 1024


class MyFTPClient:
    def __init__(self, root):
        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        self.root = root
        self.root.title("MyFTP Client")

        # Área de saída (log)
        self.text_area = tk.Text(root, height=20, width=70)
        self.text_area.pack(pady=10)

        # Botões principais
        frame = tk.Frame(root)
        frame.pack()

        tk.Button(frame, text="Login", command=self.login).grid(row=0, column=0, padx=5, pady=5)
        tk.Button(frame, text="Listar (ls)", command=self.ls).grid(row=0, column=1, padx=5, pady=5)
        tk.Button(frame, text="Upload (put)", command=self.put).grid(row=0, column=2, padx=5, pady=5)
        tk.Button(frame, text="Download (get)", command=self.get).grid(row=0, column=3, padx=5, pady=5)
        tk.Button(frame, text="Criar pasta (mkdir)", command=self.mkdir).grid(row=1, column=0, padx=5, pady=5)
        tk.Button(frame, text="Remover pasta (rmdir)", command=self.rmdir).grid(row=1, column=1, padx=5, pady=5)
        tk.Button(frame, text="Entrar pasta (cd)", command=self.cd).grid(row=1, column=2, padx=5, pady=5)
        tk.Button(frame, text="Voltar pasta (cd..)", command=self.cd_back).grid(row=1, column=3, padx=5, pady=5)
        tk.Button(frame, text="Sair", command=self.quit).grid(row=2, column=1, columnspan=2, pady=10)

    def log(self, msg):
        self.text_area.insert(tk.END, msg + "\n")
        self.text_area.see(tk.END)

    def send_command(self, cmd):
        self.client_socket.sendto(cmd.encode(), (SERVER_IP, SERVER_PORT))
        data, _ = self.client_socket.recvfrom(BUFFER_SIZE)
        resposta = data.decode("utf-8")
        self.log(resposta)
        return resposta

    def login(self):
        usuario = simpledialog.askstring("Login", "Usuário:")
        senha = simpledialog.askstring("Login", "Senha:", show="*")
        if usuario and senha:
            self.send_command(f"login {usuario} {senha}")

    def ls(self):
        self.send_command("ls")

    def mkdir(self):
        pasta = simpledialog.askstring("mkdir", "Nome da pasta:")
        if pasta:
            self.send_command(f"mkdir {pasta}")

    def rmdir(self):
        pasta = simpledialog.askstring("rmdir", "Nome da pasta:")
        if pasta:
            self.send_command(f"rmdir {pasta}")

    def cd(self):
        pasta = simpledialog.askstring("cd", "Nome da pasta:")
        if pasta:
            self.send_command(f"cd {pasta}")

    def cd_back(self):
        self.send_command("cd ..")

    def put(self):
        filename = filedialog.askopenfilename()
        if filename:
            self.send_file(filename)

    def get(self):
        filename = simpledialog.askstring("Download", "Nome do arquivo no servidor:")
        if filename:
            self.get_file(filename)

    def send_file(self, filename):
        if not os.path.isfile(filename):
            self.log(f"Arquivo '{filename}' não existe.")
            return

        base = os.path.basename(filename)
        self.client_socket.sendto(f"put {base}".encode(), (SERVER_IP, SERVER_PORT))
        data, _ = self.client_socket.recvfrom(BUFFER_SIZE)

        if data == b"READY":
            self.log(f"Enviando arquivo '{base}'...")
            with open(filename, "rb") as f:
                id_pacote = 0
                while True:
                    dados = f.read(BUFFER_SIZE - 20)
                    if not dados:
                        break
                    pacote = f"{id_pacote}|".encode() + dados
                    while True:
                        self.client_socket.sendto(pacote, (SERVER_IP, SERVER_PORT))
                        ready = select.select([self.client_socket], [], [], 2)
                        if ready[0]:
                            ack, _ = self.client_socket.recvfrom(BUFFER_SIZE)
                            if ack.decode().strip() == f"ACK {id_pacote}":
                                break
                        self.log(f"[ERRO] Reenviando pacote {id_pacote}...")
                    id_pacote += 1
            self.client_socket.sendto(b"END", (SERVER_IP, SERVER_PORT))
            data, _ = self.client_socket.recvfrom(BUFFER_SIZE)
            self.log(data.decode("utf-8"))
        else:
            self.log(data.decode("utf-8"))

    def get_file(self, filename):
        self.client_socket.sendto(f"get {filename}".encode(), (SERVER_IP, SERVER_PORT))
        data, _ = self.client_socket.recvfrom(BUFFER_SIZE)

        if data == b"START_GET":
            self.log(f"Recebendo arquivo '{filename}'...")
            save_path = filedialog.asksaveasfilename(initialfile=filename)
            if not save_path:
                return
            with open(save_path, "wb") as f:
                while True:
                    pacote, _ = self.client_socket.recvfrom(BUFFER_SIZE)
                    if pacote == b"END":
                        break
                    try:
                        id_pacote, conteudo = pacote.split(b"|", 1)
                        id_pacote = int(id_pacote.decode())
                    except Exception:
                        continue
                    f.write(conteudo)
                    self.client_socket.sendto(f"ACK {id_pacote}".encode(), (SERVER_IP, SERVER_PORT))
            self.log(f"Arquivo '{filename}' recebido com sucesso.")
        else:
            self.log(data.decode("utf-8"))

    def quit(self):
        self.client_socket.close()
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = MyFTPClient(root)
    root.mainloop()
