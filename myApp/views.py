from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.http import HttpRequest, HttpResponse

from django.contrib.auth import authenticate, login, get_user_model
from django.db.models import Q

import os
import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from openai import OpenAI

# myApp/views.py
import json
from django.http import JsonResponse, HttpResponseBadRequest
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from .models import Profile

def _to_bool(v):
    if isinstance(v, bool):
        return v
    if v is None:
        return False
    return str(v).strip().lower() in {"1", "true", "yes", "on"}

@login_required
@require_POST
@csrf_exempt
def save_onboarding(request):
    """
    Saves onboarding info to the user's Profile and marks them as onboarded.
    Expects JSON body like:
    {
      "age_group": "36-45",
      "gender": "female",
      "region": "asia",
      "style_keywords": "warm, vibrant, documentary",
      "consent_use_demographics": true
    }
    """
    try:
        data = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return HttpResponseBadRequest("Invalid JSON")

    # Pull fields (all optional except we’ll always mark onboarded=True)
    age_group = (data.get("age_group") or "").strip() or None
    gender = (data.get("gender") or "").strip() or None
    region = (data.get("region") or "").strip() or None
    style_keywords = (data.get("style_keywords") or "").strip()
    consent = _to_bool(data.get("consent_use_demographics"))

    profile, _ = Profile.objects.get_or_create(user=request.user)
    if age_group is not None:
        profile.age_group = age_group
    if gender is not None:
        profile.gender = gender
    if region is not None:
        profile.region = region
    profile.style_keywords = style_keywords
    profile.consent_use_demographics = consent
    profile.onboarded = True
    profile.save()

    return JsonResponse({
        "ok": True,
        "onboarded": True,
        "profile": {
            "age_group": profile.age_group,
            "gender": profile.gender,
            "region": profile.region,
            "style_keywords": profile.style_keywords,
            "consent_use_demographics": profile.consent_use_demographics,
        }
    }, status=200)


# ✅ create a client once and reuse it
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def login_view(request):
    if request.user.is_authenticated:
        return redirect("workshop")

    error = None
    if request.method == "POST":
        ident = request.POST.get("username", "").strip()  # email or username
        password = request.POST.get("password", "")

        user = None
        # Try username first
        user = authenticate(request, username=ident, password=password)
        if not user:
            # Try resolving email → username
            User = get_user_model()
            try:
                u = User.objects.get(Q(email__iexact=ident))
                user = authenticate(request, username=u.get_username(), password=password)
            except User.DoesNotExist:
                user = None

        if user:
            login(request, user)
            next_url = request.GET.get("next") or "workshop"
            return redirect(next_url)

        error = "Invalid credentials. Try your username or your email."

    return render(request, "login.html", {"error": error})


# myApp/views.py
# views.py
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import ensure_csrf_cookie
from .models import Profile

@ensure_csrf_cookie               # ensures the csrftoken cookie exists for your chat POST
@login_required
def workshop_view(request):
    profile, _ = Profile.objects.get_or_create(user=request.user)
    should_onboard = not bool(profile.onboarded)
    return render(request, "workshop.html", {"should_onboard": should_onboard})


def logout_view(request: HttpRequest) -> HttpResponse:
    logout(request)
    return redirect("login")



import os
import openai
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
import json

openai.api_key = os.getenv("OPENAI_API_KEY")

@csrf_exempt
@require_POST
def chat_ai(request):
    try:
        data = json.loads(request.body)
        user_message = data.get("message", "")

        if not user_message:
            return JsonResponse({"error": "No message provided"}, status=400)

        # Call OpenAI (gpt-4o-mini for speed/cost; adjust if needed)
        response = openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are PSI Vision AI, helping students clarify their bigger picture with supportive and inspiring dialogue."},
                {"role": "user", "content": user_message},
            ],
            max_tokens=300
        )

        ai_message = response.choices[0].message.content.strip()
        return JsonResponse({"reply": ai_message})

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


import os, json, base64, time, uuid
from django.http import JsonResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from openai import OpenAI

import cloudinary
from cloudinary.uploader import upload as cloudinary_upload

# --- Cloudinary config: supports CLOUDINARY_URL OR separate vars ---
def _ensure_cloudinary_config():
    cfg = cloudinary.config()
    if cfg.cloud_name:
        return
    url = os.getenv("CLOUDINARY_URL")
    if url:
        cloudinary.config(cloudinary_url=url, secure=True)
        return
    # separate env vars path (your case)
    cloud_name = os.getenv("CLOUDINARY_CLOUD_NAME")
    api_key = os.getenv("CLOUDINARY_API_KEY")
    api_secret = os.getenv("CLOUDINARY_API_SECRET")
    if not all([cloud_name, api_key, api_secret]):
        raise RuntimeError(
            "Cloudinary env missing. Provide CLOUDINARY_URL or "
            "CLOUDINARY_CLOUD_NAME / CLOUDINARY_API_KEY / CLOUDINARY_API_SECRET."
        )
    cloudinary.config(
        cloud_name=cloud_name,
        api_key=api_key,
        api_secret=api_secret,
        secure=True,
    )

