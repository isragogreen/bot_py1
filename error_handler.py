import logging
import sys

logging.basicConfig(
    filename="bot_errors.log",
    level=logging.ERROR,
    format="%(asctime)s %(levelname)s %(message)s"
)

def log_error(e, context=""):
    """
    Логирует ошибку с контекстом и выводит в консоль.
    """
    msg = f"[{context}] {type(e).__name__}: {e}"
    logging.error(msg)
    print(msg, file=sys.stderr)

def handle_io_error(e):
    log_error(e, "IO")

def handle_memory_error(e):
    log_error(e, "Memory")

def handle_network_error(e):
    log_error(e, "Network")

def handle_external_service_error(e, service=""):
    log_error(e, f"Service:{service}")