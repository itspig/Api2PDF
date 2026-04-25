from datetime import UTC, datetime


def utc_now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
