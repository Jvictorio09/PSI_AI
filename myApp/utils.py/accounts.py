# myApp/utils/accounts.py
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils.crypto import get_random_string

from ..models import Profile  # ensures type + for profile fields

User = get_user_model()

@transaction.atomic
def create_attendee(username: str, email: str, *, temp_password: str | None = None,
                    age_group: str = "", gender: str = "", region: str = ""):
    """
    Creates a User + ensures Profile.
    Returns (user, plain_password_or_None) — don't store the plain password anywhere!
    """
    if temp_password is None:
        # Short, readable, but random
        temp_password = get_random_string(12)

    user = User.objects.create_user(
        username=username,
        email=email,
        password=temp_password,  # you can set unusable and send reset instead
        is_active=True,
    )

    # Ensure profile exists (signal also does this; this is idempotent)
    profile, _ = Profile.objects.get_or_create(user=user)
    if age_group: profile.age_group = age_group
    if gender:    profile.gender = gender
    if region:    profile.region = region
    profile.onboarded = False
    profile.save()

    return user, temp_password
