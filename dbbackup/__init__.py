"""Database backup service for the Booking API.

Standalone package (stdlib only) that runs inside its own container:

* nightly full dump of the MariaDB database (``dump.py``),
* periodic archive of closed binary logs (``binlogs.py``) so a point-in-time
  recovery is possible,
* encrypted, retried delivery of both to the secondary server (``transfer.py``),
* local and remote retention (``prune.py``),
* row-level recovery after an accidental DELETE (``restore.py``),
* health reporting to Uptime Kuma (``heartbeat.py``).

It deliberately does not import anything from the Flask application.
"""
