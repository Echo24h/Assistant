-- A screenshot can be joined to a bug report (JPEG or PNG, at most 2 MB).
ALTER TABLE bug_reports ADD COLUMN image BLOB;
