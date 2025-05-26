import socket
import paramiko
import threading
import select
import hashlib

from . import session_manager
from . import bbs_db
from . import bbs


ssh_dymmy_port_id = 1234

class SSHServer(paramiko.ServerInterface):
    def __init__(self):
        self.event = threading.Event()

    def check_auth_password(self, username, password):
        db = bbs_db.init_db(db_file_name)

        username = username.strip().upper()
        print(f"Authenticating user: {username}")
        # Validate the callsign format
        if bbs.is_valid_callsign(username) is False:
            print(f"Invalid callsign: {username}")
            bbs_db.shutdown(db)
            return paramiko.AUTH_FAILED
        hashed_password = hashlib.sha1(password.encode('utf-8')).hexdigest()
        print(f"Checking user {username} with hashed password {hashed_password}")
        # Check if the user exists in the database and the password matches
        user = bbs_db.get_user(db, username)

        if user is None:
            print(f"User {username} not found in database.")
            bbs_db.add_user_with_password(db, username, hashed_password)
            print(f"User {username} added to database.")
        elif user[1] != hashed_password:
            print(f"Password for user {username} does not match.")
            bbs_db.shutdown(db)
            return paramiko.AUTH_FAILED
        call = username.upper()
        print(f"Authenticated user: {call}")
        bbs_db.change_login_time(db, username)
        bbs_db.shutdown(db)
        print(f"User {username} authenticated successfully.")
        return paramiko.AUTH_SUCCESSFUL


    def get_allowed_auths(self, username):
        return 'password'

    def check_channel_request(self, kind, chanid):
        if kind == 'session':
            return paramiko.OPEN_SUCCEEDED
        return paramiko.OPEN_FAILED_ADMINISTRATIVELY_PROHIBITED

    def check_channel_shell_request(self, channel):
        self.event.set()
        return True


def handle_client(client):
    transport = paramiko.Transport(client)
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

    # Get the authenticated username from the transport
    print("Client connected, waiting for username...")
    username = transport.get_username() if hasattr(transport, "get_username") else None
    print(f"Authenticated username: {username}")
    if username is None and hasattr(transport, "remote_username"):
      username = transport.remote_username

    call = username.upper()

    print(f"Authenticated user: {call}")

    session_manager.add_tcp(bbscallsign, call, ssh_dymmy_port_id, chan)
    bbs.send_greeting(bbscallsign, call, ssh_dymmy_port_id)
    if call is not None:
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
                bbs.handle_command(db_file_name, bbscallsign, call, ssh_dymmy_port_id, data)
      except Exception as e:
        print(f"Error: {e}")

    chan.close()
    transport.close()
    print("Client disconnected.")

    # Remove the session
    if call is not None:
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
