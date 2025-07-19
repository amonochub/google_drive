import logging, sys, orjson
from pythonjsonlogger import jsonlogger

class ORJsonFormatter(jsonlogger.JsonFormatter):
    def add_fields(self, log_record, record, msg, args):
        super().add_fields(log_record, record, msg, args)
        log_record["ts"] = record.created
    def dumps(self, obj):
        return orjson.dumps(obj).decode()

def setup(level: str = "INFO"):
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        ORJsonFormatter("(level) (ts) (event) (user_id) (file)")
    )
    root = logging.getLogger()
    root.setLevel(level)
    root.addHandler(handler) 