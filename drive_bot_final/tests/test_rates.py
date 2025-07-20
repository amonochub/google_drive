import decimal
import datetime as dt
from aioresponses import aioresponses
from app.handlers.client_calc import fetch_cbr_rate, CBR_URL
import pytest

@pytest.mark.asyncio
async def test_fetch_rate_ok():
    xml = '''<?xml version="1.0" encoding="windows-1251"?>
    <ValCurs Date="01.01.2025" name="Foreign Currency Market">
      <Valute ID="R01235">
        <NumCode>840</NumCode><CharCode>USD</CharCode><Nominal>1</Nominal><Name>US Dollar</Name><Value>90,00</Value>
      </Valute>
    </ValCurs>'''
    with aioresponses() as m:
        m.get(CBR_URL.format(for_date=dt.date(2025, 1, 1)), body=xml)
        rate = await fetch_cbr_rate("USD", dt.date(2025, 1, 1))
        assert rate == decimal.Decimal("90.00") 