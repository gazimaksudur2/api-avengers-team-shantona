"""
Tests for Payment Service - Focus on Idempotency
"""
import uuid
import json
from datetime import datetime, timedelta
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from main import app, Base, get_db, PaymentTransaction, IdempotencyKey, PaymentStateHistory

# Test database
TEST_DATABASE_URL = "sqlite:///./test_payments.db"
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


def test_create_payment_intent():
    """Test creating a payment intent"""
    donation_id = str(uuid.uuid4())
    payment_data = {
        "donation_id": donation_id,
        "amount": 100.00,
        "currency": "USD",
        "gateway": "stripe"
    }
    
    response = client.post("/api/v1/payments/intent", json=payment_data)
    assert response.status_code == 201
    
    data = response.json()
    assert data["donation_id"] == donation_id
    assert data["amount"] == 100.00
    assert data["status"] == "INITIATED"
    assert data["gateway"] == "stripe"
    assert "payment_intent_id" in data
    assert "client_secret" in data


def test_webhook_idempotency_same_key():
    """
    Test that webhooks with the same idempotency key return the same response
    This is the CORE idempotency test
    """
    # First, create a payment
    donation_id = str(uuid.uuid4())
    payment_data = {
        "donation_id": donation_id,
        "amount": 50.00,
        "currency": "USD",
        "gateway": "stripe"
    }
    create_response = client.post("/api/v1/payments/intent", json=payment_data)
    payment_intent_id = create_response.json()["payment_intent_id"]
    
    # Send webhook event (FIRST TIME)
    webhook_data = {
        "event_type": "payment_intent.succeeded",
        "payment_intent_id": payment_intent_id,
        "status": "AUTHORIZED",
        "timestamp": datetime.utcnow().isoformat(),
        "data": {"card_brand": "visa"}
    }
    
    idempotency_key = "test_webhook_123"
    headers = {"X-Idempotency-Key": idempotency_key}
    
    response1 = client.post(
        "/api/v1/payments/webhook",
        json=webhook_data,
        headers=headers
    )
    assert response1.status_code == 200
    data1 = response1.json()
    assert data1["status"] == "processed"
    assert data1["new_status"] == "AUTHORIZED"
    
    # Send SAME webhook again with SAME idempotency key (RETRY)
    response2 = client.post(
        "/api/v1/payments/webhook",
        json=webhook_data,
        headers=headers
    )
    assert response2.status_code == 200
    data2 = response2.json()
    
    # Response should be IDENTICAL
    assert data2 == data1
    
    # Verify payment status was only updated once
    db = TestingSessionLocal()
    payment = db.query(PaymentTransaction).filter_by(
        payment_intent_id=payment_intent_id
    ).first()
    assert payment.version == 2  # Only incremented once
    assert payment.status == "AUTHORIZED"
    db.close()


def test_webhook_different_keys():
    """Test that webhooks with different idempotency keys process independently"""
    # Create payment
    donation_id = str(uuid.uuid4())
    payment_data = {
        "donation_id": donation_id,
        "amount": 75.00,
        "currency": "USD",
        "gateway": "stripe"
    }
    create_response = client.post("/api/v1/payments/intent", json=payment_data)
    payment_intent_id = create_response.json()["payment_intent_id"]
    
    # Send first webhook
    webhook_data_1 = {
        "event_type": "payment_intent.succeeded",
        "payment_intent_id": payment_intent_id,
        "status": "AUTHORIZED",
        "timestamp": datetime.utcnow().isoformat()
    }
    
    response1 = client.post(
        "/api/v1/payments/webhook",
        json=webhook_data_1,
        headers={"X-Idempotency-Key": "key_1"}
    )
    assert response1.status_code == 200
    
    # Send second webhook with different key (valid transition)
    webhook_data_2 = {
        "event_type": "payment_intent.captured",
        "payment_intent_id": payment_intent_id,
        "status": "CAPTURED",
        "timestamp": (datetime.utcnow() + timedelta(seconds=5)).isoformat()
    }
    
    response2 = client.post(
        "/api/v1/payments/webhook",
        json=webhook_data_2,
        headers={"X-Idempotency-Key": "key_2"}
    )
    assert response2.status_code == 200
    data2 = response2.json()
    assert data2["new_status"] == "CAPTURED"


def test_invalid_state_transition():
    """Test that invalid state transitions are rejected"""
    # Create payment
    donation_id = str(uuid.uuid4())
    payment_data = {
        "donation_id": donation_id,
        "amount": 100.00,
        "currency": "USD",
        "gateway": "stripe"
    }
    create_response = client.post("/api/v1/payments/intent", json=payment_data)
    payment_intent_id = create_response.json()["payment_intent_id"]
    
    # Try to go directly to CAPTURED (invalid: INITIATED -> CAPTURED)
    webhook_data = {
        "event_type": "payment_intent.captured",
        "payment_intent_id": payment_intent_id,
        "status": "CAPTURED",
        "timestamp": datetime.utcnow().isoformat()
    }
    
    response = client.post(
        "/api/v1/payments/webhook",
        json=webhook_data,
        headers={"X-Idempotency-Key": "invalid_transition"}
    )
    assert response.status_code == 400
    data = response.json()
    assert data["status"] == "rejected"
    assert data["reason"] == "invalid_transition"


