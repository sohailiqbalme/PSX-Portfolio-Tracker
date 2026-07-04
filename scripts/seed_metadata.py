"""
scripts/seed_metadata.py
─────────────────────────────────────────────────────────────────────────────
Harvests all PSX listed tickers & sector categories using psxdata, 
and seeds the local database.
─────────────────────────────────────────────────────────────────────────────
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import psxdata
import pandas as pd
from app import create_app
from app.extensions import db
from app.models.company_metadata import CompanyMetadata

def seed():
    print("Fetching master symbols directory from PSX via psxdata...")
    try:
        df = psxdata.symbols()
    except Exception as e:
        print(f"Error fetching symbols from psxdata: {e}")
        sys.exit(1)
        
    if df is None or df.empty:
        print("No symbols returned by psxdata.")
        sys.exit(1)

    print(f"Fetched {len(df)} symbols from PSX. Cleaning data...")
    # Drop rows without ticker/symbol
    df = df.dropna(subset=["symbol"])
    
    # Filter out debt markets (TFCs, Bills, Bonds) as they aren't standard equities
    # Also skip ETFs to keep the list clean, but keep standard equities
    if "is_debt" in df.columns:
        df = df[df["is_debt"] == False]
    if "is_etf" in df.columns:
        df = df[df["is_etf"] == False]

    app = create_app("development")
    with app.app_context():
        print("Truncating existing company metadata...")
        # Clean the table before seeding
        db.session.query(CompanyMetadata).delete()
        
        inserted = 0
        for _, row in df.iterrows():
            ticker = str(row["symbol"]).strip().upper()
            name = str(row.get("name", ticker)).strip()
            # If name is blank or too short, fallback to ticker
            if not name or name.lower() == "nan":
                name = ticker
                
            sector = str(row.get("sector_name", "Miscellaneous")).strip().upper()
            if not sector or sector.lower() == "nan" or sector == "NONE":
                sector = "MISCELLANEOUS"

            meta = CompanyMetadata(
                ticker=ticker,
                company_name=name,
                sector=sector
            )
            db.session.add(meta)
            inserted += 1
            
        db.session.commit()
        print(f"Success! Seeded {inserted} company metadata records in company_metadata table.")

if __name__ == "__main__":
    seed()
