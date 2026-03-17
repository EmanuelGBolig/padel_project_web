import os
import requests
from django.core.mail.backends.base import BaseEmailBackend
from django.conf import settings

class BrevoBackend(BaseEmailBackend):
    """
    Email backend for Brevo (Sendinblue) V3 API.
    """
    def send_messages(self, email_messages):
        if not email_messages:
            return 0
        
        api_key = getattr(settings, 'BREVO_API_KEY', os.environ.get('BREVO_API_KEY'))
        if not api_key:
            print("!!! Missing BREVO_API_KEY")
            return 0

        headers = {
            "api-key": api_key,
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        count = 0
        for message in email_messages:
            try:
                # Prepare payload
                payload = {
                    "sender": {"email": message.from_email},
                    "to": [{"email": recipient} for recipient in message.to],
                    "subject": message.subject,
                    "textContent": message.body,
                }
                
                # Extract HTML content
                if hasattr(message, 'alternatives'):
                    for content, mimetype in message.alternatives:
                        if mimetype == 'text/html':
                            payload['htmlContent'] = content
                            break
                            
                # Fallback if body is HTML
                if not payload.get('htmlContent') and message.content_subtype == 'html':
                     payload['htmlContent'] = message.body

                # Send request
                print(f"--- Sending to Brevo: {payload['to']} ---")
                response = requests.post(
                    "https://api.brevo.com/v3/smtp/email",
                    json=payload,
                    headers=headers,
                    timeout=15
                )
                
                response.raise_for_status()
                print(f"--- Brevo Response: {response.json()} ---")
                count += 1
            except Exception as e:
                print(f"!!! Error sending via Brevo: {e}")
                if hasattr(e, 'response') and e.response is not None:
                    print(f"Response content: {e.response.text}")
                if not self.fail_silently:
                    raise e
                
        return count
