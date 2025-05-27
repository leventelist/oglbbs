import pe
import pe.app
import time
from pyfiglet import Figlet

from . import bbs_db
from . import session_manager
from . import ssh_server
import re

version = "0.0.0"
line_ending = '\r\n'


# === Main ===
def run_bbs(agw_host, agw_port, call, db_file_name, banner):
  global app
  global engine
  global db_filename
  global bbs_banner_text
  db_filename = db_file_name

  if not is_valid_callsign(call):
    print(f"Invalid callsign: {call}")
    return False

  app = pe.app.Application()
  try:
    app.start(agw_host, agw_port)
  except Exception as e:
    print(f"Error starting BBS: {e}")
    return False
  engine = app.engine

  #Generate the banner text
  f = Figlet(font='slant')
  bbs_banner_text = line_ending + line_ending
  bbs_banner_text += f.renderText(banner) + line_ending

  # Set BBS callsign
  engine.register_callsign(call)
  print(f"BBS running on {agw_host}:{agw_port} using AGWPE protocol")
  print(f"Station call: {call}")
  return True


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

def send_prompt(session):
   send_data(session, line_ending + '> ')

# === Command Handler ===
def handle_command(db_filename, src, dst, port, line):
    session = session_manager.get(src, dst, port)
    tokens = line.strip().split(maxsplit=1)
    cmd = tokens[0].upper()

    db_handle = bbs_db.init_db(db_filename)

    if cmd == 'HELP':
        send_data(session, """
Commands:
  HELP              - Show this help
  INFO              - About this BBS
  MSG <text>        - Post a public message
  LIST              - Show recent public messages
  SEND <CALL> <msg> - Send private message
  READ              - Read private messages
  DEL <ID>          - Delete private message
  BYE               - Disconnect""" + line_ending)

    elif cmd == 'INFO':
        send_data(session, "This is OGLBBS. More info on https://github.com/leventelist/oglbbs" + line_ending)

    elif cmd == 'MSG':
        if len(tokens) == 2:
            bbs_db.store_message(db_handle, src.upper(), tokens[1])
            send_data(session, "Message stored." + line_ending)
        else:
            send_data(session, "Usage: MSG <your message>" + line_ending)

    elif cmd == 'LIST':
        rows = bbs_db.list_messages(db_handle)
        if not rows:
            send_data(session, "No public messages." + line_ending)
        else:
            output = "\r\n".join([f"[{r[2]}] {r[0]}: {r[1]}" for r in rows])
            output += line_ending
            send_data(session, output)

    elif cmd == 'SEND':
        if len(tokens) == 2:
            parts = tokens[1].split(maxsplit=1)
            if len(parts) != 2:
                send_data(session, "Usage: SEND <CALLSIGN> <message>" + line_ending)
            else:
                rcpt, msg = parts
                bbs_db.store_private_message(db_handle, dst.upper(), rcpt.upper(), msg)
                send_data(session, f"Message sent to {rcpt}" + line_ending)
        else:
            send_data(session, "Usage: SEND <CALLSIGN> <message>" + line_ending)

    elif cmd == 'READ':
        rows = bbs_db.list_private_messages(db_handle, dst.upper())
        if not rows:
            send_data(session, "No private messages." + line_ending)
        else:
            output = "\n\r".join([f"[{r[3]}] ID:{r[0]} From {r[1]}: {r[2]}" for r in rows])
            output += line_ending
            send_data(session, output)

    elif cmd == 'DEL':
        if len(tokens) == 2 and tokens[1].isdigit():
            msg_id = int(tokens[1])
            ret = bbs_db.delete_message(db_handle, msg_id, dst.upper())
            if ret:
              send_data(session, "Message deleted." + line_ending)
            else:
              send_data(session, "Message not found or not yours." + line_ending)
        else:
            send_data(session, "Usage: DEL <ID>" + line_ending)

    elif cmd == 'BYE':
        send_data(session, "Goodbye!" + line_ending)
        if 'ax25_session' in session:
            session['ax25_session'].close()
        elif 'tcp_session' in session:
            # Close the TCP session
            print(f"Closing TCP session for {src} -> {dst}")
            #session['tcp_session'].close()
            ssh_server.close_client(session['tcp_session'])
        else:
            print(f"No session found. Cannot close.")
        session['active'] = False
    else:
        send_data(session, f"Unknown command: {cmd}" + line_ending)
    send_prompt(session)
    bbs_db.shutdown(db_handle)


class bbs_connection(pe.connect.Connection):

  def __init__(self, port, call_from, call_to, incoming=False):
    super().__init__(port, call_from, call_to, incoming)
    # Now perform any initialization of your own that you might need
    print(f"New connection from {call_from} to {call_to} on port {port}")

  @classmethod
  def query_accept(cls, port, call_from, call_to):
    """
    This method is called when a new connection is being established.
    You can return True to accept the connection or False to reject it.
    """
    print(f"Querying connection from {call_from} to {call_to} on port {port}")
    # Validate callsigns
    if not is_valid_callsign(call_from) or not is_valid_callsign(call_to):
      print(f"Invalid callsign: {call_from} -> {call_to}")
      return False
    print(f"Accepting connection from {call_from} to {call_to}")
    return True

  def connected(self):
    print(f"Connection opened from {self.call_from} to {self.call_to}")
    session_manager.add_ax25(self.call_from, self.call_to, self.port, self)
    send_greeting(self.call_from, self.call_to, self.port)

  def disconnected(self):
      print(f"Connection closed from {self.call_from} to {self.call_to}")
      session_manager.remove(self.call_from, self.call_to, self.port)

  def data_received(self, pid, data):
      print(f"Data received from {self.call_from} to {self.call_to}: {data}")
      handle_command(db_filename, self.call_from, self.call_to, self.port, data.decode(errors='ignore').strip())


def send_data(session, data):
  if session['active']:
    if 'ax25_session' in session:
      print(f"Sending data to ax25 session")
      session['ax25_session'].send_data(data.encode())
    elif 'tcp_session' in session:
      print(f"Sending data to tcp_session")
      ssh_server.send_data(session['tcp_session'], data.encode())
    else:
      print(f"No session found. Cannot send data.")
      return False
  else:
    print(f"Session is not active, cannot send data.")
    return False
  return True


def send_greeting(call_from, call_to, port):
  session = session_manager.get(call_from, call_to, port)
  msg = bbs_banner_text
  send_data(session, msg)
  msg = line_ending + f"Welcome to OGLBBS v{version}!" + line_ending + "Type HELP for commands." + line_ending
  send_data(session, msg)
  send_prompt(session)


def shutdown():
  try:
    app.stop()
    print("BBS stopped.")
  except Exception:
    pass