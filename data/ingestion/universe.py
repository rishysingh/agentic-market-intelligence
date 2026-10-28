"""Security Master Universe with Stable Security IDs, SEC CIKs, and Sector Classifications."""

from typing import Dict, List, Any

SECURITY_MASTER_UNIVERSE: List[Dict[str, Any]] = [
    # Benchmark & Regime ETFs
    {"security_id": "sec-etf-spy", "cik": "0000884394", "ticker": "SPY", "company_name": "SPDR S&P 500 ETF Trust", "exchange": "NYSE_ARCA", "sector": "Index Benchmark", "industry": "Broad US Equity ETF", "is_active": True, "is_etf": True, "effective_from": "1993-01-29"},
    {"security_id": "sec-etf-qqq", "cik": "0001067839", "ticker": "QQQ", "company_name": "Invesco QQQ Trust", "exchange": "NASDAQ", "sector": "Index Benchmark", "industry": "Nasdaq-100 Growth ETF", "is_active": True, "is_etf": True, "effective_from": "1999-03-10"},
    {"security_id": "sec-etf-iwm", "cik": "0001100663", "ticker": "IWM", "company_name": "iShares Russell 2000 ETF", "exchange": "NYSE_ARCA", "sector": "Index Benchmark", "industry": "Small-Cap US Equity ETF", "is_active": True, "is_etf": True, "effective_from": "2000-05-22"},
    {"security_id": "sec-etf-tlt", "cik": "0001100663", "ticker": "TLT", "company_name": "iShares 20+ Year Treasury Bond ETF", "exchange": "NASDAQ", "sector": "Fixed Income", "industry": "Long Duration US Treasury ETF", "is_active": True, "is_etf": True, "effective_from": "2002-07-22"},
    {"security_id": "sec-etf-gld", "cik": "0001222333", "ticker": "GLD", "company_name": "SPDR Gold Trust", "exchange": "NYSE_ARCA", "sector": "Commodities", "industry": "Physical Gold Bullion ETF", "is_active": True, "is_etf": True, "effective_from": "2004-11-18"},
    # Information Technology
    {"security_id": "sec-eq-nvda", "cik": "0001045810", "ticker": "NVDA", "company_name": "NVIDIA Corporation", "exchange": "NASDAQ", "sector": "Information Technology", "industry": "Semiconductors & AI Accelerators", "is_active": True, "is_etf": False, "effective_from": "1999-01-22"},
    {"security_id": "sec-eq-aapl", "cik": "0000320193", "ticker": "AAPL", "company_name": "Apple Inc.", "exchange": "NASDAQ", "sector": "Information Technology", "industry": "Consumer Hardware & Ecosystem", "is_active": True, "is_etf": False, "effective_from": "1980-12-12"},
    {"security_id": "sec-eq-msft", "cik": "0000789019", "ticker": "MSFT", "company_name": "Microsoft Corporation", "exchange": "NASDAQ", "sector": "Information Technology", "industry": "Enterprise Cloud & Software", "is_active": True, "is_etf": False, "effective_from": "1986-03-13"},
    {"security_id": "sec-eq-amd", "cik": "0000002488", "ticker": "AMD", "company_name": "Advanced Micro Devices, Inc.", "exchange": "NASDAQ", "sector": "Information Technology", "industry": "Semiconductors", "is_active": True, "is_etf": False, "effective_from": "1972-09-27"},
    # Communication Services
    {"security_id": "sec-eq-googl", "cik": "0001652044", "ticker": "GOOGL", "company_name": "Alphabet Inc.", "exchange": "NASDAQ", "sector": "Communication Services", "industry": "Interactive Media, Search & Cloud AI", "is_active": True, "is_etf": False, "effective_from": "2004-08-19"},
    {"security_id": "sec-eq-meta", "cik": "0001326801", "ticker": "META", "company_name": "Meta Platforms, Inc.", "exchange": "NASDAQ", "sector": "Communication Services", "industry": "Social Platforms & AI Advertising", "is_active": True, "is_etf": False, "effective_from": "2012-05-18"},
    {"security_id": "sec-eq-nflx", "cik": "0001065280", "ticker": "NFLX", "company_name": "Netflix, Inc.", "exchange": "NASDAQ", "sector": "Communication Services", "industry": "Streaming Entertainment", "is_active": True, "is_etf": False, "effective_from": "2002-05-23"},
    # Consumer Discretionary
    {"security_id": "sec-eq-amzn", "cik": "0001018724", "ticker": "AMZN", "company_name": "Amazon.com, Inc.", "exchange": "NASDAQ", "sector": "Consumer Discretionary", "industry": "E-Commerce & AWS Cloud", "is_active": True, "is_etf": False, "effective_from": "1997-05-15"},
    {"security_id": "sec-eq-tsla", "cik": "0001318605", "ticker": "TSLA", "company_name": "Tesla, Inc.", "exchange": "NASDAQ", "sector": "Consumer Discretionary", "industry": "Electric Vehicles & Energy Storage", "is_active": True, "is_etf": False, "effective_from": "2010-06-29"},
    {"security_id": "sec-eq-hd", "cik": "0000354950", "ticker": "HD", "company_name": "The Home Depot, Inc.", "exchange": "NYSE", "sector": "Consumer Discretionary", "industry": "Home Improvement Retail", "is_active": True, "is_etf": False, "effective_from": "1981-09-22"},
    # Financials
    {"security_id": "sec-eq-jpm", "cik": "0000019617", "ticker": "JPM", "company_name": "JPMorgan Chase & Co.", "exchange": "NYSE", "sector": "Financials", "industry": "Diversified Money Center Banks", "is_active": True, "is_etf": False, "effective_from": "1969-03-05"},
    {"security_id": "sec-eq-gs", "cik": "0000886982", "ticker": "GS", "company_name": "The Goldman Sachs Group, Inc.", "exchange": "NYSE", "sector": "Financials", "industry": "Investment Banking & Capital Markets", "is_active": True, "is_etf": False, "effective_from": "1999-05-04"},
    {"security_id": "sec-eq-v", "cik": "0001403161", "ticker": "V", "company_name": "Visa Inc.", "exchange": "NYSE", "sector": "Financials", "industry": "Transaction & Payment Processing", "is_active": True, "is_etf": False, "effective_from": "2008-03-19"},
    # Health Care
    {"security_id": "sec-eq-lly", "cik": "0000059478", "ticker": "LLY", "company_name": "Eli Lilly and Company", "exchange": "NYSE", "sector": "Health Care", "industry": "Pharmaceuticals & GLP-1 Therapeutics", "is_active": True, "is_etf": False, "effective_from": "1952-01-02"},
    {"security_id": "sec-eq-pfe", "cik": "0000078003", "ticker": "PFE", "company_name": "Pfizer Inc.", "exchange": "NYSE", "sector": "Health Care", "industry": "Biopharmaceuticals", "is_active": True, "is_etf": False, "effective_from": "1942-06-22"},
    # Energy
    {"security_id": "sec-eq-xom", "cik": "0000034088", "ticker": "XOM", "company_name": "Exxon Mobil Corporation", "exchange": "NYSE", "sector": "Energy", "industry": "Integrated Oil & Gas", "is_active": True, "is_etf": False, "effective_from": "1920-03-01"},
    {"security_id": "sec-eq-cvx", "cik": "0000093410", "ticker": "CVX", "company_name": "Chevron Corporation", "exchange": "NYSE", "sector": "Energy", "industry": "Integrated Oil & Gas", "is_active": True, "is_etf": False, "effective_from": "1926-01-02"},
    # Industrials & Consumer Staples & Utilities
    {"security_id": "sec-eq-ba", "cik": "0000012927", "ticker": "BA", "company_name": "The Boeing Company", "exchange": "NYSE", "sector": "Industrials", "industry": "Aerospace & Defense", "is_active": True, "is_etf": False, "effective_from": "1962-01-02"},
    {"security_id": "sec-eq-wmt", "cik": "0000104169", "ticker": "WMT", "company_name": "Walmart Inc.", "exchange": "NYSE", "sector": "Consumer Staples", "industry": "Hypermarkets & Super Centers", "is_active": True, "is_etf": False, "effective_from": "1972-08-25"},
    {"security_id": "sec-eq-nee", "cik": "0000753308", "ticker": "NEE", "company_name": "NextEra Energy, Inc.", "exchange": "NYSE", "sector": "Utilities", "industry": "Electric Utilities & Renewables", "is_active": True, "is_etf": False, "effective_from": "1984-12-31"},
]

TICKER_TO_SECURITY: Dict[str, Dict[str, Any]] = {
    item["ticker"]: item for item in SECURITY_MASTER_UNIVERSE
}
