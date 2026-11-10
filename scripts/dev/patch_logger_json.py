with open("modules/reporting/logger.py", "r", encoding="utf-8") as f:
    text = f.read()

helper_code = '''
def emit_structured_stdout_log(
    event: str,
    details: Optional[Dict[str, Any]] = None,
    level: str = "INFO",
) -> None:
    """
    Emit structured JSON log line to stdout for container log forwarding and SIEM services (Part E3).
    Active when LOG_STRUCTURED_JSON=1 or DEPLOYMENT_MODE=server.
    Adheres to privacy constraints: zero personal data or query names in log message.
    """
    if not (os.environ.get("LOG_STRUCTURED_JSON") == "1" or os.environ.get("DEPLOYMENT_MODE", "").lower() == "server"):
        return

    try:
        user = getpass.getuser()
    except Exception:
        user = "unknown"
    mode = os.environ.get("DEPLOYMENT_MODE", "desktop").lower()
    user_hash = hashlib.sha256(user.encode("utf-8")).hexdigest()[:12]

    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "level": level,
        "event": event,
        "mode": mode,
        "user_id": user_hash,
    }
    if details:
        payload.update(details)

    try:
        sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\\n")
        sys.stdout.flush()
    except Exception:
        pass
'''

if "def emit_structured_stdout_log" not in text:
    text = text.replace("DB_PATH = LOGS_DIR / \"screening.db\"", "DB_PATH = LOGS_DIR / \"screening.db\"\n" + helper_code)

# Add calls into log_search, log_raw_search, log_manual_check, log_acknowledgement
target_search = """        conn.commit()
        return cur.lastrowid"""

replacement_search = """        conn.commit()
        last_id = cur.lastrowid

    emit_structured_stdout_log(
        event="screening_search",
        details={
            "search_type": search_type,
            "query_type": query_type,
            "tier": overall_tier,
            "candidate_count": len(all_candidates or []),
            "sources_checked": sources_checked,
            "opensanctions_used": opensanctions_used,
            "duration_ms": duration_ms,
            "report_file": report_file_name,
        }
    )
    return last_id"""

target_raw = """        conn.commit()
        return cur.lastrowid
    finally:"""

replacement_raw = """        conn.commit()
        last_id = cur.lastrowid

    emit_structured_stdout_log(
        event="raw_search",
        details={
            "match_option": options.get("match_option"),
            "search_field": options.get("search_field"),
            "sources": options.get("sources"),
            "result_count": result_count,
            "report_file": report_file_name,
        }
    )
    return last_id
    finally:"""

text = text.replace(target_search, replacement_search)
text = text.replace(target_raw, replacement_raw)

with open("modules/reporting/logger.py", "w", encoding="utf-8") as f:
    f.write(text)

print("modules/reporting/logger.py patched with structured JSON logging!")
