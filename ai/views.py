import base64
import json
import logging
import requests
from django.conf import settings
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import AIChatSession, AIChatMessage

logger = logging.getLogger(__name__)

ANTHROPIC_API_URL = 'https://api.anthropic.com/v1/messages'
ANTHROPIC_MODEL   = 'claude-sonnet-4-6'

# MIME types that Claude vision supports as images
SUPPORTED_IMAGE_TYPES = {'image/jpeg', 'image/png', 'image/gif', 'image/webp'}


def call_claude(system_prompt: str, messages: list, max_tokens: int = 1500) -> str:
    """Make a synchronous call to the Anthropic Messages API."""
    api_key = getattr(settings, 'ANTHROPIC_API_KEY', '')
    if not api_key:
        raise ValueError('ANTHROPIC_API_KEY is not configured.')

    headers = {
        'x-api-key': api_key,
        'anthropic-version': '2023-06-01',
        'content-type': 'application/json',
    }
    payload = {
        'model': ANTHROPIC_MODEL,
        'max_tokens': max_tokens,
        'system': system_prompt,
        'messages': messages,
    }
    resp = requests.post(ANTHROPIC_API_URL, headers=headers, json=payload, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    return data['content'][0]['text']


def build_disease_user_message(farm_context: dict, media_data: str | None, media_type: str | None) -> dict:
    """
    Build the user message for the disease detection API call.
    If media is provided and is a supported image type, include it as a vision block.
    Video frames are described in text only (Claude API does not yet accept video blobs).
    """
    text_content = (
        f"Farm data:\n{json.dumps(farm_context, default=str, indent=2)}\n\n"
        "Analyse for disease risk signals."
    )

    if not media_data:
        return {'role': 'user', 'content': text_content}

    is_image = media_type in SUPPORTED_IMAGE_TYPES

    if is_image:
        # Claude vision: send image alongside the text prompt
        return {
            'role': 'user',
            'content': [
                {
                    'type': 'image',
                    'source': {
                        'type': 'base64',
                        'media_type': media_type,
                        'data': media_data,
                    },
                },
                {
                    'type': 'text',
                    'text': (
                        "The above image is a photo of the poultry farm or flock. "
                        "Use visual cues (feather quality, posture, droppings, housing condition) "
                        "alongside the farm log data below to assess disease risk.\n\n"
                        + text_content
                    ),
                },
            ],
        }
    else:
        # Video — describe that media was submitted but note it's not directly analysable
        return {
            'role': 'user',
            'content': (
                "A video of the farm was submitted by the farmer. "
                "While you cannot view the video directly, factor in that the farmer has "
                "recorded live farm footage for this assessment, which may indicate active concern. "
                "Analyse the log data below and note that a visual inspection video is available "
                "for a vet follow-up.\n\n" + text_content
            ),
        }


# ── Role-based system prompts ────────────────────────────────────────────────

ROLE_SYSTEM_PROMPTS = {
    'farmer': (
        "You are the FarmAsyst North AI Assistant for smallholder poultry farmers in northern Ghana. "
        "You help farmers with poultry health, feeding schedules, disease prevention, biosecurity practices, "
        "credit applications, farm record keeping, and understanding training content. "
        "Always give practical, actionable advice suited to smallholder poultry farming in Ghana's northern region. "
        "Be friendly, clear, and use simple language. When discussing disease symptoms, always recommend "
        "contacting a vet for diagnosis. You can speak in English or Dagbani if requested."
    ),
    'investor': (
        "You are the FarmAsyst North AI Assistant for investors and financing partners. "
        "You help investors understand farmer creditworthiness scores, portfolio performance, "
        "repayment analytics, risk assessment, and impact metrics. "
        "Provide data-driven insights and help interpret platform analytics. "
        "Be professional and concise."
    ),
    'admin': (
        "You are the FarmAsyst North AI Assistant for platform administrators. "
        "You help with credit scoring interpretation, anomaly detection in farm activity logs, "
        "user verification decisions, monitoring officer report analysis, and platform operations. "
        "Provide detailed, analytical responses to support data-driven decisions."
    ),
    'monitoring_officer': (
        "You are the FarmAsyst North AI Assistant for monitoring officers. "
        "You help with conducting farm audits, scoring biosecurity and infrastructure, "
        "identifying disease risk signals in farm logs, writing audit report summaries, "
        "and understanding best practices for field verification. "
        "Be precise and practical."
    ),
    'consumer': (
        "You are the FarmAsyst North AI Assistant for consumers and buyers. "
        "You help with understanding produce listings, poultry product quality, "
        "ordering and delivery, and nutritional information about poultry products. "
        "Be friendly and helpful."
    ),
    'vet': (
        "You are the FarmAsyst North AI Assistant for veterinarians on the platform. "
        "You help with poultry disease reference, treatment protocols, booking management, "
        "and farm health trend analysis. Use accurate veterinary terminology "
        "while keeping explanations accessible."
    ),
    'input_dealer': (
        "You are the FarmAsyst North AI Assistant for farm input dealers. "
        "You help with product listing best practices, understanding farmer needs, "
        "feed and vaccine information, and platform usage. Be helpful and informative."
    ),
}


# ── AI: Creditworthiness Engine ──────────────────────────────────────────────

class CreditworthinessView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        farmer_id = request.data.get('farmer_id')
        if not farmer_id:
            return Response({'detail': 'farmer_id is required.'}, status=400)

        user = request.user
        if user.role not in ('admin', 'farmer'):
            return Response({'detail': 'Permission denied.'}, status=403)
        if user.role == 'farmer' and str(user.id) != str(farmer_id):
            return Response({'detail': 'You can only score your own profile.'}, status=403)

        try:
            from accounts.models import User, FarmerProfile
            from farms.models import Farm, FarmActivityLog, FarmAuditReport

            farmer = User.objects.get(id=farmer_id, role='farmer')
            profile, _ = FarmerProfile.objects.get_or_create(user=farmer)

            farms = Farm.objects.filter(owner=farmer, is_active=True)
            farm_data = []
            for farm in farms:
                latest_audit = FarmAuditReport.objects.filter(farm=farm).order_by('-visit_date').first()
                recent_logs = list(
                    FarmActivityLog.objects.filter(farm=farm).order_by('-date')[:14]
                    .values('date', 'mortality', 'feed_kg', 'broiler_count',
                            'layer_count', 'eggs_collected', 'medication_given', 'notes')
                )
                total_flock = sum(
                    (l.get('broiler_count', 0) or 0) + (l.get('layer_count', 0) or 0)
                    for l in recent_logs
                ) or 1
                total_mortality = sum(l.get('mortality', 0) or 0 for l in recent_logs)
                mortality_rate = round((total_mortality / total_flock) * 100, 2)

                farm_data.append({
                    'name': farm.name,
                    'flock_type': farm.flock_type,
                    'flock_size': farm.flock_size,
                    'farm_size_acres': str(farm.farm_size_acres or 0),
                    'has_water_source': farm.has_water_source,
                    'has_electricity': farm.has_electricity,
                    'region': farm.region,
                    'district': farm.district,
                    'audit': {
                        'outcome': latest_audit.outcome if latest_audit else 'none',
                        'infrastructure_score': latest_audit.infrastructure_score if latest_audit else 0,
                        'management_score': latest_audit.management_score if latest_audit else 0,
                        'biosecurity_score': latest_audit.biosecurity_score if latest_audit else 0,
                        'flock_verified': latest_audit.flock_verified if latest_audit else 0,
                        'visit_date': str(latest_audit.visit_date) if latest_audit else None,
                    } if latest_audit else None,
                    'recent_14_days_mortality_rate_pct': mortality_rate,
                    'log_entries_count': len(recent_logs),
                })

            from credit.models import CreditApplication
            past_apps = list(
                CreditApplication.objects.filter(farmer=farmer)
                .values('status', 'credit_type', 'amount_requested', 'submitted_at')
                .order_by('-submitted_at')[:5]
            )

            context = {
                'farmer_name': farmer.get_full_name(),
                'years_of_farming': profile.years_of_farming,
                'current_credit_score': str(profile.credit_score),
                'verification_status': profile.verification_status,
                'district': profile.district,
                'region': profile.region,
                'farms': farm_data,
                'past_credit_applications': past_apps,
            }

            system_prompt = (
                "You are the FarmAsyst North AI Credit Scoring Engine. "
                "Analyse farmer data and produce a structured creditworthiness assessment. "
                "Score on a scale of 0–100 across these dimensions: "
                "Farm Infrastructure (0-20), Biosecurity & Management (0-20), "
                "Farm Activity Consistency (0-20), Credit History (0-20), "
                "Experience & Profile (0-20). "
                "Return ONLY valid JSON with this exact structure: "
                '{"overall_score": <0-100>, "grade": <"A"|"B"|"C"|"D"|"F">, '
                '"dimensions": {"infrastructure": <0-20>, "biosecurity": <0-20>, '
                '"activity_consistency": <0-20>, "credit_history": <0-20>, "experience": <0-20>}, '
                '"strengths": [<str>, ...], "risks": [<str>, ...], '
                '"recommendation": <"approve"|"review"|"reject">, '
                '"narrative": <short paragraph summary>}'
            )

            messages = [{
                'role': 'user',
                'content': f'Farmer data:\n{json.dumps(context, default=str, indent=2)}\n\nGenerate creditworthiness assessment.'
            }]

            raw = call_claude(system_prompt, messages, max_tokens=800)
            clean = raw.strip()
            if clean.startswith('```'):
                clean = clean.split('\n', 1)[1].rsplit('```', 1)[0].strip()
            result = json.loads(clean)
            result['farmer_id']    = str(farmer_id)
            result['farmer_name']  = farmer.get_full_name()
            result['generated_at'] = timezone.now().isoformat()
            return Response(result)

        except User.DoesNotExist:
            return Response({'detail': 'Farmer not found.'}, status=404)
        except Exception as exc:
            logger.error('Creditworthiness scoring failed: %s', exc)
            return Response({'detail': f'AI scoring failed: {exc}'}, status=500)


# ── AI: Disease Detection Engine ─────────────────────────────────────────────

class DiseaseDetectionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        farm_id = request.data.get('farm_id')
        if not farm_id:
            return Response({'detail': 'farm_id is required.'}, status=400)

        # Optional media fields sent by the frontend
        media_data    = request.data.get('media_data')    # base64 string, no data:// prefix
        media_type    = request.data.get('media_type')    # e.g. image/jpeg, video/webm
        capture_mode  = request.data.get('capture_mode')  # 'camera' or 'upload'

        # Validate base64 payload size (limit to ~20MB decoded ≈ ~27MB base64)
        if media_data and len(media_data) > 27_000_000:
            return Response({'detail': 'Media file is too large. Please use a smaller image or shorter video clip.'}, status=400)

        # Basic base64 integrity check
        if media_data:
            try:
                base64.b64decode(media_data, validate=True)
            except Exception:
                return Response({'detail': 'Invalid media data encoding.'}, status=400)

        user = request.user
        try:
            from farms.models import Farm, FarmActivityLog

            farm = Farm.objects.get(id=farm_id)

            if user.role == 'farmer' and farm.owner != user:
                return Response({'detail': 'You can only analyse your own farms.'}, status=403)
            if user.role not in ('farmer', 'admin', 'monitoring_officer', 'vet'):
                return Response({'detail': 'Permission denied.'}, status=403)

            # Last 21 days of logs
            logs = list(
                FarmActivityLog.objects.filter(farm=farm)
                .order_by('-date')[:21]
                .values(
                    'date', 'mortality', 'feed_kg', 'eggs_collected',
                    'medication_given', 'notes',
                    'broiler_count', 'layer_count', 'guinea_fowl_count',
                    'local_cock_count', 'local_hen_count',
                )
            )

            if not logs:
                return Response({
                    'detail': 'No activity logs found for this farm. Start logging daily activity to enable disease detection.'
                }, status=400)

            total_flock = sum(
                (l.get('broiler_count', 0) or 0) + (l.get('layer_count', 0) or 0) +
                (l.get('guinea_fowl_count', 0) or 0) + (l.get('local_cock_count', 0) or 0) +
                (l.get('local_hen_count', 0) or 0)
                for l in logs
            ) or 1
            total_mortality = sum(l.get('mortality', 0) or 0 for l in logs)
            mortality_rate  = round((total_mortality / max(total_flock, 1)) * 100, 3)

            medication_notes  = [l['medication_given'] for l in logs if l.get('medication_given')]
            observation_notes = [l['notes'] for l in logs if l.get('notes')]

            farm_context = {
                'farm_name': farm.name,
                'farm_type': farm.flock_type,
                'region': farm.region,
                'district': farm.district,
                'has_water_source': farm.has_water_source,
                'has_electricity': farm.has_electricity,
                'analysis_period_days': len(logs),
                'total_mortality': total_mortality,
                'mortality_rate_pct': mortality_rate,
                'media_submitted': bool(media_data),
                'media_capture_mode': capture_mode or 'none',
                'daily_logs': [
                    {
                        'date': str(l['date']),
                        'mortality': l.get('mortality', 0),
                        'feed_kg': str(l.get('feed_kg', 0)),
                        'eggs_collected': l.get('eggs_collected', 0),
                        'medication': l.get('medication_given', ''),
                        'notes': l.get('notes', ''),
                    }
                    for l in logs
                ],
                'medications_mentioned': medication_notes,
                'farmer_observations': observation_notes,
            }

            system_prompt = (
                "You are the FarmAsyst North AI Disease Detection Engine for poultry farms in northern Ghana. "
                "Analyse farm activity logs — and any farm image provided — to identify early health risks "
                "and disease indicators. "
                "Common diseases in this region: Newcastle Disease, Gumboro (IBD), Marek's Disease, "
                "Coccidiosis, Fowl Pox, Fowl Typhoid, Avian Influenza. "
                "If an image is provided, use visual cues (feather condition, posture, droppings colour, "
                "housing hygiene, flock behaviour) as additional evidence. "
                "Return ONLY valid JSON: "
                '{"risk_level": <"low"|"moderate"|"high"|"critical">, '
                '"risk_score": <0-100>, '
                '"detected_signals": [{"signal": <str>, "severity": <"low"|"moderate"|"high">}], '
                '"suspected_conditions": [{"condition": <str>, "confidence": <"low"|"moderate"|"high">, "reason": <str>}], '
                '"immediate_actions": [<str>], '
                '"preventive_recommendations": [<str>], '
                '"vet_consultation_required": <true|false>, '
                '"summary": <short paragraph>}'
            )

            user_message = build_disease_user_message(farm_context, media_data, media_type)

            raw = call_claude(system_prompt, [user_message], max_tokens=1200)
            clean = raw.strip()
            if clean.startswith('```'):
                clean = clean.split('\n', 1)[1].rsplit('```', 1)[0].strip()
            result = json.loads(clean)
            result['farm_id']      = str(farm_id)
            result['farm_name']    = farm.name
            result['generated_at'] = timezone.now().isoformat()
            result['media_analysed'] = bool(media_data and media_type in SUPPORTED_IMAGE_TYPES)
            return Response(result)

        except Farm.DoesNotExist:
            return Response({'detail': 'Farm not found.'}, status=404)
        except Exception as exc:
            logger.error('Disease detection failed: %s', exc)
            return Response({'detail': f'AI analysis failed: {exc}'}, status=500)


# ── AI: Flock Count Vision ───────────────────────────────────────────────────

class FlockCountView(APIView):
    """
    Proxy a flock-count vision request to Claude.
    Accepts: { base64_image: str, media_type: str }
    Returns: { count: int, confidence: str, notes: str }
    """
    permission_classes = [IsAuthenticated]

    FLOCK_COUNT_PROMPT = (
        "You are an expert poultry farm monitoring AI. Count the number of birds "
        "(chickens, broilers, layers, or any poultry) visible in this image.\n\n"
        "Respond ONLY with a JSON object (no markdown, no preamble) in exactly this shape:\n"
        '{"count": <integer — best estimate of visible bird count>, '
        '"confidence": "<high|medium|low>", '
        '"notes": "<brief 1-sentence observation about visibility, crowding, or any counting caveats>"}\n\n'
        "Rules:\n"
        "- If the image does not show poultry at all, set count to 0 and explain in notes.\n"
        "- If birds are partially obscured or very densely packed, estimate carefully and lower confidence accordingly.\n"
        "- Do not include any text outside the JSON object."
    )

    def post(self, request):
        base64_image = request.data.get('base64_image')
        media_type   = request.data.get('media_type', 'image/jpeg')

        if not base64_image:
            return Response({'detail': 'base64_image is required.'}, status=400)

        if media_type not in SUPPORTED_IMAGE_TYPES:
            return Response({'detail': f'Unsupported media type: {media_type}'}, status=400)

        # Basic size guard (~10MB decoded ≈ ~14MB base64)
        if len(base64_image) > 14_000_000:
            return Response({'detail': 'Image too large. Please use a smaller photo.'}, status=400)

        try:
            base64.b64decode(base64_image, validate=True)
        except Exception:
            return Response({'detail': 'Invalid base64 image data.'}, status=400)

        try:
            api_key = getattr(settings, 'ANTHROPIC_API_KEY', '')
            if not api_key:
                raise ValueError('ANTHROPIC_API_KEY is not configured.')

            headers = {
                'x-api-key': api_key,
                'anthropic-version': '2023-06-01',
                'content-type': 'application/json',
            }
            payload = {
                'model': ANTHROPIC_MODEL,
                'max_tokens': 200,
                'messages': [{
                    'role': 'user',
                    'content': [
                        {
                            'type': 'image',
                            'source': {
                                'type': 'base64',
                                'media_type': media_type,
                                'data': base64_image,
                            },
                        },
                        {'type': 'text', 'text': self.FLOCK_COUNT_PROMPT},
                    ],
                }],
            }
            resp = requests.post(ANTHROPIC_API_URL, headers=headers, json=payload, timeout=30)
            resp.raise_for_status()
            raw   = resp.json()['content'][0]['text'].strip()
            clean = raw.replace('```json', '').replace('```', '').strip()
            result = json.loads(clean)
            return Response(result)

        except Exception as exc:
            logger.error('Flock count vision failed: %s', exc)
            return Response({'detail': f'AI flock count failed: {exc}'}, status=500)


# ── AI: Role-Based Chat Assistant ────────────────────────────────────────────

class AIChatView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user       = request.user
        message    = request.data.get('message', '').strip()
        session_id = request.data.get('session_id')

        if not message:
            return Response({'detail': 'message is required.'}, status=400)

        role = user.role
        system_prompt = ROLE_SYSTEM_PROMPTS.get(role, ROLE_SYSTEM_PROMPTS['farmer'])

        session = None
        if session_id:
            try:
                session = AIChatSession.objects.get(id=session_id, user=user)
            except AIChatSession.DoesNotExist:
                pass

        if not session:
            session = AIChatSession.objects.create(user=user)

        history = list(
            AIChatMessage.objects.filter(session=session).order_by('created_at')[:20]
        )
        messages = [{'role': m.role, 'content': m.content} for m in history]
        messages.append({'role': 'user', 'content': message})

        try:
            reply = call_claude(system_prompt, messages, max_tokens=1000)

            AIChatMessage.objects.create(session=session, role='user', content=message)
            AIChatMessage.objects.create(session=session, role='assistant', content=reply)
            session.save()

            return Response({
                'reply': reply,
                'session_id': str(session.id),
            })

        except Exception as exc:
            logger.error('AI chat failed: %s', exc)
            return Response({'detail': f'AI assistant unavailable: {exc}'}, status=500)

    def get(self, request):
        """Return chat history for the current user's most recent session."""
        session_id = request.query_params.get('session_id')
        try:
            if session_id:
                session = AIChatSession.objects.get(id=session_id, user=request.user)
            else:
                session = AIChatSession.objects.filter(user=request.user).latest('updated_at')
        except AIChatSession.DoesNotExist:
            return Response({'session_id': None, 'messages': []})

        messages = AIChatMessage.objects.filter(session=session).order_by('created_at')
        return Response({
            'session_id': str(session.id),
            'messages': [
                {'role': m.role, 'content': m.content, 'created_at': m.created_at}
                for m in messages
            ],
        })
