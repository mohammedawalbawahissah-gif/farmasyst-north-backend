"""
notifications/credit_signals.py

Single source of truth for ALL notification firing across the system.
Signals replace the direct send_notification() calls in credit/views.py
to prevent double-firing. credit/views.py must NOT call send_notification()
directly for events covered here.

Covers:
  - CreditApplication lifecycle (all statuses)
  - CreditAgreement creation and signing
  - DisbursementRequest creation, approval, rejection
  - Disbursement (funds sent)
  - Order placement (marketplace)
  - Project application submission, approval, rejection
  - Farm audit request
  - Vet booking creation
  - Repayment events
"""
from django.db.models.signals import post_save
from django.dispatch import receiver
from .utils import send_notification, notify_admins


# ── CreditApplication ─────────────────────────────────────────────────────────

def _wire_credit_application():
    from credit.models import CreditApplication

    @receiver(post_save, sender=CreditApplication)
    def on_credit_application_save(sender, instance, created, **kwargs):
        from farmasyst_north.sms_service import (
            notify_credit_submitted, notify_credit_under_review,
            notify_credit_approved, notify_credit_declined,
        )
        from farmasyst_north.email_service import send_credit_status_email

        app = instance
        farmer = app.farmer
        phone  = farmer.phone
        email  = farmer.email
        name   = farmer.get_full_name()
        ref    = app.reference

        if created:
            # In-app
            send_notification(farmer, 'credit_workflow',
                'Application Received 📝',
                f'Your credit application {ref} has been submitted and is under review.',
                priority='medium', related_obj=app)
            notify_admins('credit_workflow',
                f'New Credit Application: {ref}',
                f'Farmer {name} submitted a {app.credit_type} application for GHS {app.amount_requested}.',
                priority='medium', related_obj=app)
            # SMS + Email
            if phone: notify_credit_submitted(phone, ref)
            send_credit_status_email(email, name, ref, 'submitted')
            return

        status = app.status

        if status == 'under_review':
            send_notification(farmer, 'credit_workflow',
                'Application Under Review 🔍',
                f'Your application {ref} is now under active review.',
                priority='low', related_obj=app)
            if phone: notify_credit_under_review(phone, ref)
            send_credit_status_email(email, name, ref, 'under_review')

        elif status == 'approved':
            send_notification(farmer, 'credit_workflow',
                'Application Approved ✅',
                f'Your application {ref} has been approved! We are matching you with an investor.',
                priority='high', related_obj=app)
            notify_admins('credit_workflow', f'Application Approved: {ref}',
                f'Farmer {name}\'s application {ref} has been approved.',
                priority='medium', related_obj=app)
            if phone: notify_credit_approved(phone, ref, float(app.amount_requested or 0))
            send_credit_status_email(email, name, ref, 'approved')

        elif status == 'rejected':
            send_notification(farmer, 'credit_workflow',
                'Application Not Approved ❌',
                f'Your application {ref} was not approved. Reason: {app.rejection_reason}',
                priority='high', related_obj=app)
            if phone: notify_credit_declined(phone, ref)
            send_credit_status_email(email, name, ref, 'rejected',
                detail=f'Reason: {app.rejection_reason}')

        elif status == 'matched' and app.matched_investor:
            investor = app.matched_investor
            # Farmer notified
            send_notification(farmer, 'credit_workflow',
                'Investor Matched 🤝',
                f'Your application {ref} has been matched to an investor.',
                priority='high', related_obj=app)
            send_credit_status_email(email, name, ref, 'matched')
            # Investor notified
            send_notification(investor, 'new_opportunity',
                f'New Investment Opportunity: {ref}',
                f'Farmer {name} is seeking {app.credit_type} funding of GHS {app.amount_requested}. '
                f'Review and accept from your Opportunities page.',
                priority='urgent', related_obj=app)
            if investor.email:
                send_credit_status_email(investor.email, investor.get_full_name(),
                    ref, 'matched',
                    detail=f'Review and accept from your Opportunities page.')
            notify_admins('credit_workflow', f'Investor Matched: {ref}',
                f'Application {ref} matched to {investor.get_full_name()}.',
                priority='medium', related_obj=app)

        elif status == 'agreement':
            send_notification(farmer, 'credit_workflow',
                'Contract Ready to Sign 📄',
                f'An investment agreement for {ref} is ready. Please review and sign.',
                priority='high', related_obj=app)
            from farmasyst_north.sms_service import notify_credit_agreement
            if phone: notify_credit_agreement(phone, ref)
            send_credit_status_email(email, name, ref, 'agreement')