# --- OpenAI client from env ---
client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    organization=os.getenv("OPENAI_ORG_ID"),
    project=os.getenv("OPENAI_PROJECT_ID"),
)

ALLOWED_SIZES = {"1024x1024", "1024x1536", "1536x1024", "auto"}
ALLOWED_BACKGROUNDS = {None, "transparent", "white"}

@csrf_exempt
@require_POST
def generate_vision(request):
    try:
        try:
            data = json.loads(request.body.decode("utf-8"))
        except json.JSONDecodeError:
            return HttpResponseBadRequest("Invalid JSON body")

        prompt = (data.get("vision") or "").strip()
        size = (data.get("size") or "1024x1024").strip().lower()
        background = (data.get("background") or None)
        if isinstance(background, str):
            background = background.strip().lower()

        if not prompt:
            return JsonResponse({"error": "No vision provided"}, status=400)
        if size not in ALLOWED_SIZES:
            return JsonResponse({"error": f"Invalid size. Allowed: {sorted(ALLOWED_SIZES)}"}, status=400)
        if background not in ALLOWED_BACKGROUNDS:
            return JsonResponse({"error": f"Invalid background. Allowed: {sorted(ALLOWED_BACKGROUNDS)}"}, status=400)

        # Generate with OpenAI (b64 is common)
        gen_kwargs = {"model": "gpt-image-1", "prompt": prompt, "size": size, "n": 1}
        if background:
            gen_kwargs["background"] = background  # "transparent"|"white"
        resp = client.images.generate(**gen_kwargs)

        item = resp.data[0]
        url = getattr(item, "url", None)
        b64 = getattr(item, "b64_json", None)
        if not (url or b64):
            return JsonResponse({"error": "No image content returned from model."}, status=502)

        # Cloudinary upload (bytes or remote URL)
        _ensure_cloudinary_config()
        public_id = f"{int(time.time())}-{uuid.uuid4().hex[:8]}"
        upload_source = base64.b64decode(b64) if b64 else url

        upload_result = cloudinary_upload(
            upload_source,
            folder="psi-vision",        # your folder
            public_id=public_id,        # final path: psi-vision/public_id
            resource_type="image",
            overwrite=True,
            invalidate=True,
            format="png",               # force PNG (keeps transparency)
        )

        secure_url = upload_result.get("secure_url")
        if not secure_url:
            return JsonResponse({"error": "Cloudinary upload failed.", "details": upload_result}, status=502)

        return JsonResponse(
            {
                "prompt": prompt,
                "image_url": secure_url,  # <- your frontend already uses this
                "size": size,
                "background": background,
                "public_id": upload_result.get("public_id"),
            },
            status=200,
        )

    except Exception as e:
        import traceback, sys
        traceback.print_exc()
        etype, _, _ = sys.exc_info()
        return JsonResponse({"etype": getattr(etype, "__name__", "Exception"), "error": str(e)}, status=500)


from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse
from django.views.decorators.csrf import ensure_csrf_cookie
import json

from .models import Profile

@ensure_csrf_cookie
@login_required
def workshop_view(request):
    # keep your existing logic, just ensure the CSRF cookie is set
    should_onboard = not getattr(getattr(request.user, "profile", None), "onboarded", False)
    return render(request, "workshop.html", {"should_onboard": should_onboard})

@login_required
@require_http_methods(["GET"])
def profile_get(request):
    prof, _ = Profile.objects.get_or_create(user=request.user)
    return JsonResponse({
        "ok": True,
        "profile": {
            "age_group": prof.age_group or "",
            "gender": prof.gender or "",
            "region": prof.region or "",
            "style_keywords": prof.style_keywords or "",
            "consent_use_demographics": bool(prof.consent_use_demographics),
            "onboarded": bool(prof.onboarded),
        }
    })

@login_required
@require_http_methods(["POST"])
def profile_save(request):
    try:
        data = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "error": "Invalid JSON."}, status=400)

    prof, _ = Profile.objects.get_or_create(user=request.user)

    # Optional: validate against your allowed choices if you like
    prof.age_group = (data.get("age_group") or "").strip()
    prof.gender = (data.get("gender") or "").strip()
    prof.region = (data.get("region") or "").strip()
    prof.style_keywords = (data.get("style_keywords") or "").strip()
    prof.consent_use_demographics = bool(data.get("consent_use_demographics"))

    # If you want saving profile to also mark onboarding complete:
    if "onboarded" in data:
        prof.onboarded = bool(data["onboarded"])

    prof.save()
    return JsonResponse({"ok": True})
