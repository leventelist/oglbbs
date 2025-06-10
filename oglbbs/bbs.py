import pe
import pe.app
import time
from pyfiglet import Figlet

from . import bbs_db
from . import session_manager
from . import ssh_server
import re

version = "1.0.0"
line_ending = "\r\n"


def init(banner):
  global bbs_banner_text
  # Generate the banner text
  f = Figlet(font="slant")
  bbs_banner_text = line_ending + line_ending
  bbs_banner_text += f.renderText(banner) + line_ending


# Connect to the AGWPE server and start the BBS
def run_bbs(agw_host, agw_port, call, db_file_name):
  global app
  global engine
  global db_filename
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
  match = re.fullmatch(
    r"([A-Z0-9]{1,2}[0-9][A-Z]{1,3})(?:-([0-9]|1[0-5]))?", callsign.upper()
  )
  if not match:
    return False

  full_prefix = match.group(1)
  prefix_part = full_prefix[:2]  # first 1–2 characters

  # Ensure at least one letter in first two characters
  return any(c.isalpha() for c in prefix_part)


def send_prompt(session, prefix=""):
  prompt = line_ending + prefix + ">" + line_ending
  send_data(session, prompt)


# === Command Handler ===
def handle_command(db_filename, src, dst, port, line):
  session = session_manager.get(src, dst, port)

  if session["active"] is False:
    print(f"Session {src} -> {dst} on port {port} is not active.")
    return

  match session["state"]:
    case "new":
      handle_new_session(session, db_filename, src, dst, port, line)
    case "chat_request":
      handle_chat_request_session(session, db_filename, src, dst, port, line)
    case "chat":
      handle_chat_session(session, db_filename, src, dst, port, line)
    case _:
      handle_new_session(session, db_filename, src, dst, port, line)

  # There might have been a change in the session state
  # Generate the prompt again
  do_prompt = True
  match session["state"]:
    case "chat":
      do_prompt = False
      prompt_prefix = None
    case "chat_request":
      prompt_prefix = f"Chat request with {session.get('chat_target')}"
    case "new":
      prompt_prefix = None
    case _:
      prompt_prefix = None
  if do_prompt:
    if prompt_prefix is not None:
      send_prompt(session, prompt_prefix)
    else:
      send_prompt(session)


def handle_chat_session(session, db_filename, src, dst, port, line):
  tokens = line.strip().split(maxsplit=1)
  if not tokens:
    return False
  cmd = tokens[0].upper()

  # Get target session
  target_sessions = session_manager.get_all_sessions_by_call(session["chat_target"])

  match cmd:
    case "_EOF_":
      print(f"Chat session ended from {src} to {dst} on port {port}")
      session["state"] = "new"
      session["chat_target"] = None
      send_data(session, "Chat session ended." + line_ending)
      for (_, _, _), target_session in target_sessions:
        send_data(target_session, "Chat session ended." + line_ending)
        target_session["state"] = "new"
        target_session["chat_target"] = None
    case _:
      for (_, _, _), target_session in target_sessions:
        send_data(target_session, line + line_ending)
  return True


def handle_chat_request_session(session, db_filename, src, dst, port, line):
  tokens = line.strip().split(maxsplit=1)
  if not tokens:
    return False
  cmd = tokens[0].upper()

  target_sessions = session_manager.get_all_sessions_by_call(session["chat_target"])

  match cmd:
    case "ACCEPT":
      print(f"Accepting chat request from {src} to {dst} on port {port}")
      if session["chat_target"] != src.upper():
        session["state"] = "chat"
        send_data(
          session,
          line_ending + "You are now connected. Type _EOF_ to end chat." + line_ending,
        )
        for (_, _, _), target_session in target_sessions:
          send_data(
            target_session,
            line_ending
            + "You are now connected. Type _EOF_ to end chat."
            + line_ending,
          )
          target_session["state"] = "chat"
    case "ABORT":
      print(f"Aborting chat request from {src} to {dst} on port {port}")
      session["state"] = "new"
      session["chat_target"] = None
      send_data(session, "Chat request aborted." + line_ending)
      for (_, _, _), target_session in target_sessions:
        send_data(target_session, "Chat request aborted." + line_ending)
        target_session["state"] = "new"
        target_session["chat_target"] = None
    case "HELP":
      send_data(
        session,
        """
Commands:
  HELP              - Show this help
  ACCEPT            - Accept chat request
  ABORT             - Abort chat request"""
        + line_ending,
      )
    case _:
      send_data(session, f"Unknown command: {cmd}" + line_ending)
  return True


