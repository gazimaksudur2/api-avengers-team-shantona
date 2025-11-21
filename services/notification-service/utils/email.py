"""
Email Sending Utilities
"""
from app.observability import tracer
from app.config import settings


def send_email(recipient: str, template_id: str, data: dict) -> bool:
    """
    Send email notification (simulated)
    
    In production, this would integrate with SendGrid, AWS SES, etc.
    
    Args:
        recipient: Email recipient
        template_id: Email template ID
        data: Template data
    
    Returns:
        True if sent successfully, False otherwise
    """
    with tracer.start_as_current_span("send_email") as span:
        span.set_attribute("recipient", recipient)
        span.set_attribute("template_id", template_id)
        
        try:
            # Simulate email sending
            print(f"📧 Sending email to {recipient}")
            print(f"   Template: {template_id}")
            print(f"   Data: {data}")
            
            # In production, integrate with email provider:
            # Example with SendGrid:
            # import sendgrid
            # from sendgrid.helpers.mail import Mail
            # 
            # sg = sendgrid.SendGridAPIClient(api_key=settings.sendgrid_api_key)
            # message = Mail(
            #     from_email='noreply@careforall.org',
            #     to_emails=recipient,
            #     subject='Thank you for your donation!',
            #     html_content=render_template(template_id, data)
            # )
            # response = sg.send(message)
            # return response.status_code == 202
            
            span.set_attribute("status", "sent")
            return True
            
        except Exception as e:
            span.set_attribute("status", "failed")
            span.set_attribute("error", str(e))
            print(f"✗ Failed to send email: {e}")
            return False


def send_sms(recipient: str, message: str) -> bool:
    """
    Send SMS notification (placeholder)
    
    Args:
        recipient: Phone number
        message: SMS message
    
    Returns:
        True if sent successfully, False otherwise
    """
    print(f"📱 SMS to {recipient}: {message}")
    # In production: integrate with Twilio, AWS SNS, etc.
    return True

