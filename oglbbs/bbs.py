import pe
import pe.app
import time
from pyfiglet import Figlet

from . import bbs_db
from . import session_manager
from . import ssh_server
import re

version = "0.0.0"

# === Main ===
def run_bbs(agw_host, agw_port, call, db_handle, banner):
  global app
  global engine
  global db
  global bbs_banner_text
  db = db_handle
  app = pe.app.Application()
  app.start(agw_host, agw_port)
  engine = app.engine

  #Generate the banner text
  f = Figlet(font='slant')
  bbs_banner_text = "\n\n"
  bbs_banner_text += f.renderText(banner)

  # Set BBS callsign
  engine.register_callsign(call)
  print(f"[*] BBS running on {agw_host}:{agw_port} using AGWPE protocol")
  print(f"[*] Station call: {call}")


def is_valid_callsign(callsign: str) -> bool:
    """
    Validate an amateur radio callsign with optional SSID (-0 to -15).
    """
    # Match full callsign with optional SSID
    match = re.fullmatch(r'([A-Z0-9]{1,2}[0-9][A-Z]{1,3})(?:-([0-9]|1[0-5]))?', callsign.upper())
    if not match:
        return False

    full_prefix = match.group(1)
    prefix_part = full_prefix[:2]  # first 1–2 characters

    # Ensure at least one letter in first two characters
    return any(c.isalpha() for c in prefix_part)


# === Command Handler ===
def handle_command(db_handle, src, dst, port, line):
    session = session_manager.get(src, dst, port)
    tokens = line.strip().split(maxsplit=1)
    cmd = tokens[0].upper()

    if cmd == 'HELP':
        send_data(session, b"""
Commands:
  HELP              - Show this help
  INFO              - About this BBS
  MSG <text>        - Post a public message
  LIST              - Show recent public messages
  SEND <CALL> <msg> - Send private message
  READ              - Read private messages
  DEL <ID>          - Delete private message
  BYE               - Disconnect
""")

    elif cmd == 'INFO':
        send_data(session, b"This is a pyham_pe BBS with SQLite backend.\n")

    elif cmd == 'MSG':
        if len(tokens) == 2:
            bbs_db.store_message(db_handle, dst.upper(), tokens[1])
            send_data(session, b"Message stored.\n")
        else:
            send_data(session, b"Usage: MSG <your message>\n")

    elif cmd == 'LIST':
        rows = bbs_db.list_messages(db_handle)
        if not rows:
            send_data(session, b"No public messages.\n")
        else:
            output = b"\r\n".join([f"[{r[2]}] {r[0]}: {r[1]}".encode() for r in rows])
            output += b"\n"
            send_data(session, output)

    elif cmd == 'SEND':
        if len(tokens) == 2:
            parts = tokens[1].split(maxsplit=1)
            if len(parts) != 2:
                send_data(session, b"Usage: SEND <CALLSIGN> <message>\n")
            else:
                rcpt, msg = parts
                bbs_db.store_private_message(db_handle, dst.upper(), rcpt.upper(), msg)
                send_data(session, f"Message sent to {rcpt}\n".encode())
        else:
            send_data(session, b"Usage: SEND <CALLSIGN> <message>\n")

    elif cmd == 'READ':
        rows = bbs_db.list_private_messages(db_handle, dst.upper())
        if not rows:
            send_data(session, b"No private messages.\n")
        else:
            output = b"\n".join([f"[{r[3]}] ID:{r[0]} From {r[1]}: {r[2]}".encode() for r in rows])
            output += b"\n"
            send_data(session, output)

    elif cmd == 'DEL':
        if len(tokens) == 2 and tokens[1].isdigit():
            msg_id = int(tokens[1])
            ret = bbs_db.delete_message(db_handle, msg_id, dst.upper())
            if ret:
              send_data(session, b"Message deleted.\n")
            else:
              send_data(session, b"Message not found or not yours.\n")
        else:
            send_data(session, b"Usage: DEL <ID>\n")

    elif cmd == 'BYE':
        send_data(session, b"Goodbye!\n")
        if 'ax25_session' in session:
            session['ax25_session'].close()
        elif 'tcp_session' in session:
            # Close the TCP session
            print(f"[*] Closing TCP session for {src} -> {dst}")
            #session['tcp_session'].close()
            ssh_server.close_client(session['tcp_session'])
        else:
            print(f"[*] No session found. Cannot close.")
        session['active'] = False
    else:
        send_data(session, f"Unknown command: {cmd}\n".encode())


class bbs_connection(pe.connect.Connection):

  def __init__(self, port, call_from, call_to, incoming=False):
    super().__init__(port, call_from, call_to, incoming)
    # Now perform any initialization of your own that you might need
    print(f"[*] New connection from {call_from} to {call_to} on port {port}")

  @classmethod
  def query_accept(cls, port, call_from, call_to):
    """
    This method is called when a new connection is being established.
    You can return True to accept the connection or False to reject it.
    """
    print(f"[*] Querying connection from {call_from} to {call_to} on port {port}")
    # Validate callsigns
    if not is_valid_callsign(call_from) or not is_valid_callsign(call_to):
      print(f"[*] Invalid callsign: {call_from} -> {call_to}")
      return False
    print(f"[*] Accepting connection from {call_from} to {call_to}")
    return True

  def connected(self):
    print(f"[*] Connection opened from {self.call_from} to {self.call_to}")
    session_manager.add_ax25(self.call_from, self.call_to, self.port, self)
    send_greeting(self.call_from, self.call_to, self.port)

  def disconnected(self):
      print(f"[*] Connection closed from {self.call_from} to {self.call_to}")
      session_manager.remove(self.call_from, self.call_to, self.port)

  def data_received(self, pid, data):
      print(f"[*] Data received from {self.call_from} to {self.call_to}: {data}")
      handle_command(db, self.call_from, self.call_to, self.port, data.decode(errors='ignore').strip())


def send_data(session, data):
  if session['active']:
    if 'ax25_session' in session:
      print(f"[*] Sending data to ax25 session")
      session['ax25_session'].send_data(data)
    elif 'tcp_session' in session:
      print(f"[*] Sending data to tcp_session")
      ssh_server.send_data(session['tcp_session'], data)
    else:
      print(f"[*] No session found. Cannot send data.")
      return False
  else:
    print(f"[*] Session is not active, cannot send data.")
    return False
  return True


def send_greeting(call_from, call_to, port):
  session = session_manager.get(call_from, call_to, port)
  msg = bbs_banner_text.encode()
  send_data(session, msg)
  msg = f"\n\nWelcome to OGLBBS v{version}!\nType HELP for commands.\r\n"
  send_data(session, msg)


def shutdown():
  try:
    print("[*] Stopping BBS...")
    app.stop()
    print("[*] BBS stopped.")
  except Exception:
    pass