"""
Database Connection and Session Management
"""
from sqlalchemy import create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from app.config import settings

# Create database engine
engine = create_engine(
    settings.database_url,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for models
Base = declarative_base()


def get_db():
    """Dependency to get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_materialized_view():
    """Initialize materialized view for campaign totals"""
    db = SessionLocal()
    try:
        print("Creating materialized view...")
        
        # Create materialized view
        db.execute(text("""
            CREATE MATERIALIZED VIEW IF NOT EXISTS campaign_totals AS
            SELECT 
                campaign_id,
                COUNT(*) as total_donations,
                SUM(amount) as total_amount,
                COUNT(DISTINCT donor_email) as unique_donors,
                MAX(updated_at) as last_updated
            FROM donations
            WHERE status = 'COMPLETED'
            GROUP BY campaign_id
        """))
        
        # Create unique index for concurrent refresh
        db.execute(text("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_campaign_totals_id 
            ON campaign_totals (campaign_id)
        """))
        
        db.commit()
        print("✓ Materialized view ready")
        
    except Exception as e:
        print(f"Note: {e}")
        db.rollback()
    finally:
        db.close()