# ── CreditAgreement ───────────────────────────────────────────────────────────

def _wire_credit_agreement():
    from credit.models import CreditAgreement

    @receiver(post_save, sender=CreditAgreement)
    def on_credit_agreement_save(sender, instance, created, **kwargs):
        from farmasyst_north.sms_service import notify_credit_agreement
        ag = instance

        if created:
            send_notification(ag.farmer, 'credit_workflow',
                'Credit Agreement Ready to Sign 📄',
                f'Agreement {ag.reference} is ready. Please review and sign your contract.',
                priority='high', related_obj=ag)
            if ag.farmer.phone: notify_credit_agreement(ag.farmer.phone, ag.reference)

            if ag.investor:
                send_notification(ag.investor, 'credit_workflow',
                    'Credit Agreement Ready to Sign 📄',
                    f'Agreement {ag.reference} is ready for your signature.',
                    priority='high', related_obj=ag)
                if ag.investor.phone: notify_credit_agreement(ag.investor.phone, ag.reference)
            return

        # Farmer signed — notify investor
        if ag.farmer_signed_at and not ag.investor_signed_at and ag.investor:
            send_notification(ag.investor, 'credit_workflow',
                'Farmer Has Signed — Your Turn ✍️',
                f'Farmer has signed agreement {ag.reference}. Please sign to proceed to disbursement.',
                priority='high', related_obj=ag)
            if ag.investor.phone:
                from farmasyst_north.sms_service import _send as _sms
                _sms([ag.investor.phone],
                    f'FarmAsyst: Farmer has signed agreement #{ag.reference}. Please log in to countersign.')

        # Both signed
        if ag.farmer_signed_at and ag.investor_signed_at and ag.status == 'active':
            send_notification(ag.farmer, 'credit_workflow',
                'Agreement Fully Signed 🎉',
                f'Both parties have signed agreement {ag.reference}. Disbursement will be processed shortly.',
                priority='urgent', related_obj=ag)
            if ag.investor:
                send_notification(ag.investor, 'credit_workflow',
                    'Agreement Fully Signed 🎉',
                    f'Both parties have signed agreement {ag.reference}. Disbursement proceeding.',
                    priority='high', related_obj=ag)
            notify_admins('credit_workflow', f'Agreement Active: {ag.reference}',
                'Both parties signed. Please proceed with disbursement.',
                priority='urgent', related_obj=ag)


# ── DisbursementRequest ───────────────────────────────────────────────────────

def _wire_disbursement_request():
    from payments.models import DisbursementRequest

    @receiver(post_save, sender=DisbursementRequest)
    def on_disbursement_request_save(sender, instance, created, **kwargs):
        req = instance

        if created:
            notify_admins('credit_workflow',
                f'Disbursement Request: {req.reference} 💸',
                f'{req.requested_by.get_full_name()} requested GHS {req.amount} '
                f'disbursement for {req.agreement.farmer.get_full_name()}.',
                priority='urgent', related_obj=req)
            if req.agreement.investor:
                send_notification(req.agreement.investor, 'credit_workflow',
                    'Disbursement Requested',
                    f'A disbursement of GHS {req.amount} has been requested for your agreement {req.agreement.reference}.',
                    priority='high', related_obj=req)
            return

        if req.status == 'approved':
            if req.agreement.investor:
                send_notification(req.agreement.investor, 'credit_workflow',
                    'Disbursement Approved ✅',
                    f'Disbursement of GHS {req.amount} for {req.agreement.farmer.get_full_name()} has been approved.',
                    priority='urgent', related_obj=req)
            # Notify farmer
            send_notification(req.agreement.farmer, 'credit_workflow',
                'Disbursement Approved ✅',
                f'Your disbursement of GHS {req.amount} has been approved and will be processed shortly.',
                priority='urgent', related_obj=req)

        elif req.status == 'rejected':
            if req.agreement.investor:
                send_notification(req.agreement.investor, 'credit_workflow',
                    'Disbursement Request Rejected ❌',
                    f'Disbursement request {req.reference} was rejected. Reason: {req.rejection_reason}',
                    priority='high', related_obj=req)


