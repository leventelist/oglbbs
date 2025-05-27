

# Sessions keyed by (src_call, dst_call, port)
sessions = {}


def add_ax25(src, dst, port, session):
    """Add a session to the sessions dictionary."""
    sessions[(src, dst, port)] = {'active': True, 'ax25_session': session}
    print(f"Added session: {src} -> {dst} on port {port}")


def add_tcp(src, dst, port, session):
    """Add a TCP session to the sessions dictionary."""
    sessions[(src, dst, port)] = {'active': True, 'tcp_session': session}
    print(f"Added TCP session: {src} -> {dst} on port {port}")


def remove(src, dst, port):
    """Remove a session from the sessions dictionary."""
    if (src, dst, port) in sessions:
        del sessions[(src, dst, port)]
        print(f"Removed session: {src} -> {dst} on port {port}")
    else:
        print(f"Session not found: {src} -> {dst} on port {port}")


def get(src, dst, port):
    """Get a session from the sessions dictionary."""
    return sessions.get((src, dst, port), None)
