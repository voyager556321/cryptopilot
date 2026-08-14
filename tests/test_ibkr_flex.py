"""Unit tests for IBKR Flex XML parsing (no network)."""

from src.ibkr.flex import parse_flex_positions_xml


SAMPLE = """<?xml version="1.0" encoding="UTF-8"?>
<FlexQueryResponse queryName="Positions" type="AF">
  <FlexStatements count="1">
    <FlexStatement accountId="U1234567" fromDate="20260801" toDate="20260807">
      <OpenPositions>
        <OpenPosition accountId="U1234567" symbol="AAPL" description="APPLE INC"
          assetCategory="STK" position="0.11" markPrice="311.43"
          positionValue="34.2573" costBasisPrice="289.52" costBasisMoney="31.8472"
          fifoPnlUnrealized="2.4101" />
        <OpenPosition accountId="U1234567" symbol="CSPX" description="ISHARES CORE S&amp;P 500"
          assetCategory="ETF" position="0.02" markPrice="832.02"
          positionValue="16.6404" costBasisPrice="899.57" costBasisMoney="17.9914"
          fifoPnlUnrealized="-1.351" />
        <OpenPosition accountId="U1234567" symbol="QBTS" description="D-WAVE QUANTUM"
          assetCategory="STK" position="0.35" markPrice="19.93"
          positionValue="6.9755" costBasisPrice="14.62" costBasisMoney="5.117"
          fifoPnlUnrealized="1.8585" />
        <OpenPosition accountId="U1234567" symbol="SPY" description="SPDR S&amp;P 500"
          assetCategory="OPT" position="1" markPrice="10" positionValue="10"
          costBasisPrice="10" costBasisMoney="10" fifoPnlUnrealized="0" />
      </OpenPositions>
      <CashReport>
        <CashReportCurrency accountId="U1234567" currency="BASE" endingCash="21.35" />
        <CashReportCurrency accountId="U1234567" currency="USD" endingCash="21.35" />
      </CashReport>
    </FlexStatement>
  </FlexStatements>
</FlexQueryResponse>
"""


def test_parse_flex_open_positions():
    positions, cash, meta = parse_flex_positions_xml(SAMPLE)
    symbols = {p["symbol"] for p in positions}
    assert symbols == {"AAPL", "CSPX", "QBTS"}  # OPT skipped
    assert abs(cash - 21.35) < 0.01
    assert meta["account_id"] == "U1234567"
    aapl = next(p for p in positions if p["symbol"] == "AAPL")
    assert abs(aapl["qty"] - 0.11) < 1e-9
    assert abs(aapl["last"] - 311.43) < 0.01
    assert aapl["tag"] == "core"
