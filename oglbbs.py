import configparser
import os
import argparse
import signal
import sys
import threading
import time

import ssh_server
import bbs_db
import bbs


shutdown_event = threading.Event()


def handle_signal(signum, frame):
  print(f"\nReceived signal {signum}, shutting down.")
  shutdown_event.set()


def shutdown():
  print("\nShutting down.")
  bbs.shutdown()
  bbs_db.shutdown(db)
  ssh_server.shutdown()
  for thread in threading.enumerate():
    if thread is not threading.current_thread():
      try:
        thread.join(timeout=1)
      except Exception:
        pass
  sys.exit(0)


if __name__ == '__main__':
  signal.signal(signal.SIGHUP, handle_signal)
  signal.signal(signal.SIGTERM, handle_signal)
  signal.signal(signal.SIGINT, handle_signal)

  # === Argument Parsing ===
  parser = argparse.ArgumentParser(description="pyham_pe SQLite BBS")
  parser.add_argument("-c", "--config", default=os.path.join(os.path.dirname(__file__), "oglbbs.conf"),
          help="Path to config file (default: oglbbs.conf in script directory)")
  args = parser.parse_args()

  # === Configuration ===
  print(f"[*] Using config file: {args.config}")
  config = configparser.ConfigParser()
  conf_path = args.config
  config.read(conf_path)

  db_file = config.get("db", "file_name", fallback="bbs.db")

  print(f"[*] Using database file: {db_file}")

  agw_host = config.get("agw", "host", fallback="localhost")
  agw_port = config.getint("agw", "port", fallback=8000)
  bbscall = config.get("station", "call", fallback="N0CALL")

  print(f"[*] Using AGWPE host: {agw_host}, port: {agw_port}")
  print(f"[*] Using station call: {bbscall}")

  ssh_addr = config.get("ssh", "listen_addr", fallback="localhost")
  ssh_port = config.getint("ssh", "listen_port", fallback=8002)
  ssh_key = config.get("ssh", "key", fallback="/etc/ssh/ssh_host_rsa_key")
  print(f"[*] Using SSH listener: {ssh_addr}:{ssh_port}")

  ssh_server.start_ssh_server(ssh_addr, ssh_port, ssh_key, bbscall, db_file)

  global db
  db = bbs_db.init_db(db_file)
  bbs.run_bbs(agw_host, agw_port, bbscall, db_file)

  # === Start BBS ===
  while True:
    ssh_server.step()
    time.sleep(0.1)
    if shutdown_event.is_set():
      shutdown()
