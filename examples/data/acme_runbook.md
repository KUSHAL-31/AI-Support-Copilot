# Payments Runbook

Enterprise card payments can fail when processor risk checks reject authorization, when a
customer card is expired, or when the payment gateway times out. Support engineers should
check the processor response code, the gateway retry log, and the customer account status.

# API Key Rotation

API keys are rotated from the admin console. Create a new key, deploy it to the service
secret store, verify traffic with the new credential, and then revoke the old key.
