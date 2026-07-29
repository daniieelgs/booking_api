import contextlib
import json
import os
import socket
import threading
import time
import uuid as uuid_lib

from globals import MAX_REPORT_SIZE, MAX_REPORTS_FILE_SIZE, REPORTS_FILE, log
from helpers.DatetimeHelper import now

try:
    import fcntl
except ImportError:
    fcntl = None

try:
    import msvcrt
except ImportError:
    msvcrt = None

# Evita colisiones entre hilos del mismo proceso (Flask arranca con threaded=True).
_thread_lock = threading.Lock()


def getReportsFile():
    return os.getenv('REPORTS_FILE', REPORTS_FILE)


def getMaxReportsFileSize():
    return int(os.getenv('MAX_REPORTS_FILE_SIZE', MAX_REPORTS_FILE_SIZE))


def getMaxReportSize():
    return int(os.getenv('MAX_REPORT_SIZE', MAX_REPORT_SIZE))


def getLockFile():
    return getReportsFile() + '.lock'


def ensureReportsFolder():
    folder = os.path.dirname(getReportsFile())
    if folder and not os.path.exists(folder):
        os.makedirs(folder, exist_ok=True)


@contextlib.contextmanager
def _cross_process_lock():
    """
    Bloqueo exclusivo a nivel de sistema operativo sobre un fichero .lock, para
    serializar el acceso al fichero de reportes entre distintos procesos
    (Apache/mod_wsgi puede levantar varios workers de la misma app).
    """
    ensureReportsFolder()

    lock_file = open(getLockFile(), 'a+')

    try:
        if os.path.getsize(lock_file.name) == 0:
            lock_file.write('0')
            lock_file.flush()

        if fcntl:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        elif msvcrt:
            lock_file.seek(0)
            msvcrt.locking(lock_file.fileno(), msvcrt.LK_LOCK, 1)

        yield
    finally:
        try:
            if fcntl:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
            elif msvcrt:
                lock_file.seek(0)
                msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
        finally:
            lock_file.close()


def _readReports(reports_file):
    if not os.path.exists(reports_file):
        return []

    try:
        with open(reports_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        if not isinstance(data, list):
            raise ValueError("The reports file does not contain a JSON array.")

        return data
    except (json.JSONDecodeError, ValueError):
        corrupt_path = f"{reports_file}.corrupt.{int(time.time())}"
        os.replace(reports_file, corrupt_path)
        log(f"The reports file was corrupted. Moved to '{corrupt_path}'.", level='WARNING')
        return []


def _writeReports(reports_file, reports):
    tmp_path = f"{reports_file}.tmp"

    with open(tmp_path, 'w', encoding='utf-8') as f:
        json.dump(reports, f, ensure_ascii=False, indent=2, default=str)

    os.replace(tmp_path, reports_file)


def _rotateIfNeeded(reports_file):
    if os.path.exists(reports_file) and os.path.getsize(reports_file) >= getMaxReportsFileSize():
        timestamp = now().strftime('%Y%m%d_%H%M%S')
        base, ext = os.path.splitext(reports_file)
        rotated_path = f"{base}.{timestamp}{ext}"

        os.replace(reports_file, rotated_path)
        log(f"The reports file reached its maximum size. Rotated to '{rotated_path}'.")


def buildRequestMeta(request):
    forwarded_for = request.headers.get('X-Forwarded-For')
    ip = forwarded_for.split(',')[0].strip() if forwarded_for else request.remote_addr

    return {
        'ip': ip,
        'headers': {
            'user_agent': request.headers.get('User-Agent'),
            'origin': request.headers.get('Origin'),
            'referer': request.headers.get('Referer'),
            'accept_language': request.headers.get('Accept-Language'),
        }
    }


def saveReport(report, request_meta):
    """
    Añade un reporte al fichero local de reportes de fallback. Devuelve (id, datetime).
    """
    reports_file = getReportsFile()

    report_id = uuid_lib.uuid4().hex
    report_datetime = now()

    entry = {
        'id': report_id,
        'datetime': report_datetime.isoformat(),
        'server': socket.gethostname(),
        **request_meta,
        'report': report,
    }

    with _thread_lock:
        with _cross_process_lock():
            _rotateIfNeeded(reports_file)
            reports = _readReports(reports_file)
            reports.append(entry)
            _writeReports(reports_file, reports)

    return report_id, report_datetime
