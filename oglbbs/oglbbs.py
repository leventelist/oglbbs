import configparser
import os
import argparse
import signal
import sys
import threading
import time

from . import ssh_server
from . import bbs_db
from . import bbs


shutdown_event = threading.Event()

# Global flags to control the start of TCP and AX.25 servers
# This is useful for testing purposes.
start_tcp = True
start_ax25 = True


def handle_signal(signum, frame):
  print(f"\nReceived signal {signum}, shutting down.")
  shutdown_event.set()


def shutdown():
  print("Shutting down.")
  bbs.shutdown()
  ssh_server.shutdown()
  for thread in threading.enumerate():
    if thread is not threading.current_thread():
      try:
        thread.join(timeout=1)
      except Exception:
        pass
  sys.exit(0)


def main():
  signal.signal(signal.SIGHUP, handle_signal)
  signal.signal(signal.SIGTERM, handle_signal)
  signal.signal(signal.SIGINT, handle_signal)

  # === Argument Parsing ===
  parser = argparse.ArgumentParser(description="pyham_pe SQLite BBS")
  parser.add_argument(
    "-c",
    "--config",
    default="./oglbbs.conf",
    help="Path to config file (default: ./oglbbs.conf)",
  )
  args = parser.parse_args()

  # === Configuration ===
  print(f"Using config file: {args.config}")
  config = configparser.ConfigParser()
  conf_path = args.config
  config.read(conf_path)

  db_file = config.get("db", "file_name", fallback="bbs.db")

  print(f"Using database file: {db_file}")

  agw_host = config.get("agw", "host", fallback="localhost")
  agw_port = config.getint("agw", "port", fallback=8000)
  bbscall = config.get("station", "call", fallback="N0CALL")

  bbsbanner = config.get("station", "banner", fallback="OGL BBS")

  print(f"Using AGWPE host: {agw_host}, port: {agw_port}")
  print(f"Using station call: {bbscall}")

  if start_tcp:
    ssh_addr = config.get("ssh", "listen_addr", fallback="localhost")
    ssh_port = config.getint("ssh", "listen_port", fallback=8002)
    ssh_key = config.get("ssh", "key", fallback="/etc/ssh/ssh_host_rsa_key")
    print(f"Using SSH listener: {ssh_addr}:{ssh_port}")

    ssh_server.start_ssh_server(ssh_addr, ssh_port, ssh_key, bbscall, db_file)
  else:
    print("Not starting the SSH server.")

  bbs.init(bbsbanner)

  if start_ax25:
    stat = bbs.run_bbs(agw_host, agw_port, bbscall, db_file)
    if not stat:
      print("Failed to start the BBS.")
      shutdown()
    print("BBS initialized and running.")
  else:
    print("Not starting the AX.25 server.")

  last_housekeeping = time.time()

  # === Start BBS ===
  while True:
    if start_tcp:
      ssh_server.step()
    time.sleep(0.1)
    # Add maintenance tasks.
    # Cancel chat requests if it is not answered in 30 seconds.
    # Delete old messages.
    # Disconnect inactive users.
    if time.time() - last_housekeeping > 600:
      # bbs.housekeeping()
      last_housekeeping = time.time()
    if shutdown_event.is_set():
      shutdown()
