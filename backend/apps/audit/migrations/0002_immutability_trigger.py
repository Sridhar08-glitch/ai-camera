"""
Database-level immutability for audit_event (ADR-016).

A BEFORE UPDATE trigger raises, so no UPDATE reaches the row from ANY client
(ORM, raw SQL, psql) — the trigger fires for the table owner too. DELETE is NOT
blocked at the database, because expired-row purging is performed by the bounded,
audited retention engine (which uses a dedicated manager; the default ORM manager
and all APIs forbid delete). Honest boundary: the owning role (aitraffic_app)
could DROP/DISABLE this trigger via explicit DDL; the application never does.
"""
from django.db import migrations

FORWARD = r"""
CREATE OR REPLACE FUNCTION audit_event_block_update() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'audit_event rows are immutable (update denied)';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_audit_event_no_update ON audit_event;
CREATE TRIGGER trg_audit_event_no_update
    BEFORE UPDATE ON audit_event
    FOR EACH ROW EXECUTE FUNCTION audit_event_block_update();
"""

REVERSE = r"""
DROP TRIGGER IF EXISTS trg_audit_event_no_update ON audit_event;
DROP FUNCTION IF EXISTS audit_event_block_update();
"""


class Migration(migrations.Migration):
    dependencies = [("audit", "0001_initial")]
    operations = [migrations.RunSQL(sql=FORWARD, reverse_sql=REVERSE)]
