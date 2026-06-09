from demo_data import get_demo_workbook


def test_demo_workbook_has_two_sheets():
    wb = get_demo_workbook()
    assert "Orders" in wb and "Monthly by region" in wb
    assert len(wb["Orders"]) == 120
    assert "revenue" in wb["Orders"].columns
