from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable

from app.models import Base


def ddl(table_name: str) -> str:
    table = Base.metadata.tables[table_name]
    return str(CreateTable(table).compile(dialect=postgresql.dialect()))


def test_all_four_tables_defined():
    assert set(Base.metadata.tables) == {
        "transformers",
        "customers",
        "transformer_readings",
        "billing",
    }


def test_transformer_geom_is_computed_geography():
    sql = ddl("transformers")
    assert "geography(POINT,4326)" in sql
    assert "GENERATED ALWAYS AS" in sql
    assert "STORED" in sql


def test_readings_and_billing_use_composite_keys():
    assert "PRIMARY KEY (transformer_id, reading_date)" in ddl("transformer_readings")
    assert "PRIMARY KEY (customer_id, billing_month)" in ddl("billing")


def test_foreign_keys_cascade():
    assert "REFERENCES transformers (id) ON DELETE CASCADE" in ddl("customers")
    assert "REFERENCES customers (id) ON DELETE CASCADE" in ddl("billing")
