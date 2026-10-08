from apps.core.generic import ScopedModelListView
from apps.payroll.models import SalaryRecord


def test_list_view_selects_related_objects_used_by_columns():
    view = ScopedModelListView()
    view.model = SalaryRecord
    view.columns = (
        {"label": "Worker", "field": "worker__user__display_name"},
        {"label": "Period", "field": "period_start"},
    )

    assert view._related_column_fields() == ("worker__user",)
