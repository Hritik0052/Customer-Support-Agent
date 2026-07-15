from django import forms

from .models import ContactMessage

INPUT_CLASS = "input"


class ContactForm(forms.ModelForm):
    # Bots fill in every field they find; humans never see this one.
    website = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={"tabindex": "-1", "autocomplete": "off"}),
    )

    class Meta:
        model = ContactMessage
        fields = ["name", "email", "subject", "message"]
        widgets = {
            "name": forms.TextInput(attrs={"class": INPUT_CLASS, "placeholder": "Jane Cooper"}),
            "email": forms.EmailInput(attrs={"class": INPUT_CLASS, "placeholder": "you@company.com"}),
            "subject": forms.TextInput(attrs={"class": INPUT_CLASS, "placeholder": "How can we help?"}),
            "message": forms.Textarea(attrs={"class": INPUT_CLASS, "rows": 5, "placeholder": "Tell us a bit more…"}),
        }

    def clean_website(self):
        if self.cleaned_data.get("website"):
            raise forms.ValidationError("Spam detected.")
        return ""
