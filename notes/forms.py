from django import forms
from django.core.validators import URLValidator

from .models import Note, SourceType


class AddSourceForm(forms.Form):
    """Submit a URL to ingest, or paste raw text directly."""

    source_url = forms.URLField(
        required=False,
        assume_scheme="https",
        # Only http/https — reject ftp/file/etc. so they fail cleanly, not via a
        # late ValueError in the worker (C1).
        validators=[URLValidator(schemes=["http", "https"])],
        widget=forms.URLInput(
            attrs={"placeholder": "https://youtube.com/... or any link", "autocomplete": "off"}
        ),
    )
    text = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={"placeholder": "...or paste text / a transcript manually", "rows": 3}
        ),
    )
    title = forms.CharField(required=False, max_length=500)

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get("source_url") and not cleaned.get("text"):
            raise forms.ValidationError("Provide a URL or some text.")
        return cleaned


class NoteEditForm(forms.ModelForm):
    class Meta:
        model = Note
        fields = ["title", "cleaned_text", "summary"]
        widgets = {
            "cleaned_text": forms.Textarea(attrs={"rows": 12}),
            "summary": forms.Textarea(attrs={"rows": 4}),
        }


# Source types a user can create by pasting (no URL fetch).
MANUAL_SOURCE_TYPES = {SourceType.TEXT}
