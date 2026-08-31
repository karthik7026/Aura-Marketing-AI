import os
import datetime
import uuid
import hmac
import hashlib
import razorpay
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from pymongo.database import Database

from backend.database import get_db
from backend.deps import get_current_user as get_current_user_helper

router = APIRouter(prefix="/api/wallet", tags=["Wallet & Razorpay Payments"])


def get_razorpay_credentials():
    key_id = os.getenv("RAZORPAY_KEY_ID", "rzp_test_TVFsRcrLVPCbPu").strip()
    key_secret = os.getenv("RAZORPAY_KEY_SECRET", "Nh5WOjudw82uTiG097Q43I9X").strip()
    client = None
    if key_id and key_id != "rzp_test_placeholder" and key_secret:
        try:
            client = razorpay.Client(auth=(key_id, key_secret))
        except Exception as e:
            print(f"Razorpay Client init warning: {e}")
            client = None
    return key_id, key_secret, client


class CreateOrderRequest(BaseModel):
    amount_in_inr: Optional[float] = None
    price: Optional[float] = None
    tier_name: str
    tokens_to_add: Optional[int] = None
    token_amount: Optional[int] = None

    def get_amount(self) -> float:
        if self.amount_in_inr is not None:
            return self.amount_in_inr
        if self.price is not None:
            return self.price
        return 0.0

    def get_tokens(self) -> int:
        if self.tokens_to_add is not None:
            return self.tokens_to_add
        if self.token_amount is not None:
            return self.token_amount
        return 0


class VerifyPaymentRequest(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str
    tier_name: str
    tokens_to_add: Optional[int] = None
    token_amount: Optional[int] = None
    amount: Optional[float] = None
    price: Optional[float] = None

    def get_tokens(self) -> int:
        if self.tokens_to_add is not None:
            return self.tokens_to_add
        if self.token_amount is not None:
            return self.token_amount
        return 0

    def get_amount(self) -> float:
        if self.amount is not None:
            return self.amount
        if self.price is not None:
            return self.price
        return 0.0


@router.get("/balance")
def get_wallet_balance(
    current_user: dict = Depends(get_current_user_helper),
    db: Database = Depends(get_db),
):
    return {
        "email": current_user["email"],
        "tokens": current_user.get("tokens", 0),
        "transactions": current_user.get("transactions", []),
    }


@router.post("/create-razorpay-order")
@router.post("/razorpay/order")
def create_razorpay_order(
    req: CreateOrderRequest,
    current_user: dict = Depends(get_current_user_helper),
):
    amount = req.get_amount()
    tokens = req.get_tokens()
    key_id, key_secret, client = get_razorpay_credentials()

    if not client:
        mock_id = f"order_mock_{uuid.uuid4().hex[:12]}"
        return {
            "order_id": mock_id,
            "currency": "INR",
            "amount": int(amount * 100),
            "key_id": key_id,
            "key": key_id,
            "is_mock": True,
        }

    try:
        amount_paisa = int(amount * 100)
        data = {
            "amount": amount_paisa,
            "currency": "INR",
            "receipt": f"rcpt_{uuid.uuid4().hex[:8]}",
            "notes": {
                "user_email": current_user["email"],
                "tier_name": req.tier_name,
                "tokens_to_add": tokens,
            },
        }
        order = client.order.create(data=data)
        return {
            "order_id": order["id"],
            "currency": order["currency"],
            "amount": order["amount"],
            "key_id": key_id,
            "key": key_id,
            "is_mock": False,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Razorpay Order Creation Failed: {str(e)}")


@router.post("/verify-payment")
@router.post("/razorpay/verify")
def verify_payment_signature(
    req: VerifyPaymentRequest,
    current_user: dict = Depends(get_current_user_helper),
    db: Database = Depends(get_db),
):
    order_id = req.razorpay_order_id
    payment_id = req.razorpay_payment_id
    signature = req.razorpay_signature
    tokens_to_credit = req.get_tokens()
    amount = req.get_amount()
    key_id, key_secret, _ = get_razorpay_credentials()

    # Idempotency Check: Prevent duplicate payment processing for the same order_id
    user_doc = db.users.find_one({"email": current_user["email"]})
    if user_doc:
        for tx in user_doc.get("transactions", []):
            if tx.get("order_id") == order_id or tx.get("payment_id") == payment_id:
                bal = user_doc.get("tokens", 0)
                return {
                    "status": "success",
                    "verified": True,
                    "is_mock": order_id.startswith("order_mock_"),
                    "message": "Payment already verified.",
                    "new_balance": bal,
                    "new_token_balance": bal,
                    "transaction_id": tx.get("transaction_id", order_id),
                }

    if order_id.startswith("order_mock_"):
        tx_id = f"TX_MOCK_{uuid.uuid4().hex[:8].upper()}"
        now_iso = datetime.datetime.utcnow().isoformat() + "Z"

        db.users.update_one(
            {"email": current_user["email"]},
            {
                "$inc": {"tokens": tokens_to_credit},
                "$push": {
                    "transactions": {
                        "transaction_id": tx_id,
                        "order_id": order_id,
                        "payment_id": payment_id,
                        "tier_name": req.tier_name,
                        "amount": tokens_to_credit,
                        "price": amount,
                        "payment_method": "razorpay_mock",
                        "status": "success",
                        "created_at": now_iso,
                    }
                },
            },
        )

        updated_user = db.users.find_one({"email": current_user["email"]})
        bal = updated_user.get("tokens", 0) if updated_user else tokens_to_credit
        return {
            "status": "success",
            "verified": True,
            "is_mock": True,
            "message": f"Successfully credited {tokens_to_credit} tokens!",
            "new_balance": bal,
            "new_token_balance": bal,
            "transaction_id": tx_id,
        }

    if not key_secret:
        raise HTTPException(
            status_code=400,
            detail="RAZORPAY_KEY_SECRET is not configured on the backend server.",
        )

    generated_signature = hmac.new(
        key_secret.encode("utf-8"),
        f"{order_id}|{payment_id}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    if generated_signature != signature:
        raise HTTPException(
            status_code=400,
            detail="Invalid Razorpay payment signature. Verification failed.",
        )

    tx_id = f"TX_RZP_{uuid.uuid4().hex[:8].upper()}"
    now_iso = datetime.datetime.utcnow().isoformat() + "Z"

    db.users.update_one(
        {"email": current_user["email"]},
        {
            "$inc": {"tokens": tokens_to_credit},
            "$push": {
                "transactions": {
                    "transaction_id": tx_id,
                    "order_id": order_id,
                    "payment_id": payment_id,
                    "tier_name": req.tier_name,
                    "amount": tokens_to_credit,
                    "price": amount,
                    "payment_method": "razorpay_card",
                    "status": "success",
                    "created_at": now_iso,
                }
            },
        },
    )

    updated_user = db.users.find_one({"email": current_user["email"]})
    bal = updated_user.get("tokens", 0) if updated_user else tokens_to_credit
    return {
        "status": "success",
        "verified": True,
        "is_mock": False,
        "message": f"Successfully credited {tokens_to_credit} tokens!",
        "new_balance": bal,
        "new_token_balance": bal,
        "transaction_id": tx_id,
    }
