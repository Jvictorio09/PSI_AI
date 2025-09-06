# myApp/models.py
from django.db import models
from django.contrib.auth.models import User
from cloudinary.models import CloudinaryField

class Profile(models.Model):
    AGE_GROUPS = [
        ("teen", "Teen"),
        ("20s", "20s"),
        ("30s", "30s"),
        ("40s", "40s"),
        ("50s", "50s"),
        ("60plus", "60+"),
    ]
    GENDER = [
        ("female", "Female"),
        ("male", "Male"),
        ("nonbinary", "Non-binary"),
        ("na", "Prefer not to say"),
    ]
    REGION = [
        ("se_asia", "Southeast Asia"),
        ("e_asia", "East Asia"),
        ("s_asia", "South Asia"),
        ("middle_east", "Middle East"),
        ("europe", "Europe"),
        ("africa", "Africa"),
        ("n_america", "North America"),
        ("latam", "Latin America"),
        ("oceania", "Oceania"),
        ("na", "Prefer not to say"),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")

    age_group = models.CharField(max_length=20, choices=AGE_GROUPS, blank=True)
    gender = models.CharField(max_length=20, choices=GENDER, blank=True)
    region = models.CharField(max_length=20, choices=REGION, blank=True)

    style_keywords = models.CharField(
        max_length=200, blank=True,
        help_text="Comma-separated (e.g. 'minimalist, cinematic, soft lighting')"
    )

    consent_use_demographics = models.BooleanField(
        default=False,
        help_text="Allow using age/region/gender to tailor generated images."
    )
    onboarded = models.BooleanField(default=False)

    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Profile({self.user.username})"


class Vision(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="visions")
    prompt = models.TextField()
    image = CloudinaryField("vision_image", folder="psi_vision/visions/")  # stores Cloudinary public_id
    meta = models.JSONField(default=dict, blank=True)  # store size, background, tokens, etc.
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.created_at.strftime('%Y-%m-%d')}"