def test_out_of_order_webhook():
    """Test that out-of-order webhooks are ignored"""
    # Create payment
    donation_id = str(uuid.uuid4())
    payment_data = {
        "donation_id": donation_id,
        "amount": 100.00,
        "currency": "USD",
        "gateway": "stripe"
    }
    create_response = client.post("/api/v1/payments/intent", json=payment_data)
    payment_intent_id = create_response.json()["payment_intent_id"]
    
    now = datetime.utcnow()
    
    # Send AUTHORIZED webhook (newer timestamp)
    webhook_data_1 = {
        "event_type": "payment_intent.succeeded",
        "payment_intent_id": payment_intent_id,
        "status": "AUTHORIZED",
        "timestamp": now.isoformat()
    }
    
    response1 = client.post(
        "/api/v1/payments/webhook",
        json=webhook_data_1,
        headers={"X-Idempotency-Key": "newer_event"}
    )
    assert response1.status_code == 200
    
    # Send older webhook (should be ignored)
    webhook_data_2 = {
        "event_type": "payment_intent.processing",
        "payment_intent_id": payment_intent_id,
        "status": "INITIATED",
        "timestamp": (now - timedelta(seconds=10)).isoformat()
    }
    
    response2 = client.post(
        "/api/v1/payments/webhook",
        json=webhook_data_2,
        headers={"X-Idempotency-Key": "older_event"}
    )
    assert response2.status_code == 200
    data2 = response2.json()
    assert data2["status"] == "ignored"
    assert data2["reason"] == "out_of_order"


def test_state_machine_valid_transitions():
    """Test the complete state machine with valid transitions"""
    # Create payment
    donation_id = str(uuid.uuid4())
    payment_data = {
        "donation_id": donation_id,
        "amount": 100.00,
        "currency": "USD",
        "gateway": "stripe"
    }
    create_response = client.post("/api/v1/payments/intent", json=payment_data)
    payment_intent_id = create_response.json()["payment_intent_id"]
    
    now = datetime.utcnow()
    
    # INITIATED -> AUTHORIZED
    webhook_1 = {
        "event_type": "payment_intent.succeeded",
        "payment_intent_id": payment_intent_id,
        "status": "AUTHORIZED",
        "timestamp": now.isoformat()
    }
    response1 = client.post(
        "/api/v1/payments/webhook",
        json=webhook_1,
        headers={"X-Idempotency-Key": "step_1"}
    )
    assert response1.status_code == 200
    
    # AUTHORIZED -> CAPTURED
    webhook_2 = {
        "event_type": "payment_intent.captured",
        "payment_intent_id": payment_intent_id,
        "status": "CAPTURED",
        "timestamp": (now + timedelta(seconds=5)).isoformat()
    }
    response2 = client.post(
        "/api/v1/payments/webhook",
        json=webhook_2,
        headers={"X-Idempotency-Key": "step_2"}
    )
    assert response2.status_code == 200
    data2 = response2.json()
    assert data2["old_status"] == "AUTHORIZED"
    assert data2["new_status"] == "CAPTURED"
    
    # Verify final state
    db = TestingSessionLocal()
    payment = db.query(PaymentTransaction).filter_by(
        payment_intent_id=payment_intent_id
    ).first()
    assert payment.status == "CAPTURED"
    assert payment.version == 3  # INITIATED (1) -> AUTHORIZED (2) -> CAPTURED (3)
    
    # Verify state history
    history = db.query(PaymentStateHistory).filter_by(
        payment_id=payment.id
    ).order_by(PaymentStateHistory.id).all()
    assert len(history) == 2
    assert history[0].from_status == "INITIATED"
    assert history[0].to_status == "AUTHORIZED"
    assert history[1].from_status == "AUTHORIZED"
    assert history[1].to_status == "CAPTURED"
    
    db.close()


def test_idempotency_key_persistence():
    """Test that idempotency keys are persisted in the database"""
    # Create payment
    donation_id = str(uuid.uuid4())
    payment_data = {
        "donation_id": donation_id,
        "amount": 50.00,
        "currency": "USD",
        "gateway": "stripe"
    }
    create_response = client.post("/api/v1/payments/intent", json=payment_data)
    payment_intent_id = create_response.json()["payment_intent_id"]
    
    # Send webhook
    webhook_data = {
        "event_type": "payment_intent.succeeded",
        "payment_intent_id": payment_intent_id,
        "status": "AUTHORIZED",
        "timestamp": datetime.utcnow().isoformat()
    }
    
    idempotency_key = "persistent_key_test"
    client.post(
        "/api/v1/payments/webhook",
        json=webhook_data,
        headers={"X-Idempotency-Key": idempotency_key}
    )
    
    # Verify idempotency key is in database
    db = TestingSessionLocal()
    idem_record = db.query(IdempotencyKey).filter_by(key=idempotency_key).first()
    assert idem_record is not None
    assert idem_record.response_status == 200
    assert "processed" in idem_record.response_body
    db.close()


def test_get_payment_status():
    """Test retrieving payment status"""
    # Create payment
    donation_id = str(uuid.uuid4())
    payment_data = {
        "donation_id": donation_id,
        "amount": 100.00,
        "currency": "USD",
        "gateway": "stripe"
    }
    
    create_response = client.post("/api/v1/payments/intent", json=payment_data)
    payment_id = create_response.json()["id"]
    
    # Get status
    response = client.get(f"/api/v1/payments/{payment_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == payment_id
    assert data["status"] == "INITIATED"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

