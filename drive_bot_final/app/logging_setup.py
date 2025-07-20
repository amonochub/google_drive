import logging, sys, orjson
from pythonjsonlogger import jsonlogger
import structlog

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
    # Structlog config
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.stdlib.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(serializer=orjson.dumps),
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    ) 