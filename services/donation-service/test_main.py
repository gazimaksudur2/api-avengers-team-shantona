"""
Tests for Donation Service
"""
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from main import app, Base, get_db, Donation, OutboxEvent

# Test database
TEST_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base.metadata.create_all(bind=engine)


def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_database():
    """Clean database before each test"""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


def test_health_check():
    """Test health check endpoint"""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ["healthy", "degraded"]
    assert data["service"] == "donation-service"


def test_create_donation():
    """Test creating a donation with outbox pattern"""
    campaign_id = str(uuid.uuid4())
    donation_data = {
        "campaign_id": campaign_id,
        "donor_email": "test@example.com",
        "amount": 100.50,
        "currency": "USD",
        "metadata": {"source": "web"}
    }
    
    response = client.post("/api/v1/donations", json=donation_data)
    assert response.status_code == 201
    
    data = response.json()
    assert data["campaign_id"] == campaign_id
    assert data["donor_email"] == "test@example.com"
    assert data["amount"] == 100.50
    assert data["status"] == "PENDING"
    
    # Verify outbox event was created
    db = TestingSessionLocal()
    donation_id = data["id"]
    outbox = db.query(OutboxEvent).filter(
        OutboxEvent.aggregate_id == uuid.UUID(donation_id)
    ).first()
    assert outbox is not None
    assert outbox.event_type == "DonationCreated"
    assert outbox.processed_at is None
    db.close()


def test_create_donation_invalid_amount():
    """Test creating donation with invalid amount"""
    campaign_id = str(uuid.uuid4())
    donation_data = {
        "campaign_id": campaign_id,
        "donor_email": "test@example.com",
        "amount": -50,  # Invalid negative amount
        "currency": "USD"
    }
    
    response = client.post("/api/v1/donations", json=donation_data)
    assert response.status_code == 422  # Validation error


def test_get_donation():
    """Test retrieving a donation by ID"""
    # Create donation first
    campaign_id = str(uuid.uuid4())
    donation_data = {
        "campaign_id": campaign_id,
        "donor_email": "test@example.com",
        "amount": 50.00,
        "currency": "USD"
    }
    
    create_response = client.post("/api/v1/donations", json=donation_data)
    donation_id = create_response.json()["id"]
    
    # Get donation
    response = client.get(f"/api/v1/donations/{donation_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == donation_id
    assert data["amount"] == 50.00


def test_get_nonexistent_donation():
    """Test retrieving a non-existent donation"""
    fake_id = str(uuid.uuid4())
    response = client.get(f"/api/v1/donations/{fake_id}")
    assert response.status_code == 404


def test_get_donation_history():
    """Test retrieving donation history for a donor"""
    email = "donor@example.com"
    campaign_id = str(uuid.uuid4())
    
    # Create multiple donations
    for i in range(3):
        donation_data = {
            "campaign_id": campaign_id,
            "donor_email": email,
            "amount": 10.00 * (i + 1),
            "currency": "USD"
        }
        client.post("/api/v1/donations", json=donation_data)
    
    # Get history
    response = client.get(f"/api/v1/donations/history?donor_email={email}")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 3
    assert all(d["donor_email"] == email for d in data)


def test_update_donation_status():
    """Test updating donation status"""
    # Create donation
    campaign_id = str(uuid.uuid4())
    donation_data = {
        "campaign_id": campaign_id,
        "donor_email": "test@example.com",
        "amount": 75.00,
        "currency": "USD"
    }
    
    create_response = client.post("/api/v1/donations", json=donation_data)
    donation_id = create_response.json()["id"]
    
    # Update status
    update_data = {
        "status": "COMPLETED",
        "payment_intent_id": "pi_test_123"
    }
    
    response = client.patch(
        f"/api/v1/donations/{donation_id}/status",
        json=update_data
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "COMPLETED"
    assert data["payment_intent_id"] == "pi_test_123"
    
    # Verify outbox event was created for status change
    db = TestingSessionLocal()
    outbox_count = db.query(OutboxEvent).filter(
        OutboxEvent.aggregate_id == uuid.UUID(donation_id)
    ).count()
    assert outbox_count == 2  # DonationCreated + DonationStatusChanged
    db.close()


def test_transactional_outbox():
    """Test that donation and outbox event are created atomically"""
    db = TestingSessionLocal()
    
    # Count before
    donations_before = db.query(Donation).count()
    outbox_before = db.query(OutboxEvent).count()
    
    # Create donation
    campaign_id = str(uuid.uuid4())
    donation_data = {
        "campaign_id": campaign_id,
        "donor_email": "test@example.com",
        "amount": 100.00,
        "currency": "USD"
    }
    
    response = client.post("/api/v1/donations", json=donation_data)
    assert response.status_code == 201
    
    # Verify both were created
    donations_after = db.query(Donation).count()
    outbox_after = db.query(OutboxEvent).count()
    
    assert donations_after == donations_before + 1
    assert outbox_after == outbox_before + 1
    
    db.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

