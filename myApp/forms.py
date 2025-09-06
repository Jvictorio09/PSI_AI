# myApp/forms.py
from django import forms
from .models import Profile

class ProfileForm(forms.ModelForm):
    consent_use_demographics = forms.BooleanField(
        required=False,
        label="Use my demographics to tailor images",
        help_text="Optional. You can turn this off anytime."
    )

    class Meta:
        model = Profile
        fields = ["age_group", "gender", "region", "style_keywords", "consent_use_demographics"]
        widgets = {
            "style_keywords": forms.TextInput(attrs={"placeholder": "e.g. minimalist, cinematic, soft lighting"}),
        }
