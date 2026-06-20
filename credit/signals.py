import farmasyst_north.sms_service as svc

CREDIT_SMS_MAP = {
    "submitted":    "notify_credit_submitted",
    "under_review": "notify_credit_under_review",
    "approved":     "notify_credit_approved",
    "rejected":     "notify_credit_declined",
    "agreement":    "notify_credit_agreement",
    "disbursed":    "notify_credit_disbursed",
}


def send_credit_status_sms(application, old_status: str):
    new_status = application.status
    if new_status == old_status:
        return
    fn_name = CREDIT_SMS_MAP.get(new_status)
    if not fn_name:
        return
    phone = application.farmer.phone
    if not phone:
        return
    fn = getattr(svc, fn_name, None)
    if fn is None:
        return
    if new_status in ("approved", "disbursed"):
        fn(phone, application.reference, float(application.amount_requested or 0))
    else:
        fn(phone, application.reference)
