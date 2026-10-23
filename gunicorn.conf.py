"""Gunicorn production configuration for Agile Hub."""
import multiprocessing
import os

# Server socket
bind = os.environ.get("GUNICORN_BIND", "0.0.0.0:8000")
backlog = 2048

# Worker processes
# Standard calculation: (2 x $num_cores) + 1, capped or configurable via WEB_CONCURRENCY
default_workers = max(multiprocessing.cpu_count() * 2 + 1, 2)
workers = int(os.environ.get("WEB_CONCURRENCY", default_workers))
worker_class = "sync"
worker_connections = 1000
timeout = int(os.environ.get("GUNICORN_TIMEOUT", 60))
keepalive = int(os.environ.get("GUNICORN_KEEPALIVE", 5))

# Process naming
proc_name = "agile_hub_gunicorn"

# Logging: stdout/stderr for Docker & 12-factor compliance
accesslog = "-"
errorlog = "-"
loglevel = os.environ.get("GUNICORN_LOG_LEVEL", "info")
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(L)ss'

# Server mechanics
preload_app = True
capture_output = True
enable_stdio_inheritance = True