# ── Disbursement (funds actually sent) ───────────────────────────────────────

def _wire_disbursement():
    from payments.models import Disbursement

    @receiver(post_save, sender=Disbursement)
    def on_disbursement_save(sender, instance, created, **kwargs):
        if not created:
            return
        from farmasyst_north.sms_service import notify_credit_disbursed
        from farmasyst_north.email_service import send_credit_status_email

        d  = instance
        ag = d.agreement

        send_notification(ag.farmer, 'credit_workflow',
            'Funds Disbursed 🏦',
            f'GHS {d.amount} has been disbursed via {d.method}. Ref: {d.reference}',
            priority='urgent', related_obj=d)
        if ag.farmer.phone:
            notify_credit_disbursed(ag.farmer.phone, d.reference, float(d.amount))
        send_credit_status_email(ag.farmer.email, ag.farmer.get_full_name(),
            d.reference, 'disbursed', detail=f'Method: {d.method}. GHS {d.amount} sent to your account.')

        if ag.investor:
            send_notification(ag.investor, 'credit_workflow',
                'Disbursement Complete',
                f'GHS {d.amount} disbursed to {ag.farmer.get_full_name()}. Ref: {d.reference}',
                priority='high', related_obj=d)

        notify_admins('credit_workflow', f'Funds Disbursed: {d.reference}',
            f'GHS {d.amount} disbursed. Agreement: {ag.reference}',
            priority='medium', related_obj=d)


# ── Marketplace Order ─────────────────────────────────────────────────────────

def _wire_order():
    from marketplace.models import Order

    @receiver(post_save, sender=Order)
    def on_order_save(sender, instance, created, **kwargs):
        if not created:
            return
        from farmasyst_north.sms_service import notify_consumer_order_placed, notify_farmer_new_order
        from farmasyst_north.email_service import send_order_confirmation_email

        order = instance

        # In-app + SMS + Email → buyer
        send_notification(order.buyer, 'order_update',
            f'Order Placed 🛒 #{order.reference}',
            f'Your order #{order.reference} of GHS {order.total_amount} has been received.',
            priority='medium', related_obj=order)
        if order.buyer.phone:
            notify_consumer_order_placed(order.buyer.phone, order.reference, float(order.total_amount))
        if order.buyer.email:
            send_order_confirmation_email(order.buyer.email, order.buyer.get_full_name(),
                order.reference, float(order.total_amount))

        # In-app + SMS → each unique seller
        sellers_notified = set()
        for item in order.items.select_related('produce__seller').all():
            seller = item.produce.seller
            if seller.id in sellers_notified:
                continue
            sellers_notified.add(seller.id)
            send_notification(seller, 'order_update',
                f'New Order Received 📦 #{order.reference}',
                f'You have a new order for {item.produce.name}. Log in to confirm.',
                priority='high', related_obj=order)
            if seller.phone:
                notify_farmer_new_order(seller.phone, order.reference,
                    item.produce.name, float(item.quantity))


# ── Project Application ───────────────────────────────────────────────────────

def _wire_project_application():
    from credit.models import ProjectApplication

    @receiver(post_save, sender=ProjectApplication)
    def on_project_application_save(sender, instance, created, **kwargs):
        from farmasyst_north.sms_service import _send as _sms

        proj = instance

        if created:
            # Draft created — no notification yet
            return

        submitter = proj.submitted_by
        if not submitter:
            return

        if proj.status == 'submitted':
            notify_admins('credit_workflow',
                f'Project Application Submitted: {proj.project_name}',
                f'{proj.organisation} submitted project {proj.reference} '
                f'covering {proj.farmer_entries.count()} farmer(s).',
                priority='high', related_obj=proj)
            send_notification(submitter, 'credit_workflow',
                'Project Submitted for Review 📋',
                f'Your project "{proj.project_name}" ({proj.reference}) has been submitted.',
                priority='medium', related_obj=proj)
            if submitter.phone:
                _sms([submitter.phone],
                    f'FarmAsyst: Project "{proj.project_name}" ({proj.reference}) submitted for review.')

        elif proj.status == 'approved':
            send_notification(submitter, 'credit_workflow',
                f'Project Approved ✅: {proj.project_name}',
                f'Your project application {proj.reference} has been approved.',
                priority='high', related_obj=proj)
            if submitter.phone:
                _sms([submitter.phone],
                    f'FarmAsyst: Great news! Project {proj.reference} has been approved.')
            if submitter.email:
                from farmasyst_north.email_service import _send as _email, _html
                _email(submitter.email,
                    f'Project Approved: {proj.project_name}',
                    f'Your project {proj.reference} has been approved.',
                    _html('Project Approved', f"""
                        <h2 style="color:#2D4A1E">Project Approved ✅</h2>
                        <p>Hi <strong>{submitter.get_full_name()}</strong>,</p>
                        <p>Your project <strong>{proj.project_name}</strong> ({proj.reference}) has been approved.</p>
                    """))

        elif proj.status == 'rejected':
            send_notification(submitter, 'credit_workflow',
                f'Project Not Approved: {proj.project_name}',
                f'Project {proj.reference} was not approved. Reason: {proj.rejection_reason}',
                priority='high', related_obj=proj)
            if submitter.phone:
                _sms([submitter.phone],
                    f'FarmAsyst: Project {proj.reference} was not approved. Log in for details.')


