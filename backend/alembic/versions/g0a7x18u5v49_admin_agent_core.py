"""Lara magtáblák (Fázis B): source_events, tasks, agent_runs,
action_traces, corrections, action_proposals, approvals, action_executions,
playbook_rules, trust_policies, settings. Additív; nem bánt meglévő táblát.

A singleton beállítás-sor (id=1) BIZTONSÁGOS alapállással jön létre: modul
kikapcsolva, mellékhatás tiltva. A trust_policies alap L0 (árnyék) minden
feladattípushoz.

Revision ID: g0a7x18u5v49
Revises: f9x6w07t4u48
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "g0a7x18u5v49"
down_revision = "f9x6w07t4u48"
branch_labels = None
depends_on = None


def _ts(t):
    t.append_column(sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()))
    t.append_column(sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()))


def upgrade() -> None:
    op.create_table(
        "aa_source_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("forras", sa.String(40), nullable=False, index=True),
        sa.Column("forras_azonosito", sa.String(255), nullable=False, index=True),
        sa.Column("forras_verzio", sa.String(120), nullable=True),
        sa.Column("allapot", sa.String(30), nullable=False, server_default="uj", index=True),
        sa.Column("metaadat", JSONB(), nullable=True),
        sa.Column("tartalom_hash", sa.String(64), nullable=True),
        sa.Column("feldolgozva_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("hiba", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("forras", "forras_azonosito", "forras_verzio", name="uq_aa_source_event"),
    )

    op.create_table(
        "aa_tasks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source_event_id", sa.Integer(), sa.ForeignKey("aa_source_events.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("tipus", sa.String(30), nullable=False, index=True),
        sa.Column("altipus", sa.String(60), nullable=True),
        sa.Column("cim", sa.String(300), nullable=False),
        sa.Column("osszefoglalo", sa.Text(), nullable=True),
        sa.Column("allapot", sa.String(30), nullable=False, server_default="new", index=True),
        sa.Column("prioritas", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("kockazat", sa.String(4), nullable=True),
        sa.Column("uncertainty", sa.Float(), nullable=True),
        sa.Column("trust_level", sa.String(4), nullable=False, server_default="L0"),
        sa.Column("felelos_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("hatarido", sa.DateTime(timezone=True), nullable=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("project_code_id", sa.Integer(), sa.ForeignKey("project_codes.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("client_id", sa.Integer(), sa.ForeignKey("clients.id", ondelete="SET NULL"), nullable=True),
        sa.Column("partner_nev", sa.String(255), nullable=True),
        sa.Column("parent_task_id", sa.Integer(), sa.ForeignKey("aa_tasks.id", ondelete="SET NULL"), nullable=True),
        sa.Column("blokkolo_ok", sa.Text(), nullable=True),
        sa.Column("utolso_hiba", sa.Text(), nullable=True),
        sa.Column("forras_referenciak", JSONB(), nullable=True),
        sa.Column("row_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("befejezve_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "aa_agent_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("task_id", sa.Integer(), sa.ForeignKey("aa_tasks.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("trigger", sa.String(40), nullable=False, server_default="manual"),
        sa.Column("allapot", sa.String(20), nullable=False, server_default="running", index=True),
        sa.Column("modell", sa.String(120), nullable=True),
        sa.Column("provider", sa.String(60), nullable=True),
        sa.Column("verzio_info", JSONB(), nullable=True),
        sa.Column("terv", JSONB(), nullable=True),
        sa.Column("kezdes_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("veg_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("token_hasznalat", sa.Integer(), nullable=True),
        sa.Column("koltseg_mikro", sa.BigInteger(), nullable=True),
        sa.Column("hibakod", sa.String(80), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "aa_action_proposals",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("task_id", sa.Integer(), sa.ForeignKey("aa_tasks.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("run_id", sa.Integer(), sa.ForeignKey("aa_agent_runs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("eszkoz", sa.String(80), nullable=False),
        sa.Column("payload", JSONB(), nullable=False),
        sa.Column("cel_verziok", JSONB(), nullable=True),
        sa.Column("payload_hash", sa.String(64), nullable=False, index=True),
        sa.Column("kockazat", sa.String(4), nullable=False),
        sa.Column("ellenorzesek", JSONB(), nullable=True),
        sa.Column("allapot", sa.String(20), nullable=False, server_default="ready", index=True),
        sa.Column("lejar_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "aa_approvals",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("proposal_id", sa.Integer(), sa.ForeignKey("aa_action_proposals.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("payload_hash", sa.String(64), nullable=False),
        sa.Column("allapot", sa.String(20), nullable=False, server_default="pending", index=True),
        sa.Column("donto_employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="SET NULL"), nullable=True),
        sa.Column("indok", sa.Text(), nullable=True),
        sa.Column("dontes_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lejar_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("felhasznalt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "aa_action_executions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("proposal_id", sa.Integer(), sa.ForeignKey("aa_action_proposals.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("approval_id", sa.Integer(), sa.ForeignKey("aa_approvals.id", ondelete="SET NULL"), nullable=True),
        sa.Column("idempotencia_kulcs", sa.String(120), nullable=False),
        sa.Column("allapot", sa.String(30), nullable=False, server_default="pending", index=True),
        sa.Column("probalkozasok", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("kulso_azonosito", sa.String(255), nullable=True),
        sa.Column("eredmeny", JSONB(), nullable=True),
        sa.Column("egyeztetes_allapot", sa.String(30), nullable=True),
        sa.Column("fencing_token", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("idempotencia_kulcs", name="uq_aa_execution_idempotencia"),
    )

    op.create_table(
        "aa_action_traces",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("task_id", sa.Integer(), sa.ForeignKey("aa_tasks.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("run_id", sa.Integer(), sa.ForeignKey("aa_agent_runs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("szereplo", sa.String(10), nullable=False),
        sa.Column("szereplo_employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="SET NULL"), nullable=True),
        sa.Column("muvelet", sa.String(80), nullable=False),
        sa.Column("eroforras", sa.String(120), nullable=True, index=True),
        sa.Column("diff", JSONB(), nullable=True),
        sa.Column("eredmeny", sa.String(40), nullable=True),
        sa.Column("tortent_at", sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "aa_corrections",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("task_id", sa.Integer(), sa.ForeignKey("aa_tasks.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("proposal_id", sa.Integer(), sa.ForeignKey("aa_action_proposals.id", ondelete="SET NULL"), nullable=True),
        sa.Column("eredeti", JSONB(), nullable=True),
        sa.Column("javitott", JSONB(), nullable=True),
        sa.Column("mezo_diff", JSONB(), nullable=True),
        sa.Column("javito_employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="SET NULL"), nullable=True),
        sa.Column("magyarazat", sa.Text(), nullable=True),
        sa.Column("tipus", sa.String(30), nullable=False, server_default="besorolando"),
        sa.Column("feldolgozas_allapot", sa.String(20), nullable=False, server_default="uj", index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "aa_playbook_rules",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("hatokor", sa.String(60), nullable=False, index=True),
        sa.Column("cim", sa.String(200), nullable=False),
        sa.Column("feltetelek", JSONB(), nullable=True),
        sa.Column("tartalom", sa.Text(), nullable=False),
        sa.Column("prioritas", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("verzio", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("allapot", sa.String(20), nullable=False, server_default="draft", index=True),
        sa.Column("forras_esetek", JSONB(), nullable=True),
        sa.Column("johaggyo_employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="SET NULL"), nullable=True),
        sa.Column("ervenyes_ig", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "aa_trust_policies",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tipus", sa.String(30), nullable=False),
        sa.Column("altipus", sa.String(60), nullable=True),
        sa.Column("szint", sa.String(4), nullable=False, server_default="L0"),
        sa.Column("auto_engedett_altipusok", JSONB(), nullable=True),
        sa.Column("modositotta_employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("tipus", "altipus", name="uq_aa_trust_tipus_altipus"),
    )

    op.create_table(
        "aa_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("module_enabled", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("side_effects_enabled", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("kill_switch", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("kill_switch_indok", sa.Text(), nullable=True),
        sa.Column("engedett_forrasok", JSONB(), nullable=True),
        sa.Column("limitek", JSONB(), nullable=True),
        sa.Column("modositotta_employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Singleton beállítás-sor BIZTONSÁGOS alapállással.
    op.execute(
        "INSERT INTO aa_settings (id, module_enabled, side_effects_enabled, kill_switch) "
        "VALUES (1, false, false, false)"
    )
    # Alap trust-policy L0 (árnyék) minden feladattípushoz (altipus = NULL = alap).
    for tipus in ("szamla", "email", "tig", "szerzodes", "utalas", "egyeb"):
        op.execute(
            f"INSERT INTO aa_trust_policies (tipus, altipus, szint) VALUES ('{tipus}', NULL, 'L0')"
        )


def downgrade() -> None:
    for tabla in (
        "aa_settings",
        "aa_trust_policies",
        "aa_playbook_rules",
        "aa_corrections",
        "aa_action_traces",
        "aa_action_executions",
        "aa_approvals",
        "aa_action_proposals",
        "aa_agent_runs",
        "aa_tasks",
        "aa_source_events",
    ):
        op.drop_table(tabla)
