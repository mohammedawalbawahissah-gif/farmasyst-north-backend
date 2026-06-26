import json
import time
import logging
from django.http import StreamingHttpResponse
from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from .models import Notification
from .serializers import NotificationSerializer

logger = logging.getLogger(__name__)


class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class   = NotificationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Notification.objects.filter(recipient=self.request.user)

    @action(detail=True, methods=['post'])
    def mark_read(self, request, pk=None):
        notif = self.get_object()
        notif.is_read = True
        notif.save()
        return Response({'detail': 'Marked as read.'})

    @action(detail=False, methods=['post'])
    def mark_all_read(self, request):
        self.get_queryset().update(is_read=True)
        return Response({'detail': 'All notifications marked as read.'})

    @action(detail=False, methods=['get'])
    def unread_count(self, request):
        count = self.get_queryset().filter(is_read=False).count()
        return Response({'unread': count})

    @action(detail=False, methods=['get'])
    def credit_workflow(self, request):
        qs = self.get_queryset().filter(notif_type='credit_workflow')
        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def resend(self, request, pk=None):
        notif = self.get_object()
        Notification.objects.create(
            recipient=notif.recipient,
            notif_type=notif.notif_type,
            title=f'[Resent] {notif.title}',
            body=notif.body,
            priority=notif.priority,
            data=notif.data,
        )
        return Response({'detail': 'Notification resent.'})


def notification_sse_stream(request):
    """
    Server-Sent Events endpoint for real-time notification delivery.

    The frontend connects once with a JWT token in the Authorization header
    (or ?token= query param for EventSource, which cannot set headers).
    The server polls for new notifications every 5 seconds and pushes them.

    URL: GET /api/v1/notifications/stream/?token=<access_token>
    """
    # ── Authenticate via JWT (query param since EventSource can't set headers) ──
    raw_token = request.GET.get('token') or request.META.get('HTTP_AUTHORIZATION', '').replace('Bearer ', '')
    user = None
    if raw_token:
        try:
            auth = JWTAuthentication()
            validated = auth.get_validated_token(raw_token)
            user = auth.get_user(validated)
        except (InvalidToken, TokenError) as exc:
            logger.warning('SSE auth failed: %s', exc)

    if not user or not user.is_authenticated:
        def _deny():
            yield 'event: error\ndata: {"detail": "Unauthorized"}\n\n'
        return StreamingHttpResponse(_deny(), content_type='text/event-stream', status=401)

    def _event_stream():
        last_check = timezone.now()
        # Send a heartbeat immediately so the connection is confirmed
        yield f'event: connected\ndata: {json.dumps({"user": str(user.id)})}\n\n'

        while True:
            try:
                new_notifs = Notification.objects.filter(
                    recipient=user,
                    created_at__gt=last_check,
                ).order_by('created_at')

                if new_notifs.exists():
                    last_check = timezone.now()
                    for n in new_notifs:
                        payload = {
                            'id':                str(n.id),
                            'notification_type': n.notif_type,
                            'notif_type':        n.notif_type,
                            'title':             n.title,
                            'message':           n.body,
                            'body':              n.body,
                            'is_read':           n.is_read,
                            'priority':          n.priority,
                            'data':              n.data,
                            'created_at':        n.created_at.isoformat(),
                        }
                        yield f'event: notification\ndata: {json.dumps(payload)}\n\n'
                else:
                    last_check = timezone.now()

                # Heartbeat every poll cycle so nginx/proxies don't close idle connections
                yield f': heartbeat {int(time.time())}\n\n'
                time.sleep(5)

            except GeneratorExit:
                break
            except Exception as exc:
                logger.error('SSE stream error for user %s: %s', user.id, exc)
                yield f'event: error\ndata: {json.dumps({"detail": str(exc)})}\n\n'
                time.sleep(10)

    response = StreamingHttpResponse(_event_stream(), content_type='text/event-stream')
    response['Cache-Control']               = 'no-cache'
    response['X-Accel-Buffering']           = 'no'   # disable nginx response buffering
    response['Access-Control-Allow-Origin'] = request.META.get('HTTP_ORIGIN', '*')
    return response
