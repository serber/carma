# SQLite storage for hit records: timestamp, plate string, confidence,
# format (KZ/RU/unknown), paths to the saved full-frame and cropped-plate
# images. Also backs the watchlist match check.
#
# TODO(stage 3, atomic step 20): schema + connection setup, insert_hit(),
# recent_hits() for the dashboard, watchlist match query.


def init_db(db_path: str) -> None:
    raise NotImplementedError
