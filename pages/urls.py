from django.urls import path

from . import views

app_name = "pages"

urlpatterns = [
    path("", views.home, name="home"),
    path("about/", views.about, name="about"),
    path("features/", views.features, name="features"),
    path("how-it-works/", views.how_it_works, name="how_it_works"),
    path("pricing/", views.pricing, name="pricing"),
    path("contact/", views.contact, name="contact"),
]
