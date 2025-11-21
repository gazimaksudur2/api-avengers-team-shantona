"""
Data Aggregation Utilities for Dashboard
"""
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func, text

from app.models import Donation


def get_dashboard_metrics(db: Session) -> dict:
    """
    Aggregate dashboard metrics from database
    
    Returns:
        Dictionary with key metrics
    """
    # Total donations
    total_result = db.query(
        func.count(Donation.id).label('count'),
        func.sum(Donation.amount).label('total'),
        func.count(func.distinct(Donation.donor_email)).label('unique_donors')
    ).filter(Donation.status == 'COMPLETED').first()
    
    total_donations = total_result.count or 0
    total_amount = float(total_result.total or 0)
    total_donors = total_result.unique_donors or 0
    
    # Avg donation amount
    avg_amount = total_amount / total_donations if total_donations > 0 else 0
    
    # Donations today
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    donations_today = db.query(func.count(Donation.id)).filter(
        Donation.created_at >= today_start
    ).scalar() or 0
    
    # Campaign counts (using raw SQL since campaigns are in different DB)
    try:
        campaign_result = db.execute(text("""
            SELECT 
                COUNT(DISTINCT campaign_id) as total,
                COUNT(DISTINCT CASE WHEN status = 'COMPLETED' THEN campaign_id END) as active
            FROM donations
        """)).fetchone()
        
        total_campaigns = campaign_result[0] if campaign_result else 0
        active_campaigns = campaign_result[1] if campaign_result else 0
    except:
        total_campaigns = 0
        active_campaigns = 0
    
    return {
        "total_donations": total_donations,
        "total_amount": round(total_amount, 2),
        "total_campaigns": total_campaigns,
        "active_campaigns": active_campaigns,
        "total_donors": total_donors,
        "avg_donation_amount": round(avg_amount, 2),
        "donations_today": donations_today,
        "last_updated": datetime.utcnow()
    }

