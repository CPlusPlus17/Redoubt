-- Run only against a coherent read-only copy of app files/places.sqlite + WAL/SHM.
-- Fresh expectation: valid schema, quick_check='ok', url_bookmark_count=0.
-- Root expectation: five type=2, fk=NULL folder GUIDs; not zero total rows.
PRAGMA query_only = ON;
PRAGMA quick_check;
PRAGMA user_version;
PRAGMA table_info(moz_bookmarks);
SELECT COUNT(*) AS url_bookmark_count FROM moz_bookmarks WHERE type = 1;
SELECT type, COUNT(*) AS row_count FROM moz_bookmarks GROUP BY type ORDER BY type;
SELECT guid, type, title, fk, parent, position
  FROM moz_bookmarks ORDER BY guid;

-- Preserve every URL bookmark in evidence, even if the joined place is missing.
SELECT b.guid, b.type, b.title, p.url, b.fk, parent.guid AS parent_guid
  FROM moz_bookmarks b
  LEFT JOIN moz_places p ON p.id = b.fk
  LEFT JOIN moz_bookmarks parent ON parent.id = b.parent
 WHERE b.type = 1 ORDER BY b.guid;

-- After real manual Bookmark page, and again after restart/upgrade:
-- Bind :control_url. Expect one row, same GUID/title/URL and a valid folder parent.
SELECT b.guid, b.title, p.url, parent.guid AS parent_guid, parent.type AS parent_type
  FROM moz_bookmarks b
  JOIN moz_places p ON p.id = b.fk
  LEFT JOIN moz_bookmarks parent ON parent.id = b.parent
 WHERE b.type = 1 AND p.url = :control_url;
SELECT COUNT(*) AS unexpected_url_bookmarks
  FROM moz_bookmarks b LEFT JOIN moz_places p ON p.id = b.fk
 WHERE b.type = 1 AND (p.url IS NULL OR p.url <> :control_url);
