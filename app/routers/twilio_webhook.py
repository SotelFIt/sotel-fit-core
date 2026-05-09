from fastapi import APIRouter, Request, Depends
from fastapi.responses import Response
from sqlalchemy.orm import Session
from twilio.twiml.messaging_response import MessagingResponse
from core.database import get_db
from core.phone import normalize_phone
from services.twilio_flow_service import handle_twilio_flow

router = APIRouter(prefix="/webhook", tags=["Twilio"])


@router.post("/twilio")
async def twilio_webhook(request: Request, db: Session = Depends(get_db)):
    form_data = await request.form()
    raw_phone = form_data.get("From", "").strip()
    incoming_msg = form_data.get("Body", "").strip()

    phone = normalize_phone(raw_phone)

    reply_text = handle_twilio_flow(phone=phone, incoming_msg=incoming_msg, db=db)

    response = MessagingResponse()
    response.message(reply_text)
    return Response(content=str(response), media_type="application/xml")