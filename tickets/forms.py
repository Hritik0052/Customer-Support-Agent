from django import forms

from .models import Category, Priority, Sentiment, Status, Ticket

INPUT_CLASS = "input"


class TicketForm(forms.ModelForm):
    class Meta:
        model = Ticket
        fields = ["customer_name", "email", "subject", "message"]
        widgets = {
            "customer_name": forms.TextInput(attrs={
                "class": INPUT_CLASS, "placeholder": "Jane Cooper", "autofocus": True,
            }),
            "email": forms.EmailInput(attrs={
                "class": INPUT_CLASS, "placeholder": "jane@company.com",
            }),
            "subject": forms.TextInput(attrs={
                "class": INPUT_CLASS, "placeholder": "Brief summary of the issue",
            }),
            "message": forms.Textarea(attrs={
                "class": INPUT_CLASS,
                "rows": 8,
                "placeholder": "Paste the customer's message here…",
                "x-model": "message",
            }),
        }
        labels = {
            "customer_name": "Customer name",
            "email": "Customer email",
            "subject": "Subject",
            "message": "Message",
        }

    def clean_customer_name(self):
        name = self.cleaned_data["customer_name"].strip()
        if len(name) < 2:
            raise forms.ValidationError("Please enter the customer's full name.")
        return name

    def clean_subject(self):
        subject = self.cleaned_data["subject"].strip()
        if len(subject) < 5:
            raise forms.ValidationError("The subject is too short to be useful — at least 5 characters.")
        return subject

    def clean_message(self):
        message = self.cleaned_data["message"].strip()
        if len(message) < 20:
            raise forms.ValidationError(
                "The message is too short for the AI to classify reliably — at least 20 characters."
            )
        if len(message) > 5000:
            raise forms.ValidationError("The message is too long — 5000 characters maximum.")
        return message


SORT_OPTIONS = {
    "newest": ("-created_at", "Newest first"),
    "oldest": ("created_at", "Oldest first"),
    "priority": (None, "Priority"),  # handled separately — needs a custom ordering
    "confidence": ("-confidence", "Confidence"),
}


class TicketFilterForm(forms.Form):
    """Bound to GET. Every field is optional."""

    q = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            "class": INPUT_CLASS,
            "placeholder": "Search name, email, subject or message…",
            "type": "search",
        }),
    )
    category = forms.ChoiceField(required=False, choices=[("", "All categories")] + list(Category.choices))
    priority = forms.ChoiceField(required=False, choices=[("", "All priorities")] + list(Priority.choices))
    sentiment = forms.ChoiceField(required=False, choices=[("", "All sentiment")] + list(Sentiment.choices))
    status = forms.ChoiceField(required=False, choices=[("", "All statuses")] + list(Status.choices))
    date_from = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date", "class": INPUT_CLASS}))
    date_to = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date", "class": INPUT_CLASS}))
    sort = forms.ChoiceField(
        required=False,
        choices=[(k, v[1]) for k, v in SORT_OPTIONS.items()],
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        select_class = INPUT_CLASS + " cursor-pointer"
        for name in ["category", "priority", "sentiment", "status", "sort"]:
            self.fields[name].widget.attrs["class"] = select_class
