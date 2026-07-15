from django.urls import path

from . import views

app_name = "tickets"

urlpatterns = [
    # `/tickets/` is the history list — search, filters, sorting and pagination
    # all live here. The roadmap listed `/tickets/` and `/tickets/history/`
    # separately, but they describe the same page.
    path("", views.ticket_list, name="list"),
    path("create/", views.ticket_create, name="create"),
    path("export/csv/", views.export_csv, name="export_csv"),
    path("export/json/", views.export_json, name="export_json"),
    path("<int:pk>/", views.ticket_detail, name="detail"),
    path("<int:pk>/result/", views.ticket_result, name="result"),
    path("<int:pk>/reanalyze/", views.ticket_reanalyze, name="reanalyze"),
    path("<int:pk>/download/", views.ticket_download_json, name="download_json"),
    path("<int:pk>/delete/", views.ticket_delete, name="delete"),
]
