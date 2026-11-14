from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from .database import get_db
from . import models
from .security import verify_password, create_access_token

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login")
def login(
    form: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    # Swagger uses `username` field — treat it as phone_number
    user = (
        db.query(models.User)
        .filter(models.User.phone_number == form.username)
        .first()
    )
    if not user or not verify_password(form.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_access_token({"sub": user.user_id, "role": user.role})
    return {"access_token": token, "token_type": "bearer"}