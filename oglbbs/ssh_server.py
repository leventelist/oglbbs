import socket
import paramiko
import threading
import select

from . import session_manager
from . import bbs_db
from . import bbs

# Dummy user credentials (use PAM or similar for real authentication)
AUTHORIZED_USERS = {
    'user': 'password'
}

ssh_dymmy_port_id = 1234

class SSHServer(paramiko.ServerInterface):
    def __init__(self):
        self.event = threading.Event()

    def check_auth_password(self, username, password):
        if username in AUTHORIZED_USERS and AUTHORIZED_USERS[username] == password:
            return paramiko.AUTH_SUCCESSFUL
        return paramiko.AUTH_FAILED

    def get_allowed_auths(self, username):
        return 'password'

    def check_channel_request(self, kind, chanid):
        if kind == 'session':
            return paramiko.OPEN_SUCCEEDED
        return paramiko.OPEN_FAILED_ADMINISTRATIVELY_PROHIBITED

    def check_channel_shell_request(self, channel):
        self.event.set()
        return True

def handle_client(client,):
    transport = paramiko.Transport(client)
    # Load system's host key (e.g., /etc/ssh/ssh_host_rsa_key)
    print(f"Loading host key... {key}")
    try:
      host_key = paramiko.RSAKey(filename=key)
      transport.add_server_key(host_key)
    except Exception as e:
      print(f"Failed to load host key: {e}")
      transport.close()
      close_client(client)
      return
    server = SSHServer()

    try:
        transport.start_server(server=server)
    except paramiko.SSHException:
        print("SSH negotiation failed.")
        return

    chan = transport.accept(20)
    if chan is None:
        print("No channel.")
        return

    server.event.wait(10)
    if not server.event.is_set():
        print("No shell request.")
        return

    chan.send(f"Welcome to OGLBBS CLI at {bbscallsign}.\nPlease enter your callsign!\nType 'exit' to disconnect.\n> ")


    db = bbs_db.init_db(db_file_name)

    call = None

    try:
        while True:
            fd = chan.fileno()
            if fd < 0:
                break
            data = chan.recv(1024).decode('utf-8').strip()
            if not data:
                break
            if data.lower() == 'exit':
                chan.send("Bye!\n")
                break
            elif data:
                call = data.upper()
                # Here you integrate your custom CLI logic
                response = f"You entered your call {call}\n> "
                chan.send(response)
                session_manager.add_tcp(bbscallsign, call, ssh_dymmy_port_id, chan)
                bbs.send_greeting(bbscallsign, call, ssh_dymmy_port_id)
                break
    except Exception as e:
        print(f"Error: {e}")

    if call != None:
      try:
        while True:
            fd = chan.fileno()
            if fd < 0:
                break
            data = chan.recv(1024).decode('utf-8').strip()
            if not data:
                break
            if data.lower() == 'exit':
                chan.send("Bye!\n")
                break
            elif data:
                bbs.handle_command(db, bbscallsign, call, ssh_dymmy_port_id, data)
      except Exception as e:
        print(f"Error: {e}")

    chan.close()
    transport.close()
    print("Client disconnected.")

    # Close the database connection
    bbs_db.shutdown(db)
    # Remove the session
    if call != None:
      session_manager.remove(bbscallsign, call, ssh_dymmy_port_id)
      print("Session removed.")

def close_client(client):
    try:
        print(f"Closing client connection...")
        client.close()
    except Exception as e:
        print(f"Error closing client: {e}")

def send_data(chan, data):
    try:
        chan.send(data)
    except Exception as e:
        print(f"Error sending data: {e}")
        return False
    return True


def start_ssh_server(host='127.0.0.1', port=8002, key_file='/etc/ssh/ssh_host_rsa_key', bbscall='N0CALL', db_file='bbs.db'):
    global sock
    global key
    global bbscallsign
    global db_file_name
    db_file_name = db_file
    bbscallsign = bbscall
    key = key_file
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind((host, port))
    sock.listen(100)
    print(f"SSH server started on {host}:{port}")


def step():
  if sock is None or sock.fileno() < 0:
    return
  readable, _, _ = select.select([sock], [], [], 0)
  if readable:
    try:
      client, addr = sock.accept()
      print(f"New connection from {addr}")
      threading.Thread(target=handle_client, args=(client,)).start()
    except Exception as e:
      print(f"Error accepting connection: {e}")

def shutdown():
    sock.close()
    print("SSH server shut down.")
