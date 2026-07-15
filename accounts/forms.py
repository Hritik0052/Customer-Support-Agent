from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

from .models import User

INPUT_CLASS = "input"


class RegisterForm(UserCreationForm):
    full_name = forms.CharField(
        max_length=120,
        widget=forms.TextInput(attrs={"class": INPUT_CLASS, "placeholder": "Jane Cooper", "autofocus": True}),
    )
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={"class": INPUT_CLASS, "placeholder": "you@company.com"}),
    )
    company = forms.CharField(
        max_length=120,
        required=False,
        widget=forms.TextInput(attrs={"class": INPUT_CLASS, "placeholder": "Acme Inc. (optional)"}),
    )

    class Meta:
        model = User
        fields = ["full_name", "email", "company"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["password1"].widget.attrs.update({"class": INPUT_CLASS, "placeholder": "At least 8 characters"})
        self.fields["password2"].widget.attrs.update({"class": INPUT_CLASS, "placeholder": "Repeat your password"})
        self.fields["password1"].label = "Password"
        self.fields["password2"].label = "Confirm password"

    def clean_email(self):
        email = self.cleaned_data["email"].lower().strip()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        if commit:
            user.save()
        return user


class LoginForm(AuthenticationForm):
    username = forms.EmailField(
        label="Email",
        widget=forms.EmailInput(attrs={"class": INPUT_CLASS, "placeholder": "you@company.com", "autofocus": True}),
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={"class": INPUT_CLASS, "placeholder": "Your password"}),
    )

    error_messages = {
        **AuthenticationForm.error_messages,
        "invalid_login": "Email or password is incorrect.",
    }


class ProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ["full_name", "company", "avatar"]
        widgets = {
            "full_name": forms.TextInput(attrs={"class": INPUT_CLASS}),
            "company": forms.TextInput(attrs={"class": INPUT_CLASS}),
            "avatar": forms.ClearableFileInput(attrs={
                "class": "block w-full text-sm text-slate-500 file:mr-4 file:rounded-lg "
                         "file:border-0 file:bg-brand-50 file:px-4 file:py-2 file:text-sm "
                         "file:font-semibold file:text-brand-700 hover:file:bg-brand-100 "
                         "dark:file:bg-brand-500/15 dark:file:text-brand-300",
                "accept": "image/*",
            }),
        }
