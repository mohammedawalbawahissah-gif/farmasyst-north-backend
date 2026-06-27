"""
0005_update_credit_type_choices
--------------------------------
Renames the stored credit_type values across every table that uses the
CreditApplication.CreditType enum so they match the frontend labels.

OLD value        → NEW value
---------------------------------
funding          → direct_financing
inputs           → farm_inputs
training         → structured_training
(new)            → mixed          (no existing rows to migrate)
"""

from django.db import migrations


# ── Old → New value mapping ───────────────────────────────────────────────────
VALUE_MAP = {
    'funding':  'direct_financing',
    'inputs':   'farm_inputs',
    'training': 'structured_training',
}

# Tables and column names that store credit_type
TARGETS = [
    ('credit_applications', 'credit_type'),
    ('credit_agreements',   'credit_type'),
    ('project_applications', 'credit_type'),
]


def forwards(apps, schema_editor):
    """Rename stored values from the old short slugs to the new descriptive slugs."""
    db = schema_editor.connection
    for table, column in TARGETS:
        for old_val, new_val in VALUE_MAP.items():
            db.cursor().execute(
                f"UPDATE {table} SET {column} = %s WHERE {column} = %s",
                [new_val, old_val],
            )


def backwards(apps, schema_editor):
    """Reverse: rename back to the old short slugs."""
    db = schema_editor.connection
    for table, column in TARGETS:
        for old_val, new_val in VALUE_MAP.items():
            db.cursor().execute(
                f"UPDATE {table} SET {column} = %s WHERE {column} = %s",
                [old_val, new_val],
            )


class Migration(migrations.Migration):

    dependencies = [
        ('credit', '0004_project_applications'),
    ]

    operations = [
        # ── 1. Rename stored values in existing rows ──────────────────────────
        migrations.RunPython(forwards, backwards),

        # ── 2. Update AlterField so Django knows the new valid choices ─────────
        #       (does not touch the DB column type — it stays VARCHAR(20))

        migrations.AlterField(
            model_name='creditapplication',
            name='credit_type',
            field=__import__('django.db.models', fromlist=['CharField']).CharField(
                max_length=20,
                choices=[
                    ('direct_financing',    'Direct Financing'),
                    ('farm_inputs',         'Farm Inputs'),
                    ('structured_training', 'Structured Training'),
                    ('mixed',               'Mixed'),
                ],
            ),
        ),

        migrations.AlterField(
            model_name='creditagreement',
            name='credit_type',
            field=__import__('django.db.models', fromlist=['CharField']).CharField(
                max_length=20,
                choices=[
                    ('direct_financing',    'Direct Financing'),
                    ('farm_inputs',         'Farm Inputs'),
                    ('structured_training', 'Structured Training'),
                    ('mixed',               'Mixed'),
                ],
            ),
        ),

        migrations.AlterField(
            model_name='projectapplication',
            name='credit_type',
            field=__import__('django.db.models', fromlist=['CharField']).CharField(
                max_length=20,
                choices=[
                    ('direct_financing',    'Direct Financing'),
                    ('farm_inputs',         'Farm Inputs'),
                    ('structured_training', 'Structured Training'),
                    ('mixed',               'Mixed'),
                ],
            ),
        ),
    ]
