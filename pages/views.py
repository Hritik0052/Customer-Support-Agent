from django.contrib import messages
from django.shortcuts import redirect, render

from .forms import ContactForm


def home(request):
    return render(request, "pages/home.html")


def about(request):
    return render(request, "pages/about.html")


def features(request):
    return render(request, "pages/features.html")


def how_it_works(request):
    return render(request, "pages/how_it_works.html")


def pricing(request):
    return render(request, "pages/pricing.html")


def contact(request):
    if request.method == "POST":
        form = ContactForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Thanks — we'll get back to you within one business day.")
            return redirect("pages:contact")
    else:
        initial = {}
        if request.user.is_authenticated:
            initial = {"name": request.user.display_name, "email": request.user.email}
        form = ContactForm(initial=initial)

    return render(request, "pages/contact.html", {"form": form})
