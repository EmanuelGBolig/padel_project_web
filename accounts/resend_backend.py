import os
import requests
from django.core.mail.backends.base import BaseEmailBackend
from django.conf import settings

class ResendBackend(BaseEmailBackend):
    def send_messages(self, email_messages):
        if not email_messages:
            return 0
        
        api_key = getattr(settings, 'RESEND_API_KEY', os.environ.get('RESEND_API_KEY'))
        if not api_key:
            print("!!! Missing RESEND_API_KEY")
            return 0

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        count = 0
        for message in email_messages:
            try:
                # Prepare payload
                payload = {
                    "from": message.from_email,
                    "to": message.to,
                    "subject": message.subject,
                    "text": message.body,
                }
                
                # Extract HTML content
                if hasattr(message, 'alternatives'):
                    for content, mimetype in message.alternatives:
                        if mimetype == 'text/html':
                            payload['html'] = content
                            break
                            
                # Fallback if body is HTML
                if not payload.get('html') and message.content_subtype == 'html':
                     payload['html'] = message.body

                # Send request
                print(f"--- Sending to Resend: {payload['to']} ---")
                response = requests.post(
                    "https://api.resend.com/emails",
                    json=payload,
                    headers=headers,
                    timeout=15
                )
                
                response.raise_for_status()
                print(f"--- Resend Response: {response.json()} ---")
                count += 1
            except Exception as e:
                print(f"!!! Error sending via Resend: {e}")
                if hasattr(e, 'response') and e.response is not None:
                    print(f"Response content: {e.response.text}")
                if not self.fail_silently:
                    raise e
                
        return count
