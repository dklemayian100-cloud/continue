import os
import base64
import requests
from datetime import datetime

from dotenv import load_dotenv

load_dotenv()

MPESA_ENV = os.getenv("MPESA_ENV", "sandbox")
CONSUMER_KEY = os.getenv("MPESA_CONSUMER_KEY", "")
CONSUMER_SECRET = os.getenv("MPESA_CONSUMER_SECRET", "")
SHORTCODE = os.getenv("MPESA_SHORTCODE", "174379")
PASSKEY = os.getenv("MPESA_PASSKEY", "")
CALLBACK_URL = os.getenv("MPESA_CALLBACK_URL", "")

BASE = (
    "https://sandbox.safaricom.co.ke"
    if MPESA_ENV == "sandbox"
    else "https://api.safaricom.co.ke"
)

B2C_SHORTCODE = os.getenv("MPESA_B2C_SHORTCODE", SHORTCODE)
B2C_INITIATOR_NAME = os.getenv("MPESA_B2C_INITIATOR", "testapi")
B2C_SECURITY_CREDENTIAL = os.getenv("MPESA_B2C_SECURITY_CREDENTIAL", "")
B2C_RESULT_URL = os.getenv("MPESA_B2C_RESULT_URL", CALLBACK_URL)
B2C_TIMEOUT_URL = os.getenv("MPESA_B2C_TIMEOUT_URL", CALLBACK_URL)


def b2c_payout(phone: str, amount: int, remarks: str, occasion: str) -> dict:
    """Send money from shortcode to a customer phone (B2C). Sandbox-friendly."""
    token = get_access_token()
    payload = {
        "InitiatorName": B2C_INITIATOR_NAME,
        "SecurityCredential": B2C_SECURITY_CREDENTIAL,
        "CommandID": "BusinessPayment",
        "Amount": int(amount),
        "PartyA": B2C_SHORTCODE,
        "PartyB": phone,
        "Remarks": remarks[:100],
        "QueueTimeOutURL": B2C_TIMEOUT_URL,
        "ResultURL": B2C_RESULT_URL,
        "Occasion": occasion[:100],
    }
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.post(
        f"{BASE}/mpesa/b2c/v1/paymentrequest",
        json=payload,
        headers=headers,
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def get_access_token() -> str:
    url = f"{BASE}/oauth/v1/generate?grant_type=client_credentials"
    resp = requests.get(url, auth=(CONSUMER_KEY, CONSUMER_SECRET), timeout=20)
    resp.raise_for_status()
    return resp.json()["access_token"]


def stk_push(phone: str, amount: int, account_ref: str, description: str) -> dict:
    """Kick off an STK Push (Lipa na M-Pesa Online). Amount must be a whole KSh integer."""
    token = get_access_token()
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    password = base64.b64encode(
        f"{SHORTCODE}{PASSKEY}{timestamp}".encode()
    ).decode()

    payload = {
        "BusinessShortCode": SHORTCODE,
        "Password": password,
        "Timestamp": timestamp,
        "TransactionType": "CustomerPayBillOnline",
        "Amount": int(amount),
        "PartyA": phone,
        "PartyB": SHORTCODE,
        "PhoneNumber": phone,
        "CallBackURL": CALLBACK_URL,
        "AccountReference": account_ref[:12],
        "TransactionDesc": description[:13],
    }
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.post(
        f"{BASE}/mpesa/stkpush/v1/processrequest",
        json=payload,
        headers=headers,
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()