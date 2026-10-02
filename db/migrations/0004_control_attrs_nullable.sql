-- A policy passage offered as a mapping candidate (pipeline/passages.py) has no extracted
-- attributes, so type and nature can be unknown. objective stays NOT NULL ('' for a passage).
ALTER TABLE control ALTER COLUMN type DROP NOT NULL;
ALTER TABLE control ALTER COLUMN nature DROP NOT NULL;
