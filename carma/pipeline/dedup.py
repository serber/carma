# Don't record the same plate repeatedly within a configurable time window.
#
# TODO(stage 4, atomic step 24): track last-seen timestamp per plate string,
# return whether a read should be recorded given dedup.window_seconds.


def should_record(plate: str, seen_at: float, window_seconds: float) -> bool:
    raise NotImplementedError
