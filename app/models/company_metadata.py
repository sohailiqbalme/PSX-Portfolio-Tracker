"""
app/models/company_metadata.py
─────────────────────────────────────────────────────────────────────────────
CompanyMetadata model — holds the master list of PSX symbols, names, and sectors.
─────────────────────────────────────────────────────────────────────────────
"""

from app.extensions import db

class CompanyMetadata(db.Model):
    """
    Holds master listing details for a PSX company/instrument.
    """
    __tablename__ = "company_metadata"

    ticker: db.Mapped[str] = db.mapped_column(
        db.String(20),
        primary_key=True,
        comment="Ticker symbol (e.g. 'ENGRO')"
    )
    
    company_name: db.Mapped[str] = db.mapped_column(
        db.String(255),
        nullable=False,
        comment="Official company name (e.g. 'Engro Corporation Limited')"
    )
    
    sector: db.Mapped[str] = db.mapped_column(
        db.String(100),
        nullable=False,
        index=True,
        comment="PSX industry sector (e.g. 'FERTILIZER')"
    )

    def to_dict(self) -> dict:
        """Serialize the model to a JSON-safe dictionary."""
        return {
            "ticker": self.ticker,
            "company_name": self.company_name,
            "sector": self.sector,
        }

    def __repr__(self) -> str:
        return f"<CompanyMetadata ticker={self.ticker!r} name={self.company_name!r}>"
