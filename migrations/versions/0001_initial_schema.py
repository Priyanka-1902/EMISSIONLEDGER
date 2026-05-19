"""Initial multi-tenant schema with RLS

Revision ID: 0001_initial
Revises:
Create Date: 2024-01-15 00:00:00.000000

This migration:
1. Creates all core tables with tenant_id on every row-bearing table
2. Enables Row-Level Security (RLS) on all tenant-scoped tables
3. Creates the RLS policy using app.current_tenant_id session variable
4. Converts emission_records to a TimescaleDB hypertable
5. Creates continuous aggregates for monthly/annual emission summaries
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Enable required extensions ─────────────────────────────────────────────
    op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE")
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    # ── Application roles ──────────────────────────────────────────────────────
    op.execute("""
        DO $$ BEGIN
            CREATE ROLE emissionledger_app LOGIN PASSWORD 'changeme';
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE ROLE emissionledger_ro LOGIN PASSWORD 'changeme_ro';
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """)

    # ── Tenants ────────────────────────────────────────────────────────────────
    op.create_table("tenants",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("slug", sa.String(63), nullable=False),
        sa.Column("legal_name", sa.String(255), nullable=False),
        sa.Column("gstin", sa.String(15), nullable=False),
        sa.Column("pan", sa.String(10), nullable=False),
        sa.Column("registered_address", sa.Text, nullable=False),
        sa.Column("city", sa.String(100), nullable=False),
        sa.Column("state", sa.String(100), nullable=False),
        sa.Column("pincode", sa.String(10), nullable=False),
        sa.Column("country", sa.String(2), nullable=False, server_default="IN"),
        sa.Column("industry_sector", sa.String(50), nullable=False),
        sa.Column("isic_code", sa.String(4), nullable=False),
        sa.Column("tier", sa.String(20), nullable=False, server_default="entry"),
        sa.Column("status", sa.String(20), nullable=False, server_default="onboarding"),
        sa.Column("kms_key_arn", sa.String(255)),
        sa.Column("eu_exporter", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("cbam_declarant_id", sa.String(100)),
        sa.Column("bee_dc_number", sa.String(100)),
        sa.Column("settings", JSONB, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("ix_tenants_slug", "tenants", ["slug"], unique=True)
    op.create_index("ix_tenants_gstin", "tenants", ["gstin"], unique=True)

    # ── Users ──────────────────────────────────────────────────────────────────
    op.create_table("users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("cognito_sub", sa.String(255), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("role", sa.String(50), nullable=False),
        sa.Column("facility_ids", ARRAY(UUID(as_uuid=True)), nullable=False, server_default="{}"),
        sa.Column("mfa_enabled", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("last_login", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("ix_users_tenant_id", "users", ["tenant_id"])
    op.create_index("ix_users_cognito_sub", "users", ["cognito_sub"], unique=True)
    op.execute("ALTER TABLE users ADD CONSTRAINT uq_users_tenant_email UNIQUE (tenant_id, email)")

    # ── Facilities ─────────────────────────────────────────────────────────────
    op.create_table("facilities",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("address", sa.Text, nullable=False),
        sa.Column("city", sa.String(100), nullable=False),
        sa.Column("state", sa.String(100), nullable=False),
        sa.Column("pincode", sa.String(10), nullable=False),
        sa.Column("grid_region", sa.String(50)),
        sa.Column("discom", sa.String(100)),
        sa.Column("discom_consumer_number", sa.String(100)),
        sa.Column("naics_code", sa.String(10)),
        sa.Column("is_designated_consumer", sa.Boolean, server_default="false"),
        sa.Column("annual_energy_tep", sa.Numeric(12, 2)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("ix_facilities_tenant_id", "facilities", ["tenant_id"])

    # ── Emission Records (will become TimescaleDB hypertable) ─────────────────
    op.create_table("emission_records",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("facility_id", UUID(as_uuid=True), sa.ForeignKey("facilities.id"), nullable=False),
        sa.Column("activity_date", sa.Date, nullable=False),
        sa.Column("reporting_period_start", sa.Date, nullable=False),
        sa.Column("reporting_period_end", sa.Date, nullable=False),
        sa.Column("scope", sa.String(10), nullable=False),
        sa.Column("activity_type", sa.String(50), nullable=False),
        sa.Column("calculation_method", sa.String(30), nullable=False),
        sa.Column("confidence_level", sa.String(10), nullable=False),
        sa.Column("activity_description", sa.Text, nullable=False),
        sa.Column("activity_quantity", sa.Numeric(20, 6), nullable=False),
        sa.Column("activity_unit", sa.String(30), nullable=False),
        sa.Column("factor_id", UUID(as_uuid=True), nullable=False),
        sa.Column("factor_value", sa.Numeric(20, 10), nullable=False),
        sa.Column("factor_unit", sa.String(50), nullable=False),
        sa.Column("factor_version_hash", sa.String(64), nullable=False),
        sa.Column("tco2e", sa.Numeric(20, 6), nullable=False),
        sa.Column("tco2e_lower", sa.Numeric(20, 6), nullable=False),
        sa.Column("tco2e_upper", sa.Numeric(20, 6), nullable=False),
        sa.Column("source_record_id", sa.String(255)),
        sa.Column("source_system", sa.String(50)),
        sa.Column("source_document_s3_key", sa.String(500)),
        sa.Column("input_hash", sa.String(64), nullable=False),
        sa.Column("output_hash", sa.String(64), nullable=False),
        sa.Column("is_deleted", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id")),
    )
    op.create_index("ix_emission_records_tenant_date", "emission_records", ["tenant_id", "activity_date"])
    op.create_index("ix_emission_records_tenant_scope", "emission_records", ["tenant_id", "scope"])
    op.execute("""
        ALTER TABLE emission_records
        ADD CONSTRAINT ck_emission_records_tco2e_positive CHECK (tco2e >= 0),
        ADD CONSTRAINT ck_emission_records_lower_lte CHECK (tco2e_lower <= tco2e),
        ADD CONSTRAINT ck_emission_records_upper_gte CHECK (tco2e_upper >= tco2e)
    """)

    # Convert to TimescaleDB hypertable — partition by activity_date monthly
    op.execute("""
        SELECT create_hypertable(
            'emission_records',
            'activity_date',
            chunk_time_interval => INTERVAL '1 month',
            if_not_exists => TRUE
        )
    """)

    # Continuous aggregate: monthly totals per tenant/scope
    op.execute("""
        CREATE MATERIALIZED VIEW emission_monthly_totals
        WITH (timescaledb.continuous) AS
        SELECT
            tenant_id,
            facility_id,
            scope,
            time_bucket('1 month', activity_date) AS month,
            SUM(tco2e) AS total_tco2e,
            SUM(tco2e_lower) AS total_tco2e_lower,
            SUM(tco2e_upper) AS total_tco2e_upper,
            COUNT(*) AS record_count
        FROM emission_records
        WHERE is_deleted = false
        GROUP BY tenant_id, facility_id, scope, time_bucket('1 month', activity_date)
        WITH NO DATA
    """)
    op.execute("""
        SELECT add_continuous_aggregate_policy(
            'emission_monthly_totals',
            start_offset => INTERVAL '3 months',
            end_offset => INTERVAL '1 hour',
            schedule_interval => INTERVAL '1 day'
        )
    """)

    # ── Emission Factors ───────────────────────────────────────────────────────
    op.create_table("emission_factors",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("activity_type", sa.String(50), nullable=False),
        sa.Column("fuel_type", sa.String(50)),
        sa.Column("grid_region", sa.String(50)),
        sa.Column("isic_code", sa.String(10)),
        sa.Column("gas_type", sa.String(10), nullable=False, server_default="CO2e"),
        sa.Column("value", sa.Numeric(20, 10), nullable=False),
        sa.Column("unit", sa.String(50), nullable=False),
        sa.Column("gwp_basis", sa.String(10), nullable=False, server_default="AR6"),
        sa.Column("source", sa.String(50), nullable=False),
        sa.Column("source_publication", sa.Text, nullable=False),
        sa.Column("source_url", sa.String(500)),
        sa.Column("source_page", sa.String(50)),
        sa.Column("effective_from", sa.Date, nullable=False),
        sa.Column("effective_to", sa.Date),
        sa.Column("published_date", sa.Date, nullable=False),
        sa.Column("version", sa.String(20), nullable=False),
        sa.Column("version_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("superseded_by", UUID(as_uuid=True), sa.ForeignKey("emission_factors.id")),
        sa.Column("approved_by", sa.String(255)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("ix_emission_factors_activity_type", "emission_factors", ["activity_type", "effective_from"])

    # ── Reports ────────────────────────────────────────────────────────────────
    op.create_table("reports",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("report_type", sa.String(50), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("reporting_period_start", sa.Date, nullable=False),
        sa.Column("reporting_period_end", sa.Date, nullable=False),
        sa.Column("scope_1_tco2e", sa.Numeric(20, 6), nullable=False, server_default="0"),
        sa.Column("scope_2_tco2e", sa.Numeric(20, 6), nullable=False, server_default="0"),
        sa.Column("scope_3_tco2e", sa.Numeric(20, 6), nullable=False, server_default="0"),
        sa.Column("total_tco2e", sa.Numeric(20, 6), nullable=False, server_default="0"),
        sa.Column("data_completeness_pct", sa.Numeric(5, 2), nullable=False, server_default="0"),
        sa.Column("verification_level", sa.String(20)),
        sa.Column("s3_key", sa.String(500)),
        sa.Column("xml_s3_key", sa.String(500)),
        sa.Column("signature_hash", sa.String(128)),
        sa.Column("qr_audit_trail", sa.Text),
        sa.Column("approval_steps", JSONB, nullable=False, server_default="[]"),
        sa.Column("submitted_to", sa.String(255)),
        sa.Column("submission_reference", sa.String(255)),
        sa.Column("submitted_at", sa.DateTime(timezone=True)),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("parent_report_id", UUID(as_uuid=True), sa.ForeignKey("reports.id")),
        sa.Column("cbam_goods_category", sa.String(50)),
        sa.Column("cbam_cn_codes", ARRAY(sa.String), nullable=False, server_default="{}"),
        sa.Column("cbam_certificate_price_eur", sa.Numeric(10, 2)),
        sa.Column("cbam_financial_exposure_eur", sa.Numeric(20, 2)),
        sa.Column("uses_cbam_defaults", sa.Boolean, server_default="false"),
        sa.Column("cbam_declarant_id", sa.String(100)),
        sa.Column("metadata", JSONB, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("ix_reports_tenant_type", "reports", ["tenant_id", "report_type"])
    op.create_index("ix_reports_tenant_status", "reports", ["tenant_id", "status"])

    # ── Audit Log ──────────────────────────────────────────────────────────────
    op.create_table("audit_logs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("sequence_number", sa.Integer, nullable=False),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("actor_id", UUID(as_uuid=True)),
        sa.Column("actor_email", sa.String(255)),
        sa.Column("resource_type", sa.String(100)),
        sa.Column("resource_id", sa.String(255)),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("ip_address", sa.String(45)),
        sa.Column("user_agent", sa.String(500)),
        sa.Column("payload_hash", sa.String(64)),
        sa.Column("previous_hash", sa.String(64)),
        sa.Column("chain_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("ix_audit_logs_tenant_created", "audit_logs", ["tenant_id", "created_at"])
    op.execute("ALTER TABLE audit_logs ADD CONSTRAINT uq_audit_logs_tenant_seq UNIQUE (tenant_id, sequence_number)")

    # ── Ingestion Jobs ─────────────────────────────────────────────────────────
    op.create_table("ingestion_jobs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_system", sa.String(50), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("records_processed", sa.Integer, server_default="0"),
        sa.Column("records_failed", sa.Integer, server_default="0"),
        sa.Column("error_summary", JSONB, server_default="{}"),
        sa.Column("s3_source_key", sa.String(500)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id")),
    )
    op.create_index("ix_ingestion_jobs_tenant_status", "ingestion_jobs", ["tenant_id", "status"])

    # ── Compliance Rules ───────────────────────────────────────────────────────
    op.create_table("compliance_rules",
        sa.Column("id", sa.String(50), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("category", sa.String(30), nullable=False),
        sa.Column("severity", sa.String(10), nullable=False),
        sa.Column("effective_from", sa.Date, nullable=False),
        sa.Column("effective_to", sa.Date),
        sa.Column("version", sa.String(20), nullable=False),
        sa.Column("version_hash", sa.String(64), nullable=False),
        sa.Column("regulation_reference", sa.String(500), nullable=False),
        sa.Column("condition", JSONB, nullable=False),
        sa.Column("message_template", sa.Text, nullable=False),
        sa.Column("remediation_url", sa.String(500)),
        sa.Column("approved_by", sa.String(255)),
        sa.Column("approved_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
    )

    # ── Row-Level Security ─────────────────────────────────────────────────────
    rls_tables = ["users", "facilities", "emission_records", "reports", "audit_logs", "ingestion_jobs"]
    for table in rls_tables:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        # App role sees only its tenant's rows
        op.execute(f"""
            CREATE POLICY tenant_isolation ON {table}
            USING (tenant_id = current_setting('app.current_tenant_id')::uuid)
        """)
        # Superuser and service accounts bypass RLS (they set the session variable)
        op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO emissionledger_app")

    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON tenants TO emissionledger_app")
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON emission_factors TO emissionledger_app")
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON compliance_rules TO emissionledger_app")

    # Read-only role for BI/reporting
    for table in rls_tables + ["tenants", "emission_factors", "compliance_rules"]:
        op.execute(f"GRANT SELECT ON {table} TO emissionledger_ro")


def downgrade() -> None:
    rls_tables = ["users", "facilities", "emission_records", "reports", "audit_logs", "ingestion_jobs"]
    for table in rls_tables:
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")

    op.execute("DROP MATERIALIZED VIEW IF EXISTS emission_monthly_totals CASCADE")
    op.drop_table("compliance_rules")
    op.drop_table("ingestion_jobs")
    op.drop_table("audit_logs")
    op.drop_table("reports")
    op.drop_table("emission_factors")
    op.drop_table("emission_records")
    op.drop_table("facilities")
    op.drop_table("users")
    op.drop_table("tenants")