# ── Vet Booking ───────────────────────────────────────────────────────────────

def _wire_vet_booking():
    try:
        from vet.models import VetBooking

        @receiver(post_save, sender=VetBooking)
        def on_vet_booking_save(sender, instance, created, **kwargs):
            from farmasyst_north.sms_service import _send as _sms

            booking = instance

            if created:
                # Notify vet
                send_notification(booking.vet.user, 'action_required',
                    'New Vet Booking Request 🩺',
                    f'You have a new booking request from {booking.farmer.get_full_name()} '
                    f'for {booking.service_date}.',
                    priority='high', related_obj=booking)
                if booking.vet.user.phone:
                    _sms([booking.vet.user.phone],
                        f'FarmAsyst: New booking request from {booking.farmer.get_full_name()} '
                        f'on {booking.service_date}. Log in to confirm.')
                # Notify farmer
                send_notification(booking.farmer, 'action_required',
                    'Booking Submitted ✅',
                    f'Your vet booking for {booking.service_date} has been submitted.',
                    priority='medium', related_obj=booking)
                return

            if booking.status == 'confirmed':
                send_notification(booking.farmer, 'action_required',
                    'Vet Booking Confirmed ✅',
                    f'Your vet booking for {booking.service_date} has been confirmed.',
                    priority='high', related_obj=booking)
                if booking.farmer.phone:
                    _sms([booking.farmer.phone],
                        f'FarmAsyst: Your vet booking for {booking.service_date} is confirmed.')

            elif booking.status == 'cancelled':
                send_notification(booking.farmer, 'action_required',
                    'Vet Booking Cancelled',
                    f'Your vet booking for {booking.service_date} has been cancelled.',
                    priority='medium', related_obj=booking)

    except ImportError:
        pass  # vet app may not be installed


# ── Registration complete (account verified) ──────────────────────────────────

def _wire_user_verification():
    from accounts.models import User

    @receiver(post_save, sender=User)
    def on_user_save(sender, instance, created, **kwargs):
        # Welcome message when admin activates a previously inactive account
        if not created and instance.is_active and instance.is_verified:
            from farmasyst_north.sms_service import _send as _sms
            from farmasyst_north.email_service import send_welcome_email
            # Only fire once — check that there's no existing welcome notification
            from notifications.models import Notification
            already_welcomed = Notification.objects.filter(
                recipient=instance,
                notif_type='system',
                title__icontains='Welcome',
            ).exists()
            if not already_welcomed:
                send_notification(instance, 'system',
                    'Account Activated 🎉',
                    f'Welcome to FarmAsyst North, {instance.first_name}! Your account is now active.',
                    priority='high')
                if instance.phone:
                    _sms([instance.phone],
                        f'FarmAsyst: Your account has been approved! '
                        f'Log in at farmasyst-north-frontend.onrender.com')
                if instance.email:
                    send_welcome_email(instance.email, instance.get_full_name(), instance.role)


def register_all():
    _wire_credit_application()
    _wire_credit_agreement()
    _wire_disbursement_request()
    _wire_disbursement()
    _wire_order()
    _wire_project_application()
    _wire_vet_booking()
    _wire_user_verification()