def handle_new_session(session, db_filename, src, dst, port, line):
  tokens = line.strip().split(maxsplit=1)
  if not tokens:
    return False

  cmd = tokens[0].upper()

  db_handle = bbs_db.init_db(db_filename)

  match cmd:
    case "HELP":
      send_data(
        session,
        """
Commands:
  HELP              - Show this help
  INFO              - About this BBS
  MSG <text>        - Post a public message
  LIST              - Show recent public messages
  SEND <CALL> <msg> - Send private message
  READ              - Read private messages
  DEL <ID>          - Delete private message
  VER               - Show version
  CHAT <CALL>       - Send a chat message
  WHO               - List connected sessions
  BYE               - Disconnect"""
        + line_ending,
      )

    case "INFO":
      send_data(
        session,
        "This is OGLBBS. More info on https://github.com/leventelist/oglbbs"
        + line_ending,
      )

    case "MSG":
      if len(tokens) == 2:
        bbs_db.store_message(db_handle, src.upper(), tokens[1])
        send_data(session, "Message stored." + line_ending)
      else:
        send_data(session, "Usage: MSG <your message>" + line_ending)

    case "LIST":
      rows = bbs_db.list_messages(db_handle)
      if not rows:
        send_data(session, "No public messages." + line_ending)
      else:
        output = "\r\n".join([f"[{r[2]}] {r[0]}: {r[1]}" for r in rows])
        output += line_ending
        send_data(session, output)

    case "SEND":
      if len(tokens) == 2:
        parts = tokens[1].split(maxsplit=1)
        if len(parts) != 2:
          send_data(session, "Usage: SEND <CALLSIGN> <message>" + line_ending)
        else:
          rcpt, msg = parts
          bbs_db.store_private_message(db_handle, src.upper(), rcpt.upper(), msg)
          send_data(session, f"Message sent to {rcpt}" + line_ending)
      else:
        send_data(session, "Usage: SEND <CALLSIGN> <message>" + line_ending)

    case "READ":
      rows = bbs_db.list_private_messages(db_handle, src.upper())
      if not rows:
        output = "No private messages." + line_ending
      else:
        output = line_ending + "Private messages:" + line_ending
        for r in rows:
          output += f"[{r[3]}] ID:{r[0]} From {r[1]}: {r[2]}" + line_ending
        output += line_ending
      send_data(session, output)

    case "DEL":
      if len(tokens) == 2 and tokens[1].isdigit():
        msg_id = int(tokens[1])
        ret = bbs_db.delete_message(db_handle, msg_id, src.upper())
        if ret:
          send_data(session, "Message deleted." + line_ending)
        else:
          send_data(session, "Message not found or not yours." + line_ending)
      else:
        send_data(session, "Usage: DEL <ID>" + line_ending)

    case "BYE":
      send_data(session, "Goodbye!" + line_ending)
      if "ax25_session" in session:
        session["ax25_session"].close()
      elif "tcp_session" in session:
        # Close the TCP session
        print(f"Closing TCP session for {src} -> {dst}")
        ssh_server.close_client(session["tcp_session"])
      else:
        print(f"No session found. Cannot close.")
      session["active"] = False

    case "WHO":
      active_sessions = session_manager.get_active_sessions()
      if not active_sessions:
        # This is very unlikely, but handle it gracefully
        send_data(session, "No active sessions." + line_ending)
      else:
        output = "Active sessions:" + line_ending
        for (s, d, port), _ in active_sessions:
          output += f"{s} -> {d} on port {port}" + line_ending
        send_data(session, output + line_ending)

    case "CHAT":
      if len(tokens) == 2:
        chat_target = tokens[1].upper()
        return chat_init(session, chat_target, src)
      else:
        send_data(session, "Usage: CHAT <CALLSIGN>" + line_ending)

    case "VER":
      send_data(session, f"OGLBBS version {version}" + line_ending)

    case _:
      send_data(session, f"Unknown command: {cmd}" + line_ending)
      send_data(session, "Type HELP for commands." + line_ending)
  bbs_db.shutdown(db_handle)
  return True


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
    handle_command(
      db_filename,
      self.call_from,
      self.call_to,
      self.port,
      data.decode(errors="ignore").strip(),
    )


def chat_init(session, chat_target, call):
  # validate the chat target callsign
  if not is_valid_callsign(chat_target):
    send_data(session, f"Invalid callsign: {chat_target}" + line_ending)
    return False

  target_active = False
  # check if the target is active, i.e. connected to the BBS
  target_sessions = session_manager.get_all_sessions_by_call(chat_target)
  print(f"Got sessions for {chat_target}: {target_sessions}")
  for (_, _, _), target_session in target_sessions:
    if target_session["active"]:
      session["chat_target"] = chat_target
      # print(f"Chatting with {chat_target} on port {session['port']}")
      target_active = True
      break

  if not target_active:
    send_data(session, f"{chat_target} is not connected." + line_ending)
    send_data(
      session,
      "You might send a message. Use SEND <CALLSIGN> <message>" + line_ending,
    )
    return False

  # Check if the target is already in a chat
  if target_session["state"] == "chat_request" or target_session["state"] == "chat":
    send_data(session, f"{chat_target} is already in a chat." + line_ending)
    return False

  # Set the chat target in the session
  session["chat_target"] = chat_target
  session["state"] = "chat_request"
  target_session["state"] = "chat_request"
  target_session["chat_target"] = call

  # Notify the target about the chat request
  send_data(
    target_session,
    f"{call} wants to chat with you. Type ACCEPT to start chatting." + line_ending,
  )

  return True


# Send data to the session, either ax25 or tcp
def send_data(session, data):
  if session["active"]:
    if "ax25_session" in session:
      print(f"Sending data to ax25 session")
      session["ax25_session"].send_data(data.encode())
    elif "tcp_session" in session:
      print(f"Sending data to tcp_session")
      ssh_server.send_data(session["tcp_session"], data.encode())
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
  msg = (
    line_ending
    + f"Welcome to OGLBBS v{version}!"
    + line_ending
    + "Type HELP for commands."
    + line_ending
  )
  # Get number of messages
  db_handle = bbs_db.init_db(db_filename)
  private_messages = bbs_db.list_private_messages(db_handle, call_from.upper())
  bbs_db.shutdown(db_handle)
  message_count = len(private_messages)
  if message_count > 0:
    msg += f"You have {message_count} private messages." + line_ending
  else:
    msg += "You have no private messages." + line_ending

  send_data(session, msg)
  send_prompt(session)


def shutdown():
  try:
    app.stop()
    print("BBS stopped.")
  except Exception:
    pass
